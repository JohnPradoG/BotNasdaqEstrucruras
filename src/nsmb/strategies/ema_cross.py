"""Cruce de EMAs 20/50 en H1 (módulo del bot pedido por John, reglas congeladas el 2026-10-21).

Son las reglas de scripts/run_ema_cross.py, variante "H1|20/50|2R|ambas" (la mejor de H1; NO aprobada: +0,15 R en
2021-23, +0,03 R en 2024 y +0,04 R en 2025-26, t < 2). Por eso el bot la ejecuta en OBSERVACIÓN por defecto.
  - Velas H1 UTC (las mismas que el backtest). Al cierre de la vela en que la EMA 20 cruza la EMA 50: compra (cruza
    hacia arriba) o venta (hacia abajo), a mercado.
  - Stop a 1,5 x ATR14 de H1 (media simple del rango verdadero) desde el precio de entrada; objetivo 2 R.
  - Si llega el cruce contrario con la posición abierta: se cierra y se abre la contraria.
  - No se entra si el spread supera 8 puntos.
Solo se usan velas H1 CERRADAS: con datos cortados en T, los eventos son los de los datos completos con
detected_time <= T (lo comprueba tests/test_ema_cross.py).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.timeframes import resample
from .opening import OpeningEvent

FAST, SLOW, STOP_ATR, TARGET_R, ATR_N = 20, 50, 1.5, 2.0, 14
MAX_SPREAD_PTS = 8.0
NAME = "ema2050h1"


def h1_bars(m1: pd.DataFrame, now: pd.Timestamp | None = None) -> pd.DataFrame:
    if now is not None:
        m1 = m1[m1.index + pd.Timedelta(minutes=1) <= now]
    b = resample(m1, "H1")
    b = b[b["complete"]].copy()
    if now is not None:
        b = b[b["close_time"] <= now]
    pc = b["close"].shift(1)
    tr = pd.concat([b["high"] - b["low"], (b["high"] - pc).abs(), (b["low"] - pc).abs()], axis=1).max(axis=1)
    b["atr"] = tr.rolling(ATR_N).mean()
    b["ema_f"] = b["close"].ewm(span=FAST, adjust=False).mean()
    b["ema_s"] = b["close"].ewm(span=SLOW, adjust=False).mean()
    return b


def cross_events(m1: pd.DataFrame, now: pd.Timestamp | None = None, last_n: int | None = 3) -> list[OpeningEvent]:
    """Eventos de los últimos `last_n` cruces (None = todos). Cada cruce cierra la posición anterior (si sigue
    abierta) y abre la contraria. El stop va como distancia (stop_dist) desde el precio real de entrada."""
    b = h1_bars(m1, now)
    side = np.sign(b["ema_f"] - b["ema_s"]).to_numpy()
    ok = (np.arange(len(b)) >= 3 * SLOW) & np.isfinite(b["atr"].to_numpy())
    idx = [k for k in range(1, len(b)) if ok[k] and ((side[k] > 0 and side[k - 1] <= 0) or (side[k] < 0 and side[k - 1] >= 0))]
    if last_n is not None:
        idx = idx[-(last_n + 1):]
    ev, prev = [], None
    for k in idx:
        d = int(side[k])
        t = pd.Timestamp(b["close_time"].iloc[k])
        cid = f"{NAME}-{t:%Y%m%d%H%M}"
        if prev is not None:
            ev.append(OpeningEvent("cerrar", NAME, prev, -d, t, reason="cruce"))
        ev.append(OpeningEvent("abrir", NAME, cid, d, t, None, TARGET_R, stop_dist=float(STOP_ATR * b["atr"].iloc[k]),
                              max_spread=MAX_SPREAD_PTS))
        prev = cid
    if last_n is not None and ev and ev[0].kind == "abrir" and len(idx) > last_n:
        ev = ev[1:]                      # el cruce extra solo servía para saber qué cerrar
    return ev
