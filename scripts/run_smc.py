"""Fase 6r: Smart Money (SMC) completo, como se opera habitualmente (pedido por John, 2026-10-21: "revísela de todas
las maneras"). Rejilla y regla guardadas en git ANTES de ejecutar.

Flujo de una compra (las ventas, al revés):
  1. Sesgo de la temporalidad mayor (H4 o H1): estructura alcista desde que una vela CIERRA por encima del último
     máximo de oscilación confirmado (fractal 2+2); bajista al cerrar por debajo del último mínimo. Variante "ninguno":
     sin sesgo.
  2. Barrido de liquidez en la temporalidad menor (M15 o M5): una vela perfora el último mínimo de oscilación
     confirmado (fractal 3+3). Variante "mecha": además cierra otra vez por encima del nivel. Cada nivel se barre una vez.
  3. CHOCH: en las 24 velas siguientes, una vela CIERRA por encima del último máximo confirmado anterior al barrido.
     La señal se conoce al cierre de esa vela.
  4. Entrada (3 variantes):
       - "OB": orden limitada en el máximo de la última vela bajista entre 5 velas antes del mínimo del barrido y el
         mínimo (order block);
       - "FVG": orden limitada en el borde superior del último hueco alcista (mín(i) > máx(i-2)) entre el mínimo y el
         CHOCH;
       - "mercado": a mercado al cierre de la vela del CHOCH.
     La limitada vale 24 velas de la temporalidad menor; se cancela si antes toca el objetivo.
  5. Stop: mínimo del barrido - 0,1 x ATR14 (temporalidad menor). Objetivo 2 R o 3 R. Tope 3 días. Riesgo mínimo
     0,3 x ATR (si no, se descarta). Una posición a la vez; sin entradas con spread > 8; las compras pagan swap.
Rejilla (144): mayor/menor {H4/M15, H1/M15, H1/M5} x barrido {cualquiera, mecha} x entrada {OB, FVG, mercado}
x objetivo {2R, 3R} x sesión del CHOCH {todas, NY 9:30-16:00} x sesgo {estructura, ninguno}.
Regla: se elige SOLO con 2021-11..2023-12 (mayor t con >= 100 operaciones) y se mira 2024-01..2026-10 sin tocar.
Aprobada si 2021-23 t >= 2 y 2024-26 > 0 con t >= 1. Con 144 pruebas, Bonferroni pide t ~ 3,4.

Uso: python scripts/run_smc.py
"""
from __future__ import annotations

import itertools
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

import run_ema_cross as E  # noqa: E402
import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.data.timeframes import TF_MINUTES  # noqa: E402
from nsmb.market_structure.pivots import fractal_pivots  # noqa: E402

COMBOS = (("H4", "M15"), ("H1", "M15"), ("H1", "M5"))
SWEEPS = ("cualquiera", "mecha")
ENTRIES = ("OB", "FVG", "mercado")
TARGETS = (2.0, 3.0)
SESSIONS = ("todas", "NY")
BIASES = ("estructura", "ninguno")
W, VALID, OB_BACK, BUF_ATR, MIN_RISK_ATR, MAX_DAYS, MAX_SPREAD = 24, 24, 5, 0.1, 0.3, 3, 8.0
DEV = ("2021-11-01", "2024-01-01")
TEST = ("2024-01-01", "2026-12-31")


def htf_bias(b: pd.DataFrame) -> pd.DataFrame:
    """Sesgo por estructura (BOS al cierre) conocido al cierre de cada vela mayor."""
    h, l, c = b["high"].to_numpy(), b["low"].to_numpy(), b["close"].to_numpy()
    piv = fractal_pivots(h, l, 2, 2)
    by_conf: dict[int, list] = {}
    for p in piv:
        by_conf.setdefault(p.confirm_idx, []).append(p)
    sh = sl = None
    st, out = 0, np.zeros(len(b))
    for k in range(len(b)):
        for p in by_conf.get(k, []):
            if p.kind == "H":
                sh = p.price
            else:
                sl = p.price
        if sh is not None and c[k] > sh:
            st = 1
        elif sl is not None and c[k] < sl:
            st = -1
        out[k] = st
    return pd.DataFrame({"close_time": b["close_time"].to_numpy("datetime64[ns]"), "bias": out})


