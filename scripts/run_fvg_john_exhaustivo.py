"""Fase 6n: pruebas exhaustivas del EA de John EA_Nasdaq_FVG_Retest_H1M15_PartialBE (pedido por John, 2026-10-21).

John lo tenía preparado para operar con 10.000 USD. Todo lo que sigue usa la réplica de scripts/run_fvg_john.py.
  1. Cuenta de 10.000 USD al 1 % por operación (lotes reales de USTECm: mín. 0,05, paso 0,01, 1 USD/punto/lote),
     en dos tramos: fuera de su optimización (2021-10 a 2024-08) y dentro (2024-08 a 2026-08), y año por año.
  2. Ajustes vecinos a "Pass 195", uno por uno: si es una ventaja real, los vecinos también deberían ganar
     (meseta); si es suerte, solo gana el punto elegido (pico).
  3. Costes x2 de spread y 1 punto de deslizamiento; solo compras; solo ventas; parcial + BE encendido (50 % en 1 R,
     stop a +0,1 R).
  4. Entradas al azar: mismas horas, mismo stop y objetivo, dirección al azar (300 repeticiones).

Uso: python scripts/run_fvg_john_exhaustivo.py
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_fvg_john as F  # noqa: E402
import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.reporting.charts import equity_chart  # noqa: E402

OOS = ("2021-01-01", "2024-08-13")
IS = ("2024-08-13", "2026-08-24")
SEED = 20261021


def seg(df, a, b):
    return df[(df["detected_time"] >= a) & (df["detected_time"] < b)]


def brief(df) -> dict:
    o, i = seg(df, *OOS), seg(df, *IS)
    so, si = I.cluster_stats(o), I.cluster_stats(i)
    return {"fuera_n": so["n"], "fuera_r": so.get("r"), "fuera_t": so.get("t"),
            "dentro_n": si["n"], "dentro_r": si.get("r"), "dentro_t": si.get("t")}


def account(df: pd.DataFrame, equity0=10_000.0, risk_pct=1.0) -> tuple[pd.DataFrame, dict]:
    eq, rows = equity0, []
    for t in df.sort_values("entry_time").itertuples(index=False):
        lot = math.floor(eq * risk_pct / 100 / t.riesgo_pts / 0.01 + 1e-9) * 0.01
        lot = max(lot, 0.05)                       # el EA sube al lote mínimo si no llega (CalcLotSize)
        eq += t.r * t.riesgo_pts * lot
        rows.append({"exit_time": t.exit_time, "equity": eq, "r": t.r})
    res = pd.DataFrame(rows)
    if res.empty:
        return res, {}
    e = res.set_index("exit_time")["equity"]
    dd = float((e / e.cummax().clip(lower=equity0) - 1).min() * 100)
    yr = e.resample("YE").last()
    yret = yr.pct_change().fillna(yr.iloc[0] / equity0 - 1)
    return res, {"final_usd": round(float(eq)), "resultado_pct": round((eq / equity0 - 1) * 100, 1),
                 "max_caida_pct": round(dd, 1), "por_año_pct": {str(k.year): round(float(v * 100), 1) for k, v in yret.items()}}


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")

    def arrays(spread, slip):
        I.SPREAD_PTS, I.SLIP = spread, slip
        m = M1Arrays.from_frame(m1, spec.point, False, spread / spec.point)
        m.flat_mask = np.zeros(len(m1), bool)
        return m

    m = arrays(1.12, 0.5)
    fr = F.frames(m1)
    rep = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    base = F.run(m1, m, fr=fr)
    rep["base"] = brief(base)
    print("base", rep["base"], flush=True)

    # 1. cuenta de 10.000 USD
    rep["cuenta_10000"] = {}
    for name, (a, b) in {"fuera_2021_2024-08": OOS, "dentro_2024-08_2026-08": IS, "todo": ("2021-01-01", "2026-12-31")}.items():
        res, st = account(seg(base, a, b))
        rep["cuenta_10000"][name] = st
        if name == "todo":
            equity_chart(res, 10_000, ROOT / "reports" / "fvg_john" / "equity_10000.png", "EA FVG Retest H1/M15 de John, 1 %")
    print("cuenta", rep["cuenta_10000"], flush=True)

    # 2. vecinos
    grid = {"min_gap_atr": [0.1, 0.15, 0.25, 0.3, 0.4], "ema": [50, 100, 150, 200], "rr": [1.5, 2.0, 3.0, 3.5],
            "sl_buf_atr": [0.3, 0.45, 0.75, 0.9], "timeout": [50, 200]}
    rep["vecinos"] = []
    for k, vals in grid.items():
        for v in vals:
            r = brief(F.run(m1, m, {k: v}, fr=fr))
            rep["vecinos"].append({"ajuste": f"{k}={v}", **r})
            print(k, v, r, flush=True)
    for rt, name in ((0, "solo_toque"), (2, "mecha_50")):
        r = brief(F.run(m1, m, rej_type=rt, fr=fr))
        rep["vecinos"].append({"ajuste": f"rechazo={name}", **r})
        print(name, r, flush=True)

    # 3. variantes
    rep["variantes"] = {}
    rep["variantes"]["parcial_BE"] = brief(F.run(m1, m, pbe=True, fr=fr))
    rep["variantes"]["solo_compras"] = brief(F.run(m1, m, dirs=(1,), fr=fr))
    rep["variantes"]["solo_ventas"] = brief(F.run(m1, m, dirs=(-1,), fr=fr))
    m2 = arrays(2.24, 1.0)
    rep["variantes"]["costes_x2_desliz_1"] = brief(F.run(m1, m2, fr=fr))
    m = arrays(1.12, 0.5)
    print("variantes", rep["variantes"], flush=True)

    # 4. azar: mismas entradas, dirección al azar, mismo riesgo en puntos y 2,5 R
    rng = np.random.default_rng(SEED)
    ent = base[["entry_time", "riesgo_pts", "detected_time"]].reset_index(drop=True)
    idx = [m.index_at(t) for t in ent["entry_time"]]
    sims = {"fuera": [], "dentro": []}
    is_oos = (ent["detected_time"] < OOS[1]).to_numpy()
    for _ in range(300):
        dirs = rng.choice([-1, 1], size=len(ent))
        rr = np.empty(len(ent))
        for j, (i0, rp, d) in enumerate(zip(idx, ent["riesgo_pts"], dirs)):
            px = m.open[i0] + m.spread[i0] + I.SLIP if d > 0 else m.open[i0] - I.SLIP
            res = I.trade(m, i0, int(d), px, px - d * rp, px + d * 2.5 * rp, I.end_index(m, i0, 60 * 24 * 60), False,
                          use_flat=False)
            sw = I.nights_swap(pd.Timestamp(m.time[i0]), pd.Timestamp(m.time[res[2]])) if (res and d > 0) else 0.0
            rr[j] = (res[0] - sw) / res[1] if res else np.nan
        sims["fuera"].append(float(np.nanmean(rr[is_oos])))
        sims["dentro"].append(float(np.nanmean(rr[~is_oos & (ent["detected_time"] < IS[1]).to_numpy()])))
    rep["azar"] = {k: {"media": round(float(np.mean(v)), 3), "p5": round(float(np.percentile(v, 5)), 3),
                       "p95": round(float(np.percentile(v, 95)), 3)} for k, v in sims.items()}
    rep["azar"]["ea_fuera_percentil"] = round(float((np.array(sims["fuera"]) < rep["base"]["fuera_r"]).mean() * 100), 0)
    rep["azar"]["ea_dentro_percentil"] = round(float((np.array(sims["dentro"]) < rep["base"]["dentro_r"]).mean() * 100), 0)
    print("azar", rep["azar"], flush=True)

    out = ROOT / "reports" / "fvg_john"
    out.mkdir(parents=True, exist_ok=True)
    (out / "exhaustivo.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
