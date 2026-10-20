"""Motor de decisión: combina la regla de la estrategia con la memoria de casos comparables.

Para cada señal candidata en el instante T:
  1. se buscan los k episodios más parecidos (mismo tipo de estructura y temporalidad) cuyo desenlace
     ya era conocido en T;
  2. se calcula la probabilidad de alcanzar el objetivo antes de la invalidación (intervalo de Wilson 90 %),
     la expectativa neta en R (con su cota inferior 90 %), el MAE/MFE típicos y la duración;
  3. se OPERA solo si hay suficientes casos efectivos y la cota exigida es positiva; si no, NO OPERAR.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..memory.features import FEATURES
from ..similarity.knn import SimilarityIndex


@dataclass
class DecisionConfig:
    k: int = 50
    min_effective_n: int = 30
    criterion: str = "lcb"          # "lcb": cota inferior 90 % > umbral; "mean": media > umbral
    threshold_r: float = 0.0
    min_separation_min: int = 30


class MemoryDecision:
    def __init__(self, pool: pd.DataFrame, train: pd.DataFrame, cfg: DecisionConfig):
        self.cfg = cfg
        self.index = SimilarityIndex(k=cfg.k, min_separation=pd.Timedelta(minutes=cfg.min_separation_min)).fit(train)
        self.index.set_pool(pool)

    def evaluate(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Añade a cada señal la respuesta de la memoria y la decisión (take=True/False)."""
        rows = []
        X = signals[FEATURES].to_numpy(float)
        for x, t in zip(X, signals["detected_time"].to_numpy("datetime64[ns]")):
            a = self.index.query(x, t)
            if a is None or a.n_effective < self.cfg.min_effective_n:
                rows.append({"take": False, "mem_n": 0 if a is None else a.n_effective, "mem_exp": np.nan,
                             "mem_exp_lo": np.nan, "mem_hit": np.nan, "mem_hit_lo": np.nan, "mem_mae": np.nan,
                             "mem_mfe": np.nan, "mem_min": np.nan, "reason": "pocos_casos"})
                continue
            score = a.exp_lo if self.cfg.criterion == "lcb" else a.exp_r
            take = bool(score > self.cfg.threshold_r)
            rows.append({"take": take, "mem_n": a.n_effective, "mem_exp": a.exp_r, "mem_exp_lo": a.exp_lo,
                         "mem_hit": a.hit_rate, "mem_hit_lo": a.hit_lo, "mem_mae": a.median_mae_r,
                         "mem_mfe": a.median_mfe_r, "mem_min": a.median_minutes,
                         "reason": "ventaja_estimada" if take else "no_operar_expectativa"})
        return pd.concat([signals.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
