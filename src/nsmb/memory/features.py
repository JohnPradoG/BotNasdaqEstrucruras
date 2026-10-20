"""Características normalizadas de cada episodio. TODAS usan solo información disponible al cierre
de la vela de detección (t). Se expresan "a favor de la dirección" (d) para comparar compras y ventas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEATURES = ["trend_tf", "trend_ctx1", "trend_ctx2", "stop_atr", "room_atr", "atr_rel", "rel_vol",
            "rsi_d", "mom_d", "body_ratio", "wick_d", "struct_size_atr", "bars_since", "conf_div",
            "conf_rej", "hour_sin", "hour_cos"]

# Columna con el tamaño propio de cada tipo de estructura
_SIZE_COL = {"bos": "break_size_atr", "choch": "break_size_atr", "retest": "retest_depth_atr",
             "sweep": "sweep_depth_atr", "double_top": "pattern_height_atr",
             "double_bottom": "pattern_height_atr", "head_shoulders": "pattern_height_atr",
             "inv_head_shoulders": "pattern_height_atr", "fvg": "gap_atr", "impulse": "range_atr"}

EPISODE_TYPES = ["bos", "choch", "retest", "sweep", "false_break", "double_top", "double_bottom",
                 "head_shoulders", "inv_head_shoulders", "fvg", "impulse", "rsi_divergence"]


def invalidation_price(ev: pd.Series, bar_low: float, bar_high: float) -> float:
    """Nivel cuya superación invalida la idea (antes del colchón)."""
    d, typ = ev["direction"], ev["type"]
    if typ in ("retest", "sweep", "false_break", "double_top", "double_bottom", "head_shoulders",
               "inv_head_shoulders"):
        return float(ev["extreme"])
    if typ in ("bos", "choch", "impulse"):
        return bar_low if d > 0 else bar_high
    if typ in ("fvg", "rsi_divergence"):
        return float(ev["level"])
    raise ValueError(typ)


def build_features(events: pd.DataFrame, df: pd.DataFrame, state: pd.DataFrame,
                   ctx1_trend: np.ndarray, ctx2_trend: np.ndarray, stop_buffer_atr: float,
                   point: float, spread_override_points: float | None = None) -> pd.DataFrame:
    """Devuelve un DataFrame por evento con características, invalidación y stop."""
    ev = events[events["type"].isin(EPISODE_TYPES)].copy()
    t = ev["t"].to_numpy()
    d = ev["direction"].to_numpy()
    close = df["close"].to_numpy()[t]
    atr = df["atr"].to_numpy()[t]
    low, high = df["low"].to_numpy()[t], df["high"].to_numpy()[t]
    spread_px = (np.full(len(t), spread_override_points) if spread_override_points is not None
                 else df["spread"].to_numpy()[t]) * point
    ev["atr"] = atr
    ev["entry_ref"] = close
    ev["spread_points"] = df["spread"].to_numpy()[t]            # spread real registrado
    ev["cost_spread_points"] = spread_px / point                  # spread usado como coste
    ev["session"] = df["session"].to_numpy()[t]
    inval = np.array([invalidation_price(r, lo, hi) for (_, r), lo, hi in zip(ev.iterrows(), low, high)])
    ev["invalidation"] = inval
    # stop = invalidación ± colchón; para ventas se suma el spread porque el stop se evalúa contra el ASK
    ev["stop"] = np.where(d > 0, inval - stop_buffer_atr * atr, inval + stop_buffer_atr * atr + spread_px)
    f = pd.DataFrame(index=ev.index)
    f["trend_tf"] = state["trend"].to_numpy()[t] * d
    f["trend_ctx1"] = np.nan_to_num(ctx1_trend[t]) * d
    f["trend_ctx2"] = np.nan_to_num(ctx2_trend[t]) * d
    f["stop_atr"] = np.abs(close - ev["stop"].to_numpy()) / atr
    sh, sl = state["swing_high"].to_numpy()[t], state["swing_low"].to_numpy()[t]
    room = np.where(d > 0, (sh - close) / atr, (close - sl) / atr)
    f["room_atr"] = np.clip(np.nan_to_num(room, nan=0.0), -5, 10)
    f["atr_rel"] = np.clip(np.nan_to_num(df["atr_rel"].to_numpy()[t], nan=1.0), 0, 5)
    f["rel_vol"] = np.clip(np.nan_to_num(df["rel_vol"].to_numpy()[t], nan=1.0), 0, 5)
    f["rsi_d"] = (np.nan_to_num(df["rsi"].to_numpy()[t], nan=50.0) - 50) * d / 50
    f["mom_d"] = np.clip(np.nan_to_num(df["ret_20_atr"].to_numpy()[t]) * d, -10, 10)
    f["body_ratio"] = np.nan_to_num(df["body_ratio"].to_numpy()[t], nan=0.0)
    f["wick_d"] = np.where(d > 0, df["lower_wick"].to_numpy()[t], df["upper_wick"].to_numpy()[t])
    f["wick_d"] = np.nan_to_num(f["wick_d"].to_numpy(), nan=0.0)
    size = np.full(len(ev), np.nan)
    for typ, col in _SIZE_COL.items():
        if col in ev:
            m = (ev["type"] == typ).to_numpy()
            size[m] = ev.loc[m, col].to_numpy(float)
    exc = (np.abs(ev["extreme"].to_numpy(float) - ev["level"].to_numpy(float)) / atr)
    m = ev["type"].isin(["false_break", "rsi_divergence"]).to_numpy()
    size[m] = exc[m]                                     # excursión más allá del nivel
    f["struct_size_atr"] = np.clip(np.nan_to_num(size, nan=0.0), 0, 10)
    bs = ev["bars_since_break"].to_numpy(float) if "bars_since_break" in ev else np.zeros(len(ev))
    f["bars_since"] = np.nan_to_num(bs, nan=0.0)
    # confirmaciones: divergencia RSI en la misma dirección en las 10 velas previas; vela de rechazo
    div = events[events["type"] == "rsi_divergence"]
    conf_div = np.zeros(len(ev))
    for sign in (1, -1):
        dt = np.sort(div.loc[div["direction"] == sign, "t"].to_numpy())
        m = d == sign
        if len(dt) and m.any():
            pos = np.searchsorted(dt, t[m], side="right") - 1
            prev = np.where(pos >= 0, dt[np.clip(pos, 0, None)], -10**9)
            conf_div[m] = ((t[m] - prev) <= 10).astype(float)
    f["conf_div"] = conf_div
    rej = np.where(d > 0, df["bull_rejection"].to_numpy()[t], df["bear_rejection"].to_numpy()[t])
    f["conf_rej"] = np.nan_to_num(rej.astype(float))
    ny = pd.DatetimeIndex(ev["time"]).tz_localize("UTC").tz_convert("America/New_York")
    hr = (ny.hour + ny.minute / 60).to_numpy()
    f["hour_sin"], f["hour_cos"] = np.sin(2 * np.pi * hr / 24), np.cos(2 * np.pi * hr / 24)
    return ev.join(f)
