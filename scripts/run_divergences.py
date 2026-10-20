"""Fase 6g: la idea de John, operar divergencias RSI en cada temporalidad (prerregistrado, 2026-10-20).

La rejilla y la regla de selección se guardaron en git ANTES de ejecutar por primera vez.

Divergencias (RSI 14 de la misma temporalidad, pivotes fractales 3-3: se conocen 3 velas después del extremo):
  normal alcista: el precio hace un mínimo más bajo y el RSI un mínimo más alto      -> compra
  normal bajista: el precio hace un máximo más alto y el RSI un máximo más bajo      -> venta
  oculta alcista: el precio hace un mínimo más alto y el RSI un mínimo más bajo      -> compra
  oculta bajista: el precio hace un máximo más bajo y el RSI un máximo más alto      -> venta
  Entre los dos pivotes: de 5 a 60 velas. La señal se conoce al cierre de la vela que confirma el segundo pivote;
  la entrada es en la apertura siguiente.

Objetivos de John (en puntos del índice; con USTECm 1 punto = 1 USD por lote, así que con 1 lote son esos dólares):
  M1 15 · M5 20 · M15 40 · H1 80 · H4 160 puntos. Variante: objetivo de 2 ATR de la temporalidad.
Stop: {pivote (extremo del segundo pivote +- 0,1 ATR), simétrico (a la misma distancia que el objetivo)}.
Contexto: {todas, solo a favor de la media de 50 días}.
Rejilla: 5 TF x {normal, oculta} x 2 objetivos x 2 stops x 2 contextos                                         = 80
Máximo 60 velas; sin cierre diario forzado; compras con swap. Coste: spread 1,12 + 0,5 por lado.

Diagnóstico sin stop ni costes (no se usa para elegir): movimiento a favor tras 5, 20 y 60 velas, en ATR, y
proporción de casos en que el precio avanza 1 ATR a favor antes que 1 ATR en contra.

Periodos y selección: los mismos de siempre (desarrollo 2021-11..2023 con n >= 100, media > 0, t >= 2; validación
2024 con n >= 50, media > 0, t >= 1; 2025-26 solo diagnóstico). Bonferroni con todas las variantes de hoy.

Uso: python scripts/run_divergences.py
"""
from __future__ import annotations

import json
import subprocess
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
from nsmb.market_structure.pivots import fractal_pivots  # noqa: E402

TFS = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240}
JOHN_PTS = {"M1": 15.0, "M5": 20.0, "M15": 40.0, "H1": 80.0, "H4": 160.0}
MAX_BARS = 60
N_PREVIOUS = 265 + 96


def detect(df: pd.DataFrame) -> pd.DataFrame:
    h, l = df["high"].to_numpy(), df["low"].to_numpy()
    r, a = df["rsi"].to_numpy(), df["atr"].to_numpy()
    piv = fractal_pivots(h, l, 3, 3)
    last = {"H": None, "L": None}
    out = []
    for p in piv:                         # ordenados por vela de confirmación
        prev = last[p.kind]
        last[p.kind] = p
        if prev is None or not (5 <= p.idx - prev.idx <= 60):
            continue
        r1, r2 = r[prev.idx], r[p.idx]
        if not (np.isfinite(r1) and np.isfinite(r2) and np.isfinite(a[p.confirm_idx])):
            continue
        typ = None
        if p.kind == "L":
            if p.price < prev.price and r2 > r1:
                typ, d = "normal", 1
            elif p.price > prev.price and r2 < r1:
                typ, d = "oculta", 1
        else:
            if p.price > prev.price and r2 < r1:
                typ, d = "normal", -1
            elif p.price < prev.price and r2 > r1:
                typ, d = "oculta", -1
        if typ:
            out.append({"t": p.confirm_idx, "tipo": typ, "direction": d, "pivot": p.price, "atr": a[p.confirm_idx]})
    return pd.DataFrame(out)


def reaction(sig: pd.DataFrame, df: pd.DataFrame) -> dict:
    """Movimiento a favor sin stop ni costes, en ATR, desde la apertura de la vela siguiente."""
    o, c, h, l = (df[k].to_numpy() for k in ("open", "close", "high", "low"))
    res = {}
    n = len(df)
    for N in (5, 20, 60):
        v = []
        for x in sig.itertuples(index=False):
            j, e = x.t + 1, x.t + N
            if e < n:
                v.append(x.direction * (c[e] - o[j]) / x.atr)
        v = np.array(v)
        res[f"a_favor_{N}_velas_atr"] = round(float(v.mean()), 4) if len(v) else None
        res[f"t_{N}"] = round(float(v.mean() / (v.std(ddof=1) / np.sqrt(len(v)))), 2) if len(v) > 2 else None
    first = []
    for x in sig.itertuples(index=False):
        j = x.t + 1
        if j >= n:
            continue
        e0 = o[j]
        up, dn = e0 + x.atr, e0 - x.atr
        for k in range(j, min(j + 60, n)):
            hit_fav = h[k] >= up if x.direction > 0 else l[k] <= dn
            hit_adv = l[k] <= dn if x.direction > 0 else h[k] >= up
            if hit_fav and hit_adv:
                first.append(0.5)
                break
            if hit_fav:
                first.append(1.0)
                break
            if hit_adv:
                first.append(0.0)
                break
    res["avanza_1ATR_antes_que_retrocede"] = round(float(np.mean(first)), 4) if first else None
    res["n"] = int(len(sig))
    return res


