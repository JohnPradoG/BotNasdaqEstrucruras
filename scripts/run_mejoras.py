"""Fase 6j: ¿se pueden mejorar las estrategias de apertura de NY sin sobreajustar? (2026-10-20)

Pedido por John ("mejore las estrategias para que funcionen"). Rejilla y regla guardadas en git ANTES de ejecutar.

Regla de elección: dentro de cada familia se elige UNA variante solo con 2021-23 (mayor t). Después se mira 2024
sin tocar nada. 2025-26 ya se vio y solo es diagnóstico. Aprobada si 2021-23 t >= 2 y 2024 t >= 1, ambos > 0.

M1 ORB 5 min: objetivo {3 R, 5 R, 10 R, cierre del día} x stop {extremo de la vela, mitad} x {ambas, solo compras}. 16.
M2 Noise area cada 30 min, stop en la banda: ancho {x0,75, x1, x1,25, x1,5} x {ambas, solo compras}. 8.
   (Solo compras se añade porque el Nasdaq sube a largo plazo y otra búsqueda pública lo señaló; queda registrado.)
M3 Cartera fija, sin elegir nada: ORB 15 min media 50 + ORB 5 min (10 R, extremo, ambas) + noise area (x1, 30 min,
   banda, ambas), cada una con el mismo riesgo. Se mide la suma diaria en R. Correlación diaria entre ellas.

Uso: python scripts/run_mejoras.py
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
import run_web as W  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.indicators.core import add_indicators  # noqa: E402
from nsmb.market_structure.engine import StructureEngine, StructureParams  # noqa: E402

N_PREVIOUS = 579


def stats(df: pd.DataFrame) -> dict:
    res = I.by_period(df) if len(df) else {p: {"n": 0} for p in I.PERIODS}
    r = {}
    for p in I.PERIODS:
        for k in ("n", "r", "t", "bruto", "aciertos"):
            r[f"{p}_{k}"] = res[p].get(k)
    r["cumple"] = I.passes(res, "M")
    return r


def daily(df: pd.DataFrame) -> pd.Series:
    return df.groupby(df["detected_time"].dt.floor("D"))["r"].sum()


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
    rth = W.rth_frame(m1)

    fam = {"M1": W.w3_orb5(rth, m, bias, targets=(3, 5, 10, None), stops=("extremo", "mitad"),
                           dirs=("ambas", "compras_only")),
           "M2": sum((W.w1_noise(rth, m, bias, mult=k, steps=(30,), stops=("banda",), dirs=("ambas", "compras"))
                      for k in (0.75, 1.0, 1.25, 1.5)), [])}
    # "compras_only" en ORB5: se filtra aquí (la función solo conoce ambas/media50)
    for v in fam["M1"]:
        if v["clave"].endswith("compras_only") and len(v["df"]):
            v["df"] = v["df"][v["df"]["direction"] > 0]
    rows, chosen = [], {}
    for f, V in fam.items():
        best = None
        for v in V:
            r = {"familia": f, "clave": v["clave"], **stats(v["df"])}
            rows.append(r)
            if r["dev_t"] is not None and (best is None or r["dev_t"] > best["dev_t"]):
                best = r
        chosen[f] = best
    tab = pd.DataFrame(rows)

    # M3 cartera fija
    orb15 = {v["clave"]: v["df"] for v in I.f5_orb(m1, m, bias)}["F5b|rango15m|mercado|stop_otro_lado|fin_dia|media50"]
    orb5 = [v["df"] for v in fam["M1"] if v["clave"] == "W3|orb5|ambas"]
    orb5 = orb5[0] if orb5 else W.w3_orb5(rth, m, bias, dirs=("ambas",))[0]["df"]
    noise = [v["df"] for v in fam["M2"] if v["clave"] == "W1|noise|cada30m|stop_banda|ambas"][0]
    parts = {"orb15_media50": orb15, "orb5": orb5, "noise": noise}
    D = pd.DataFrame({k: daily(v) for k, v in parts.items()}).fillna(0.0)
    port = pd.DataFrame({"detected_time": D.index, "r": D.sum(axis=1).to_numpy(), "cost_r": 0.0})
    port_stats = {}
    for p, (a, b) in I.PERIODS.items():
        y = port[(port["detected_time"] >= pd.Timestamp(a)) & (port["detected_time"] <= pd.Timestamp(b))]
        se = y["r"].std(ddof=1) / np.sqrt(len(y))
        port_stats[p] = {"dias": len(y), "r_dia": round(float(y["r"].mean()), 4), "t": round(float(y["r"].mean() / se), 2)}
        for k, v in parts.items():
            z = D.loc[(D.index >= pd.Timestamp(a)) & (D.index <= pd.Timestamp(b)), k]
            port_stats[p][f"{k}_t"] = round(float(z.mean() / (z.std(ddof=1) / np.sqrt(len(z)))), 2)
    c = port["r"].cumsum()
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variantes": len(tab),
               "elegidas": {f: {k: b[k] for k in ("clave", "dev_r", "dev_t", "val_r", "val_t", "hol_r", "hol_t", "cumple")}
                            for f, b in chosen.items()},
               "cartera": port_stats, "cartera_max_dd_R": round(float((c - c.cummax()).min()), 1),
               "correlacion_diaria": D.corr().round(2).to_dict(),
               "bonferroni_t": round(float(norm.ppf(1 - 0.05 / (N_PREVIOUS + len(tab) + 1))), 2)}
    out = ROOT / "data" / "backtests" / f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_mejoras"
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (ROOT / "reports" / "mejoras.json").write_text(json.dumps({**summary, "tabla": tab.to_dict("records")}, indent=1,
                                                              ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, default=str))
    pd.set_option("display.width", 250)
    print(tab.drop(columns=["familia"]).to_string(index=False))


if __name__ == "__main__":
    main()
