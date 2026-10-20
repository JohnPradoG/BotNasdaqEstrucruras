"""Estrategias de referencia sencillas para comparar."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .simulator import M1Arrays, simulate


def random_entries(m1a: M1Arrays, atr_at, signal_times: pd.Series, max_minutes: int, slippage: float,
                   target_r: float = 2.0, stop_atr: float = 1.0, seed: int = 0) -> pd.Series:
    """Misma cantidad de entradas y en las mismas horas del día que las señales, pero en días al azar
    y con dirección al azar; stop = `stop_atr` ATR y objetivo `target_r` R. Devuelve resultados en R.
    `atr_at(ts)` devuelve el ATR de la temporalidad de entrada conocido en ts."""
    rng = np.random.default_rng(seed)
    times = pd.to_datetime(signal_times).to_numpy("datetime64[ns]")
    lo, hi = times.min(), times.max()
    days = (hi - lo) / np.timedelta64(1, "D")
    out = []
    for t in times:
        tod = (t - t.astype("datetime64[D]"))
        for _ in range(20):           # busca un día con mercado abierto a esa hora
            d0 = lo.astype("datetime64[D]") + np.timedelta64(int(rng.integers(0, max(int(days), 1))), "D")
            ts = d0 + tod
            i = m1a.index_at(ts)
            if i < len(m1a.time) and (m1a.time[i] - ts) <= np.timedelta64(2, "m"):
                break
        else:
            continue
        a = atr_at(m1a.time[i])
        if not np.isfinite(a) or a <= 0:
            continue
        d = 1 if rng.random() < 0.5 else -1
        ref = m1a.open[i] + (m1a.spread[i] if d > 0 else 0.0)
        stop = ref - d * stop_atr * a
        r0 = simulate(m1a, i, d, stop, None, max_minutes, slippage)
        if r0 is None:
            continue
        tgt = r0.entry_price + d * target_r * r0.risk_price
        r = simulate(m1a, i, d, stop, tgt, max_minutes, slippage)
        if r is not None:
            out.append(r.pnl_price / r.risk_price)
    return pd.Series(out, dtype=float)
