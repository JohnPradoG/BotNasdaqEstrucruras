"""Fase 6l: FVG con retesteo (idea de John; sus EA de MT5 se llaman EA_Nasdaq_FVG_Retest). Prerregistrado 2026-10-21.

Rejilla y regla guardadas en git ANTES de ejecutar. Definición estándar (a la espera del código .mq5 de John):
  - FVG alcista en la vela t: mínimo(t) - máximo(t-2) >= 0,3 ATR(14). Bajista al revés. Se conoce al cierre de t.
  - Retesteo: orden limitada que espera hasta 20 velas a que el precio vuelva al hueco. Entrada en
    {borde: mínimo(t) en alcista / máximo(t) en bajista; mitad: punto medio del hueco}.
    Cuenta como llena solo si el precio cruza el límite 0,25 puntos (trade-through).
  - Stop: el otro lado del hueco +- 0,1 ATR. Objetivo {2 R, 3 R}. Máximo 60 velas; cierre forzado 15:57 NY.
  - Filtro {todas, a favor de la media 50 D1}.
  - Temporalidades del hueco {M5, M15, H1}.
24 variantes. Coste: spread 1,12 + 0,5 (orden limitada: deslizamiento solo a la salida).
Selección igual que siempre (2021-23 t >= 2 y 2024 t >= 1, ambos positivos); 2025-26 solo diagnóstico.

Uso: python scripts/run_fvg.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.data.timeframes import resample  # noqa: E402
from nsmb.indicators.core import add_indicators  # noqa: E402
from nsmb.market_structure.engine import StructureEngine, StructureParams  # noqa: E402

TFS = {"M5": 5, "M15": 15, "H1": 60}
MIN_GAP_ATR, WAIT_BARS, MAX_BARS = 0.3, 20, 60
N_PREVIOUS = 579 + 24 + 1


def detect(df: pd.DataFrame) -> pd.DataFrame:
    h, l, a = df["high"].to_numpy(), df["low"].to_numpy(), df["atr"].to_numpy()
    ct = df["close_time"].to_numpy()
    out = []
    for t in range(2, len(df)):
        if not np.isfinite(a[t]) or a[t] <= 0:
            continue
        if l[t] - h[t - 2] >= MIN_GAP_ATR * a[t]:
            out.append({"detected_time": pd.Timestamp(ct[t]), "direction": 1, "top": l[t], "bot": h[t - 2], "atr": a[t]})
        elif l[t - 2] - h[t] >= MIN_GAP_ATR * a[t]:
            out.append({"detected_time": pd.Timestamp(ct[t]), "direction": -1, "top": l[t - 2], "bot": h[t], "atr": a[t]})
    return pd.DataFrame(out)


def simulate(sig: pd.DataFrame, m: M1Arrays, tfm: int, entry_kind: str, R: float) -> pd.DataFrame:
    rows = []
    for x in sig.itertuples(index=False):
        d = int(x.direction)
        if entry_kind == "borde":
            lim = x.top if d > 0 else x.bot
        else:
            lim = (x.top + x.bot) / 2
        f = I.limit_fill(m, x.detected_time, d, lim, WAIT_BARS * tfm)
        if f is None:
            continue
        i, px = f
        stop = (x.bot - 0.1 * x.atr) if d > 0 else (x.top + 0.1 * x.atr + I.SPREAD_PTS)
        risk = (px - stop) * d
        if risk <= 0:
            continue
        res = I.trade(m, i, d, px, stop, px + d * R * risk, I.end_index(m, i, MAX_BARS * tfm), True)
        if res is None:
            continue
        r = I.row(x.detected_time, d, res, i, m)
        r["cost_r"] = (I.SPREAD_PTS + I.SLIP) / res[1]
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, True, I.SPREAD_PTS / spec.point)
    ny = m1.index.tz_localize("UTC").tz_convert(I.NY)
    mins = np.asarray(ny.hour * 60 + ny.minute)
    m.flat_mask = (mins >= 957) & (mins < 1110)
    d1 = I.daily_bars(m1)
    _, st = StructureEngine(StructureParams.from_cfg(cfg["structure"])).run(add_indicators(d1))
    bias = I.daily_bias(d1, st)
    rows = []
    for tf, tfm in TFS.items():
        bars = resample(m1, tf)
        df = add_indicators(bars[bars["complete"]])
        sig = I.attach_bias(detect(df), bias)
        for entry_kind in ("borde", "mitad"):
            for R in (2.0, 3.0):
                for filt in ("todas", "media50"):
                    s = sig if filt == "todas" else sig[sig["direction"] * sig["sma_bias"] > 0]
                    res_df = simulate(s, m, tfm, entry_kind, R)
                    res = I.by_period(res_df) if len(res_df) else {p: {"n": 0} for p in I.PERIODS}
                    r = {"clave": f"fvg|{tf}|entrada_{entry_kind}|{R:g}R|{filt}", "huecos": len(s)}
                    for p in I.PERIODS:
                        for k in ("n", "r", "t", "bruto", "aciertos"):
                            r[f"{p}_{k}"] = res[p].get(k)
                    r["cumple"] = I.passes(res, "W")
                    rows.append(r)
        print(tf, "listo", flush=True)
    tab = pd.DataFrame(rows)
    n_total = N_PREVIOUS + len(tab)
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variantes": len(tab),
               "cumplen": int(tab["cumple"].sum()), "bonferroni_t": round(float(norm.ppf(1 - 0.05 / n_total)), 2),
               "variantes_totales": n_total}
    out = ROOT / "data" / "backtests" / f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_fvg"
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (ROOT / "reports" / "fvg.json").write_text(json.dumps({**summary, "tabla": tab.to_dict("records")}, indent=1,
                                                          ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    pd.set_option("display.width", 250)
    print(tab.to_string(index=False))


if __name__ == "__main__":
    main()
