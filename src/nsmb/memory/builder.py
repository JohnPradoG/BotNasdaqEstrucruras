"""Construye la memoria: estructuras -> episodios (nivel 1) -> desenlaces (nivel 2) -> agregados (nivel 3)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict

import numpy as np
import pandas as pd

from ..backtesting.simulator import M1Arrays, simulate_multi
from ..config.loader import SymbolSpec
from ..data.timeframes import TF_MINUTES, align_higher, resample
from ..indicators import add_indicators
from ..market_structure import StructureEngine, StructureParams
from .features import FEATURES, build_features


def params_hash(p: StructureParams, extra: dict) -> str:
    return hashlib.sha1(json.dumps({**asdict(p), **extra}, sort_keys=True).encode()).hexdigest()[:12]


class FrameCache:
    """Velas + indicadores + estructura por temporalidad, calculados una vez."""

    def __init__(self, m1: pd.DataFrame, params: StructureParams, atr_n: int = 14, rsi_n: int = 14,
                 complete_only: bool = False):
        self.m1, self.p, self.atr_n, self.rsi_n = m1, params, atr_n, rsi_n
        self.complete_only = complete_only      # en vivo: descarta la última vela aún abierta
        self._c: dict[str, tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]] = {}

    def get(self, tf: str):
        if tf not in self._c:
            bars = resample(self.m1, tf)
            if self.complete_only:
                bars = bars[bars["complete"]]
            df = add_indicators(bars, self.atr_n, self.rsi_n)
            ev, st = StructureEngine(self.p).run(df)
            self._c[tf] = (df, ev, st)
        return self._c[tf]


def context_trend(entry_df: pd.DataFrame, ctx_df: pd.DataFrame, ctx_state: pd.DataFrame, tag: str) -> np.ndarray:
    h = ctx_df[["close_time", "complete"]].assign(trend=ctx_state["trend"].to_numpy())
    al = align_higher(entry_df[["close_time"]], h, ["trend"], f"{tag}_")
    return al[f"{tag}_trend"].to_numpy(float)


def build_episodes(cache: FrameCache, combo: list[str], spec: SymbolSpec, m1a: M1Arrays, cfg_bt: dict,
                   cfg_mem: dict, dataset_id: str, symbol: str) -> pd.DataFrame:
    ctx1, ctx2, tf = combo
    df, ev, st = cache.get(tf)
    if ev.empty:
        return pd.DataFrame()
    c1 = context_trend(df, *[cache.get(ctx1)[i] for i in (0, 2)], "c1")
    c2 = context_trend(df, *[cache.get(ctx2)[i] for i in (0, 2)], "c2")
    ep = build_features(ev, df, st, c1, c2, cfg_bt["stop_buffer_atr"], spec.point, cfg_bt.get("cost_spread_points"))
    ph = params_hash(cache.p, {"stop_buffer_atr": cfg_bt["stop_buffer_atr"], "combo": combo,
                               "cost_spread_points": cfg_bt.get("cost_spread_points")})
    ep["tf"], ep["context_tfs"], ep["symbol"], ep["dataset_id"], ep["params_hash"] = tf, f"{ctx1},{ctx2}", symbol, dataset_id, ph
    ep["structure_type"] = ep["type"]
    ep["bar_index"] = ep["t"]
    ep["detected_time"] = pd.to_datetime(ep["time"])
    ep["origin"] = ep["origin"] if "origin" in ep else None
    ep["episode_id"] = [hashlib.sha1(f"{symbol}|{tf}|{ctx1},{ctx2}|{ty}|{d}|{tm}|{ph}".encode()).hexdigest()[:20]
                        for ty, d, tm in zip(ep["type"], ep["direction"], ep["detected_time"])]
    ep = ep.drop_duplicates("episode_id")
    ep["features_json"] = [json.dumps({k: round(float(v), 5) for k, v in zip(FEATURES, row)}) for row in ep[FEATURES].to_numpy()]
    ep["confirmations_json"] = [json.dumps({"divergencia_rsi": bool(a), "vela_rechazo": bool(b), "volumen_alto": bool(v > 1.5)})
                                for a, b, v in zip(ep["conf_div"], ep["conf_rej"], ep["rel_vol"])]
    ep["data_quality"] = "m1_bid+spread"
    return ep.reset_index(drop=True)


def compute_outcomes(ep: pd.DataFrame, m1a: M1Arrays, tf: str, cfg_bt: dict, cfg_mem: dict, spec: SymbolSpec) -> pd.DataFrame:
    """Desenlace de cada episodio con la operación hipotética estándar: entrada en la apertura M1 siguiente
    al cierre de la vela de detección, stop en la invalidación, objetivos 1/1,5/2 R y salida por tiempo."""
    slip = cfg_bt["slippage_points"] * spec.point
    max_min = cfg_bt["max_hold_bars"] * TF_MINUTES[tf]
    targets = cfg_mem["targets_r"]
    rows = []
    for e in ep.itertuples(index=False):
        base = {"episode_id": e.episode_id}
        i = m1a.index_at(e.detected_time)
        if i >= len(m1a.time) or (m1a.time[i] - np.datetime64(e.detected_time, "ns")) > np.timedelta64(30, "m"):
            rows.append({**base, "status": "sin_datos"})
            continue
        stop = e.stop
        r = simulate_multi(m1a, i, int(e.direction), stop, targets, max_min, slip) if np.isfinite(stop) else None
        if r is None:
            rows.append({**base, "status": "geometria_invalida"})
            continue
        b = r["time"]
        risk_atr = b.risk_price / e.atr
        if not (0.15 <= risk_atr <= 6.0):
            rows.append({**base, "status": "geometria_invalida", "risk_atr": risk_atr})
            continue
        exit_times = [m1a.time[x.exit_i] for x in r.values() if x is not None]
        out = {**base, "status": "ok", "entry_time": pd.Timestamp(m1a.time[i]), "entry_price": b.entry_price,
               "risk_price": b.risk_price, "risk_atr": risk_atr,
               "matured_time": pd.Timestamp(max(exit_times)) + pd.Timedelta(minutes=1),
               "mfe_r": b.mfe_price / b.risk_price, "mae_r": b.mae_price / b.risk_price,
               "mfe_atr": b.mfe_price / e.atr, "mae_atr": b.mae_price / e.atr,
               "duration_min": int((m1a.time[b.exit_i] - m1a.time[i]) / np.timedelta64(1, "m")) + 1,
               "res_time": b.pnl_price / b.risk_price,
               "cost_r": (e.cost_spread_points * spec.point + 2 * slip) / b.risk_price}
        for tr, col in zip(targets, ["res_1r", "res_1_5r", "res_2r"]):
            x = r[tr]
            out[col] = x.pnl_price / x.risk_price
            if tr == 2.0:
                out["exit_reason_2r"] = x.reason
                out["dur_2r_min"] = int((m1a.time[x.exit_i] - m1a.time[i]) / np.timedelta64(1, "m")) + 1
        rows.append(out)
    return pd.DataFrame(rows)


def wilson(k: float, n: float, z: float = 1.645) -> tuple[float, float]:
    if n <= 0:
        return np.nan, np.nan
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def effective_n(times: pd.Series, min_gap: pd.Timedelta) -> int:
    """Número de episodios separados al menos `min_gap` (los solapados cuentan como uno)."""
    t = np.sort(pd.to_datetime(times).to_numpy())
    if len(t) == 0:
        return 0
    n, last = 1, t[0]
    for x in t[1:]:
        if x - last >= min_gap:
            n += 1
            last = x
    return n


def aggregate(df: pd.DataFrame, period: str, min_gap: pd.Timedelta) -> pd.DataFrame:
    """Nivel 3: estadísticas por estructura, tf, dirección, sesión, volatilidad y contexto."""
    d = df[df["status"] == "ok"].copy()
    if d.empty:
        return pd.DataFrame()
    d["vol_bucket"] = pd.cut(d["atr_rel"] if "atr_rel" in d else 1.0, [-np.inf, 0.8, 1.25, np.inf], labels=["baja", "normal", "alta"]).astype(str)
    d["context"] = np.where(d["trend_ctx1"] > 0, "a_favor", np.where(d["trend_ctx1"] < 0, "en_contra", "neutro"))
    out = []
    for dims in (["structure_type", "tf", "direction"], ["structure_type", "tf", "direction", "session"],
                 ["structure_type", "tf", "direction", "vol_bucket"], ["structure_type", "tf", "direction", "context"]):
        for key, g in d.groupby(dims):
            key = dict(zip(dims, key if isinstance(key, tuple) else (key,)))
            n = len(g)
            wins = (g["res_2r"] > 0).sum()
            lo, hi = wilson(wins, n)
            m, s = g["res_2r"].mean(), g["res_2r"].std(ddof=1) if n > 1 else np.nan
            se = s / np.sqrt(max(n, 1)) if n > 1 else np.nan
            out.append({"agg_key": "|".join(f"{k}={v}" for k, v in key.items()) + f"|{period}",
                        "structure_type": key["structure_type"], "tf": key["tf"], "direction": int(key["direction"]),
                        "session": key.get("session"), "vol_bucket": key.get("vol_bucket"), "context": key.get("context"),
                        "period": period, "n": n, "n_eff": effective_n(g["detected_time"], min_gap),
                        "hit_2r": wins / n, "hit_2r_lo": lo, "hit_2r_hi": hi, "exp_r": m,
                        "exp_r_lo": m - 1.645 * se if n > 1 else np.nan, "exp_r_hi": m + 1.645 * se if n > 1 else np.nan,
                        "median_mae_r": g["mae_r"].median(), "median_mfe_r": g["mfe_r"].median()})
    return pd.DataFrame(out)
