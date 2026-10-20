"""Métricas de backtest."""
from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series, initial: float) -> tuple[float, float, float]:
    """(drawdown máximo en dinero, en %, días de la recuperación más larga)."""
    eq = pd.concat([pd.Series([initial]), equity.reset_index(drop=True)], ignore_index=True)
    peak = eq.cummax()
    dd = eq - peak
    mdd = float(-dd.min())
    mdd_pct = float(-(dd / peak).min() * 100)
    return mdd, mdd_pct, np.nan


def recovery_days(trades: pd.DataFrame, initial: float) -> float:
    if trades.empty:
        return np.nan
    eq = trades["equity"].to_numpy()
    t = pd.to_datetime(trades["exit_time"]).to_numpy()
    peak, peak_t, longest = initial, t[0], 0.0
    for x, tt in zip(eq, t):
        if x >= peak:
            longest = max(longest, (tt - peak_t) / np.timedelta64(1, "D"))
            peak, peak_t = x, tt
    longest = max(longest, (t[-1] - peak_t) / np.timedelta64(1, "D"))   # incluye la que aún no se recupera
    return float(longest)


def summarize(trades: pd.DataFrame, initial: float) -> dict:
    if trades is None or trades.empty:
        return {"operaciones": 0}
    pnl = trades["pnl"]
    r = trades["r"]
    gains, losses = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    mdd, mdd_pct, _ = max_drawdown(trades["equity"], initial)
    n = len(trades)
    se = r.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return {
        "operaciones": n,
        "beneficio_neto": round(float(pnl.sum()), 2),
        "rentabilidad_pct": round(float(pnl.sum() / initial * 100), 2),
        "profit_factor": round(float(gains / losses), 3) if losses > 0 else np.inf,
        "tasa_aciertos": round(float((pnl > 0).mean()), 4),
        "expectativa_r": round(float(r.mean()), 4),
        "expectativa_r_ic90": [round(float(r.mean() - 1.645 * se), 4), round(float(r.mean() + 1.645 * se), 4)] if n > 1 else None,
        "t_stat": round(float(r.mean() / se), 2) if n > 1 and se > 0 else np.nan,
        "expectativa_dinero": round(float(pnl.mean()), 2),
        "drawdown_max": round(mdd, 2),
        "drawdown_max_pct": round(mdd_pct, 2),
        "recuperacion_mas_larga_dias": round(recovery_days(trades, initial), 1),
        "mae_r_mediana": round(float(trades["mae_r"].median()), 3),
        "mfe_r_mediana": round(float(trades["mfe_r"].median()), 3),
        "costes_totales": round(float(trades["cost"].sum()), 2),
        "lote_medio": round(float(trades["lot"].mean()), 3),
    }


def breakdown(trades: pd.DataFrame, by: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    if by == "year":
        t["year"] = pd.to_datetime(t["entry_time"]).dt.year
    if by == "vol":
        t["vol"] = pd.cut(t["atr_rel"], [-np.inf, 0.8, 1.25, np.inf], labels=["baja", "normal", "alta"]).astype(str)
    g = t.groupby(by)
    out = g.agg(operaciones=("r", "size"), expectativa_r=("r", "mean"), aciertos=("pnl", lambda x: (x > 0).mean()),
                beneficio=("pnl", "sum"))
    out["t_stat"] = g["r"].apply(lambda x: x.mean() / (x.std(ddof=1) / np.sqrt(len(x))) if len(x) > 2 and x.std() > 0 else np.nan)
    return out.round(4)


def r_stats(r: pd.Series) -> dict:
    """Estadística de una serie de resultados en R, sin cartera (todas las señales)."""
    r = r.dropna()
    n = len(r)
    if n == 0:
        return {"n": 0}
    se = r.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return {"n": n, "exp_r": round(float(r.mean()), 4), "lo90": round(float(r.mean() - 1.645 * se), 4) if n > 1 else None,
            "hi90": round(float(r.mean() + 1.645 * se), 4) if n > 1 else None,
            "t": round(float(r.mean() / se), 2) if n > 1 and se > 0 else None,
            "aciertos": round(float((r > 0).mean()), 4)}
