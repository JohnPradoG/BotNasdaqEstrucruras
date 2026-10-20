"""Temporalidades y remuestreo sin anticipación."""
from __future__ import annotations

import pandas as pd

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def tf_delta(tf: str) -> pd.Timedelta:
    return pd.Timedelta(minutes=TF_MINUTES[tf])


def resample(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Agrega velas M1 (índice = apertura, UTC) a la temporalidad `tf`.

    Cada vela resultante lleva `close_time` = apertura + duración: es el primer instante
    en que su cierre es conocido. Las velas incompletas al final (sin M1 hasta el cierre)
    se marcan con `complete=False` y no deben usarse para decidir.
    """
    if tf == "M1":
        out = m1.copy()
        out["close_time"] = out.index + tf_delta("M1")
        out["complete"] = True
        return out
    rule = f"{TF_MINUTES[tf]}min"
    agg = {"open": "first", "high": "max", "low": "min", "close": "last",
           "tickvol": "sum", "spread": "median"}
    g = m1.resample(rule, label="left", closed="left", origin="epoch")
    out = g.agg(agg)
    out["n_m1"] = g["close"].count()
    out = out[out["n_m1"] > 0].copy()
    out["close_time"] = out.index + tf_delta(tf)
    last_m1 = m1.index[-1]
    out["complete"] = out["close_time"] <= last_m1 + tf_delta("M1")
    return out


def align_higher(lower: pd.DataFrame, higher: pd.DataFrame, cols: list[str], prefix: str) -> pd.DataFrame:
    """Adjunta a cada vela de `lower` los valores de la última vela de `higher` YA CERRADA
    cuando cierra la vela de `lower` (as-of por close_time). Nunca usa velas abiertas."""
    h = higher[higher["complete"]][["close_time", *cols]].rename(columns={c: f"{prefix}{c}" for c in cols})
    h = h.rename(columns={"close_time": f"{prefix}close_time"}).sort_values(f"{prefix}close_time")
    l = lower.reset_index().rename(columns={lower.index.name or "index": "time"})
    merged = pd.merge_asof(l.sort_values("close_time"), h, left_on="close_time",
                           right_on=f"{prefix}close_time", direction="backward")
    return merged.set_index("time").sort_index()
