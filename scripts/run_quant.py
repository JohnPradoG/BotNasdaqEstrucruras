"""Fase 6d: ideas cuantitativas clásicas (no solo estructuras), con protocolo prerregistrado (2026-10-20).

La rejilla y la regla de selección se guardaron en git ANTES de ejecutar por primera vez.

Todas las señales usan solo precios ya cerrados; la ejecución es en la apertura de la vela siguiente.
Coste: spread 1,12 + 0,5 de deslizamiento por lado (2,12 puntos por operación ida y vuelta). Las compras que
cruzan el cierre diario (17:00 Nueva York) pagan swap: -6,555 puntos por noche, triple el viernes. Ventas sin swap.
Unidad: puntos básicos (pb) del precio. Bruto = neto + costes + swap.

Familias (73 variantes):
 Q1 tendencia_D1 (serie diaria, posición mantenida)
    media N {20,50,100,200} x {compra/fuera, compra/venta}                                   8
    canal Donchian N {20,55}: entra al romper el máximo (mínimo) de N días, sale con N/2,
    x {compra/fuera, compra/venta}                                                           4
    momento L {20,60,120} días: signo del rendimiento de L días x {compra/fuera, compra/venta} 6
 Q1b tendencia_H1 (serie horaria): media N {20,50,100} x {compra/fuera, compra/venta}
    x {24 h con swap, solo 10:00-16:00 Nueva York}                                           12
 Q2 reversion
    RSI(2) diario de Connors: compra si RSI2 < {5,10} y cierre > media 200; sale si cierre > media 5;
    x {solo compras, también ventas espejo}                                                  4
    H1 extremo: si el movimiento de la última hora / ATR(14) H1 <= -k (>= k)
    k {1,5, 2,0} x mantener h {1,3} horas x {contra el movimiento, a favor del movimiento}
    x {ambas direcciones, solo compras}; señales entre 10:00 y 15:00 NY; sale como tarde a las 16:00   16
 Q3 estacionalidad
    noche (compra 15:55 -> 9:30) y sesión (compra 9:31 -> 15:59), cada una compra y venta     4
    hora del día: se eligen en DESARROLLO las horas NY con |t| >= 2 (y su signo); se prueban en
    validación como una sola estrategia                                                      1
    día de la semana: igual, con los 5 días                                                  1
    cambio de mes: compra desde la apertura del último día del mes hasta el cierre del 3.er día   1
 Q4 regimen_volatilidad: ATR(14) D1 / mediana de 250 días {< 1 baja, > 1 alta} aplicado a
    media 50 compra/fuera, RSI2<10 solo compras, H1 extremo k2 h1 contra, H1 extremo k2 h1 a favor  8
 Q5 gap_apertura: gap = apertura 9:30 - cierre 16:00 anterior, en ATR D1; |gap| >= g {0,25, 0,5}
    x {contra el gap, a favor} x salida {10:29, 15:59}; entrada 9:31                          8

Periodos: desarrollo 2021-11-01..2023-12-31, validación 2024, 2025-01-01..hoy (ya visto antes en otras pruebas:
solo diagnóstico; la confirmación final tiene que ser la demo en adelante).

Selección (prerregistrada), t por día (operaciones del mismo día agrupadas):
  desarrollo: n >= 100 (operaciones o días con posición), media neta > 0, t >= 2,0
  validación: n >= 50, media neta > 0, t >= 1,0
  Se informa además el umbral de Bonferroni para todas las variantes probadas en las fases 6c y 6d juntas.
  Si nada cumple: NO OPERAR.

Uso: python scripts/run_quant.py
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

from nsmb.indicators.core import atr, rsi  # noqa: E402

NY = "America/New_York"
SPREAD, SLIP = 1.12, 0.5
RT = SPREAD + 2 * SLIP
SWAP = 6.555
PERIODS = {"dev": ("2021-11-01", "2023-12-31"), "val": ("2024-01-01", "2024-12-31"), "hol": ("2025-01-01", "2026-12-31")}
N_PREVIOUS = 164        # variantes de la fase 6c (run_ideas.py), para el umbral conjunto de Bonferroni


# ---------------------------------------------------------------------------------------------------------------
class M1:
    def __init__(self, m1: pd.DataFrame):
        self.df = m1
        self.t = m1.index.to_numpy("datetime64[ns]")
        self.o, self.c = m1["open"].to_numpy(float), m1["close"].to_numpy(float)
        nyt = m1.index.tz_localize("UTC").tz_convert(NY)
        self.ny_date = np.asarray(nyt.tz_localize(None).normalize())
        self.ny_min = np.asarray(nyt.hour * 60 + nyt.minute)

    def utc(self, dates: pd.Series | pd.DatetimeIndex, hhmm: str) -> np.ndarray:
        h, mm = map(int, hhmm.split(":"))
        loc = pd.DatetimeIndex(dates) + pd.Timedelta(hours=h, minutes=mm)
        return np.asarray(loc.tz_localize(NY, ambiguous="NaT", nonexistent="shift_forward").tz_convert("UTC")
                          .tz_localize(None), dtype="datetime64[ns]")

    def open_at(self, ts: np.ndarray, tol_min: int = 5):
        i = np.searchsorted(self.t, ts)
        ok = i < len(self.t)
        i = np.minimum(i, len(self.t) - 1)
        ok &= (self.t[i] - ts) <= np.timedelta64(tol_min, "m")
        return np.where(ok, self.o[i], np.nan), np.where(ok, self.t[i], np.datetime64("NaT", "ns"))

    def close_before(self, ts: np.ndarray, tol_min: int = 5):
        i = np.searchsorted(self.t, ts) - 1
        ok = i >= 0
        i = np.maximum(i, 0)
        ok &= (ts - self.t[i]) <= np.timedelta64(tol_min + 1, "m")
        return np.where(ok, self.c[i], np.nan)


def swap_nights(t0: pd.Timestamp, t1: pd.Timestamp) -> float:
    """Noches de swap (17:00 NY cruzadas entre t0 y t1, UTC); viernes cuenta 3."""
    if pd.isna(t0) or pd.isna(t1):
        return 0.0
    a = pd.Timestamp(t0).tz_localize("UTC").tz_convert(NY)
    b = pd.Timestamp(t1).tz_localize("UTC").tz_convert(NY)
    n, day = 0.0, a.normalize()
    while day <= b:
        roll = day + pd.Timedelta(hours=17)
        if a < roll <= b and roll.weekday() < 5:
            n += 3 if roll.weekday() == 4 else 1
        day += pd.Timedelta(days=1)
    return n


def trades_frame(date, d, entry_mid, exit_mid, t_entry, t_exit) -> pd.DataFrame:
    """Operaciones de entrada en la APERTURA de una M1 y salida en un CIERRE de M1 (precios BID)."""
    df = pd.DataFrame({"date": pd.to_datetime(date), "d": d, "e": entry_mid, "x": exit_mid,
                       "te": pd.to_datetime(t_entry), "tx": pd.to_datetime(t_exit)}).dropna()
    df = df[df["d"] != 0]
    gross = df["d"] * (df["x"] - df["e"])
    nights = np.array([swap_nights(a, b) if dd > 0 else 0.0 for a, b, dd in zip(df["te"], df["tx"], df["d"])])
    net = gross - RT - SWAP * nights
    return pd.DataFrame({"detected_time": df["date"].to_numpy(), "r": (net / df["e"] * 1e4).to_numpy(),
                         "bruto_r": (gross / df["e"] * 1e4).to_numpy()})


def daily_series(o: pd.Series, c: pd.Series, pos: pd.Series, roll_weekday: pd.Series) -> pd.DataFrame:
    """Serie diaria con posición decidida al cierre de t-1 y ejecutada en la apertura de t.
    pnl_t = p_{t-1}(O_t - C_{t-1}) + p_t(C_t - O_t) - coste·|p_t - p_{t-1}| - swap si p_t > 0 al cierre de t."""
    p = pos.shift(1).fillna(0.0)          # posición vigente durante el día t
    pp = p.shift(1).fillna(0.0)
    cprev = c.shift(1)
    gross = pp * (o - cprev) + p * (c - o)
    cost = (RT / 2) * (p - pp).abs()
    sw = SWAP * np.where(p > 0, np.where(roll_weekday == 4, 3, 1), 0)
    net = gross - cost - sw
    out = pd.DataFrame({"detected_time": c.index, "r": (net / cprev * 1e4).to_numpy(),
                        "bruto_r": (gross / cprev * 1e4).to_numpy(), "activo": (p != 0) | (pp != 0)})
    return out.dropna(subset=["r"])


def stats(df: pd.DataFrame, col: str) -> dict:
    x = df.dropna(subset=[col])
    if "activo" in x:
        n_act = int(x["activo"].sum())
    else:
        n_act = len(x)
    if len(x) < 2:
        return {"n": n_act, "r": None, "t": None}
    g = x.groupby(pd.to_datetime(x["detected_time"]).dt.floor("D"))[col].sum()
    if "activo" in x:          # serie diaria: media por día (incluidos días fuera, valen 0)
        mean, se = g.mean(), g.std(ddof=1) / np.sqrt(len(g))
        return {"n": n_act, "r": round(float(mean), 3), "t": round(float(mean / se), 2) if se > 0 else None,
                "sharpe_anual": round(float(g.mean() / g.std(ddof=1) * np.sqrt(252)), 2) if g.std() > 0 else None}
    N = x.groupby(pd.to_datetime(x["detected_time"]).dt.floor("D"))[col].count()
    mean = g.sum() / N.sum()
    se = np.sqrt(((g - mean * N) ** 2).sum()) / N.sum()
    return {"n": n_act, "r": round(float(mean), 3), "t": round(float(mean / se), 2) if se > 0 else None}


def by_period(df: pd.DataFrame) -> dict:
    out = {}
    for p, (a, b) in PERIODS.items():
        y = df[(df["detected_time"] >= pd.Timestamp(a)) & (df["detected_time"] < pd.Timestamp(b) + pd.Timedelta(days=1))]
        s = stats(y, "r")
        out[p] = {**s, "bruto": stats(y, "bruto_r").get("r")}
    return out


# ---------------------------------------------------------------------------------------------------------------
def daily_bars(m1: pd.DataFrame) -> pd.DataFrame:
    ny = m1.index.tz_localize("UTC").tz_convert(NY)
    day = (ny + pd.Timedelta(hours=7)).normalize().tz_localize(None)
    g = m1.groupby(day)
    d = g.agg(open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"),
              tickvol=("tickvol", "sum"), n=("close", "size"))
    d = d[d["n"] >= 120].copy()
    d["roll_wd"] = d.index.weekday      # el cierre de las 17:00 del día de trading cae en este día
    d["atr"] = atr(d, 14)
    d["atr_rel"] = d["atr"] / d["atr"].shift(1).rolling(250, min_periods=100).median()
    d["rsi2"] = rsi(d["close"], 2)
    return d


def hourly_bars(m1: pd.DataFrame) -> pd.DataFrame:
    g = m1.resample("60min", label="left", closed="left")
    h = g.agg({"open": "first", "high": "max", "low": "min", "close": "last"})
    h["n"] = g["close"].count()
    h = h[h["n"] >= 30].copy()
    ny = h.index.tz_localize("UTC").tz_convert(NY)
    h["ny_hour"] = ny.hour
    h["ny_date"] = ny.tz_localize(None).normalize()
    h["roll_wd"] = ny.weekday
    h["atr"] = atr(h, 14)
    return h


def hourly_series(h: pd.DataFrame, pos: pd.Series) -> pd.DataFrame:
    """Como daily_series, con swap si la posición es compradora en la vela que termina a las 17:00 NY."""
    p = pos.shift(1).fillna(0.0)
    pp = p.shift(1).fillna(0.0)
    cprev = h["close"].shift(1)
    gross = pp * (h["open"] - cprev) + p * (h["close"] - h["open"])
    cost = (RT / 2) * (p - pp).abs()
    # la vela es la última del día de trading (cierre diario de 17:00 NY, o la pausa de 16:00-18:30 NY de 2021-23)
    tday = (h.index.tz_localize("UTC").tz_convert(NY) + pd.Timedelta(hours=7)).tz_localize(None).normalize()
    at_roll = pd.Series(tday != tday.to_series().shift(-1).to_numpy(), index=h.index)
    sw = SWAP * np.where((p > 0) & at_roll, np.where(h["roll_wd"] == 4, 3, 1), 0)
    net = gross - cost - sw
    out = pd.DataFrame({"detected_time": h.index, "r": (net / cprev * 1e4).to_numpy(),
                        "bruto_r": (gross / cprev * 1e4).to_numpy(), "activo": ((p != 0) | (pp != 0)).to_numpy()})
    return out.dropna(subset=["r"])


# ---------------------------------------------------------------------------------------------------------------
def q1_daily(d: pd.DataFrame) -> list[dict]:
    v = []
    c = d["close"]
    for n in (20, 50, 100, 200):
        sig = np.sign(c - c.rolling(n).mean()).fillna(0)
        for mode in ("compra_fuera", "compra_venta"):
            pos = sig.clip(lower=0) if mode == "compra_fuera" else sig
            v.append(("Q1_tendencia_D1", f"Q1|media{n}|{mode}", daily_series(d["open"], c, pos, d["roll_wd"])))
    for n in (20, 55):
        up = c > d["high"].shift(1).rolling(n).max()
        dn = c < d["low"].shift(1).rolling(n).min()
        ex_l = c < d["low"].shift(1).rolling(n // 2).min()
        ex_s = c > d["high"].shift(1).rolling(n // 2).max()
        for mode in ("compra_fuera", "compra_venta"):
            p, cur = [], 0.0
            for u, dd, el, es in zip(up, dn, ex_l, ex_s):
                if cur > 0 and el:
                    cur = 0.0
                if cur < 0 and es:
                    cur = 0.0
                if u:
                    cur = 1.0
                elif dd and mode == "compra_venta":
                    cur = -1.0
                p.append(cur)
            v.append(("Q1_tendencia_D1", f"Q1|donchian{n}|{mode}",
                      daily_series(d["open"], c, pd.Series(p, index=d.index), d["roll_wd"])))
    for L in (20, 60, 120):
        sig = np.sign(c - c.shift(L)).fillna(0)
        for mode in ("compra_fuera", "compra_venta"):
            pos = sig.clip(lower=0) if mode == "compra_fuera" else sig
            v.append(("Q1_tendencia_D1", f"Q1|momento{L}d|{mode}", daily_series(d["open"], c, pos, d["roll_wd"])))
    return v


def q1_hourly(h: pd.DataFrame) -> list[dict]:
    v = []
    c = h["close"]
    session = h["ny_hour"].between(10, 15)
    for n in (20, 50, 100):
        sig = np.sign(c - c.rolling(n).mean()).fillna(0)
        for mode in ("compra_fuera", "compra_venta"):
            base = sig.clip(lower=0) if mode == "compra_fuera" else sig
            for hours in ("24h", "sesion_NY"):
                # pos se decide al cierre de la vela y vale para la siguiente: se filtra por la hora de la siguiente
                pos = base if hours == "24h" else base.where(session.shift(-1, fill_value=False), 0.0)
                v.append(("Q1b_tendencia_H1", f"Q1b|media{n}|{mode}|{hours}", hourly_series(h, pos)))
    return v


def connors(d: pd.DataFrame, lvl: float, shorts: bool, filt: pd.Series | None = None) -> pd.DataFrame:
    c = d["close"]
    s200, s5 = c.rolling(200).mean(), c.rolling(5).mean()
    p, cur = [], 0.0
    for i in range(len(d)):
        ok = True if filt is None else bool(filt.iloc[i])
        if cur > 0 and c.iloc[i] > s5.iloc[i]:
            cur = 0.0
        if cur < 0 and c.iloc[i] < s5.iloc[i]:
            cur = 0.0
        if cur == 0 and ok:
            if d["rsi2"].iloc[i] < lvl and c.iloc[i] > s200.iloc[i]:
                cur = 1.0
            elif shorts and d["rsi2"].iloc[i] > 100 - lvl and c.iloc[i] < s200.iloc[i]:
                cur = -1.0
        p.append(cur)
    return daily_series(d["open"], c, pd.Series(p, index=d.index), d["roll_wd"])


def h1_extreme(h: pd.DataFrame, k: float, hold: int, mode: str, dirs: str, ok_day: pd.Series | None = None):
    """Señal al cierre de una vela H1 que termina entre 10:00 y 15:00 NY; entrada en la apertura de la siguiente;
    salida al cierre de la vela hold-ésima, como tarde la que termina a las 16:00. Sin solapes."""
    z = (h["close"] - h["close"].shift(1)) / h["atr"].shift(1)
    rows, busy_until = [], None
    idx = h.index
    hr = h["ny_hour"].to_numpy()
    for i in range(1, len(h) - 1):
        if busy_until is not None and idx[i] < busy_until:
            continue
        if not 9 <= hr[i] <= 14:          # la vela i termina entre 10:00 y 15:00
            continue
        zi = z.iloc[i]
        if not np.isfinite(zi) or abs(zi) < k:
            continue
        d = -np.sign(zi) if mode == "contra" else np.sign(zi)
        if dirs == "solo_compras" and d < 0:
            continue
        if ok_day is not None and not bool(ok_day.iloc[i]):
            continue
        j = i + 1
        end = j
        while end + 1 < len(h) and end - j + 1 < hold and hr[end + 1] <= 15 and h["ny_date"].iloc[end + 1] == h["ny_date"].iloc[j]:
            end += 1
        if h["ny_date"].iloc[j] != h["ny_date"].iloc[i] or hr[j] > 15:
            continue
        rows.append((idx[i], d, h["open"].iloc[j], h["close"].iloc[end], idx[j], idx[end] + pd.Timedelta(minutes=59)))
        busy_until = idx[end] + pd.Timedelta(hours=1)
    if not rows:
        return pd.DataFrame(columns=["detected_time", "r", "bruto_r"])
    a = list(zip(*rows))
    return trades_frame(a[0], np.array(a[1]), np.array(a[2]), np.array(a[3]), a[4], a[5])


def session_trades(m: M1, dates: pd.DatetimeIndex, t_in: str, t_out: str, d: int, next_day: bool = False):
    te = m.utc(dates, t_in)
    out_dates = pd.DatetimeIndex(dates) + (pd.Timedelta(days=1) if next_day else pd.Timedelta(0))
    tx = m.utc(out_dates, t_out)
    e, te_real = m.open_at(te)
    if t_out == "09:30":
        x, _ = m.open_at(tx)          # salida en la apertura de las 9:30 (BID)
    else:
        x = m.close_before(tx)
    return trades_frame(dates, np.full(len(dates), d), e, x, te_real, tx)


def q3_seasonality(m: M1, h: pd.DataFrame, d: pd.DataFrame, dates: pd.DatetimeIndex) -> list:
    v = []
    # noche: compra a las 15:55 (apertura de esa M1; en 2021-24 el símbolo no cotiza de 16:00 a 18:30 NY) y sale en
    # la apertura de 9:30 del siguiente día hábil
    nxt = pd.Series(dates[1:].append(pd.DatetimeIndex([dates[-1] + pd.Timedelta(days=1)])), index=dates)
    for d_ in (1, -1):
        te = m.utc(dates, "15:55")
        tx = m.utc(pd.DatetimeIndex(nxt.values), "09:30")
        e, ter = m.open_at(te)
        x, _ = m.open_at(tx)
        v.append(("Q3_estacionalidad", f"Q3|noche|{'compra' if d_ > 0 else 'venta'}",
                  trades_frame(dates, np.full(len(dates), d_), e, x, ter, tx)))
        v.append(("Q3_estacionalidad", f"Q3|sesion|{'compra' if d_ > 0 else 'venta'}",
                  session_trades(m, dates, "09:31", "16:00", d_)))
    # hora del día: elegida en desarrollo
    hh = h.copy()
    hh["ret"] = (hh["close"] - hh["open"]) / hh["open"] * 1e4
    dev = hh[(hh.index >= PERIODS["dev"][0]) & (hh.index < pd.Timestamp(PERIODS["dev"][1]) + pd.Timedelta(days=1))]
    chosen = {}
    for hr, g in dev.groupby("ny_hour"):
        net = g["ret"] - RT / g["open"] * 1e4
        for s in (1, -1):
            x = s * g["ret"] - RT / g["open"] * 1e4
            t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
            if t >= 2:
                chosen[int(hr)] = s
    sel = hh[hh["ny_hour"].isin(chosen) & ~hh["ny_hour"].isin([16, 17])]
    dd = sel["ny_hour"].map(chosen).to_numpy()
    tf = trades_frame(sel.index, dd, sel["open"].to_numpy(), sel["close"].to_numpy(), sel.index,
                      sel.index + pd.Timedelta(minutes=59))
    v.append(("Q3_estacionalidad", f"Q3|horas_elegidas_en_dev|{chosen}", tf))
    # día de la semana (día de trading D1), elegido en desarrollo
    dd1 = d.copy()
    dd1["ret"] = (dd1["close"] - dd1["open"]) / dd1["open"] * 1e4
    dev = dd1[(dd1.index >= PERIODS["dev"][0]) & (dd1.index <= PERIODS["dev"][1])]
    chosen_d = {}
    for wd, g in dev.groupby(dev.index.weekday):
        for s in (1, -1):
            x = s * g["ret"] - RT / g["open"] * 1e4 - (SWAP / g["open"] * 1e4 * 0)   # sin noche: abre y cierra el día
            t = x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))
            if t >= 2:
                chosen_d[int(wd)] = s
    sel = dd1[dd1.index.weekday.isin(list(chosen_d))]
    tf = pd.DataFrame({"detected_time": sel.index,
                       "bruto_r": (sel.index.weekday.map(chosen_d).to_numpy() * sel["ret"]).to_numpy()})
    tf["r"] = tf["bruto_r"] - (RT / sel["open"] * 1e4).to_numpy()
    v.append(("Q3_estacionalidad", f"Q3|dias_elegidos_en_dev|{chosen_d}", tf))
    # cambio de mes: apertura del último día de trading del mes -> cierre del 3.er día del mes siguiente
    idx = d.index
    month = idx.to_period("M")
    rows = []
    for i in range(len(idx) - 4):
        if month[i] != month[i + 1]:
            j = i + 3
            if j < len(idx):
                rows.append((idx[i], d["open"].iloc[i], d["close"].iloc[j], idx[i], idx[j]))
    a = list(zip(*rows))
    tf = pd.DataFrame({"detected_time": a[0]})
    gross = np.array(a[2]) - np.array(a[1])
    nights = np.array([np.sum([3 if w == 4 else 1 for w in d.loc[s:e].index[:-1].weekday]) for s, e in zip(a[3], a[4])])
    tf["bruto_r"] = gross / np.array(a[1]) * 1e4
    tf["r"] = (gross - RT - SWAP * nights) / np.array(a[1]) * 1e4
    v.append(("Q3_estacionalidad", "Q3|cambio_de_mes|compra", tf))
    return v


def q5_gap(m: M1, d: pd.DataFrame, dates: pd.DatetimeIndex) -> list:
    v = []
    prev_dates = pd.DatetimeIndex([dates[0] - pd.Timedelta(days=1)]).append(dates[:-1])
    pc = m.close_before(m.utc(prev_dates, "16:00"))
    op, _ = m.open_at(m.utc(dates, "09:30"), tol_min=1)
    # ATR diario conocido antes de la apertura: el del último día de trading cerrado (cierre 17:00 del día anterior)
    atr_prev = d["atr"].reindex(prev_dates, method="ffill").to_numpy()
    gap = (op - pc) / atr_prev
    for g in (0.25, 0.5):
        for mode in ("contra", "a_favor"):
            for out in ("10:30", "16:00"):
                dd = np.where(np.abs(gap) >= g, -np.sign(gap) if mode == "contra" else np.sign(gap), 0)
                dd = np.nan_to_num(dd)
                te = m.utc(dates, "09:31")
                tx = m.utc(dates, out)
                e, ter = m.open_at(te)
                x = m.close_before(tx)
                v.append(("Q5_gap_apertura", f"Q5|gap{g}ATR|{mode}|sale{out}",
                          trades_frame(dates, dd, e, x, ter, tx)))
    return v


def passes(res: dict) -> bool:
    d, v = res["dev"], res["val"]
    return (d.get("n", 0) >= 100 and (d.get("r") or -1) > 0 and (d.get("t") or 0) >= 2.0
            and v.get("n", 0) >= 50 and (v.get("r") or -1) > 0 and (v.get("t") or 0) >= 1.0)


def main() -> None:
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1(m1)
    d = daily_bars(m1)
    h = hourly_bars(m1)
    nyd = pd.DatetimeIndex(np.unique(m.ny_date[(m.ny_min >= 570) & (m.ny_min < 960)]))
    nyd = nyd[pd.DatetimeIndex(nyd).weekday < 5]
    print("días D1", len(d), "velas H1", len(h), "sesiones NY", len(nyd), flush=True)

    V = []
    V += q1_daily(d)
    V += q1_hourly(h)
    for lvl in (5, 10):
        for sh in (False, True):
            V.append(("Q2_reversion", f"Q2|RSI2<{lvl}|{'compra_y_venta' if sh else 'solo_compras'}", connors(d, lvl, sh)))
    for k in (1.5, 2.0):
        for hold in (1, 3):
            for mode in ("contra", "a_favor"):
                for dirs in ("ambas", "solo_compras"):
                    V.append(("Q2_reversion", f"Q2|H1extremo_k{k}|{hold}h|{mode}|{dirs}", h1_extreme(h, k, hold, mode, dirs)))
    print("Q1/Q2 listos", flush=True)
    V += q3_seasonality(m, h, d, nyd)
    print("Q3 listo", flush=True)
    # Q4: régimen de volatilidad (conocido al cierre del día anterior)
    for reg in ("baja", "alta"):
        okd = (d["atr_rel"] < 1) if reg == "baja" else (d["atr_rel"] > 1)
        sig = np.sign(d["close"] - d["close"].rolling(50).mean()).clip(lower=0).fillna(0)
        V.append(("Q4_regimen_volatilidad", f"Q4|vol_{reg}|media50_compra_fuera",
                  daily_series(d["open"], d["close"], sig.where(okd, 0.0), d["roll_wd"])))
        V.append(("Q4_regimen_volatilidad", f"Q4|vol_{reg}|RSI2<10_compras", connors(d, 10, False, okd)))
        # para H1: régimen del último día de trading cerrado antes de la vela
        h_day = (h.index.tz_localize("UTC").tz_convert(NY) + pd.Timedelta(hours=7)).tz_localize(None).normalize()
        prev = pd.DatetimeIndex(h_day) - pd.Timedelta(days=1)
        okh = pd.Series(okd.reindex(prev, method="ffill").fillna(False).to_numpy(), index=h.index)
        for mode in ("contra", "a_favor"):
            V.append(("Q4_regimen_volatilidad", f"Q4|vol_{reg}|H1extremo_k2.0|1h|{mode}",
                      h1_extreme(h, 2.0, 1, mode, "ambas", okh)))
    V += q5_gap(m, d, nyd)
    print("Q4/Q5 listos", flush=True)

    rows = []
    for fam, key, df in V:
        res = by_period(df) if len(df) else {p: {"n": 0} for p in PERIODS}
        r = {"familia": fam, "clave": key}
        for p in PERIODS:
            for kk in ("n", "r", "t", "bruto", "sharpe_anual"):
                if kk in res[p]:
                    r[f"{p}_{kk}"] = res[p][kk]
        r["cumple"] = passes(res)
        rows.append(r)
    # referencia: comprar y mantener (con swap)
    bh = daily_series(d["open"], d["close"], pd.Series(1.0, index=d.index), d["roll_wd"])
    ref = by_period(bh)
    tab = pd.DataFrame(rows)
    n_total = N_PREVIOUS + len(tab)
    z_bonf = float(norm.ppf(1 - 0.05 / n_total))
    winners = tab[tab["cumple"]].assign(score=lambda x: x[["dev_t", "val_t"]].min(axis=1)).sort_values("score", ascending=False)
    pos = lambda c: int((tab[c].fillna(-1) > 0).sum())  # noqa: E731
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "version_codigo": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                text=True).stdout.strip(),
               "coste": f"spread {SPREAD} + {SLIP} por lado; swap compras {SWAP} por noche (x3 viernes)",
               "unidad": "puntos básicos del precio (pb)", "variantes": len(tab), "cumplen": len(winners),
               "elegida": winners.iloc[0]["clave"] if len(winners) else "NO_OPERAR",
               "dev_positivas": pos("dev_r"), "val_positivas": pos("val_r"),
               "dev_y_val_positivas": int(((tab.dev_r.fillna(-1) > 0) & (tab.val_r.fillna(-1) > 0)).sum()),
               "las_tres_positivas": int(((tab.dev_r.fillna(-1) > 0) & (tab.val_r.fillna(-1) > 0) & (tab.hol_r.fillna(-1) > 0)).sum()),
               "bonferroni": {"variantes_totales_6c_6d": n_total, "t_necesario": round(z_bonf, 2)},
               "comprar_y_mantener": ref,
               "ganadoras": winners.drop(columns=["score"]).to_dict("records")}
    run_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_quant"
    out = ROOT / "data" / "backtests" / run_id
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    (out / "resumen.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (ROOT / "reports" / "quant.json").write_text(json.dumps({**summary, "tabla": tab.round(4).to_dict("records")},
                                                            indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    pd.set_option("display.width", 250)
    cols = [c for c in ["clave", "dev_n", "dev_r", "dev_t", "val_n", "val_r", "val_t", "hol_n", "hol_r", "hol_t",
                        "hol_bruto", "cumple"] if c in tab]
    print(tab.sort_values("dev_t", ascending=False)[cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()
