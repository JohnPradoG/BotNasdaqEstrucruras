"""Gráficos de los informes (equity, drawdown y distribución de resultados)."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

INK, MUTED, BLUE, RED, GRID = "#1f2328", "#59636e", "#2f6fdb", "#c93c37", "#e6e8eb"


def equity_chart(trades: pd.DataFrame, initial: float, path: Path, title: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    t = pd.to_datetime(trades["exit_time"])
    eq = trades["equity"].to_numpy()
    peak = pd.Series(eq).cummax().clip(lower=initial)
    dd = (pd.Series(eq) / peak - 1) * 100
    fig, ax = plt.subplots(3, 1, figsize=(10, 8), gridspec_kw={"height_ratios": [3, 1.3, 1.6]})
    ax[0].plot(t, eq, color=BLUE, lw=1.6)
    ax[0].axhline(initial, color=MUTED, lw=0.8, ls="--")
    ax[0].set_title(f"Equity (USD) — {title}", loc="left", color=INK, fontsize=11)
    ax[1].fill_between(t, dd, 0, color=RED, alpha=0.35, lw=0)
    ax[1].set_title("Drawdown (%)", loc="left", color=INK, fontsize=10)
    ax[2].hist(trades["r"], bins=40, color=BLUE, alpha=0.8)
    ax[2].axvline(0, color=MUTED, lw=0.8)
    ax[2].set_title("Distribución del resultado por operación (R, neto de costes)", loc="left", color=INK, fontsize=10)
    for a in ax:
        a.grid(color=GRID, lw=0.6)
        a.spines[["top", "right"]].set_visible(False)
        a.tick_params(colors=MUTED, labelsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)
