"""Cartera completa del bot: apertura de NY (orb15, orb5, noise) + cruce de EMAs 20/50 en H1.

Un solo bucle, un solo número mágico y un solo control de riesgo para todas: así el límite de posiciones abiertas
(máx. 3) y la pérdida diaria (1 %) cuentan para la cartera entera, no para cada estrategia por separado.
"""
from __future__ import annotations

import pandas as pd

from . import ema_cross
from .opening import OpeningEvent, day_events

STRATEGIES = ("orb15", "orb5", "noise", ema_cross.NAME)
KEEP_OVERNIGHT = (ema_cross.NAME,)          # el cruce de EMAs no se cierra a las 15:57 NY


def all_events(m1: pd.DataFrame, now: pd.Timestamp | None = None) -> list[OpeningEvent]:
    ev = day_events(m1, now) + ema_cross.cross_events(m1, now)
    return sorted(ev, key=lambda e: (e.detected_time, e.kind != "cerrar"))
