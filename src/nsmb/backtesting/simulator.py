"""Simulación de una operación sobre el camino M1 (precios BID + spread de cada vela).

Reglas (documentadas en docs/backtesting.md):
- La señal se conoce al CIERRE de la vela de la temporalidad de entrada; la entrada es la apertura de la
  primera vela M1 que empieza en ese instante o después (nunca antes).
- Compra: entra al ASK (= bid + spread) + deslizamiento; el stop y el objetivo se evalúan contra el BID.
- Venta: entra al BID − deslizamiento; el stop y el objetivo se evalúan contra el ASK (= bid + spread).
- Si en la misma vela M1 se tocan stop y objetivo, se asume el STOP (hipótesis conservadora): no hay ticks
  históricos para conocer el orden.
- Hueco (gap): si una vela abre más allá del stop, se ejecuta a la apertura (peor que el stop).
- Salida por tiempo: cierre de la última vela M1 permitida (máximo de velas o cierre forzado de sesión).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class M1Arrays:
    time: np.ndarray      # datetime64[ns] apertura
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    spread: np.ndarray    # en precio (spread_points * point)
    flat_mask: np.ndarray  # True si en esta vela M1 hay que estar fuera (cierre forzado de sesión)

    @classmethod
    def from_frame(cls, m1: pd.DataFrame, point: float, flat_before_rollover: bool = True,
                   spread_override_points: float | None = None) -> "M1Arrays":
        flat = np.zeros(len(m1), bool)
        if flat_before_rollover:
            ny = m1.index.tz_localize("UTC").tz_convert("America/New_York")
            mins = ny.hour * 60 + ny.minute
            flat = np.asarray((mins >= 16 * 60 + 55) & (mins < 18 * 60))   # 16:55-18:00 Nueva York
        return cls(m1.index.to_numpy().astype("datetime64[ns]"), m1["open"].to_numpy(float), m1["high"].to_numpy(float),
                   m1["low"].to_numpy(float), m1["close"].to_numpy(float),
                   (np.full(len(m1), float(spread_override_points)) if spread_override_points is not None
                    else m1["spread"].to_numpy(float)) * point, flat)

    def index_at(self, ts) -> int:
        return int(np.searchsorted(self.time, np.datetime64(ts, "ns"), side="left"))


@dataclass
class TradeResult:
    entry_i: int
    exit_i: int
    entry_price: float
    exit_price: float
    reason: str          # "target", "stop", "time", "flat", "no_data"
    pnl_price: float     # por unidad, con signo, neto de spread y deslizamiento
    mfe_price: float
    mae_price: float
    risk_price: float


def simulate_multi(m: M1Arrays, entry_i: int, direction: int, stop: float, targets_r: list[float],
                   max_minutes: int, slippage: float = 0.0) -> dict | None:
    """Una sola pasada para varias salidas hipotéticas: objetivos en R y salida por tiempo.
    Devuelve resultados netos en R, MFE/MAE (en precio, hasta el stop o el horizonte) y tiempos."""
    res = {}
    base = simulate(m, entry_i, direction, stop, None, max_minutes, slippage)
    if base is None:
        return None
    res["time"] = base
    for tr in targets_r:
        tgt = base.entry_price + direction * tr * base.risk_price
        # el objetivo de una venta se evalúa contra el ASK: simulate ya lo hace
        res[tr] = simulate(m, entry_i, direction, stop, tgt, max_minutes, slippage)
    return res


def simulate(m: M1Arrays, entry_i: int, direction: int, stop: float, target: float | None,
             max_minutes: int, slippage: float = 0.0, conservative: bool = True) -> TradeResult | None:
    """Simula una operación. `stop`/`target` son precios BID para compras y ASK para ventas."""
    n = len(m.time)
    if entry_i >= n:
        return None
    if m.flat_mask[entry_i]:
        return None
    end_time = m.time[entry_i] + np.timedelta64(max_minutes, "m")
    end_i = int(np.searchsorted(m.time, end_time, side="left"))
    end_i = max(min(end_i, n), entry_i + 1)
    sl = slice(entry_i, end_i)
    o, h, l, c, sp = m.open[sl], m.high[sl], m.low[sl], m.close[sl], m.spread[sl]
    if direction > 0:
        entry = o[0] + sp[0] + slippage
        if stop >= entry:
            return None
        risk = entry - stop
        hit_stop = l <= stop
        hit_tgt = (h >= target) if target is not None else np.zeros_like(hit_stop)
        fav, adv = h - entry, entry - l
    else:
        entry = o[0] - slippage
        if stop <= entry:
            return None
        risk = stop - entry
        hit_stop = h + sp >= stop
        hit_tgt = (l + sp <= target) if target is not None else np.zeros_like(hit_stop)
        fav, adv = entry - (l + sp), (h + sp) - entry
    flat = m.flat_mask[sl].copy()
    flat[0] = False
    i_s = int(np.argmax(hit_stop)) if hit_stop.any() else len(o)
    i_t = int(np.argmax(hit_tgt)) if hit_tgt.any() else len(o)
    i_f = int(np.argmax(flat)) if flat.any() else len(o)
    first = min(i_s, i_t, i_f)
    if first == len(o):
        k, reason = len(o) - 1, "time"
        exit_px = c[k] if direction > 0 else c[k] + sp[k]
    elif i_f == first and i_f < i_s and i_f < i_t:
        k, reason = i_f - 1, "flat"                      # sale al cierre de la vela anterior al cierre forzado
        exit_px = c[k] if direction > 0 else c[k] + sp[k]
    elif i_s == first and (i_t > i_s or conservative):
        k, reason = i_s, "stop"
        if direction > 0:
            exit_px = min(o[k], stop) if k > 0 else stop
        else:
            exit_px = max(o[k] + sp[k], stop) if k > 0 else stop
    else:
        k, reason = i_t, "target"
        exit_px = target
    exit_px = exit_px - slippage if direction > 0 else exit_px + slippage
    pnl = (exit_px - entry) * direction
    mfe = max(0.0, float(np.max(fav[:k + 1])))     # 0 si nunca estuvo en ganancias
    mae = max(0.0, float(np.max(adv[:k + 1])))
    return TradeResult(entry_i, entry_i + k, float(entry), float(exit_px), reason, float(pnl), mfe, mae, float(risk))
