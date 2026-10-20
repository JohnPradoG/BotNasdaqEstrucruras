"""Auditoría de integridad de velas M1: duplicados, orden, OHLC incoherente, huecos y anomalías."""
from __future__ import annotations

import numpy as np
import pandas as pd


def classify_gap(start: pd.Timestamp, end: pd.Timestamp) -> str:
    """start = última vela antes del hueco, end = primera vela después."""
    minutes = (end - start).total_seconds() / 60
    if start.weekday() == 4 and end.weekday() in (6, 0) and minutes > 24 * 60:
        return "fin_de_semana"
    if minutes <= 75 and start.hour in (19, 20, 21, 22) and end.hour in (21, 22, 23):
        return "pausa_diaria"
    # 2021-2022: el bróker cerraba ~2,5 h (19:58/20:58 -> 22:30/23:30 UTC)
    if minutes <= 200 and start.hour in (19, 20) and end.hour in (22, 23):
        return "pausa_diaria_larga"
    if minutes > 24 * 60:
        return "festivo_o_cierre_largo"
    if minutes <= 5:
        return "micro_hueco"
    return "hueco_intradia"


def audit_m1(df: pd.DataFrame, ret_sigma: float = 12.0) -> tuple[pd.DataFrame, dict]:
    """Devuelve (datos limpios, informe). No inventa velas: los huecos solo se clasifican."""
    rep: dict = {"rows_in": int(len(df))}
    dup = df.index.duplicated(keep="last")
    rep["duplicates"] = int(dup.sum())
    df = df[~dup]
    rep["unsorted"] = bool(not df.index.is_monotonic_increasing)
    df = df.sort_index()

    bad_ohlc = (df["high"] < df[["open", "close"]].max(axis=1)) | (df["low"] > df[["open", "close"]].min(axis=1)) | (df["high"] < df["low"])
    rep["bad_ohlc"] = int(bad_ohlc.sum())
    nonpos = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    rep["non_positive"] = int(nonpos.sum())
    df = df[~(bad_ohlc | nonpos)]

    lr = np.log(df["close"]).diff()
    mad = (lr - lr.median()).abs().median() * 1.4826
    spikes = lr.abs() > ret_sigma * mad
    rep["return_spikes"] = int(spikes.sum())
    rep["spike_examples"] = [str(t) for t in df.index[spikes.fillna(False).to_numpy()][:10]]
    rep["spread_points"] = {"median": float(df["spread"].median()), "p95": float(df["spread"].quantile(0.95)),
                             "p99": float(df["spread"].quantile(0.99)), "max": int(df["spread"].max())}
    rep["zero_tickvol"] = int((df["tickvol"] == 0).sum())

    dt = df.index.to_series().diff()
    gaps = dt[dt > pd.Timedelta(minutes=1)]
    kinds: dict[str, int] = {}
    long_gaps = []
    for end, d in gaps.items():
        start = end - d
        k = classify_gap(start, end)
        kinds[k] = kinds.get(k, 0) + 1
        if k in ("hueco_intradia", "festivo_o_cierre_largo") and d > pd.Timedelta(minutes=30):
            long_gaps.append((str(start), str(end), round(d.total_seconds() / 3600, 2), k))
    rep["gaps_by_kind"] = kinds
    rep["long_gaps_count"] = len(long_gaps)
    rep["long_gaps_sample"] = long_gaps[:25]
    rep["start"], rep["end"] = str(df.index[0]), str(df.index[-1])
    rep["rows_out"] = int(len(df))
    per_year = df.groupby(df.index.year).size()
    rep["rows_per_year"] = {int(k): int(v) for k, v in per_year.items()}
    return df, rep