def setups(b: pd.DataFrame, sweep: str) -> pd.DataFrame:
    """Barrido + CHOCH en la temporalidad menor. Una fila por CHOCH con zonas OB/FVG y stop."""
    o, h, l, c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
    atr = b["atr"].to_numpy()
    ct = b["close_time"].to_numpy("datetime64[ns]")
    piv = fractal_pivots(h, l, 3, 3)
    by_conf: dict[int, list] = {}
    for p in piv:
        by_conf.setdefault(p.confirm_idx, []).append(p)
    last = {"H": None, "L": None}          # último pivote confirmado de cada tipo (sin barrer)
    lastH_any = {"H": None, "L": None}     # para el nivel del CHOCH (último confirmado, barrido o no)
    pend = {1: None, -1: None}             # [k_barrido, nivel_choch]
    rows = []
    for k in range(len(b)):
        for p in by_conf.get(k - 1, []):   # confirmado al cierre de k-1 => usable en la vela k
            last[p.kind] = p
            lastH_any[p.kind] = p
        if not np.isfinite(atr[k]):
            continue
        # barridos
        pl, ph = last["L"], last["H"]
        if pl is not None and l[k] < pl.price and (sweep == "cualquiera" or c[k] > pl.price):
            if lastH_any["H"] is not None and lastH_any["H"].idx < k:
                pend[1] = [k, lastH_any["H"].price]
            last["L"] = None
        if ph is not None and h[k] > ph.price and (sweep == "cualquiera" or c[k] < ph.price):
            if lastH_any["L"] is not None and lastH_any["L"].idx < k:
                pend[-1] = [k, lastH_any["L"].price]
            last["H"] = None
        # CHOCH
        for d in (1, -1):
            pd_ = pend[d]
            if pd_ is None:
                continue
            k0, lvl = pd_
            if k - k0 > W:
                pend[d] = None
                continue
            if k == k0 or not ((d > 0 and c[k] > lvl) or (d < 0 and c[k] < lvl)):
                continue
            seg = slice(k0, k + 1)
            a = k0 + int(np.argmin(l[seg]) if d > 0 else np.argmax(h[seg]))
            ext = l[a] if d > 0 else h[a]
            stop = ext - d * BUF_ATR * atr[k]
            ob = None
            for i in range(a, max(a - OB_BACK, 0) - 1, -1):
                if (d > 0 and c[i] < o[i]) or (d < 0 and c[i] > o[i]):
                    ob = h[i] if d > 0 else l[i]
                    break
            fvg = None
            for i in range(k, a + 1, -1):
                if d > 0 and l[i] > h[i - 2]:
                    fvg = l[i]
                    break
                if d < 0 and h[i] < l[i - 2]:
                    fvg = h[i]
                    break
            rows.append({"t": ct[k], "d": d, "atr": atr[k], "stop": stop, "OB": ob, "FVG": fvg, "close": c[k]})
            pend[d] = None
    df = pd.DataFrame(rows)
    ny = pd.DatetimeIndex(df["t"]).tz_localize("UTC").tz_convert(I.NY)
    mins = ny.hour * 60 + ny.minute
    df["NY"] = (mins >= 570) & (mins <= 960)
    return df


def simulate(m: M1Arrays, s: pd.DataFrame, entry: str, rr: float, tf_min: int) -> pd.DataFrame:
    rows, busy, n = [], np.datetime64("1970-01-01"), len(m.time)
    for r in s.itertuples(index=False):
        t = np.datetime64(r.t, "ns")
        if t < busy:
            continue
        d = int(r.d)
        if entry == "mercado":
            i0 = int(np.searchsorted(m.time, t))
            if i0 >= n or m.spread[i0] > MAX_SPREAD:
                continue
            px = (m.open[i0] + m.spread[i0] + I.SLIP) if d > 0 else (m.open[i0] - I.SLIP)
            limit = False
        else:
            lvl = getattr(r, entry)
            if lvl is None or not np.isfinite(lvl) or (lvl - r.stop) * d <= 0 or (r.close - lvl) * d < 0:
                continue
            tgt0 = lvl + d * rr * (lvl - r.stop) * d
            f = I.limit_fill(m, pd.Timestamp(t), d, float(lvl), VALID * tf_min)
            if f is None:
                continue
            i0, px = f
            j0 = int(np.searchsorted(m.time, t))
            if i0 > j0:                                      # ¿tocó el objetivo antes de llenarse? => cancelada
                seg_h, seg_l = m.high[j0:i0], m.low[j0:i0] + m.spread[j0:i0]
                if (d > 0 and (seg_h >= tgt0).any()) or (d < 0 and (seg_l <= tgt0).any()):
                    continue
            limit = True
        risk = (px - r.stop) * d
        if risk < MIN_RISK_ATR * r.atr:
            continue
        tgt = px + d * rr * risk
        res = I.trade(m, i0, d, px, r.stop, tgt, I.end_index(m, i0, MAX_DAYS * 24 * 60), limit, use_flat=False)
        if res is None:
            continue
        swap = I.nights_swap(pd.Timestamp(m.time[i0]), pd.Timestamp(m.time[res[2]])) if d > 0 else 0.0
        row = I.row(pd.Timestamp(t), d, res, i0, m, swap=swap)
        row["cost_r"] = ((I.SPREAD_PTS if not limit else 0.0) + 2 * I.SLIP + swap) / res[1]
        rows.append(row)
        busy = np.datetime64(row["exit_time"])
    return pd.DataFrame(rows)


