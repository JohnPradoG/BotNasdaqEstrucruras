"""Fase 6f: figuras chartistas clásicas bien definidas, en M15, H1, H4 y D1 (protocolo prerregistrado, 2026-10-20).

La rejilla, las definiciones y la regla de selección se guardaron en git ANTES de ejecutar por primera vez.

Oscilaciones: pivotes fractales 3-3 (se conocen 3 velas después del extremo) con alternancia máximo/mínimo y
tamaño mínimo de 0,5 ATR (la misma lógica que el motor del bot). Una figura solo se forma con oscilaciones ya
confirmadas y solo se opera cuando una vela CIERRA más allá de su línea de ruptura. Entrada en la apertura siguiente.

Figuras (altura = tamaño de la figura; tol = 15 % de la altura):
  doble       Doble techo: máximo, mínimo, máximo con |H1-H2| <= tol, altura >= 1,5 ATR, >= 6 velas entre máximos.
              Ruptura: cierre por debajo del mínimo (línea clavicular). Stop: máximo de la figura + 0,1 ATR.
              Objetivo medido: clavicular - altura. Doble suelo, al revés. Caduca: 2 x anchura o si supera el máximo.
  hch         Hombro-cabeza-hombro: H1 L1 H2 L2 H3 con cabeza H2 >= max(H1,H3) + 0,3 ATR, |H1-H3| <= 25 % de la altura,
              clavicular = recta L1-L2. Ruptura: cierre bajo la clavicular. Stop: hombro derecho H3 + 0,1 ATR.
              Objetivo: clavicular - (cabeza - clavicular). HCH invertido, al revés.
  triangulo   Dos máximos y dos mínimos alternados que se estrechan: H2 <= H1 + tol, L2 >= L1 - tol, rango final
              < 80 % del inicial, y no ambos planos. Ruptura: cierre fuera de la recta de máximos (compra) o de
              mínimos (venta). Stop: última oscilación contraria + 0,1 ATR. Objetivo: altura inicial desde la ruptura.
  rectangulo  Dos máximos y dos mínimos planos (|H1-H2| y |L1-L2| <= tol), altura >= 1,5 ATR. Ruptura: cierre fuera.
              Stop: mitad del rango. Objetivo: altura desde la ruptura.
  cuna        Cuña ascendente: máximos y mínimos subiendo (más de tol) y estrechándose (< 80 %); ruptura: cierre bajo
              la recta de mínimos (venta). Cuña descendente, al revés (compra). Stop: último extremo + 0,1 ATR.
              Objetivo: altura inicial.
  bandera     Mástil: oscilación de >= 3 ATR en <= 15 velas; consolidación: retroceso <= 50 % del mástil en <= 15
              velas. Ruptura: cierre más allá del final del mástil, a favor. Stop: extremo de la consolidación
              + 0,1 ATR. Objetivo: longitud del mástil desde la ruptura.

Rejilla: 6 figuras x TF {M15, H1, H4, D1} x salida {objetivo medido, 2 R} x contexto {todas, a favor de la media de
50 días}                                                                                                  = 96
Máximo de 60 velas de la temporalidad; sin cierre diario forzado; las compras pagan swap por noche (x3 viernes).
Coste: spread 1,12 + 0,5 por lado.

Periodos y selección: desarrollo 2021-11..2023, validación 2024; 2025-26 solo diagnóstico (ya visto).
  desarrollo: n >= 100 (40 en H4 y D1), media > 0, t >= 2 (agrupado por día);
  validación: n >= 50 (15 en H4 y D1), media > 0, t >= 1. Si nada cumple: NO OPERAR.
Bonferroni con todas las variantes probadas hoy (265 + 96).

Uso: python scripts/run_patterns.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
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

TFS = {"M15": 15, "H1": 60, "H4": 240, "D1": 1440}
PATTERNS = ["doble", "hch", "triangulo", "rectangulo", "cuna", "bandera"]
MAX_BARS = 60
N_PREVIOUS = 265


@dataclass
class Sw:
    idx: int
    price: float
    kind: str


@dataclass
class Pend:
    name: str
    d: int                # +1 compra / -1 venta (para figuras bidireccionales se crean dos)
    p0: tuple             # recta de ruptura: (idx, precio) x 2
    p1: tuple
    stop: float
    height: float
    expire: int
    cancel_above: float = np.inf
    cancel_below: float = -np.inf
    key: tuple = field(default_factory=tuple)

    def line(self, t: int) -> float:
        (i0, y0), (i1, y1) = self.p0, self.p1
        return y0 if i1 == i0 else y0 + (y1 - y0) * (t - i0) / (i1 - i0)


def detect(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve señales (una fila por ruptura confirmada al cierre)."""
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    a = df["atr"].to_numpy()
    piv = fractal_pivots(h, l, 3, 3)
    by_conf: dict[int, list] = {}
    for p in piv:
        by_conf.setdefault(p.confirm_idx, []).append(p)
    swings: list[Sw] = []
    pend: list[Pend] = []
    seen: set = set()
    out = []
    for t in range(len(df)):
        at = a[t]
        # 1) rupturas al cierre de t de figuras ya formadas
        keep = []
        for q in pend:
            if t > q.expire or h[t] > q.cancel_above or l[t] < q.cancel_below:
                continue
            lv = q.line(t)
            if (q.d > 0 and c[t] > lv) or (q.d < 0 and c[t] < lv):
                out.append({"t": t, "figura": q.name, "direction": q.d, "stop": q.stop, "height": q.height,
                            "level": lv, "atr": at})
                continue
            keep.append(q)
        pend = keep
        if not np.isfinite(at) or at <= 0:
            continue
        # 2) oscilaciones confirmadas al cierre de t
        changed = False
        for pv in by_conf.get(t, []):
            sw = Sw(pv.idx, pv.price, pv.kind)
            if not swings:
                swings.append(sw)
                changed = True
            elif swings[-1].kind == sw.kind:
                if (sw.kind == "H" and sw.price > swings[-1].price) or (sw.kind == "L" and sw.price < swings[-1].price):
                    swings[-1] = sw
                    changed = True
            elif abs(sw.price - swings[-1].price) >= 0.5 * at:
                swings.append(sw)
                changed = True
        if not changed or len(swings) < 3:
            continue
        swings = swings[-12:]
        for q in new_patterns(swings, t, at):
            if q.key not in seen:
                seen.add(q.key)
                pend.append(q)
    return pd.DataFrame(out)


