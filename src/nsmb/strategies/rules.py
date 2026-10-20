"""Las tres familias de estrategias como reglas sobre los episodios de la memoria.

Todas comparten la mecánica de la operación hipotética estándar (memory/builder.compute_outcomes):
  entrada  = apertura de la primera vela M1 tras el cierre de la vela de detección (precio ASK en compras),
  stop     = nivel de invalidación ± 0,10 ATR (en ventas, + spread porque se evalúa contra el ASK),
  objetivo = 2 R; salida por tiempo a las 48 velas; cierre forzado a las 16:55 de Nueva York.

A. Continuación: retesteo de un BOS a favor de la tendencia de la temporalidad de contexto 1.
   Excluye: contexto en contra o neutro.
B. Reversión: barrido de liquidez (mecha más allá de un pivote y cierre de vuelta) o falsa ruptura
   (cierre más allá y vuelta en ≤3 velas). Excluye: contexto 1 en contra de la operación.
C. Cambio de tendencia: retesteo de un CHOCH (primera ruptura contra la tendencia previa), o doble techo/suelo
   y HCH confirmados por cierre al otro lado de la línea clavicular. Excluye: contexto 1 en contra.
Exclusiones comunes (risk/filters): spread anormal, geometría del stop fuera de [0,15; 6] ATR,
entradas entre 16:30 y 18:00 de Nueva York, datos sin desenlace.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STRATEGIES = {
    "A_continuacion": lambda e: (e["structure_type"] == "retest") & (e["origin"] == "bos") & (e["trend_ctx1"] > 0),
    "B_reversion": lambda e: e["structure_type"].isin(["sweep", "false_break"]) & (e["trend_ctx1"] >= 0),
    "C_cambio_tendencia": lambda e: (((e["structure_type"] == "retest") & (e["origin"] == "choch"))
                                     | e["structure_type"].isin(["double_top", "double_bottom", "head_shoulders",
                                                                 "inv_head_shoulders"])) & (e["trend_ctx1"] >= 0),
}

# Reglas "sin filtro de contexto", para medir si el contexto aporta algo
BASE_NO_CONTEXT = {
    "A_sin_contexto": lambda e: (e["structure_type"] == "retest") & (e["origin"] == "bos"),
    "B_sin_contexto": lambda e: e["structure_type"].isin(["sweep", "false_break"]),
    "C_sin_contexto": lambda e: ((e["structure_type"] == "retest") & (e["origin"] == "choch"))
                                 | e["structure_type"].isin(["double_top", "double_bottom", "head_shoulders",
                                                             "inv_head_shoulders"]),
}


def common_exclusions(e: pd.DataFrame, max_spread_multiple: float, max_spread_abs: float) -> pd.Series:
    """True = la señal se EXCLUYE. El spread de referencia es la mediana móvil de los 500 episodios previos
    (solo pasado)."""
    med = e["spread_points"].shift(1).rolling(500, min_periods=50).median().fillna(e["spread_points"].expanding().median())
    bad_spread = (e["spread_points"] > max_spread_multiple * med) | (e["spread_points"] > max_spread_abs)
    ny = pd.DatetimeIndex(e["detected_time"]).tz_localize("UTC").tz_convert("America/New_York")
    mins = ny.hour * 60 + ny.minute
    late = np.asarray((mins >= 16 * 60 + 30) & (mins < 18 * 60))
    bad_geo = (e["status"] != "ok") | ~e["risk_atr"].between(0.15, 6.0)
    return bad_spread | pd.Series(late, index=e.index) | bad_geo


def select(e: pd.DataFrame, name: str, risk_cfg: dict) -> pd.DataFrame:
    rule = {**STRATEGIES, **BASE_NO_CONTEXT}[name]
    e = e.sort_values("detected_time")
    m = rule(e) & ~common_exclusions(e, risk_cfg["max_spread_multiple"], risk_cfg["max_spread_points_abs"])
    return e[m].assign(strategy=name)