def stats(df, a, b):
    if df.empty:
        return {"n": 0, "r": None, "t": None}
    return I.cluster_stats(df[(df["detected_time"] >= a) & (df["detected_time"] < b)])


def main() -> None:
    spec = SymbolSpec.from_settings(load_settings())
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    m.flat_mask = np.zeros(len(m1), bool)
    bars = {tf: E.bars(m1, tf) for tf in ("H4", "H1", "M15", "M5")}
    rows = []
    for (hi, lo), sw in itertools.product(COMBOS, SWEEPS):
        s = setups(bars[lo], sw)
        bias = htf_bias(bars[hi])
        s = pd.merge_asof(s.sort_values("t"), bias.rename(columns={"close_time": "t"}), on="t", direction="backward")
        print(hi, lo, sw, "setups", len(s), flush=True)
        for en, rr, ses, bi in itertools.product(ENTRIES, TARGETS, SESSIONS, BIASES):
            x = s
            if ses == "NY":
                x = x[x["NY"]]
            if bi == "estructura":
                x = x[x["bias"] == x["d"]]
            df = simulate(m, x, en, rr, TF_MINUTES[lo])
            dv, ts = stats(df, *DEV), stats(df, *TEST)
            per = I.by_period(df) if len(df) else {}
            rows.append({"clave": f"{hi}/{lo}|{sw}|{en}|{rr:g}R|{ses}|{bi}", "dev_n": dv["n"], "dev_r": dv.get("r"),
                         "dev_t": dv.get("t"), "test_n": ts["n"], "test_r": ts.get("r"), "test_t": ts.get("t"),
                         "val2024_r": per.get("val", {}).get("r"), "hol2025_26_r": per.get("hol", {}).get("r"),
                         "dev_bruto": per.get("dev", {}).get("bruto")})
            print(rows[-1], flush=True)
    tab = pd.DataFrame(rows)
    ok = tab[tab["dev_n"] >= 100]
    best = ok.loc[ok["dev_t"].idxmax()].to_dict()
    best["aprobada"] = bool(best["dev_t"] >= 2 and (best["test_r"] or -1) > 0 and (best["test_t"] or 0) >= 1)
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variantes": len(tab), "elegida": best,
               "positivas_en_dev": int((tab["dev_r"] > 0).sum()),
               "positivas_en_ambos": int(((tab["dev_r"] > 0) & (tab["test_r"] > 0)).sum()),
               "bonferroni_t": round(float(norm.ppf(1 - 0.05 / len(tab))), 2)}
    for col in ("clave",):
        parts = tab[col].str.split("|", expand=True)
        for i, name in enumerate(("combo", "barrido", "entrada", "objetivo", "sesion", "sesgo")):
            summary[f"media_por_{name}"] = tab.groupby(parts[i])[["dev_r", "test_r"]].mean().round(3).to_dict(orient="index")
    out = ROOT / "reports" / "smc"
    out.mkdir(parents=True, exist_ok=True)
    (out / "smc.json").write_text(json.dumps({**summary, "tabla": rows}, indent=1, ensure_ascii=False, default=str),
                                  encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    print(tab.sort_values("dev_t", ascending=False).head(15).to_string(index=False))


if __name__ == "__main__":
    main()