def simulate(sig, df, m, tf, target_kind, stop_kind):
    rows = []
    ct = df["close_time"].to_numpy()
    for x in sig.itertuples(index=False):
        d = int(x.direction)
        ts = pd.Timestamp(ct[x.t])
        me = I.market_entry(m, ts, d)
        if me is None:
            continue
        i, px = me
        dist = JOHN_PTS[tf] if target_kind == "puntos_John" else 2.0 * x.atr
        tgt = px + d * dist
        if stop_kind == "pivote":
            stop = x.pivot - 0.1 * x.atr if d > 0 else x.pivot + 0.1 * x.atr + I.SPREAD_PTS
        else:
            stop = px - d * dist
        risk = (px - stop) * d
        if risk <= 0 or risk > 10 * x.atr:
            continue
        res = I.trade(m, i, d, px, stop, tgt, I.end_index(m, i, MAX_BARS * TFS[tf]), False, use_flat=False)
        if res is None:
            continue
        swap = I.nights_swap(pd.Timestamp(m.time[i]), pd.Timestamp(m.time[res[2]])) if d > 0 else 0.0
        r = I.row(ts, d, res, i, m, {"tipo": x.tipo}, swap=swap)
        r["cost_r"] = (I.SPREAD_PTS + 2 * I.SLIP + swap) / res[1]
        r["pts"] = (res[0] - swap)
        rows.append(r)
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    d1 = I.daily_bars(m1)
    _, st = StructureEngine(StructureParams.from_cfg(cfg["structure"])).run(add_indicators(d1))
    bias = I.daily_bias(d1, st)

    rows, diag = [], {}
    for tf in TFS:
        bars = resample(m1, tf)
        bars = bars[bars["complete"]]
        df = add_indicators(bars)
        sig = detect(df)
        print(tf, len(df), "velas,", len(sig), "divergencias", sig["tipo"].value_counts().to_dict(), flush=True)
        for typ in ("normal", "oculta"):
            s0 = sig[sig["tipo"] == typ]
            diag[f"{tf}|{typ}"] = {"todo": reaction(s0, df)}
            for p, (a_, b_) in I.PERIODS.items():
                tt = pd.to_datetime(df["close_time"].to_numpy()[s0["t"]]) if len(s0) else pd.DatetimeIndex([])
                mask = (tt >= pd.Timestamp(a_)) & (tt < pd.Timestamp(b_) + pd.Timedelta(days=1))
                diag[f"{tf}|{typ}"][p] = reaction(s0[np.asarray(mask)], df)
        for tk in ("puntos_John", "2ATR"):
            for sk in ("pivote", "simetrico"):
                s = simulate(sig, df, m, tf, tk, sk)
                s = I.attach_bias(s, bias) if len(s) else s
                for typ in ("normal", "oculta"):
                    x = s[s["tipo"] == typ]
                    for ctx in ("todas", "media50"):
                        y = x if ctx == "todas" else x[x["direction"] * x["sma_bias"] > 0]
                        res = I.by_period(y) if len(y) else {p: {"n": 0} for p in I.PERIODS}
                        r = {"clave": f"{tf}|{typ}|obj_{tk}|stop_{sk}|{ctx}", "tf": tf, "tipo": typ, "objetivo": tk,
                             "stop": sk, "contexto": ctx}
                        for p in I.PERIODS:
                            for kk in ("n", "r", "t", "bruto", "aciertos"):
                                r[f"{p}_{kk}"] = res[p].get(kk)
                        r["puntos_medios"] = round(float(y["pts"].mean()), 2) if len(y) else None
                        r["cumple"] = I.passes(res, "x")
                        rows.append(r)
        print(tf, "listo", flush=True)
    tab = pd.DataFrame(rows)
    n_total = N_PREVIOUS + len(tab)
    winners = tab[tab["cumple"]].assign(score=lambda x: x[["dev_t", "val_t"]].min(axis=1)).sort_values("score", ascending=False)
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "version_codigo": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                text=True).stdout.strip(),
               "objetivos_John_puntos": JOHN_PTS, "variantes": len(tab), "cumplen": len(winners),
               "elegida": winners.iloc[0]["clave"] if len(winners) else "NO_OPERAR",
               "dev_positivas": int((tab.dev_r.fillna(-1) > 0).sum()), "val_positivas": int((tab.val_r.fillna(-1) > 0).sum()),
               "las_tres_positivas": int(((tab.dev_r.fillna(-1) > 0) & (tab.val_r.fillna(-1) > 0) & (tab.hol_r.fillna(-1) > 0)).sum()),
               "bonferroni": {"variantes_totales_hoy": n_total, "t_necesario": round(float(norm.ppf(1 - 0.05 / n_total)), 2)},
               "reaccion_sin_stop_ni_costes": diag,
               "ganadoras": winners.drop(columns=["score"]).to_dict("records")}
    run_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_divergencias"
    out = ROOT / "data" / "backtests" / run_id
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (out / "resumen.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (ROOT / "reports" / "divergencias.json").write_text(json.dumps({**summary, "tabla": tab.round(4).to_dict("records")},
                                                                   indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "reaccion_sin_stop_ni_costes"}, indent=1, ensure_ascii=False, default=str))
    for k, v in diag.items():
        print(k, v["todo"])
    pd.set_option("display.width", 250)
    cols = ["clave", "dev_n", "dev_r", "dev_t", "dev_bruto", "val_n", "val_r", "val_t", "hol_n", "hol_r", "hol_t", "hol_bruto",
            "dev_aciertos", "puntos_medios"]
    print(tab[cols].to_string(index=False))


if __name__ == "__main__":
    main()
