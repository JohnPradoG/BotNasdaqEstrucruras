"""Fase 6h: ¿una relación riesgo/beneficio 1:1, 1:1,5, 1:2 o 1:3 vuelve rentables las divergencias? (2026-10-20)

Pedido por John. Rejilla y regla guardadas en git ANTES de ejecutar.

Divergencias RSI (definición de scripts/run_divergences.py), M1, M5, M15, H1, H4, normal y oculta.
Stop {pivote (extremo del pivote +- 0,1 ATR), 1 ATR desde la entrada}; objetivo = R x riesgo con R {1, 1,5, 2, 3}.
Además, como referencia, la ruptura del rango de apertura de NY de 15 min (stop al otro lado, a favor de la media
de 50 días) con los mismos R, saliendo a las 15:57 NY como tarde.
Rejilla: 5 TF x 2 tipos x 2 stops x 4 R = 80 divergencias + 4 ORB = 84.
Para cada una: acierto (operaciones que llegan al objetivo), acierto de equilibrio antes de costes 1/(1+R),
expectativa bruta y neta. Máximo 60 velas; compras con swap. Coste: spread 1,12 + 0,5 por lado.
Selección igual que siempre (desarrollo t >= 2 y validación t >= 1, ambos positivos); Bonferroni con todo lo de hoy.

Uso: python scripts/run_rr.py
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

import run_divergences as DV  # noqa: E402
import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.data.timeframes import resample  # noqa: E402
from nsmb.indicators.core import add_indicators  # noqa: E402
from nsmb.market_structure.engine import StructureEngine, StructureParams  # noqa: E402

RS = (1.0, 1.5, 2.0, 3.0)
N_PREVIOUS = 265 + 96 + 120


def sim(sig, df, m, tfm, stop_kind, R):
    rows = []
    ct = df["close_time"].to_numpy()
    for x in sig.itertuples(index=False):
        d = int(x.direction)
        ts = pd.Timestamp(ct[x.t])
        me = I.market_entry(m, ts, d)
        if me is None:
            continue
        i, px = me
        if stop_kind == "pivote":
            stop = x.pivot - 0.1 * x.atr if d > 0 else x.pivot + 0.1 * x.atr + I.SPREAD_PTS
        else:
            stop = px - d * x.atr
        risk = (px - stop) * d
        if risk <= 0 or risk > 10 * x.atr:
            continue
        res = I.trade(m, i, d, px, stop, px + d * R * risk, I.end_index(m, i, 60 * tfm), False, use_flat=False)
        if res is None:
            continue
        swap = I.nights_swap(pd.Timestamp(m.time[i]), pd.Timestamp(m.time[res[2]])) if d > 0 else 0.0
        r = I.row(ts, d, res, i, m, swap=swap)
        r["cost_r"] = (I.SPREAD_PTS + 2 * I.SLIP + swap) / res[1]
        r["objetivo"] = res[3] == "objetivo"
        rows.append(r)
    return pd.DataFrame(rows)


def summarize(key, df, R, tf):
    res = I.by_period(df) if len(df) else {p: {"n": 0} for p in I.PERIODS}
    out = {"clave": key, "R": R, "equilibrio_bruto": round(1 / (1 + R), 3)}
    for p, (a, b) in I.PERIODS.items():
        y = df[(df["detected_time"] >= pd.Timestamp(a)) & (df["detected_time"] < pd.Timestamp(b) + pd.Timedelta(days=1))] if len(df) else df
        out[f"{p}_n"] = res[p].get("n")
        out[f"{p}_acierto"] = round(float(y["objetivo"].mean()), 3) if len(y) else None
        out[f"{p}_bruto"] = res[p].get("bruto")
        out[f"{p}_neto"] = res[p].get("r")
        out[f"{p}_t"] = res[p].get("t")
    out["cumple"] = I.passes({p: {"n": res[p].get("n", 0), "r": res[p].get("r"), "t": res[p].get("t")} for p in I.PERIODS}, "x")
    return out


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    rows = []
    for tf, tfm in DV.TFS.items():
        bars = resample(m1, tf)
        df = add_indicators(bars[bars["complete"]])
        sig = DV.detect(df)
        for typ in ("normal", "oculta"):
            s0 = sig[sig["tipo"] == typ]
            for sk in ("pivote", "1ATR"):
                for R in RS:
                    rows.append(summarize(f"div|{tf}|{typ}|stop_{sk}|1:{R}", sim(s0, df, m, tfm, sk, R), R, tf))
        print(tf, "listo", flush=True)
    # ORB de referencia
    mf = M1Arrays.from_frame(m1, spec.point, True, I.SPREAD_PTS / spec.point)
    ny = m1.index.tz_localize("UTC").tz_convert("America/New_York")
    mins = np.asarray(ny.hour * 60 + ny.minute)
    mf.flat_mask = (mins >= 957) & (mins < 1110)
    d1 = I.daily_bars(m1)
    _, st = StructureEngine(StructureParams.from_cfg(cfg["structure"])).run(add_indicators(d1))
    bias = I.daily_bias(d1, st)
    orb = {v["clave"]: v["df"] for v in I.f5_orb(m1, mf, bias)}
    base = orb["F5b|rango15m|mercado|stop_otro_lado|fin_dia|media50"]
    # reconstruye con cada R a partir de las mismas entradas: se re-simula con el objetivo R
    for R in RS:
        rr = []
        for x in base.itertuples(index=False):
            i = mf.index_at(x.entry_time)
            d = int(x.direction)
            px = (mf.open[i] + mf.spread[i] + I.SLIP) if d > 0 else (mf.open[i] - I.SLIP)
            risk = (I.SPREAD_PTS + 2 * I.SLIP) / x.cost_r
            stop = px - d * risk
            res = I.trade(mf, i, d, px, stop, px + d * R * risk, I.end_index(mf, i, 24 * 60), False)
            if res is None:
                continue
            r = I.row(x.detected_time, d, res, i, mf)
            r["cost_r"] = (I.SPREAD_PTS + 2 * I.SLIP) / res[1]
            r["objetivo"] = res[3] == "objetivo"
            rr.append(r)
        rows.append(summarize(f"ORB15|media50|1:{R}", pd.DataFrame(rr), R, "M5"))
    tab = pd.DataFrame(rows)
    n_total = N_PREVIOUS + len(tab)
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variantes": len(tab),
               "cumplen": int(tab["cumple"].sum()), "bonferroni_t": round(float(norm.ppf(1 - 0.05 / n_total)), 2),
               "variantes_totales_hoy": n_total}
    out = ROOT / "data" / "backtests" / f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_rr"
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (ROOT / "reports" / "rr.json").write_text(json.dumps({**summary, "tabla": tab.to_dict("records")}, indent=1,
                                                         ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    pd.set_option("display.width", 250)
    print(tab.to_string(index=False))


if __name__ == "__main__":
    main()
