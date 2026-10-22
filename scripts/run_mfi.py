"""Fase 6q: Money Flow Index (MFI) en varias temporalidades (pedido por John, 2026-10-21: "una con money no sé qué").
Rejilla y regla guardadas en git ANTES de ejecutar.

MFI(14) = RSI calculado con el flujo de dinero (precio típico x volumen). En el CFD USTECm no hay volumen real:
se usa el volumen de ticks, que es lo que da MT5 (igual que el indicador MFI de MT5 en este símbolo).
Reglas (las clásicas):
  - Compra cuando el MFI sale de sobreventa (cruza hacia arriba el nivel bajo) al cierre de la vela; venta cuando
    sale de sobrecompra (cruza hacia abajo el nivel alto). Solo velas cerradas; entrada a mercado al minuto siguiente.
  - Stop 1,5 x ATR14 de esa temporalidad.
  - Salida "2R": objetivo 2 R o stop. Salida "mfi50": cuando el MFI cruza 50 (al cierre de esa vela) o stop.
  - Filtro "tendencia": solo a favor de la EMA 200 de esa temporalidad (cierre por encima: solo compras).
  - Una posición a la vez; no se entra con spread > 8; las compras pagan swap; tope de 10 días por operación.
Rejilla (32): temporalidad {M5, M15, H1, H4} x niveles {20/80, 10/90} x salida {2R, mfi50} x filtro {no, tendencia}.
Periodos: dev 2021-11..2023-12, val 2024, hol 2025-26 (solo diagnóstico).
Aprobado: dev n >= 100, t >= 2 y val > 0 con t >= 1. Con 32 pruebas, Bonferroni pide t ~ 2,95.

Uso: python scripts/run_mfi.py
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

TFS = ("M5", "M15", "H1", "H4")
LEVELS = ((20, 80), (10, 90))
EXITS = ("2R", "mfi50")
FILTERS = ("no", "tendencia")
N, STOP_ATR, RR, MAX_SPREAD, MAX_DAYS = 14, 1.5, 2.0, 8.0, 10


def mfi(b: pd.DataFrame, n: int = N) -> pd.Series:
    tp = (b["high"] + b["low"] + b["close"]) / 3
    flow = tp * b["tickvol"]
    up = flow.where(tp > tp.shift(1), 0.0).rolling(n).sum()
    dn = flow.where(tp < tp.shift(1), 0.0).rolling(n).sum()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def signals(b: pd.DataFrame, lo: int, hi: int, flt: str) -> pd.DataFrame:
    x = mfi(b).to_numpy()
    prev = np.r_[np.nan, x[:-1]]
    d = np.where((prev < lo) & (x >= lo), 1, np.where((prev > hi) & (x <= hi), -1, 0))
    if flt == "tendencia":
        ema = b["close"].ewm(span=200, adjust=False).mean().to_numpy()
        tr = np.sign(b["close"].to_numpy() - ema)
        d = np.where(d == tr, d, 0)
        d[: 600] = 0                                      # calentar la EMA 200
    # salida mfi50: primera vela posterior en que el MFI cruza 50 en contra de la posición
    ct = b["close_time"].to_numpy("datetime64[ns]")
    above = x >= 50
    out = []
    for k in np.flatnonzero(d != 0):
        if not np.isfinite(b["atr"].iloc[k]):
            continue
        j = k + 1
        while j < len(x) and not ((d[k] > 0 and above[j]) or (d[k] < 0 and not above[j] and np.isfinite(x[j]))):
            j += 1
        out.append((ct[k], int(d[k]), float(b["atr"].iloc[k]), ct[j] if j < len(x) else None))
    return pd.DataFrame(out, columns=["t", "d", "atr", "t50"])


def run(m: M1Arrays, sg: pd.DataFrame, exit_kind: str) -> pd.DataFrame:
    rows, busy, n = [], np.datetime64("1970-01-01"), len(m.time)
    for t, d, atr, t50 in sg.itertuples(index=False):
        t = np.datetime64(t, "ns")
        if t < busy:
            continue
        i0 = int(np.searchsorted(m.time, t))
        if i0 >= n or m.spread[i0] > MAX_SPREAD:
            continue
        px = (m.open[i0] + m.spread[i0] + I.SLIP) if d > 0 else (m.open[i0] - I.SLIP)
        stop = px - d * STOP_ATR * atr
        cap = I.end_index(m, i0, MAX_DAYS * 24 * 60)
        if exit_kind == "2R":
            tgt, i_end = px + d * RR * STOP_ATR * atr, cap
        else:
            tgt = None
            i_end = min(cap, int(np.searchsorted(m.time, np.datetime64(t50, "ns")))) if t50 is not None else cap
        res = I.trade(m, i0, d, px, stop, tgt, i_end, False, use_flat=False)
        if res is None:
            continue
        swap = I.nights_swap(pd.Timestamp(m.time[i0]), pd.Timestamp(m.time[res[2]])) if d > 0 else 0.0
        r = I.row(pd.Timestamp(t), d, res, i0, m, swap=swap)
        r["cost_r"] = (I.SPREAD_PTS + 2 * I.SLIP + swap) / res[1]
        rows.append(r)
        busy = np.datetime64(r["exit_time"])
    return pd.DataFrame(rows)


def main() -> None:
    spec = SymbolSpec.from_settings(load_settings())
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    m.flat_mask = np.zeros(len(m1), bool)
    rows = []
    for tf in TFS:
        b = E.bars(m1, tf)
        for (lo, hi), ex, flt in itertools.product(LEVELS, EXITS, FILTERS):
            df = run(m, signals(b, lo, hi, flt), ex)
            per = I.by_period(df) if len(df) else {}
            dv, va = per.get("dev", {}), per.get("val", {})
            ok = bool(dv.get("n", 0) >= 100 and (dv.get("t") or 0) >= 2 and (va.get("r") or -1) > 0
                      and (va.get("t") or 0) >= 1)
            rows.append({"clave": f"{tf}|{lo}/{hi}|{ex}|{flt}", "tf": tf,
                         **{f"{p}_{k}": per.get(p, {}).get(k) for p in ("dev", "val", "hol") for k in ("n", "r", "t", "bruto")},
                         "aprobada": ok})
            print(rows[-1], flush=True)
    tab = pd.DataFrame(rows)
    por_tf = tab.groupby("tf")[["dev_r", "val_r", "hol_r", "dev_bruto", "val_bruto", "hol_bruto"]].mean().round(3)
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variantes": len(tab),
               "aprobadas": tab.loc[tab["aprobada"], "clave"].tolist(),
               "positivas_dev_y_val": int(((tab["dev_r"] > 0) & (tab["val_r"] > 0)).sum()),
               "bonferroni_t": round(float(norm.ppf(1 - 0.05 / len(tab))), 2),
               "por_temporalidad_media": por_tf.to_dict(orient="index")}
    out = ROOT / "reports" / "mfi"
    out.mkdir(parents=True, exist_ok=True)
    (out / "mfi.json").write_text(json.dumps({**summary, "tabla": rows}, indent=1, ensure_ascii=False, default=str),
                                  encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    cols = ["clave", "dev_n", "dev_r", "dev_t", "val_r", "val_t", "hol_r", "hol_t"]
    print(tab.sort_values("dev_t", ascending=False)[cols].head(12).to_string(index=False))


if __name__ == "__main__":
    main()
