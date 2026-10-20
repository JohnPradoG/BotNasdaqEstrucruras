"""Fases 5 y 6: backtest de las estrategias A/B/C, filtro de memoria, walk-forward, referencias, estrés
y selección con protocolo prerregistrado (docs/protocolo_estadistico.md).

Uso:
  python scripts/run_research.py --combo 0 --stage select    # desarrollo + validación; congela la selección
  python scripts/run_research.py --combo 0 --stage holdout   # UNA vez, con la selección congelada
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nsmb.backtesting.benchmark import random_entries  # noqa: E402
from nsmb.backtesting.metrics import breakdown, r_stats, summarize  # noqa: E402
from nsmb.backtesting.portfolio import run_portfolio  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_risk, load_settings  # noqa: E402
from nsmb.data.pipeline import load_m1  # noqa: E402
from nsmb.data.timeframes import TF_MINUTES  # noqa: E402
from nsmb.memory.store import MemoryStore  # noqa: E402
from nsmb.reporting.charts import equity_chart  # noqa: E402
from nsmb.risk.manager import RiskLimits  # noqa: E402
from nsmb.strategies.decision import DecisionConfig, MemoryDecision  # noqa: E402
from nsmb.strategies.rules import BASE_NO_CONTEXT, STRATEGIES, select  # noqa: E402

GRID = [DecisionConfig(k=30, criterion="mean", threshold_r=0.0),
        DecisionConfig(k=60, criterion="mean", threshold_r=0.05),
        DecisionConfig(k=100, criterion="mean", threshold_r=0.0),
        DecisionConfig(k=100, criterion="lcb", threshold_r=0.0)]
TYPES = {"A_continuacion": ["retest"], "B_reversion": ["sweep", "false_break"],
         "C_cambio_tendencia": ["retest", "double_top", "double_bottom", "head_shoulders", "inv_head_shoulders"]}
CURRENT_SPREAD_POINTS = 112   # spread de USTECm observado en la demo en 2026-08..10


def code_version() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip() or "sin_commit"
    except Exception:  # noqa: BLE001
        return "desconocida"


def period(df, a, b):
    return df[(df["detected_time"] >= pd.Timestamp(a)) & (df["detected_time"] <= pd.Timestamp(b) + pd.Timedelta(days=1))]


def cfg_name(c: DecisionConfig) -> str:
    return f"mem_k{c.k}_{c.criterion}{c.threshold_r:+.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", type=int, default=0)
    ap.add_argument("--stage", choices=["select", "holdout"], default="select")
    args = ap.parse_args()
    cfg, risk_cfg = load_settings(), load_risk()
    spec, limits = SymbolSpec.from_settings(cfg), RiskLimits.from_cfg(risk_cfg)
    combo = cfg["backtest"]["combos"][args.combo]
    tf = combo[2]
    tag = "_".join(combo)
    seed = cfg["project"]["seed"]
    slip = cfg["backtest"]["slippage_points"] * spec.point
    eq0 = cfg["backtest"]["initial_equity"]
    sp = cfg["split"]
    ep = pd.read_parquet(ROOT / "data" / "processed" / f"episodes_{tag}.parquet")
    ep = ep[ep["status"] == "ok"].copy()
    run_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{tag}_{args.stage}"
    out_dir = ROOT / "data" / "backtests" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    rep_dir = ROOT / "reports"
    sel_path = ROOT / "models" / f"seleccion_{tag}.json"
    res: dict = {"cost_spread_points": cfg["backtest"].get("cost_spread_points"), "run_id": run_id, "combo": combo, "stage": args.stage, "code_version": code_version(), "seed": seed,
                 "split": sp, "slippage_points": cfg["backtest"]["slippage_points"], "initial_equity": eq0}

    dev = period(ep, *sp["development"])
    val = period(ep, *sp["validation"])
    hol = period(ep, *sp["holdout"])
    periods = {"desarrollo": dev, "validacion": val} if args.stage == "select" else {"holdout": hol}
    pool_end = sp["validation"][1] if args.stage == "select" else sp["holdout"][1]
    pool_all = ep[ep["detected_time"] <= pd.Timestamp(pool_end) + pd.Timedelta(days=1)]

    # ---------------- 1. reglas base (sin memoria) -------------------------------------------
    res["reglas_base"] = {}
    for name in list(STRATEGIES) + list(BASE_NO_CONTEXT):
        res["reglas_base"][name] = {}
        for pl, d in periods.items():
            s = select(d, name, risk_cfg)
            tr, _ = run_portfolio(s, spec, limits, eq0, slip)
            # sensibilidad: el spread histórico real de cada vela en vez del spread de coste (aprox.: coste extra fijo)
            hist = s["res_2r"] - ((s["spread_points"] - s["cost_spread_points"]).clip(lower=0) * spec.point) / s["risk_price"]
            res["reglas_base"][name][pl] = {"todas_las_senales": r_stats(s["res_2r"]),
                                            "bruto_sin_costes": r_stats(s["res_2r"] + s["cost_r"]),
                                            "sensibilidad_spread_historico": r_stats(hist),
                                            "cartera": summarize(tr, eq0)}
        print(name, {k: v["todas_las_senales"] for k, v in res["reglas_base"][name].items()}, flush=True)

    # ---------------- 2. filtro de memoria (vecinos cercanos, walk-forward) --------------------
    res["memoria"] = {}
    taken_cache: dict = {}
    for name in STRATEGIES:
        pool = pool_all[pool_all["structure_type"].isin(TYPES[name])]
        train = dev[dev["structure_type"].isin(TYPES[name])]       # escalas: solo desarrollo
        configs = GRID
        if args.stage == "holdout":
            sel = json.loads(sel_path.read_text(encoding="utf-8")) if sel_path.exists() else {}
            configs = GRID   # se informan todas, pero solo la congelada cuenta como resultado
        for dc in configs:
            md = MemoryDecision(pool, train, dc)
            key = f"{name}|{cfg_name(dc)}"
            res["memoria"][key] = {}
            for pl, d in periods.items():
                s = select(d, name, risk_cfg)
                ev = md.evaluate(s) if len(s) else s.assign(take=False)
                taken = ev[ev["take"]]
                taken_cache[(key, pl)] = taken
                tr, sk = run_portfolio(taken, spec, limits, eq0, slip)
                res["memoria"][key][pl] = {"senales": int(len(s)), "operadas": int(len(taken)),
                                           "r": r_stats(taken["res_2r"]) if len(taken) else {"n": 0},
                                           "cartera": summarize(tr, eq0)}
            print(key, {pl: v["r"] for pl, v in res["memoria"][key].items()}, flush=True)

    # ---------------- 3. selección prerregistrada / evaluación congelada -----------------------
    if args.stage == "select":
        cands = []
        for key, v in res["memoria"].items():
            dv, vl = v["desarrollo"]["r"], v["validacion"]["r"]
            ok = (dv.get("n", 0) >= 30 and (dv.get("exp_r") or -1) > 0 and (dv.get("t") or 0) > 1.0
                  and vl.get("n", 0) >= 15 and (vl.get("exp_r") or -1) > 0)
            cands.append({"clave": key, "cumple": ok, "dev": dv, "val": vl,
                          "puntuacion": min(dv.get("t") or -9, vl.get("t") or -9)})
        for name, v in res["reglas_base"].items():
            if name not in STRATEGIES:
                continue
            dv, vl = v["desarrollo"]["todas_las_senales"], v["validacion"]["todas_las_senales"]
            ok = dv.get("n", 0) >= 30 and dv["exp_r"] > 0 and (dv.get("t") or 0) > 1.0 and vl.get("n", 0) >= 15 and vl["exp_r"] > 0
            cands.append({"clave": f"{name}|base", "cumple": ok, "dev": dv, "val": vl,
                          "puntuacion": min(dv.get("t") or -9, vl.get("t") or -9)})
        winners = sorted([c for c in cands if c["cumple"]], key=lambda c: -c["puntuacion"])
        decision = winners[0]["clave"] if winners else "NO_OPERAR"
        res["seleccion"] = {"criterio": "dev: n>=30, media>0, t>1; val: n>=15, media>0; gana el mayor min(t_dev, t_val)",
                            "candidatos": cands, "elegida": decision}
        sel_path.write_text(json.dumps({"combo": combo, "elegida": decision, "run_id": run_id,
                                        "congelada_en": datetime.now(timezone.utc).isoformat()}, indent=2), encoding="utf-8")
        print("SELECCION:", decision, flush=True)
    else:
        sel = json.loads(sel_path.read_text(encoding="utf-8")) if sel_path.exists() else {"elegida": "NO_OPERAR"}
        res["seleccion_congelada"] = sel

    # ---------------- 4. walk-forward anual de la mejor opción de cada estrategia ------------------
    years = sorted(set(pd.to_datetime(pool_all["detected_time"]).dt.year))
    res["walk_forward"] = {}
    for name in STRATEGIES:
        pool = pool_all[pool_all["structure_type"].isin(TYPES[name])]
        dc = GRID[0]
        rows = {}
        for y in years:
            if y <= years[0]:
                continue
            fold = pool_all[pd.to_datetime(pool_all["detected_time"]).dt.year == y]
            if args.stage == "select" and y >= int(sp["holdout"][0][:4]):
                continue
            train = pool[pool["detected_time"] < pd.Timestamp(f"{y}-01-01")]    # escalas reajustadas al inicio del pliegue
            if len(train) < 200:
                continue
            s = select(fold, name, risk_cfg)
            ev = MemoryDecision(pool, train, dc).evaluate(s) if len(s) else s.assign(take=False)
            rows[str(y)] = {"base": r_stats(s["res_2r"]), "memoria": r_stats(ev.loc[ev["take"], "res_2r"])}
        res["walk_forward"][f"{name}|{cfg_name(dc)}"] = rows

    # ---------------- 5. referencias, estrés y desgloses -------------------------------------------
    m1 = load_m1(cfg)
    m1a = M1Arrays.from_frame(m1, spec.point, cfg["backtest"]["flat_before_rollover"], cfg["backtest"].get("cost_spread_points"))
    atr_series = ep.set_index("detected_time")["atr"].sort_index()
    atr_series = atr_series[~atr_series.index.duplicated()]

    def atr_at(ts):
        i = atr_series.index.searchsorted(pd.Timestamp(ts), side="right") - 1
        return float(atr_series.iloc[i]) if i >= 0 else np.nan

    res["referencias"] = {}
    for pl, d in periods.items():
        s = select(d, "A_sin_contexto", risk_cfg)
        rnd = random_entries(m1a, atr_at, s["entry_time"], cfg["backtest"]["max_hold_bars"] * TF_MINUTES[tf], slip, seed=seed)
        res["referencias"][pl] = {"entradas_aleatorias_2R": r_stats(rnd),
                                  "todas_las_estructuras": r_stats(d["res_2r"]),
                                  "comprar_y_mantener_pct": round(float(m1.loc[d["detected_time"].min():d["detected_time"].max(), "close"].iloc[[0, -1]].pct_change().iloc[-1] * 100), 2)}

    # estrés de costes y desgloses para la regla/configuración más relevante
    focus_key = (res.get("seleccion", {}).get("elegida") or res.get("seleccion_congelada", {}).get("elegida") or "NO_OPERAR")
    res["foco"] = focus_key
    if focus_key == "NO_OPERAR":
        # sin estrategia elegida, se documenta la regla A con contexto (la menos mala en desarrollo) como ejemplo
        focus_key = "A_continuacion|base"
    fname, fcfg = focus_key.split("|")
    last_pl = list(periods)[-1]
    if fcfg == "base":
        sig = select(periods[last_pl], fname, risk_cfg)
    else:
        sig = taken_cache[(focus_key, last_pl)]
    tr, sk = run_portfolio(sig, spec, limits, eq0, slip)
    res["foco_detalle"] = {"periodo": last_pl, "clave": focus_key, "cartera": summarize(tr, eq0),
                           "descartes": sk["reason"].value_counts().to_dict() if len(sk) else {},
                           "por_sesion": breakdown(tr, "session").reset_index().to_dict("records"),
                           "por_anio": breakdown(tr, "year").reset_index().to_dict("records"),
                           "por_volatilidad": breakdown(tr, "vol").reset_index().to_dict("records"),
                           "por_estructura": breakdown(tr, "structure_type").reset_index().to_dict("records")}
    res["estres"] = {}
    for lab, extra in [("deslizamiento_x2", 2 * slip), ("deslizamiento_x3", 4 * slip),
                       ("spread_x2", float(sig["cost_spread_points"].median()) * spec.point if len(sig) else 0.0),
                       ("spread_historico_real", float((sig["spread_points"] - sig["cost_spread_points"]).clip(lower=0).median()) * spec.point if len(sig) else 0.0)]:
        t2, _ = run_portfolio(sig, spec, limits, eq0, slip, extra_cost_price=extra)
        res["estres"][lab] = summarize(t2, eq0)
    # con el equity real de la demo (543,93 USD) el lote mínimo bloquea muchas operaciones
    t3, s3 = run_portfolio(sig, spec, limits, 543.93, slip)
    res["equity_demo_543"] = {"cartera": summarize(t3, 543.93),
                              "descartes": s3["reason"].value_counts().to_dict() if len(s3) else {}}
    if len(tr):
        tr.to_csv(out_dir / "operaciones_foco.csv", index=False)
        equity_chart(tr, eq0, rep_dir / f"equity_{tag}_{args.stage}.png", f"{focus_key} ({last_pl})")

    (out_dir / "resultados.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (rep_dir / f"backtest_{tag}_{args.stage}.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    store = MemoryStore(ROOT / cfg["memory"]["db_path"])
    store.log_experiment(run_id, res["code_version"], {"combo": combo, "split": sp, "grid": [d.__dict__ for d in GRID]},
                         seed, str(out_dir), {"foco": res["foco"]})
    print("guardado en", out_dir, flush=True)


if __name__ == "__main__":
    main()
