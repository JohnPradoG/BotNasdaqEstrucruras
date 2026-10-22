"""Fase 6p: cruce de EMAs en varias temporalidades (pedido por John, 2026-10-21). Rejilla y regla guardadas en git
ANTES de ejecutar.

Reglas (las clásicas, sin adornos):
  - Señal al CIERRE de la vela en que la EMA rápida cruza la lenta (rápida > lenta ahora y <= en la vela anterior:
    compra; al revés: venta). Solo velas cerradas. Entrada a mercado en el primer minuto después del cierre.
  - Stop 1,5 x ATR14 de esa temporalidad (hace falta un stop para medir en R y para el riesgo del bot).
  - Salida "cruce": en el cruce contrario (al cierre de esa vela) o en el stop.
    Salida "2R": objetivo 2 R, stop o cruce contrario, lo que llegue antes.
  - Una posición a la vez por variante; no se entra si el spread supera 8 puntos.
  - Puede quedarse noches abiertas: las compras pagan swap (6,555 pts/noche, x3 viernes).
  - D1 = día de trading de NY (cierre 17:00 NY).
Rejilla (90): temporalidad {M5, M15, H1, H4, D1} x EMAs {9/21, 20/50, 50/200} x salida {cruce, 2R}
x dirección {ambas, solo compras, solo ventas}.
Periodos: dev 2021-11..2023-12, val 2024, hol 2025-26 (ya visto en otras pruebas: solo diagnóstico).
Aprobado: dev n >= 100, t >= 2 y val > 0 con t >= 1. Con 90 pruebas, Bonferroni pide t ~ 3,3.

Uso: python scripts/run_ema_cross.py
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

import run_fvg_john as F  # noqa: E402
import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.data.timeframes import resample  # noqa: E402

TFS = ("M5", "M15", "H1", "H4", "D1")
PAIRS = ((9, 21), (20, 50), (50, 200))
EXITS = ("cruce", "2R")
DIRS = {"ambas": (1, -1), "compras": (1,), "ventas": (-1,)}
STOP_ATR, RR, MAX_SPREAD = 1.5, 2.0, 8.0


def bars(m1: pd.DataFrame, tf: str) -> pd.DataFrame:
    b = I.daily_bars(m1) if tf == "D1" else resample(m1, tf)
    b = b[b["complete"]].copy()
    b["atr"] = F.mt5_atr(b)
    return b


def crosses(b: pd.DataFrame, fast: int, slow: int) -> pd.DataFrame:
    ef = b["close"].ewm(span=fast, adjust=False).mean()
    es = b["close"].ewm(span=slow, adjust=False).mean()
    side = np.sign(ef - es)
    prev = side.shift(1)
    sig = np.where((side > 0) & (prev <= 0), 1, np.where((side < 0) & (prev >= 0), -1, 0))
    ok = np.arange(len(b)) >= 3 * slow                 # deja calentar la EMA lenta
    out = pd.DataFrame({"t": b["close_time"].to_numpy(), "d": sig, "atr": b["atr"].to_numpy()})
    return out[(out["d"] != 0) & ok & np.isfinite(out["atr"])].reset_index(drop=True)


def run(m: M1Arrays, cx: pd.DataFrame, exit_kind: str, dirs: tuple) -> pd.DataFrame:
    rows, busy = [], np.datetime64("1970-01-01")
    T, D, A = cx["t"].to_numpy("datetime64[ns]"), cx["d"].to_numpy(), cx["atr"].to_numpy()
    n = len(m.time)
    for j in range(len(cx)):
        d = int(D[j])
        if d not in dirs or T[j] < busy:
            continue
        i0 = int(np.searchsorted(m.time, T[j]))
        if i0 >= n or m.spread[i0] > MAX_SPREAD:
            continue
        px = (m.open[i0] + m.spread[i0] + I.SLIP) if d > 0 else (m.open[i0] - I.SLIP)
        stop = px - d * STOP_ATR * A[j]
        tgt = px + d * RR * STOP_ATR * A[j] if exit_kind == "2R" else None
        # salida por cruce contrario: el siguiente cruce (siempre es de signo contrario)
        i_end = int(np.searchsorted(m.time, T[j + 1])) if j + 1 < len(cx) else n
        res = I.trade(m, i0, d, px, stop, tgt, i_end, False, use_flat=False)
        if res is None:
            continue
        swap = I.nights_swap(pd.Timestamp(m.time[i0]), pd.Timestamp(m.time[res[2]])) if d > 0 else 0.0
        r = I.row(pd.Timestamp(T[j]), d, res, i0, m, swap=swap)
        r["cost_r"] = (I.SPREAD_PTS + 2 * I.SLIP + swap) / res[1]
        rows.append(r)
        busy = np.datetime64(r["exit_time"])
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    m.flat_mask = np.zeros(len(m1), bool)
    rows, streams = [], {}
    for tf in TFS:
        b = bars(m1, tf)
        for (fa, sl), ex, dn in itertools.product(PAIRS, EXITS, DIRS):
            df = run(m, crosses(b, fa, sl), ex, DIRS[dn])
            key = f"{tf}|{fa}/{sl}|{ex}|{dn}"
            per = I.by_period(df) if len(df) else {}
            dv, va = per.get("dev", {}), per.get("val", {})
            ok = bool(dv.get("n", 0) >= 100 and (dv.get("t") or 0) >= 2 and (va.get("r") or -1) > 0
                      and (va.get("t") or 0) >= 1)
            rows.append({"clave": key, "tf": tf, **{f"{p}_{k}": per.get(p, {}).get(k) for p in ("dev", "val", "hol")
                                                     for k in ("n", "r", "t", "bruto")}, "aprobada": ok})
            streams[key] = df
            print(rows[-1], flush=True)
    tab = pd.DataFrame(rows)
    # resumen por temporalidad: media de las 18 variantes de cada una (neto y bruto, todo el periodo)
    por_tf = {}
    for tf in TFS:
        allr = pd.concat([s for k, s in streams.items() if k.startswith(tf + "|") and len(s)])
        st = I.cluster_stats(allr)
        por_tf[tf] = {"ops_total": st["n"], "neto_r": st["r"], "bruto_r": round(float((allr["r"] + allr["cost_r"]).mean()), 4),
                      "mejor_dev": tab[tab.tf == tf].sort_values("dev_t", ascending=False).iloc[0]["clave"]}
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variantes": len(tab),
               "aprobadas": tab.loc[tab["aprobada"], "clave"].tolist(),
               "positivas_dev_y_val": int(((tab["dev_r"] > 0) & (tab["val_r"] > 0)).sum()),
               "bonferroni_t": round(float(norm.ppf(1 - 0.05 / len(tab))), 2), "por_temporalidad": por_tf}
    out = ROOT / "reports" / "ema_cross"
    out.mkdir(parents=True, exist_ok=True)
    (out / "ema_cross.json").write_text(json.dumps({**summary, "tabla": rows}, indent=1, ensure_ascii=False, default=str),
                                        encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    cols = ["clave", "dev_n", "dev_r", "dev_t", "val_r", "val_t", "hol_r", "hol_t"]
    print(tab.sort_values("dev_t", ascending=False)[cols].head(15).to_string(index=False))


if __name__ == "__main__":
    main()