def new_patterns(s: list[Sw], t: int, at: float) -> list[Pend]:
    res = []
    last = s[-1]

    def k(name, d, *sws):
        return (name, d) + tuple(x.idx for x in sws)

    # --- doble techo / doble suelo (último pivote = segundo extremo) ---
    if len(s) >= 3:
        x1, m, x2 = s[-3], s[-2], s[-1]
        if x2.kind == "H":
            top = max(x1.price, x2.price)
            hgt = top - m.price
            if hgt >= 1.5 * at and abs(x1.price - x2.price) <= 0.15 * hgt and x2.idx - x1.idx >= 6:
                res.append(Pend("doble", -1, (m.idx, m.price), (m.idx, m.price), top + 0.1 * at, hgt,
                                t + 2 * (x2.idx - x1.idx), cancel_above=top + 0.15 * hgt, key=k("doble", -1, x1, m, x2)))
        else:
            bot = min(x1.price, x2.price)
            hgt = m.price - bot
            if hgt >= 1.5 * at and abs(x1.price - x2.price) <= 0.15 * hgt and x2.idx - x1.idx >= 6:
                res.append(Pend("doble", 1, (m.idx, m.price), (m.idx, m.price), bot - 0.1 * at, hgt,
                                t + 2 * (x2.idx - x1.idx), cancel_below=bot - 0.15 * hgt, key=k("doble", 1, x1, m, x2)))
    # --- HCH / HCH invertido ---
    if len(s) >= 5:
        s1, n1, hd, n2, s2 = s[-5:]
        if s2.kind == "H":
            neck_h = n1.price + (n2.price - n1.price) * (hd.idx - n1.idx) / max(n2.idx - n1.idx, 1)
            hgt = hd.price - neck_h
            if hd.price >= max(s1.price, s2.price) + 0.3 * at and hgt > 0 and abs(s1.price - s2.price) <= 0.25 * hgt:
                res.append(Pend("hch", -1, (n1.idx, n1.price), (n2.idx, n2.price), s2.price + 0.1 * at, hgt,
                                t + (s2.idx - s1.idx), cancel_above=hd.price, key=k("hch", -1, s1, n1, hd, n2, s2)))
        else:
            neck_h = n1.price + (n2.price - n1.price) * (hd.idx - n1.idx) / max(n2.idx - n1.idx, 1)
            hgt = neck_h - hd.price
            if hd.price <= min(s1.price, s2.price) - 0.3 * at and hgt > 0 and abs(s1.price - s2.price) <= 0.25 * hgt:
                res.append(Pend("hch", 1, (n1.idx, n1.price), (n2.idx, n2.price), s2.price - 0.1 * at, hgt,
                                t + (s2.idx - s1.idx), cancel_below=hd.price, key=k("hch", 1, s1, n1, hd, n2, s2)))
    # --- figuras de 4 oscilaciones: triángulo, rectángulo, cuña ---
    if len(s) >= 4:
        w = s[-4:]
        H = [x for x in w if x.kind == "H"]
        L = [x for x in w if x.kind == "L"]
        if len(H) == 2 and len(L) == 2:
            h1, h2 = H
            l1, l2 = L
            first = w[0]
            hgt0 = (h1.price - l1.price)
            hgt1 = (h2.price - l2.price)
            if hgt0 > 0:
                tol = 0.15 * hgt0
                width = w[-1].idx - w[0].idx
                flat_h, flat_l = abs(h2.price - h1.price) <= tol, abs(l2.price - l1.price) <= tol
                narrowing = hgt1 < 0.8 * hgt0
                up, lo_ = ((h1.idx, h1.price), (h2.idx, h2.price)), ((l1.idx, l1.price), (l2.idx, l2.price))
                # triángulo (simétrico, ascendente o descendente)
                if h2.price <= h1.price + tol and l2.price >= l1.price - tol and narrowing and not (flat_h and flat_l):
                    exp = t + 3 * max(width, 4)
                    res.append(Pend("triangulo", 1, *up, l2.price - 0.1 * at, hgt0, exp, cancel_below=l2.price,
                                    key=k("tri", 1, *w)))
                    res.append(Pend("triangulo", -1, *lo_, h2.price + 0.1 * at, hgt0, exp, cancel_above=h2.price,
                                    key=k("tri", -1, *w)))
                # rectángulo
                if flat_h and flat_l and hgt0 >= 1.5 * at:
                    top, bot = max(h1.price, h2.price), min(l1.price, l2.price)
                    mid = (top + bot) / 2
                    exp = t + 3 * max(width, 4)
                    res.append(Pend("rectangulo", 1, (t, top), (t, top), mid, top - bot, exp, key=k("rect", 1, *w)))
                    res.append(Pend("rectangulo", -1, (t, bot), (t, bot), mid, top - bot, exp, key=k("rect", -1, *w)))
                # cuñas
                if h2.price > h1.price + tol and l2.price > l1.price + tol and narrowing:      # ascendente: venta
                    res.append(Pend("cuna", -1, *lo_, h2.price + 0.1 * at, hgt0, t + 3 * max(width, 4),
                                    cancel_above=h2.price + 0.5 * hgt0, key=k("cuna", -1, *w)))
                if h2.price < h1.price - tol and l2.price < l1.price - tol and narrowing:      # descendente: compra
                    res.append(Pend("cuna", 1, *up, l2.price - 0.1 * at, hgt0, t + 3 * max(width, 4),
                                    cancel_below=l2.price - 0.5 * hgt0, key=k("cuna", 1, *w)))
                del first
    # --- bandera: mástil (s[-3] -> s[-2]) y consolidación (s[-1]) ---
    if len(s) >= 3:
        a0, a1, a2 = s[-3], s[-2], s[-1]
        pole = a1.price - a0.price
        if a1.kind == "H" and pole >= 3 * at and a1.idx - a0.idx <= 15 and a2.idx - a1.idx <= 15 \
                and (a1.price - a2.price) <= 0.5 * pole:
            res.append(Pend("bandera", 1, (a1.idx, a1.price), (a1.idx, a1.price), a2.price - 0.1 * at, pole,
                            t + 15, cancel_below=a2.price, key=k("band", 1, a0, a1, a2)))
        if a1.kind == "L" and -pole >= 3 * at and a1.idx - a0.idx <= 15 and a2.idx - a1.idx <= 15 \
                and (a2.price - a1.price) <= 0.5 * (-pole):
            res.append(Pend("bandera", -1, (a1.idx, a1.price), (a1.idx, a1.price), a2.price + 0.1 * at, -pole,
                            t + 15, cancel_above=a2.price, key=k("band", -1, a0, a1, a2)))
    return res


