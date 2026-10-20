"""Fase 6b: ajustes razonables a las estrategias A/B/C con protocolo prerregistrado.

Pregunta: ¿algún ajuste sencillo (stop más amplio, otro objetivo, stop mínimo para que el coste pese menos,
solo sesiones activas) da expectativa NETA positiva fuera de muestra?

Rejilla (fijada ANTES de ver resultados, 2026-10-20):
  estrategia      A_continuacion, B_reversion, C_cambio_tendencia (reglas de strategies/rules.py)
  colchon_stop    0,10 ATR (original) | 0,50 ATR (stop más amplio)
  objetivo        1 R | 1,5 R | 2 R | 3 R
  stop_minimo     0 | 20 puntos de índice (el coste fijo de 2,12 puntos pesa como máximo ~0,1 R)
  sesion          todas | activas (londres, ny_apertura, ny)
  = 96 variantes por combinación. Coste: spread 1,12 puntos + 0,5 puntos de deslizamiento por lado.

Selección (prerregistrada; más estricta que la de run_research porque se prueban 96 variantes):
  desarrollo: n >= 100, media > 0, t >= 2,0 · validación: n >= 50, media > 0, t >= 1,0
  gana el mayor min(t_dev, t_val). Si ninguna cumple: NO_OPERAR y el holdout no se usa para elegir.
  El holdout se informa para TODAS las variantes solo como diagnóstico (y para ver cuántas saldrían positivas
  por azar), nunca para elegir.

Uso: python scripts/run_adjustments.py --combo 0
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nsmb.backtesting.metrics import r_stats, summarize  # noqa: E402
from nsmb.backtesting.portfolio import run_portfolio  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays, simulate_multi  # noqa: E402
from nsmb.config import SymbolSpec, load_risk, load_settings  # noqa: E402
from nsmb.data.timeframes import TF_MINUTES  # noqa: E402
from nsmb.risk.manager import RiskLimits  # noqa: E402
from nsmb.strategies.rules import STRATEGIES, select  # noqa: E402

BUFFERS = [0.10, 0.50]
TARGETS = [1.0, 1.5, 2.0, 3.0]
MIN_STOP_PTS = [0.0, 20.0]
SESSIONS = {"todas": None, "activas": ["londres", "ny_apertura", "ny"]}
ACTIVE = ["londres", "ny_apertura", "ny"]


def resimulate(sig: pd.DataFrame, m1a: M1Arrays, buffer_atr: float, tf: str, cfg_bt: dict, spec: SymbolSpec,
               cost_pts: float) -> pd.DataFrame:
    """Vuelve a simular cada señal con otro colchón de stop y varios objetivos (misma entrada, sin anticipación)."""
    slip = cfg_bt["slippage_points"] * spec.point
    max_min = cfg_bt["max_hold_bars"] * TF_MINUTES[tf]
    spread_px = cost_pts * spec.point
    rows = []
    for e in sig.itertuples(index=False):
        d = int(e.direction)
        stop = e.invalidation - buffer_atr * e.atr if d > 0 else e.invalidation + buffer_atr * e.atr + spread_px
        i = m1a.index_at(e.entry_time)
        r = simulate_multi(m1a, i, d, stop, TARGETS, max_min, slip)
        if r is None:
            continue
        risk = r["time"].risk_price
        if not (0.15 <= risk / e.atr <= 6.0):
            continue
        row = {"episode_id": e.episode_id, "risk_price": risk, "cost_r": (spread_px + 2 * slip) / risk}
        for tr in TARGETS:
            x = r[tr]
            row[f"r_{tr}"] = x.pnl_price / x.risk_price
            row[f"dur_{tr}"] = int((m1a.time[x.exit_i] - m1a.time[i]) / np.timedelta64(1, "m")) + 1
        rows.append(row)
    out = pd.DataFrame(rows)
    keep = [c for c in sig.columns if c not in ("risk_price", "cost_r")]
    return sig[keep].merge(out, on="episode_id")


def period(df, a, b):
    return df[(df["detected_time"] >= pd.Timestamp(a)) & (df["detected_time"] <= pd.Timestamp(b) + pd.Timedelta(days=1))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--combo", type=int, default=0)
    args = ap.parse_args()
    cfg, risk_cfg = load_settings(), load_risk()
    spec, limits = SymbolSpec.from_settings(cfg), RiskLimits.from_cfg(risk_cfg)
    combo = cfg["backtest"]["combos"][args.combo]
    tf, tag = combo[2], "_".join(combo)
    cost_pts = cfg["backtest"]["cost_spread_points"]
    slip = cfg["backtest"]["slippage_points"] * spec.point
    eq0 = cfg["backtest"]["initial_equity"]
    sp = cfg["split"]

    ep = pd.read_parquet(ROOT / "data" / "processed" / f"episodes_{tag}.parquet")
    ep = ep[ep["status"] == "ok"].copy()
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1a = M1Arrays.from_frame(m1, spec.point, cfg["backtest"]["flat_before_rollover"], cost_pts)

    sims = {}
    for name in STRATEGIES:
        sig = select(ep, name, risk_cfg)
        for b in BUFFERS:
            sims[(name, b)] = resimulate(sig, m1a, b, tf, cfg["backtest"], spec, cost_pts)
        print(name, len(sig), "señales", flush=True)

    rows = []
    for (name, b), s in sims.items():
        for tr in TARGETS:
            for ms in MIN_STOP_PTS:
                for ses, allowed in SESSIONS.items():
                    x = s[s["risk_price"] >= ms]
                    if allowed:
                        x = x[x["session"].isin(allowed)]
                    row = {"clave": f"{name}|stop{b:.2f}ATR|obj{tr}R|min{ms:.0f}pts|{ses}",
                           "estrategia": name, "colchon": b, "objetivo": tr, "stop_min": ms, "sesion": ses}
                    for pl, (a, z) in (("dev", sp["development"]), ("val", sp["validation"]), ("hol", sp["holdout"])):
                        y = period(x, a, z)
                        st = r_stats(y[f"r_{tr}"])
                        gross = r_stats(y[f"r_{tr}"] + y["cost_r"])
                        row[f"{pl}_n"], row[f"{pl}_r"], row[f"{pl}_t"] = st.get("n", 0), st.get("exp_r"), st.get("t")
                        row[f"{pl}_bruto"] = gross.get("exp_r")
                    rows.append(row)
    tab = pd.DataFrame(rows)

    def passes(r):
        return (r.dev_n >= 100 and (r.dev_r or -1) > 0 and (r.dev_t or 0) >= 2.0
                and r.val_n >= 50 and (r.val_r or -1) > 0 and (r.val_t or 0) >= 1.0)

    tab["cumple"] = tab.apply(passes, axis=1)
    tab["puntuacion"] = tab[["dev_t", "val_t"]].min(axis=1)
    winners = tab[tab["cumple"]].sort_values("puntuacion", ascending=False)
    decision = winners.iloc[0]["clave"] if len(winners) else "NO_OPERAR"

    res = {"combo": combo, "coste_spread_points": cost_pts, "deslizamiento_points": cfg["backtest"]["slippage_points"],
           "variantes": len(tab), "cumplen": int(tab["cumple"].sum()), "elegida": decision,
           "dev_positivas": int((tab.dev_r > 0).sum()), "val_positivas": int((tab.val_r > 0).sum()),
           "dev_y_val_positivas": int(((tab.dev_r > 0) & (tab.val_r > 0)).sum()),
           "hol_positivas": int((tab.hol_r > 0).sum()),
           "todas_positivas": int(((tab.dev_r > 0) & (tab.val_r > 0) & (tab.hol_r > 0)).sum())}
    if decision != "NO_OPERAR":
        w = winners.iloc[0]
        s = sims[(w.estrategia, w.colchon)]
        s = s[s["risk_price"] >= w.stop_min]
        if SESSIONS[w.sesion]:
            s = s[s["session"].isin(SESSIONS[w.sesion])]
        h = period(s, *sp["holdout"]).assign(res_x=lambda d: d[f"r_{w.objetivo}"], dur_x=lambda d: d[f"dur_{w.objetivo}"])
        tr_, _ = run_portfolio(h, spec, limits, eq0, slip, res_col="res_x", dur_col="dur_x")
        res["holdout_elegida"] = {"r": r_stats(h["res_x"]), "cartera": summarize(tr_, eq0)}

    run_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{tag}_ajustes"
    out = ROOT / "data" / "backtests" / run_id
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (out / "resumen.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (ROOT / "reports" / f"ajustes_{tag}.json").write_text(json.dumps({**res, "tabla": tab.round(4).to_dict("records")},
                                                                     indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False, default=str))
    cols = ["clave", "dev_n", "dev_r", "dev_t", "val_n", "val_r", "val_t", "hol_n", "hol_r", "hol_t", "hol_bruto"]
    print(tab.sort_values("puntuacion", ascending=False)[cols].head(12).round(3).to_string(index=False))


if __name__ == "__main__":
    main()
