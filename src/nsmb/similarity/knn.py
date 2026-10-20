"""Búsqueda de episodios históricos comparables (vecinos cercanos ponderados, interpretable).

Reglas anti-anticipación:
- Para una consulta en el instante T solo se usan episodios cuyo desenlace ya estaba MADURADO (matured_time <= T).
- La escala de cada característica se ajusta con datos de entrenamiento anteriores a la consulta
  (fit() recibe solo ese periodo) y se congela.
- Se descartan vecinos casi simultáneos: dos vecinos a menos de `min_separation` cuentan como uno.
Un "caso comparable" = mismo tipo de estructura y temporalidad, cualquier dirección (las características
están expresadas a favor de la dirección), entre los k más cercanos por distancia euclídea ponderada.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..memory.builder import wilson
from ..memory.features import FEATURES

DEFAULT_WEIGHTS = {"trend_tf": 1.0, "trend_ctx1": 1.0, "trend_ctx2": 0.7, "stop_atr": 1.0, "room_atr": 0.6,
                   "atr_rel": 0.8, "rel_vol": 0.5, "rsi_d": 0.7, "mom_d": 0.8, "body_ratio": 0.4, "wick_d": 0.4,
                   "struct_size_atr": 0.8, "bars_since": 0.3, "conf_div": 0.5, "conf_rej": 0.4,
                   "hour_sin": 0.6, "hour_cos": 0.6}


@dataclass
class SimilarityAnswer:
    n_candidates: int
    n_neighbors: int
    n_effective: int
    hit_rate: float          # proporción que alcanzó el objetivo antes de la invalidación
    hit_lo: float
    hit_hi: float
    exp_r: float             # expectativa neta (R) de la salida elegida
    exp_lo: float            # cota inferior 90 %
    exp_hi: float
    median_mae_r: float
    median_mfe_r: float
    median_minutes: float
    mean_distance: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


class SimilarityIndex:
    def __init__(self, k: int = 50, min_separation: pd.Timedelta = pd.Timedelta(minutes=30),
                 weights: dict | None = None, outcome_col: str = "res_2r", features: list[str] | None = None):
        self.k, self.min_sep, self.outcome_col = k, min_separation, outcome_col
        self.features = features or FEATURES
        w = weights or DEFAULT_WEIGHTS
        self.w = np.array([w.get(f, 1.0) for f in self.features])
        self.center = self.scale = None

    def fit(self, train: pd.DataFrame) -> "SimilarityIndex":
        X = train[self.features].to_numpy(float)
        self.center = np.nanmedian(X, axis=0)
        q75, q25 = np.nanpercentile(X, 75, axis=0), np.nanpercentile(X, 25, axis=0)
        iqr = q75 - q25
        sd = np.nanstd(X, axis=0)
        self.scale = np.where(iqr > 1e-9, iqr / 1.349, np.where(sd > 1e-9, sd, 1.0))
        return self

    def set_pool(self, pool: pd.DataFrame) -> "SimilarityIndex":
        """Pool de episodios con desenlace (ordenados por matured_time)."""
        p = pool[pool["status"] == "ok"].sort_values("matured_time")
        self.pool = p
        self.Xp = (p[self.features].to_numpy(float) - self.center) / self.scale * self.w
        self.mat = p["matured_time"].to_numpy("datetime64[ns]")
        self.det = p["detected_time"].to_numpy("datetime64[ns]")
        self.y = p[self.outcome_col].to_numpy(float)
        self.mae = p["mae_r"].to_numpy(float)
        self.mfe = p["mfe_r"].to_numpy(float)
        self.dur = p["duration_min"].to_numpy(float)
        return self

    def query(self, x: np.ndarray, at_time) -> SimilarityAnswer | None:
        m = int(np.searchsorted(self.mat, np.datetime64(at_time, "ns"), side="right"))   # solo madurados
        if m == 0:
            return None
        xq = (np.asarray(x, float) - self.center) / self.scale * self.w
        d = np.sqrt(np.nansum((self.Xp[:m] - xq) ** 2, axis=1))
        order = np.argsort(d, kind="stable")
        chosen: list[int] = []
        taken_times: list[np.datetime64] = []
        for j in order:
            tj = self.det[j]
            if any(abs(tj - u) < self.min_sep for u in taken_times):
                continue
            chosen.append(j)
            taken_times.append(tj)
            if len(chosen) >= self.k:
                break
        idx = np.array(chosen)
        y = self.y[idx]
        n = len(y)
        wins = int((y > 0).sum())
        lo, hi = wilson(wins, n)
        mean = float(np.mean(y))
        se = float(np.std(y, ddof=1) / np.sqrt(n)) if n > 1 else np.nan
        return SimilarityAnswer(m, n, n, wins / n, lo, hi, mean, mean - 1.645 * se, mean + 1.645 * se,
                                float(np.median(self.mae[idx])), float(np.median(self.mfe[idx])),
                                float(np.median(self.dur[idx])), float(np.mean(d[idx])))

    def neighbors(self, x: np.ndarray, at_time, k: int | None = None) -> pd.DataFrame:
        """Devuelve los episodios vecinos (para inspección o informes)."""
        k = k or self.k
        m = int(np.searchsorted(self.mat, np.datetime64(at_time, "ns"), side="right"))
        xq = (np.asarray(x, float) - self.center) / self.scale * self.w
        d = np.sqrt(np.nansum((self.Xp[:m] - xq) ** 2, axis=1))
        o = np.argsort(d)[:k]
        return self.pool.iloc[o].assign(distance=d[o])