def simulate_signals(sig: pd.DataFrame, df: pd.DataFrame, m: M1Arrays, tf_min: int, exit_kind: str) -> pd.DataFrame:
    rows = []
    close_time = df["close_time"].to_numpy()
    for x in sig.itertuples(index=False):
        d = int(x.direction)
        ts = pd.Timestamp(close_time[x.t])
        me = I.market_entry(m, ts, d)
        if me is None:
            continue
        i, px = me
        stop = x.stop if d > 0 else x.stop + I.SPREAD_PTS
        risk = (px - stop) * d
        if risk <= 0 or not (0.15 <= risk / x.atr <= 8.0):
            continue
        tgt = x.level + d * x.height if exit_kind == "medido" else px + d * 2 * risk
        if (tgt - px) * d <= 0:
            continue
        res = I.trade(m, i, d, px, stop, tgt, I.end_index(m, i, MAX_BARS * tf_min), False, use_flat=False)
        if res is None:
            continue
        swap = I.nights_swap(pd.Timestamp(m.time[i]), pd.Timestamp(m.time[res[2]])) if d > 0 else 0.0
        r = I.row(ts, d, res, i, m, {"figura": x.figura}, swap=swap)
        r["cost_r"] = (I.SPREAD_PTS + 2 * I.SLIP + swap) / res[1]
        r["obj_r"] = (tgt - px) * d / risk
        r["motivo"] = res[3]
        rows.append(r)
    return pd.DataFrame(rows)


