"""Fase 6m: réplica exacta del EA de John "EA_Nasdaq_FVG_Retest_H1M15_PartialBE" (el más nuevo, 2026-10-21).

Una sola configuración: los parámetros por defecto del EA (los "Pass 195" de su optimización en MT5). Parcial y
break-even vienen apagados por defecto, así que es la misma lógica que su v1. Reglas (leídas del .mq5):
  - En cada vela H1 nueva: busca hacia atrás (hasta 100 velas) el FVG más reciente de cualquier dirección:
    alcista si mínimo(i) > máximo(i+2) y el hueco >= 0,2 x ATR14(H1). Solo lo toma si la tendencia coincide
    (cierre H1 de la última vela frente a EMA 80 de H1). Se guarda una zona por dirección; caduca a las 100 velas H1.
    Si la zona está inactiva y el FVG más reciente es el mismo, vuelve a activarse (así lo hace el código).
  - En cada vela M15 nueva, sin posición abierta: si la última M15 cerrada tocó la zona y cerró fuera a favor
    (alcista: cierre > borde superior), entra a mercado (si la tendencia sigue a favor; si no, descarta la zona).
    Primero mira la zona alcista.
  - Stop: borde lejano de la zona -/+ 0,6 x ATR14(H1). Objetivo 2,5 R. Sin salida por tiempo (aguanta noches:
    las compras pagan swap). Una posición a la vez. Pausa de 2 días tras 5 pérdidas seguidas.
ATR de MT5 = media simple del rango verdadero. Costes: spread 1,12 + 0,5 por lado; swap de compra 6,555 pts/noche.

Ojo: John optimizó estos parámetros en MT5 con datos de 2024-08 a 2026-08. Por eso 2021-23 es la prueba limpia
(datos que la optimización no vio); 2024-08..2026-08 es "dentro de muestra" y se espera que salga mejor.

Uso: python scripts/run_fvg_john.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.data.timeframes import resample  # noqa: E402

P = dict(min_gap_atr=0.2, search_bars=100, ema=80, timeout=100, sl_buf_atr=0.6, rr=2.5, max_losses=5, pause_days=2,
         max_spread_pts=8.0)
IS_PERIOD = ("2024-08-13", "2026-08-24")      # periodo en que John optimizó el EA


def mt5_atr(df: pd.DataFrame, n=14) -> pd.Series:
    pc = df["close"].shift(1)
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.rolling(n).mean()


def run(m1: pd.DataFrame, m: M1Arrays) -> pd.DataFrame:
    h1 = resample(m1, "H1")
    h1 = h1[h1["complete"]].copy()
    h1["atr"] = mt5_atr(h1)
    h1["ema"] = h1["close"].ewm(span=P["ema"], adjust=False).mean()
    m15 = resample(m1, "M15")
    m15 = m15[m15["complete"]]
    H_t = h1.index.to_numpy()                   # apertura de cada H1
    Hh, Hl, Hc = h1["high"].to_numpy(), h1["low"].to_numpy(), h1["close"].to_numpy()
    Ha, He = h1["atr"].to_numpy(), h1["ema"].to_numpy()
    Q_t = m15.index.to_numpy()
    Qh, Ql, Qc = m15["high"].to_numpy(), m15["low"].to_numpy(), m15["close"].to_numpy()
    one_h = np.timedelta64(60, "m")

    zone = {1: None, -1: None}                  # [alto, bajo, edad, activa]
    busy_until = np.datetime64("1970-01-01")
    losses, pause_until = 0, np.datetime64("1970-01-01")
    rows = []
    last_h_scanned = -1

    def trend(k):                                # k = índice de la última H1 cerrada
        if k < 0 or not np.isfinite(He[k]):
            return 0
        return 1 if Hc[k] > He[k] else (-1 if Hc[k] < He[k] else 0)

    for q in range(1, len(Q_t)):
        T = Q_t[q]                               # apertura de la nueva M15 (el EA actúa en su primer tick)
        # última H1 cerrada en T
        k = int(np.searchsorted(H_t, T - one_h, side="right")) - 1
        if k > last_h_scanned:
            # una pasada por cada vela H1 nueva (con huecos de fin de semana puede haber varias)
            for kk in range(last_h_scanned + 1, k + 1):
                if kk < P["search_bars"] + 2 or not np.isfinite(Ha[kk]):
                    continue
                min_gap = P["min_gap_atr"] * Ha[kk]
                for i in range(0, P["search_bars"]):
                    j = kk - i                   # vela 1 = kk, vela 3 = kk-2
                    if Hl[j] > Hh[j - 2] and Hl[j] - Hh[j - 2] >= min_gap:
                        z = zone[1]
                        if trend(kk) == 1 and (z is None or not z[3] or z[0] != Hl[j]):
                            zone[1] = [Hl[j], Hh[j - 2], 0, True]
                        break
                    if Hh[j] < Hl[j - 2] and Hl[j - 2] - Hh[j] >= min_gap:
                        z = zone[-1]
                        if trend(kk) == -1 and (z is None or not z[3] or z[1] != Hh[j]):
                            zone[-1] = [Hl[j - 2], Hh[j], 0, True]
                        break
                for d in (1, -1):
                    z = zone[d]
                    if z is not None and z[3]:
                        z[2] += 1
                        if z[2] > P["timeout"]:
                            z[3] = False
            last_h_scanned = k
        if T < busy_until or T < pause_until:
            continue
        p = q - 1                                # "vela 1" del EA: la última M15 cerrada (también tras una pausa)
        for d in (1, -1):
            z = zone[d]
            if z is None or not z[3]:
                continue
            hi, lo = z[0], z[1]
            touched = Qh[p] >= lo and Ql[p] <= hi
            rej = touched and ((Qc[p] > hi) if d > 0 else (Qc[p] < lo))
            if not rej:
                continue
            if trend(k) != d:
                z[3] = False
                break
            f = I.market_entry(m, pd.Timestamp(T), d)
            if f is None:
                break
            i0, px = f
            if m.spread[i0] > P["max_spread_pts"]:
                break
            stop = (lo - P["sl_buf_atr"] * Ha[k]) if d > 0 else (hi + P["sl_buf_atr"] * Ha[k])
            risk = (px - stop) * d
            if risk <= 0:
                break
            res = I.trade(m, i0, d, px, stop, px + d * P["rr"] * risk, I.end_index(m, i0, 60 * 24 * 60), False,
                          use_flat=False)
            if res is None:
                break
            swap = I.nights_swap(pd.Timestamp(m.time[i0]), pd.Timestamp(m.time[res[2]])) if d > 0 else 0.0
            r = I.row(pd.Timestamp(T), d, res, i0, m, swap=swap)
            r["cost_r"] = (I.SPREAD_PTS + 2 * I.SLIP + swap) / res[1]
            r["riesgo_pts"] = risk
            rows.append(r)
            z[3] = False
            busy_until = np.datetime64(r["exit_time"])
            losses = losses + 1 if r["r"] < 0 else 0
            if losses >= P["max_losses"]:
                pause_until = busy_until + np.timedelta64(P["pause_days"], "D")
                losses = 0
            break
    return pd.DataFrame(rows)


def main() -> None:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    m.flat_mask = np.zeros(len(m1), bool)
    df = run(m1, m)
    res = I.by_period(df)
    a, b = IS_PERIOD
    ins = df[(df["detected_time"] >= a) & (df["detected_time"] <= b)]
    oos = df[df["detected_time"] < a]
    after = df[df["detected_time"] > b]
    ny = df["detected_time"].dt.tz_localize("UTC").dt.tz_convert(I.NY)
    summary = {
        "fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "parametros": P,
        "periodos": {p: {k: res[p].get(k) for k in ("n", "r", "t", "bruto", "aciertos")} for p in I.PERIODS},
        "fuera_de_su_optimizacion_2021_2024-08": I.cluster_stats(oos),
        "dentro_de_su_optimizacion_2024-08_2026-08": I.cluster_stats(ins),
        "despues_2026-08": I.cluster_stats(after),
        "por_año": {int(y): {"n": int(g.size), "r": round(float(g.mean()), 3), "suma_R": round(float(g.sum()), 1)}
                    for y, g in df.groupby(ny.dt.year)["r"]},
        "compras_ventas": {("compra" if d > 0 else "venta"): {"n": int(g.size), "r": round(float(g.mean()), 3)}
                           for d, g in df.groupby("direction")["r"]},
        "salidas": df["motivo"].value_counts().to_dict(),
        "horas_medias": round(float(((df["exit_time"] - df["entry_time"]).dt.total_seconds() / 3600).mean()), 1),
        "swap_medio_R": round(float((df["cost_r"] - (I.SPREAD_PTS + 2 * I.SLIP) / df["riesgo_pts"]).mean()), 3),
        "riesgo_pts_mediana": round(float(df["riesgo_pts"].median()), 1),
    }
    out = ROOT / "data" / "backtests" / f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_fvg_john"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "operaciones.csv", index=False)
    (ROOT / "reports" / "fvg_john.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str),
                                                   encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
