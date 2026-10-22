"""Fase 6i: estrategias publicadas en la web, probadas con nuestros datos y costes (2026-10-20)

Pedido por John: buscar en la web y en GitHub estrategias de Nasdaq que digan ser rentables. Las que tienen reglas
claras y alguna evidencia pública se reprograman aquí y se pasan por el mismo examen. Rejilla y regla guardadas en
git ANTES de ejecutar.

W1 "Noise area" (Zarattini, Aziz y Barbon 2024, publicado para SPY). Banda del día = apertura 9:30 (o cierre previo
   si queda más lejos) +- media de |movimiento desde la apertura hasta esa hora| de los 14 días anteriores.
   Revisión cada 30 min de 10:00 a 15:30 NY: cierre por encima de la banda -> compra; por debajo -> venta.
   Salida en una revisión si el precio vuelve a cruzar el stop: {banda, máx(banda, VWAP) como en el artículo}.
   Cambio de dirección permitido. Cierre forzado 15:57. Filtro {ambas, a favor de la media 50 D1}. 4 variantes.
   Además, revisión cada 15 min (mismas reglas) -> 8 variantes.
W2 Momentum intradía (Gao, Han, Li y Zhou 2018, JFE): el rendimiento del cierre previo a las 10:00 predice el de la
   última media hora. Entrada 15:30, salida 15:57, en la dirección del primer tramo. Medido desde {cierre previo,
   apertura 9:30}; filtro {todos, solo si |primer tramo| > mediana de los 60 días previos}. 4 variantes.
W3 ORB de 5 min (Zarattini y Aziz 2023, publicado para QQQ): dirección de la primera vela de 5 min (9:30-9:35);
   entrada 9:35; stop en el extremo opuesto de esa vela; objetivo 10 R o cierre 15:57; sin operar si la vela es
   casi plana (|cierre - apertura| < 5 % de su rango). Filtro {ambas, media50}. 2 variantes.
Total 14. Unidad R: W3 riesgo inicial; W1 y W2 el ancho de la banda / mediana del movimiento, para que el t
sea comparable. Coste: spread 1,12 + 0,5 por lado. Sin swap (todo intradía). Selección igual que siempre
(desarrollo t >= 2 y validación t >= 1, ambos positivos); Bonferroni con todo lo probado hoy.

Uso: python scripts/run_web.py
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

import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.indicators.core import add_indicators  # noqa: E402
from nsmb.market_structure.engine import StructureEngine, StructureParams  # noqa: E402

N_PREVIOUS = 265 + 96 + 120 + 84
COST = I.SPREAD_PTS + 2 * I.SLIP


def rth_frame(m1: pd.DataFrame) -> pd.DataFrame:
    ny = m1.index.tz_localize("UTC").tz_convert(I.NY)
    df = m1.assign(mins=np.asarray(ny.hour * 60 + ny.minute), date=np.asarray(ny.normalize().tz_localize(None)),
                   pos=np.arange(len(m1)))
    return df[(df["mins"] >= 570) & (df["mins"] < 957)]


def fill(m: M1Arrays, pos: int, d: int, opening: bool) -> float:
    """Precio de ejecución a mercado en la apertura de la vela M1 pos (compra al ask)."""
    buy = (d > 0) == opening
    return m.open[pos] + m.spread[pos] + I.SLIP if buy else m.open[pos] - I.SLIP


def w1_noise(rth: pd.DataFrame, m: M1Arrays, bias: pd.DataFrame, mult: float = 1.0, steps=(30, 15),
             stops=("banda", "banda_vwap"), dirs=("ambas", "media50"), hard_stop: float | None = None) -> list[dict]:
    """hard_stop: stop de protección en el bróker a hard_stop x media banda desde la entrada (None = sin él)."""
    days = {k: g for k, g in rth.groupby("date")}
    dates = sorted(days)
    # movimiento absoluto desde la apertura, por minuto del día
    mv, opens, closes = {}, {}, {}
    for dt in dates:
        g = days[dt]
        if g["mins"].iloc[0] != 570 or len(g) < 350:
            continue
        o = g["open"].iloc[0]
        opens[dt], closes[dt] = o, g["close"].iloc[-1]
        mv[dt] = pd.Series(np.abs(g["close"].to_numpy() / o - 1), index=g["mins"].to_numpy())
    good = [d for d in dates if d in mv]
    t0 = pd.DataFrame({"date": good, "detected_time": [days[x].index[0] for x in good]})
    sb_day = I.attach_bias(t0, bias).set_index("date")["sma_bias"].fillna(0).to_dict()
    out = []
    for step in steps:
        checks = list(range(600, 931, step))
        for stop_kind in stops:
            for dir_f in dirs:
                rows = []
                for j in range(14, len(good)):
                    dt, prev = good[j], good[j - 1]
                    hist = pd.concat([mv[x] for x in good[j - 14:j]], axis=1).mean(axis=1)
                    g = days[dt].set_index("mins")
                    o = opens[dt]
                    up_ref, lo_ref = max(o, closes[prev]), min(o, closes[prev])
                    tp = (g["high"] + g["low"] + g["close"]) / 3
                    vol = g["tickvol"].clip(lower=1)
                    vwap = (tp * vol).cumsum() / vol.cumsum()
                    sb = sb_day.get(dt, 0.0)
                    pos, entry_px, entry_pos, unit, t_sig = 0, 0.0, 0, 0.0, None

                    def close_pos(at_min):
                        nonlocal pos
                        p = int(g["pos"].get(at_min, g["pos"].iloc[-1]))
                        px = fill(m, p, pos, False)
                        rows.append({"detected_time": t_sig, "direction": pos, "r": ((px - entry_px) * pos) / unit,
                                     "cost_r": COST / unit, "entry_time": pd.Timestamp(m.time[entry_pos]),
                                     "exit_time": pd.Timestamp(m.time[p])})
                        pos = 0

                    def hit_hard(p_to):
                        """Si el stop de protección se tocó entre la entrada y la vela p_to (excluida), cierra ahí."""
                        nonlocal pos
                        if hard_stop is None or pos == 0 or p_to <= entry_pos:
                            return
                        stp = entry_px - pos * hard_stop * unit
                        sl = slice(entry_pos, p_to)
                        hit = m.low[sl] <= stp if pos > 0 else m.high[sl] + m.spread[sl] >= stp
                        if hit.any():
                            k0 = entry_pos + int(np.argmax(hit))
                            px = (min(m.open[k0], stp) - I.SLIP) if pos > 0 else (max(m.open[k0] + m.spread[k0], stp) + I.SLIP)
                            if k0 == entry_pos:
                                px = stp - I.SLIP * pos
                            rows.append({"detected_time": t_sig, "direction": pos, "r": ((px - entry_px) * pos) / unit,
                                         "cost_r": COST / unit, "entry_time": pd.Timestamp(m.time[entry_pos]),
                                         "exit_time": pd.Timestamp(m.time[k0])})
                            pos = 0

                    for c in checks:
                        k = c - 1  # vela que cierra a la hora c
                        if k not in g.index or c not in hist.index or c not in g.index:
                            continue
                        sig = hist.loc[c] * mult
                        hit_hard(int(g.at[c, "pos"]))
                        U, L = up_ref * (1 + sig), lo_ref * (1 - sig)
                        px_c = g.at[k, "close"]
                        if pos > 0:
                            st = max(U, vwap.at[k]) if stop_kind == "banda_vwap" else U
                            if px_c < st:
                                close_pos(c)
                        elif pos < 0:
                            st = min(L, vwap.at[k]) if stop_kind == "banda_vwap" else L
                            if px_c > st:
                                close_pos(c)
                        if pos == 0:
                            d = 1 if px_c > U else (-1 if px_c < L else 0)
                            if d and (dir_f == "ambas" or (dir_f == "compras" and d > 0) or (dir_f == "media50" and d * sb > 0)):
                                p = int(g.at[c, "pos"])
                                entry_px, entry_pos, pos = fill(m, p, d, True), p, d
                                unit = (U - L) / 2
                                t_sig = pd.Timestamp(m.time[p])
                    hit_hard(int(g["pos"].iloc[-1]))
                    if pos != 0:
                        close_pos(957 if 957 in g.index else int(g.index[-1]))
                out.append({"clave": (f"hard{hard_stop}|" if hard_stop else "") + (f"W1|noise|x{mult}|cada{step}m|stop_{stop_kind}|{dir_f}" if mult != 1.0 else f"W1|noise|cada{step}m|stop_{stop_kind}|{dir_f}"), "df": pd.DataFrame(rows)})
    return out


def w2_intraday_mom(rth: pd.DataFrame, m: M1Arrays) -> list[dict]:
    days = {k: g.set_index("mins") for k, g in rth.groupby("date")}
    dates = sorted(days)
    recs = []
    for j in range(1, len(dates)):
        g, gp = days[dates[j]], days[dates[j - 1]]
        if not {570, 599, 930}.issubset(g.index):
            continue
        prev_close = gp["close"].iloc[-1]
        recs.append({"date": dates[j], "r_prev": g.at[599, "close"] / prev_close - 1,
                     "r_open": g.at[599, "close"] / g.at[570, "open"] - 1,
                     "p_in": int(g.at[930, "pos"]), "p_out": int(g.at[957, "pos"]) if 957 in g.index else int(g["pos"].iloc[-1]),
                     "last30": abs(g["close"].iloc[-1] / g.at[930, "open"] - 1) * g.at[930, "open"]})
    d = pd.DataFrame(recs)
    d["unit"] = d["last30"].shift(1).rolling(60).median()
    out = []
    for base in ("r_prev", "r_open"):
        thr = d[base].abs().shift(1).rolling(60).median()
        for filt in ("todos", "fuerte"):
            rows = []
            for x, th in zip(d.itertuples(index=False), thr):
                r1 = getattr(x, base)
                if not np.isfinite(x.unit) or x.unit <= 0 or r1 == 0:
                    continue
                if filt == "fuerte" and not (np.isfinite(th) and abs(r1) > th):
                    continue
                s = 1 if r1 > 0 else -1
                pin, pout = fill(m, x.p_in, s, True), fill(m, x.p_out, s, False)
                rows.append({"detected_time": pd.Timestamp(m.time[x.p_in]), "direction": s,
                             "r": (pout - pin) * s / x.unit, "cost_r": COST / x.unit,
                             "entry_time": pd.Timestamp(m.time[x.p_in]), "exit_time": pd.Timestamp(m.time[x.p_out])})
            out.append({"clave": f"W2|mom_ultima_media_hora|desde_{base[2:]}|{filt}", "df": pd.DataFrame(rows)})
    return out


def w3_orb5(rth: pd.DataFrame, m: M1Arrays, bias: pd.DataFrame, targets=(10,), stops=("extremo",),
            dirs=("ambas", "media50")) -> list[dict]:
    out = []
    first = rth[rth["mins"] < 575].groupby("date").agg(o=("open", "first"), h=("high", "max"), l=("low", "min"),
                                                       c=("close", "last"), n=("open", "size"))
    first = first[first["n"] == 5]
    pos935 = rth[rth["mins"] == 575].set_index("date")["pos"]
    first = first.join(pos935.rename("p"), how="inner")
    first["detected_time"] = [pd.Timestamp(m.time[int(p)]) for p in first["p"]]
    first = I.attach_bias(first.reset_index(), bias)
    for tg, sk, dir_f in itertools.product(targets, stops, dirs):
        rows = []
        for x in first.itertuples(index=False):
            if abs(x.c - x.o) < 0.05 * (x.h - x.l) or x.h <= x.l:
                continue
            d = 1 if x.c > x.o else -1
            if dir_f == "media50" and not d * x.sma_bias > 0:
                continue
            i = int(x.p)
            px = fill(m, i, d, True)
            stop = (x.l if d > 0 else x.h + I.SPREAD_PTS) if sk == "extremo" else (
                (x.h + x.l) / 2 + (0 if d > 0 else I.SPREAD_PTS))
            risk = (px - stop) * d
            if risk <= 0:
                continue
            res = I.trade(m, i, d, px, stop, None if tg is None else px + d * tg * risk, I.end_index(m, i, 24 * 60), False)
            if res is None:
                continue
            r = I.row(x.detected_time, d, res, i, m)
            r["cost_r"] = COST / res[1]
            rows.append(r)
        key = f"W3|orb5|{dir_f}" if (tg, sk) == (10, "extremo") else f"W3|orb5|obj_{tg or 'fin_dia'}|stop_{sk}|{dir_f}"
        out.append({"clave": key, "df": pd.DataFrame(rows)})
    return out


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
    rth = rth_frame(m1)
    V = w1_noise(rth, m, bias) + w2_intraday_mom(rth, m) + w3_orb5(rth, m, bias)
    rows = []
    for v in V:
        df = v["df"]
        res = I.by_period(df) if len(df) else {p: {"n": 0} for p in I.PERIODS}
        r = {"clave": v["clave"]}
        for p in I.PERIODS:
            for k in ("n", "r", "t", "bruto", "aciertos"):
                r[f"{p}_{k}"] = res[p].get(k)
        if len(df):
            r["ops_por_año"] = round(len(df) / ((df["detected_time"].max() - df["detected_time"].min()).days / 365.25), 1)
        r["cumple"] = I.passes(res, "W")
        rows.append(r)
    tab = pd.DataFrame(rows)
    n_total = N_PREVIOUS + len(tab)
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"), "variantes": len(tab),
               "cumplen": int(tab["cumple"].sum()), "bonferroni_t": round(float(norm.ppf(1 - 0.05 / n_total)), 2),
               "variantes_totales_hoy": n_total}
    out = ROOT / "data" / "backtests" / f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_web"
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (ROOT / "reports" / "web.json").write_text(json.dumps({**summary, "tabla": tab.to_dict("records")}, indent=1,
                                                          ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    pd.set_option("display.width", 250)
    print(tab.to_string(index=False))


if __name__ == "__main__":
    main()