def passes(res: dict, tf: str) -> bool:
    dn, vn = (40, 15) if tf in ("H4", "D1") else (100, 50)
    d, v = res["dev"], res["val"]
    return (d.get("n", 0) >= dn and (d.get("r") or -1) > 0 and (d.get("t") or 0) >= 2.0
            and v.get("n", 0) >= vn and (v.get("r") or -1) > 0 and (v.get("t") or 0) >= 1.0)


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    d1 = I.daily_bars(m1)
    _, st = StructureEngine(StructureParams.from_cfg(cfg["structure"])).run(add_indicators(d1))
    bias = I.daily_bias(d1, st)

    variants, pooled = [], []
    for tf, tfm in TFS.items():
        bars = d1 if tf == "D1" else resample(m1, tf)
        bars = bars[bars["complete"]] if "complete" in bars else bars
        df = add_indicators(bars)
        if "close_time" not in df:
            df["close_time"] = bars["close_time"]
        sig = detect(df)
        print(tf, len(df), "velas,", len(sig), "rupturas", sig["figura"].value_counts().to_dict() if len(sig) else {}, flush=True)
        for exit_kind in ("medido", "2R"):
            s = simulate_signals(sig, df, m, tfm, exit_kind)
            s = I.attach_bias(s, bias) if len(s) else s
            for fig in PATTERNS:
                x = s[s["figura"] == fig] if len(s) else s
                for ctx in ("todas", "media50"):
                    y = x if ctx == "todas" or not len(x) else x[x["direction"] * x["sma_bias"] > 0]
                    variants.append({"tf": tf, "figura": fig, "salida": exit_kind, "contexto": ctx, "df": y})
            if len(s):
                pooled.append(s.assign(tf=tf, salida=exit_kind))
        print(tf, "listo", flush=True)

    rows = []
    for v in variants:
        res = I.by_period(v["df"]) if len(v["df"]) else {p: {"n": 0} for p in I.PERIODS}
        r = {"clave": f"{v['figura']}|{v['tf']}|{v['salida']}|{v['contexto']}", "figura": v["figura"], "tf": v["tf"],
             "salida": v["salida"], "contexto": v["contexto"]}
        for p in I.PERIODS:
            for kk in ("n", "r", "t", "bruto", "aciertos"):
                r[f"{p}_{kk}"] = res[p].get(kk)
        y = v["df"]
        r["compras_r"] = round(float(y[y["direction"] > 0]["r"].mean()), 4) if len(y) and (y["direction"] > 0).any() else None
        r["ventas_r"] = round(float(y[y["direction"] < 0]["r"].mean()), 4) if len(y) and (y["direction"] < 0).any() else None
        r["obj_medio_r"] = round(float(y["obj_r"].mean()), 2) if len(y) else None
        r["cumple"] = passes(res, v["tf"])
        rows.append(r)
    tab = pd.DataFrame(rows)
    # diagnóstico por figura (todas las TF, objetivo medido, sin filtro): no se usa para elegir
    allp = pd.concat(pooled) if pooled else pd.DataFrame()
    por_figura = {}
    if len(allp):
        base = allp[allp["salida"] == "medido"]
        for fig, g in base.groupby("figura"):
            pr = I.by_period(g)
            por_figura[fig] = {"n_total": int(len(g)), "aciertos": round(float((g["r"] > 0).mean()), 3),
                               "neto_r_todo": round(float(g["r"].mean()), 4),
                               "bruto_r_todo": round(float((g["r"] + g["cost_r"]).mean()), 4),
                               "objetivo_alcanzado": round(float((g["motivo"] == "objetivo").mean()), 3),
                               "por_periodo": pr}
    n_total = N_PREVIOUS + len(tab)
    winners = tab[tab["cumple"]].assign(score=lambda x: x[["dev_t", "val_t"]].min(axis=1)).sort_values("score", ascending=False)
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "version_codigo": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                text=True).stdout.strip(),
               "variantes": len(tab), "cumplen": len(winners),
               "elegida": winners.iloc[0]["clave"] if len(winners) else "NO_OPERAR",
               "dev_positivas": int((tab.dev_r.fillna(-1) > 0).sum()), "val_positivas": int((tab.val_r.fillna(-1) > 0).sum()),
               "dev_y_val_positivas": int(((tab.dev_r.fillna(-1) > 0) & (tab.val_r.fillna(-1) > 0)).sum()),
               "las_tres_positivas": int(((tab.dev_r.fillna(-1) > 0) & (tab.val_r.fillna(-1) > 0) & (tab.hol_r.fillna(-1) > 0)).sum()),
               "bonferroni": {"variantes_totales_hoy": n_total, "t_necesario": round(float(norm.ppf(1 - 0.05 / n_total)), 2)},
               "por_figura_diagnostico": por_figura,
               "ganadoras": winners.drop(columns=["score"]).to_dict("records")}
    run_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_figuras"
    out = ROOT / "data" / "backtests" / run_id
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    if len(allp):
        allp.drop(columns=[c for c in ("bias_time",) if c in allp]).to_csv(out / "operaciones.csv", index=False)
    (out / "resumen.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (ROOT / "reports" / "figuras.json").write_text(json.dumps({**summary, "tabla": tab.round(4).to_dict("records")},
                                                              indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "por_figura_diagnostico"}, indent=1, ensure_ascii=False, default=str))
    pd.set_option("display.width", 250)
    cols = ["clave", "dev_n", "dev_r", "dev_t", "dev_bruto", "val_n", "val_r", "val_t", "hol_n", "hol_r", "hol_t", "hol_bruto", "cumple"]
    print(tab[cols].to_string(index=False))


if __name__ == "__main__":
    main()
