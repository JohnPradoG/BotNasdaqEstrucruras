"""Fase 6c: cinco ideas nuevas para buscar ventaja neta, con protocolo prerregistrado (2026-10-20).

La rejilla y la regla de selección se fijaron y se guardaron en git ANTES de ejecutar por primera vez.

Ideas (familias):
  F1 limite_retesteo  Tras un BOS (a favor del contexto) o un CHOCH (contexto no en contra), orden LIMITADA en el
                      nivel roto, válida 12 velas de la temporalidad de entrada. Se llena solo si el precio cruza el
                      límite en 0,25 puntos (compra: ASK <= límite - 0,25). Sin deslizamiento en la entrada.
                      En la vela M1 del llenado: si toca el stop, stop; el objetivo no cuenta en esa vela.
                      Rejilla: TF {M15, M5} x origen {bos, choch} x desfase {0, 0,1 ATR a favor del llenado}
                               x stop {0,5, 1,0 ATR más allá del nivel} x objetivo {1,5, 2, 3 R}        = 48
  F2 sesgo_D1         Señales A/B/C de siempre (entrada a mercado, stop = invalidación +-0,10 ATR) filtradas por
                      un sesgo diario ya cerrado: {media 50 días a favor, tendencia de estructura D1 a favor,
                      solo compras}. Salida {2 R, fin del día (15:57 Nueva York) sin objetivo}.
                      2 combos x 3 estrategias x 3 sesgos x 2 salidas                                       = 36
  F3 memoria_knn      Las mismas señales sin sesgo; se opera solo si los 50 casos pasados más parecidos de la
                      MISMA regla (ya cerrados, separados >= 30 min, con >= 100 casos previos) dan
                      {cota inferior 90 % > 0, media > 0,05 R}. Escala de las características congelada con
                      datos anteriores a 2022-05-01; antes de esa fecha no se opera.
                      2 combos x 3 estrategias x 2 salidas x 2 umbrales                                     = 24
  F4 horizonte_D1     Estructuras en velas diarias (día de Nueva York, cierre 17:00): A/B/C con la tendencia D1.
                      Entrada en la primera M1 tras el cierre diario, stop = invalidación +-0,10 ATR diario,
                      objetivo {2, 3 R}, máximo 10 días, sin cierre diario forzado. Incluye swap real
                      (compra -6,555 puntos por noche y lote unidad, triple el viernes; venta 0).
                      3 estrategias x {sin filtro, media 50 a favor} x 2 objetivos                          = 12
  F5 apertura_NY      a) señales A/B/C solo de 9:30 a 11:00 Nueva York, salida {2 R, fin del día}
                         2 combos x 3 estrategias x 2 salidas                                               = 12
                      b) ruptura del rango de apertura (ORB): rango de los primeros {15, 30} min desde 9:30 NY;
                         primera vela M5 que cierra fuera del rango antes de 11:30 NY. Entrada {a mercado,
                         limitada en el borde del rango durante 60 min}; stop {otro lado del rango, mitad del
                         rango}; salida {2 R, fin del día}; dirección {ambas, solo a favor de la media 50 D1}.
                         Una operación por día como máximo.                                                 = 32
                                                                                                    Total = 164
Costes: spread fijo 1,12 puntos (actual de Exness) + 0,5 puntos de deslizamiento en cada entrada a mercado y en
cada salida. El bruto = neto + coste (+ swap en F4).

Periodos: desarrollo 2021-11-01..2023-12-31, validación 2024, y 2025-01-01..hoy. El periodo 2025-26 ya se miró en
las pruebas anteriores, así que aquí es SOLO diagnóstico; la confirmación final tiene que ser la demo en adelante.

Selección (prerregistrada). t = media / error estándar agrupado por día (las señales del mismo día no son
independientes).
  desarrollo: n >= 100 (40 en F4), media > 0, t >= 2,0 · validación: n >= 50 (15 en F4), media > 0, t >= 1,0
  Si nada cumple: NO OPERAR. Nunca se elige por el resultado de 2025-26.

Uso: python scripts/run_ideas.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_risk, load_settings  # noqa: E402
from nsmb.indicators.core import add_indicators  # noqa: E402
from nsmb.market_structure.engine import StructureEngine, StructureParams  # noqa: E402
from nsmb.memory.features import FEATURES  # noqa: E402
from nsmb.strategies.rules import STRATEGIES, select  # noqa: E402

PERIODS = {"dev": ("2021-11-01", "2023-12-31"), "val": ("2024-01-01", "2024-12-31"), "hol": ("2025-01-01", "2026-12-31")}
COMBOS = {"M15": "H4_H1_M15", "M5": "H1_M15_M5"}
TF_MIN = {"M15": 15, "M5": 5}
SPREAD_PTS = 1.12
SLIP = 0.5
TRADE_THROUGH = 0.25
SWAP_LONG_PER_NIGHT = 6.555     # 655,5 points x 0,01 (symbol_info 2026-10-20), por unidad de precio
KNN_SCALE_END = pd.Timestamp("2022-05-01")
NY = "America/New_York"


# ---------------------------------------------------------------------------------------------------------------
# Simulación
# ---------------------------------------------------------------------------------------------------------------
def trade(m: M1Arrays, i0: int, d: int, entry: float, stop: float, target: float | None, i_end: int,
          limit_fill: bool, use_flat: bool = True):
    """Una operación desde la vela M1 i0 (incluida). Devuelve (pnl_precio, riesgo, i_salida, motivo) o None.
    Compras: stop/objetivo contra el BID; ventas: contra el ASK. Regla conservadora: stop antes que objetivo."""
    n = len(m.time)
    i_end = max(min(i_end, n), i0 + 1)
    if i0 >= n or (use_flat and m.flat_mask[i0]):
        return None
    sl = slice(i0, i_end)
    o, h, l, c, sp = m.open[sl], m.high[sl], m.low[sl], m.close[sl], m.spread[sl]
    risk = (entry - stop) * d
    if risk <= 0:
        return None
    if d > 0:
        hs, ht = l <= stop, (h >= target) if target is not None else np.zeros(len(o), bool)
    else:
        hs, ht = h + sp >= stop, (l + sp <= target) if target is not None else np.zeros(len(o), bool)
    if limit_fill:
        ht = ht.copy()
        ht[0] = False
    fl = m.flat_mask[sl].copy() if use_flat else np.zeros(len(o), bool)
    fl[0] = False
    L = len(o)
    i_s = int(np.argmax(hs)) if hs.any() else L
    i_t = int(np.argmax(ht)) if ht.any() else L
    i_f = int(np.argmax(fl)) if fl.any() else L
    first = min(i_s, i_t, i_f)
    if first == L:
        k, why = L - 1, "tiempo"
        px = c[k] if d > 0 else c[k] + sp[k]
    elif i_f == first and i_f < i_s and i_f < i_t:
        k, why = i_f - 1, "cierre_dia"
        px = c[k] if d > 0 else c[k] + sp[k]
    elif i_s == first:
        k, why = i_s, "stop"
        if k == 0:
            px = stop
        else:
            px = min(o[k], stop) if d > 0 else max(o[k] + sp[k], stop)
    else:
        k, why = i_t, "objetivo"
        px = target
    px = px - SLIP if d > 0 else px + SLIP
    return (px - entry) * d, risk, i0 + k, why


def market_entry(m: M1Arrays, ts, d: int):
    i = m.index_at(ts)
    if i >= len(m.time):
        return None
    return i, (m.open[i] + m.spread[i] + SLIP) if d > 0 else (m.open[i] - SLIP)


def limit_fill(m: M1Arrays, ts, d: int, limit: float, valid_min: int):
    """Primera vela M1 en [ts, ts+valid) que cruza el límite. Devuelve (i, precio) o None."""
    i0 = m.index_at(ts)
    i1 = int(np.searchsorted(m.time, np.datetime64(ts, "ns") + np.timedelta64(valid_min, "m")))
    if i0 >= i1:
        return None
    if d > 0:
        hit = m.low[i0:i1] + m.spread[i0:i1] <= limit - TRADE_THROUGH
    else:
        hit = m.high[i0:i1] >= limit + TRADE_THROUGH
    hit &= ~m.flat_mask[i0:i1]
    if not hit.any():
        return None
    k = i0 + int(np.argmax(hit))
    if d > 0:
        return k, min(limit, m.open[k] + m.spread[k])
    return k, max(limit, m.open[k])


def end_index(m: M1Arrays, i0: int, minutes: int) -> int:
    return int(np.searchsorted(m.time, m.time[i0] + np.timedelta64(minutes, "m")))


def row(sig_time, d, res, entry_i, m, extra=None, swap=0.0):
    pnl, risk, ix, why = res
    net = (pnl - swap) / risk
    out = {"detected_time": pd.Timestamp(sig_time), "direction": d, "r": net,
           "exit_time": pd.Timestamp(m.time[ix]) + pd.Timedelta(minutes=1), "motivo": why,
           "entry_time": pd.Timestamp(m.time[entry_i])}
    out["cost_r"] = None  # se rellena fuera (depende del tipo de entrada)
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------------------------------------------------------
# Estadística
# ---------------------------------------------------------------------------------------------------------------
def cluster_stats(df: pd.DataFrame, col: str = "r") -> dict:
    x = df.dropna(subset=[col])
    n = len(x)
    if n < 2:
        return {"n": n, "r": float(x[col].mean()) if n else None, "t": None}
    g = x.groupby(x["detected_time"].dt.floor("D"))[col]
    S, N = g.sum(), g.count()
    mean = S.sum() / N.sum()
    se = np.sqrt(((S - mean * N) ** 2).sum()) / N.sum()
    return {"n": n, "dias": int(len(S)), "r": round(float(mean), 4),
            "t": round(float(mean / se), 2) if se > 0 else None, "aciertos": round(float((x[col] > 0).mean()), 3)}


def by_period(df: pd.DataFrame) -> dict:
    out = {}
    for p, (a, b) in PERIODS.items():
        y = df[(df["detected_time"] >= pd.Timestamp(a)) & (df["detected_time"] < pd.Timestamp(b) + pd.Timedelta(days=1))]
        st = cluster_stats(y)
        gross = cluster_stats(y.assign(g=y["r"] + y["cost_r"]), "g") if len(y) else {}
        out[p] = {**st, "bruto": gross.get("r")}
    return out


# ---------------------------------------------------------------------------------------------------------------
# Datos auxiliares: velas diarias de Nueva York, sesgos
# ---------------------------------------------------------------------------------------------------------------
def daily_bars(m1: pd.DataFrame) -> pd.DataFrame:
    ny = m1.index.tz_localize("UTC").tz_convert(NY)
    day = (ny + pd.Timedelta(hours=7)).normalize().tz_localize(None)     # día de trading (cierre 17:00 NY)
    g = m1.groupby(day)
    d = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
              tickvol=("tickvol", "sum"), spread=("spread", "median"))
    d["close_time"] = g.apply(lambda x: x.index[-1]) + pd.Timedelta(minutes=1)
    d = d[g.size() >= 120]          # descarta días casi vacíos (festivos)
    d["complete"] = True
    return d


def daily_bias(d1: pd.DataFrame, d1_state: pd.DataFrame) -> pd.DataFrame:
    """Sesgo conocido al cierre de cada día (se usa as-of por close_time: nunca el día en curso)."""
    sma = d1["close"].rolling(50, min_periods=50).mean()
    return pd.DataFrame({"close_time": d1["close_time"].to_numpy(),
                         "sma_bias": np.sign(d1["close"] - sma).to_numpy(),
                         "d1_trend": d1_state["trend"].to_numpy(float)}).dropna(subset=["close_time"])


def attach_bias(df: pd.DataFrame, bias: pd.DataFrame) -> pd.DataFrame:
    x = df.sort_values("detected_time").reset_index(drop=True)
    b = bias.sort_values("close_time").rename(columns={"close_time": "bias_time"})
    b["bias_time"] = b["bias_time"].astype("datetime64[ns]")
    x["detected_time"] = x["detected_time"].astype("datetime64[ns]")
    return pd.merge_asof(x, b, left_on="detected_time", right_on="bias_time", direction="backward")


# ---------------------------------------------------------------------------------------------------------------
# F1: orden limitada en el nivel roto
# ---------------------------------------------------------------------------------------------------------------
def f1_limit(ep: pd.DataFrame, m: M1Arrays, tf: str, risk_cfg: dict) -> list[dict]:
    variants = []
    for origin in ("bos", "choch"):
        e = ep[(ep["structure_type"] == origin) & (ep["status"] == "ok")].copy()
        e = e[(e["trend_ctx1"] > 0) if origin == "bos" else (e["trend_ctx1"] >= 0)]
        e = e[e["spread_points"] <= risk_cfg["max_spread_points_abs"]].sort_values("detected_time")
        for off in (0.0, 0.1):
            fills = []
            for x in e.itertuples(index=False):
                d = int(x.direction)
                lim = x.level + d * off * x.atr
                f = limit_fill(m, x.detected_time, d, lim, 12 * TF_MIN[tf])
                fills.append(f)
            for stop_atr in (0.5, 1.0):
                for tr in (1.5, 2.0, 3.0):
                    rows = []
                    for x, f in zip(e.itertuples(index=False), fills):
                        if f is None:
                            continue
                        d = int(x.direction)
                        i, px = f
                        stop = x.level - d * stop_atr * x.atr
                        risk = (px - stop) * d
                        if risk <= 0:
                            continue
                        res = trade(m, i, d, px, stop, px + d * tr * risk, end_index(m, i, 48 * TF_MIN[tf]), True)
                        if res is None:
                            continue
                        r = row(x.detected_time, d, res, i, m, {"session": x.session})
                        r["cost_r"] = (SPREAD_PTS + SLIP) / res[1]
                        rows.append(r)
                    variants.append({"familia": "F1_limite_retesteo",
                                     "clave": f"F1|{tf}|{origin}|desfase{off}|stop{stop_atr}ATR|obj{tr}R",
                                     "señales": len(e), "llenadas": sum(f is not None for f in fills),
                                     "df": pd.DataFrame(rows)})
        print("F1", tf, origin, flush=True)
    return variants


# ---------------------------------------------------------------------------------------------------------------
# F2/F3/F5a: señales A/B/C de siempre con otra salida / filtros
# ---------------------------------------------------------------------------------------------------------------
def abc_stream(ep: pd.DataFrame, m: M1Arrays, tf: str, name: str, exit_kind: str, risk_cfg: dict) -> pd.DataFrame:
    sig = select(ep, name, risk_cfg)
    rows = []
    for x in sig.itertuples(index=False):
        d = int(x.direction)
        me = market_entry(m, x.detected_time, d)
        if me is None:
            continue
        i, px = me
        stop = x.invalidation - 0.10 * x.atr if d > 0 else x.invalidation + 0.10 * x.atr + SPREAD_PTS
        risk = (px - stop) * d
        if risk <= 0 or not (0.15 <= risk / x.atr <= 6.0):
            continue
        if exit_kind == "2R":
            res = trade(m, i, d, px, stop, px + d * 2 * risk, end_index(m, i, 48 * TF_MIN[tf]), False)
        else:   # fin del día: sin objetivo, cierre forzado 16:55 NY (máximo 24 h)
            res = trade(m, i, d, px, stop, None, end_index(m, i, 24 * 60), False)
        if res is None:
            continue
        r = row(x.detected_time, d, res, i, m, {"session": x.session, **{f: getattr(x, f) for f in FEATURES}})
        r["cost_r"] = (SPREAD_PTS + 2 * SLIP) / res[1]
        rows.append(r)
    return pd.DataFrame(rows)


def knn_filter(s: pd.DataFrame, k: int, criterion: str) -> pd.DataFrame:
    """Opera solo si los k casos pasados más parecidos de la misma regla (ya cerrados) lo justifican."""
    s = s.sort_values("detected_time").reset_index(drop=True)
    X = s[FEATURES].to_numpy(float)
    base = X[(s["detected_time"] < KNN_SCALE_END).to_numpy()]
    center = np.nanmedian(base, axis=0)
    iqr = np.nanpercentile(base, 75, axis=0) - np.nanpercentile(base, 25, axis=0)
    sd = np.nanstd(base, axis=0)
    scale = np.where(iqr > 1e-9, iqr / 1.349, np.where(sd > 1e-9, sd, 1.0))
    Z = np.nan_to_num((X - center) / scale)
    det = s["detected_time"].to_numpy("datetime64[ns]")
    ex = s["exit_time"].to_numpy("datetime64[ns]")
    y = s["r"].to_numpy(float)
    sep = np.timedelta64(30, "m")
    keep = np.zeros(len(s), bool)
    for q in range(len(s)):
        if det[q] < np.datetime64(KNN_SCALE_END):
            continue
        cand = np.flatnonzero(ex[:q] <= det[q])
        if len(cand) < 100:
            continue
        dist = np.sqrt(((Z[cand] - Z[q]) ** 2).sum(axis=1))
        chosen, times = [], []
        for j in cand[np.argsort(dist, kind="stable")]:
            if any(abs(det[j] - u) < sep for u in times):
                continue
            chosen.append(j)
            times.append(det[j])
            if len(chosen) >= k:
                break
        yy = y[chosen]
        mean = yy.mean()
        if criterion == "lcb":
            keep[q] = mean - 1.645 * yy.std(ddof=1) / np.sqrt(len(yy)) > 0
        else:
            keep[q] = mean > 0.05
    return s[keep]


# ---------------------------------------------------------------------------------------------------------------
# F4: estructuras diarias
# ---------------------------------------------------------------------------------------------------------------
def nights_swap(t0: pd.Timestamp, t1: pd.Timestamp) -> float:
    """Swap de una compra entre t0 y t1 (UTC): una noche por cada cierre de las 17:00 NY cruzado; viernes x3."""
    a = t0.tz_localize("UTC").tz_convert(NY)
    b = t1.tz_localize("UTC").tz_convert(NY)
    total = 0.0
    day = (a + pd.Timedelta(hours=7)).normalize()
    while True:
        roll = day + pd.Timedelta(hours=17)   # 17:00 NY del día "day"
        if roll > b:
            break
        if roll > a and roll.weekday() < 5:
            total += SWAP_LONG_PER_NIGHT * (3 if roll.weekday() == 4 else 1)
        day += pd.Timedelta(days=1)
    return total


def f4_daily(d1: pd.DataFrame, ev: pd.DataFrame, bias: pd.DataFrame, m: M1Arrays) -> list[dict]:
    d1i = add_indicators(d1)
    ev = ev.copy()
    ev["atr"] = d1i["atr"].to_numpy()[ev["t"].to_numpy()]
    ev["detected_time"] = pd.to_datetime(ev["time"])
    ev["trend_d1"] = ev["trend_before"].astype(float)     # tendencia D1 antes del evento (solo pasado)
    ev = attach_bias(ev, bias)
    ty, og = ev["type"], ev["origin"] if "origin" in ev else pd.Series("", index=ev.index)
    rules = {"A": (ty == "retest") & (og == "bos"),
             "B": ty.isin(["sweep", "false_break"]),
             "C": ((ty == "retest") & (og == "choch"))
                  | ty.isin(["double_top", "double_bottom", "head_shoulders", "inv_head_shoulders"])}
    ctx = {"A": lambda e: e["direction"] * e["trend_d1"] > 0, "B": lambda e: e["direction"] * e["trend_d1"] >= 0,
           "C": lambda e: e["direction"] * e["trend_d1"] >= 0}
    variants = []
    for name, rule in rules.items():
        e = ev[rule.to_numpy()]
        e = e[ctx[name](e) & np.isfinite(e["atr"])]
        for filt in ("sin_filtro", "media50"):
            ee = e if filt == "sin_filtro" else e[e["direction"] * e["sma_bias"] > 0]
            for tr in (2.0, 3.0):
                rows = []
                for x in ee.itertuples(index=False):
                    d = int(x.direction)
                    inval = x.extreme if x.type in ("retest", "sweep", "false_break") else (
                        x.extreme if np.isfinite(x.extreme) else np.nan)
                    if not np.isfinite(inval):
                        continue
                    me = market_entry(m, x.detected_time, d)
                    if me is None:
                        continue
                    i, px = me
                    stop = inval - 0.10 * x.atr if d > 0 else inval + 0.10 * x.atr + SPREAD_PTS
                    risk = (px - stop) * d
                    if risk <= 0 or not (0.15 <= risk / x.atr <= 6.0):
                        continue
                    res = trade(m, i, d, px, stop, px + d * tr * risk, end_index(m, i, 14 * 24 * 60), False, use_flat=False)
                    if res is None:
                        continue
                    swap = nights_swap(pd.Timestamp(m.time[i]), pd.Timestamp(m.time[res[2]])) if d > 0 else 0.0
                    r = row(x.detected_time, d, res, i, m, swap=swap)
                    r["cost_r"] = (SPREAD_PTS + 2 * SLIP + swap) / res[1]
                    rows.append(r)
                variants.append({"familia": "F4_horizonte_D1", "clave": f"F4|D1|{name}|{filt}|obj{tr}R",
                                 "df": pd.DataFrame(rows)})
    return variants


# ---------------------------------------------------------------------------------------------------------------
# F5b: ruptura del rango de apertura de Nueva York
# ---------------------------------------------------------------------------------------------------------------
def f5_orb(m1: pd.DataFrame, m: M1Arrays, bias: pd.DataFrame) -> list[dict]:
    ny = m1.index.tz_localize("UTC").tz_convert(NY)
    mins = np.asarray(ny.hour * 60 + ny.minute)
    dates = np.asarray(ny.normalize().tz_localize(None))
    variants = []
    for rng in (15, 30):
        days = []
        in_rng = (mins >= 570) & (mins < 570 + rng)
        after = (mins >= 570 + rng) & (mins < 690)
        df = pd.DataFrame({"date": dates, "mins": mins, "high": m1["high"].to_numpy(), "low": m1["low"].to_numpy(),
                           "close": m1["close"].to_numpy(), "time": m1.index})
        r = df[in_rng].groupby("date").agg(hi=("high", "max"), lo=("low", "min"), cnt=("high", "size"))
        r = r[r["cnt"] >= rng - 2]
        post = df[after]
        # velas M5 cerradas tras el rango (cierre = última M1 de cada bloque de 5 minutos)
        post = post.assign(b5=(post["mins"] // 5))
        m5 = post.groupby(["date", "b5"]).agg(close=("close", "last"), last=("time", "last"), cnt=("close", "size"))
        m5 = m5.reset_index().merge(r, left_on="date", right_index=True)
        m5["dir"] = np.where(m5["close"] > m5["hi"], 1, np.where(m5["close"] < m5["lo"], -1, 0))
        first = m5[m5["dir"] != 0].groupby("date").first().reset_index()
        first["detected_time"] = first["last"] + pd.Timedelta(minutes=1)
        first = attach_bias(first, bias)
        for entry_kind in ("mercado", "limite_borde"):
            for stop_kind in ("otro_lado", "mitad"):
                for exit_kind in ("2R", "fin_dia"):
                    for dir_f in ("ambas", "media50"):
                        rows = []
                        for x in first.itertuples(index=False):
                            d = int(x.dir)
                            if dir_f == "media50" and not d * x.sma_bias > 0:
                                continue
                            if entry_kind == "mercado":
                                f = market_entry(m, x.detected_time, d)
                            else:
                                f = limit_fill(m, x.detected_time, d, x.hi if d > 0 else x.lo, 60)
                            if f is None:
                                continue
                            i, px = f
                            mid = (x.hi + x.lo) / 2
                            stop = (x.lo if d > 0 else x.hi + SPREAD_PTS) if stop_kind == "otro_lado" else (
                                mid if d > 0 else mid + SPREAD_PTS)
                            risk = (px - stop) * d
                            if risk <= 0:
                                continue
                            tgt = px + d * 2 * risk if exit_kind == "2R" else None
                            res = trade(m, i, d, px, stop, tgt, end_index(m, i, 24 * 60), entry_kind != "mercado")
                            if res is None:
                                continue
                            rr = row(x.detected_time, d, res, i, m)
                            rr["cost_r"] = (SPREAD_PTS + (2 if entry_kind == "mercado" else 1) * SLIP) / res[1]
                            rows.append(rr)
                        variants.append({"familia": "F5b_ORB_NY",
                                         "clave": f"F5b|rango{rng}m|{entry_kind}|stop_{stop_kind}|{exit_kind}|{dir_f}",
                                         "df": pd.DataFrame(rows)})
    return variants


# ---------------------------------------------------------------------------------------------------------------
def passes(res: dict, fam: str) -> bool:
    dn, vn = (40, 15) if fam.startswith("F4") else (100, 50)
    d, v = res["dev"], res["val"]
    return (d.get("n", 0) >= dn and (d.get("r") or -1) > 0 and (d.get("t") or 0) >= 2.0
            and v.get("n", 0) >= vn and (v.get("r") or -1) > 0 and (v.get("t") or 0) >= 1.0)


def main() -> None:
    cfg, risk_cfg = load_settings(), load_risk()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, True, SPREAD_PTS / spec.point)
    # Hasta 2023-06 el símbolo dejaba de cotizar a las 15:59 NY y volvía a las 18:30 NY, así que la ventana de
    # cierre forzado de 16:55-18:00 no existía en los datos y las operaciones cruzaban la pausa. Para que "fin del
    # día" signifique lo mismo en todos los años, el cierre forzado aquí es de 15:57 a 18:30 NY.
    ny = m1.index.tz_localize("UTC").tz_convert("America/New_York")
    mins = np.asarray(ny.hour * 60 + ny.minute)
    m.flat_mask = (mins >= 15 * 60 + 57) & (mins < 18 * 60 + 30)
    m_nf = M1Arrays.from_frame(m1, spec.point, False, SPREAD_PTS / spec.point)

    d1 = daily_bars(m1)
    d1i = add_indicators(d1)
    ev_d1, st_d1 = StructureEngine(StructureParams.from_cfg(cfg["structure"])).run(d1i)
    bias = daily_bias(d1, st_d1)
    print("D1", len(d1), "velas,", len(ev_d1), "eventos", flush=True)

    variants: list[dict] = []
    for tf, tag in COMBOS.items():
        ep = pd.read_parquet(ROOT / "data" / "processed" / f"episodes_{tag}.parquet")
        ep["detected_time"] = ep["detected_time"].astype("datetime64[ns]")
        variants += f1_limit(ep, m, tf, risk_cfg)
        for name in STRATEGIES:
            for exit_kind in ("2R", "fin_dia"):
                s = abc_stream(ep, m, tf, name, exit_kind, risk_cfg)
                sb = attach_bias(s, bias)
                for bname, cond in (("media50", lambda z: z["direction"] * z["sma_bias"] > 0),
                                    ("estructura_D1", lambda z: z["direction"] * z["d1_trend"] > 0),
                                    ("solo_compras", lambda z: z["direction"] > 0)):
                    variants.append({"familia": "F2_sesgo_D1", "clave": f"F2|{tf}|{name}|{bname}|{exit_kind}",
                                     "df": sb[cond(sb)]})
                for crit in ("lcb", "media005"):
                    variants.append({"familia": "F3_memoria_knn", "clave": f"F3|{tf}|{name}|knn50_{crit}|{exit_kind}",
                                     "df": knn_filter(s, 50, "lcb" if crit == "lcb" else "mean")})
                variants.append({"familia": "F5a_estructura_apertura_NY", "clave": f"F5a|{tf}|{name}|{exit_kind}",
                                 "df": s[s["session"] == "ny_apertura"]})
                variants.append({"familia": "referencia_sin_filtro", "clave": f"REF|{tf}|{name}|{exit_kind}", "df": s})
                print("F2/F3/F5a", tf, name, exit_kind, len(s), flush=True)
    variants += f4_daily(d1, ev_d1, bias, m_nf)
    print("F4 listo", flush=True)
    variants += f5_orb(m1, m, bias)
    print("F5b listo", flush=True)

    rows = []
    for v in variants:
        res = by_period(v["df"]) if len(v["df"]) else {p: {"n": 0} for p in PERIODS}
        r = {"familia": v["familia"], "clave": v["clave"]}
        for p in PERIODS:
            for kk in ("n", "r", "t", "bruto"):
                r[f"{p}_{kk}"] = res[p].get(kk)
        r["cumple"] = v["familia"] != "referencia_sin_filtro" and passes(res, v["familia"])
        if "llenadas" in v:
            r["llenado_pct"] = round(v["llenadas"] / max(v["señales"], 1), 3)
        rows.append(r)
    tab = pd.DataFrame(rows)
    tested = tab[tab["familia"] != "referencia_sin_filtro"]
    tested_score = tested.assign(score=tested[["dev_t", "val_t"]].min(axis=1))
    winners = tested_score[tested_score["cumple"]].sort_values("score", ascending=False)

    def pos(c):
        return int((tested[c].fillna(-1) > 0).sum())
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "version_codigo": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                text=True).stdout.strip(),
               "coste": f"spread {SPREAD_PTS} + deslizamiento {SLIP} por lado (entradas limitadas sin deslizamiento)",
               "variantes_probadas": len(tested), "cumplen": len(winners),
               "elegida": winners.iloc[0]["clave"] if len(winners) else "NO_OPERAR",
               "dev_positivas": pos("dev_r"), "val_positivas": pos("val_r"),
               "dev_y_val_positivas": int(((tested.dev_r.fillna(-1) > 0) & (tested.val_r.fillna(-1) > 0)).sum()),
               "las_tres_positivas": int(((tested.dev_r.fillna(-1) > 0) & (tested.val_r.fillna(-1) > 0)
                                          & (tested.hol_r.fillna(-1) > 0)).sum()),
               "bruto_dev_positivas": pos("dev_bruto"),
               "por_familia": {f: {"variantes": int(len(g)), "cumplen": int(g["cumple"].sum()),
                                   "mejor_dev_t": g.sort_values("dev_t", ascending=False).iloc[0]["clave"]}
                               for f, g in tested.groupby("familia")},
               "ganadoras": winners.drop(columns=["score"]).to_dict("records")}
    run_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_ideas"
    out = ROOT / "data" / "backtests" / run_id
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (out / "resumen.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (ROOT / "reports" / "ideas.json").write_text(json.dumps({**summary, "tabla": tab.round(4).to_dict("records")},
                                                            indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    pd.set_option("display.width", 250)
    cols = ["clave", "dev_n", "dev_r", "dev_t", "val_n", "val_r", "val_t", "hol_n", "hol_r", "hol_t", "hol_bruto", "cumple"]
    print(tab.sort_values("dev_t", ascending=False)[cols].head(25).to_string(index=False))


if __name__ == "__main__":
    main()
