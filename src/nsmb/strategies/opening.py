"""Estrategias de la apertura de Nueva York (módulos de la cartera, reglas congeladas el 2026-10-20).

Son las mismas reglas que midieron scripts/run_ideas.py (F5b), scripts/run_web.py (W1, W3) y run_profundo.py:
  - orb15: rango 9:30-9:45 NY; primera vela M5 que cierra fuera antes de 11:30, solo a favor de la media de 50 días;
           stop al otro lado del rango; sin objetivo; salida 15:57 NY.
  - orb5:  dirección de la primera vela de 5 min (9:30-9:35) si no es casi plana; stop en su extremo opuesto;
           objetivo 10 R; salida 15:57 NY.
  - noise: banda = máx/mín(apertura, cierre previo) +- media de |movimiento desde la apertura| de las 14 sesiones
           anteriores a esa hora; revisión cada 30 min (10:00-15:30); fuera de la banda => entrar; volver a cruzarla
           => salir; stop de protección a 2 medias bandas; salida 15:57 NY.

Todo se calcula solo con velas M1 CERRADAS (índice = apertura de la vela, en UTC). Un evento se conoce al cierre de
la vela que lo produce (`detected_time`). Con datos cortados en T, los eventos son exactamente los de los datos
completos con detected_time <= T (lo comprueba tests/test_opening.py).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

NY = "America/New_York"
OPEN_MIN, ORB15_END, ORB_LIMIT, FLAT_MIN = 570, 585, 690, 957     # 9:30, 9:45, 11:30, 15:57
NOISE_CHECKS = tuple(range(600, 931, 30))                          # 10:00 ... 15:30
NOISE_LOOKBACK, NOISE_HARD_STOP = 14, 2.0
ORB5_TARGET_R, ORB5_FLAT_FRAC = 10.0, 0.05
# Días sin mercado de contado en EE. UU. (NYSE). El CFD cotiza, pero el backtest no operó esos días.
NYSE_HOLIDAYS = frozenset(pd.Timestamp(d) for d in (
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31", "2027-06-18",
    "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"))


@dataclass(frozen=True)
class OpeningEvent:
    kind: str                 # "abrir" | "cerrar"
    strategy: str             # orb15 | orb5 | noise
    client_id: str            # único por estrategia, día y número de entrada
    direction: int
    detected_time: pd.Timestamp   # UTC: cierre de la vela que produce el evento
    stop: float | None = None     # nivel de stop sobre el BID (en ventas hay que sumar el spread)
    target_r: float | None = None
    reason: str = ""
    stop_dist: float | None = None    # si se da (y stop es None): stop a esta distancia del precio real de entrada
    max_spread: float | None = None   # no abrir si el spread (en precio) lo supera


def _ny(m1: pd.DataFrame) -> pd.DataFrame:
    ny = m1.index.tz_localize("UTC").tz_convert(NY)
    return m1.assign(mins=np.asarray(ny.hour * 60 + ny.minute), date=np.asarray(ny.normalize().tz_localize(None)))


def sma50_bias(m1: pd.DataFrame, asof: pd.Timestamp) -> float:
    """Signo de (cierre diario - media 50) con el último día de trading CERRADO antes de `asof` (día = cierre 17:00 NY)."""
    ny = m1.index.tz_localize("UTC").tz_convert(NY)
    day = (ny + pd.Timedelta(hours=7)).normalize().tz_localize(None)
    g = m1.groupby(day)
    d = pd.DataFrame({"close": g["close"].last(), "n": g.size(),
                      "close_time": g.apply(lambda x: x.index[-1]) + pd.Timedelta(minutes=1)})
    d = d[d["n"] >= 120]
    sma = d["close"].rolling(50, min_periods=50).mean()
    s = np.sign(d["close"] - sma)[d["close_time"] <= asof].dropna()
    return float(s.iloc[-1]) if len(s) else 0.0


def orb15(day: pd.DataFrame, date, bias: float) -> list[OpeningEvent]:
    rng = day[(day["mins"] >= OPEN_MIN) & (day["mins"] < ORB15_END)]
    if len(rng) < 13 or bias == 0:
        return []
    hi, lo = rng["high"].max(), rng["low"].min()
    post = day[(day["mins"] >= ORB15_END) & (day["mins"] < ORB_LIMIT)]
    last_min = int(day["mins"].iloc[-1])
    for b5, blk in post.groupby(post["mins"] // 5, sort=True):
        # la vela M5 está cerrada si existe su último minuto o ya hay velas posteriores
        if not (blk["mins"].iloc[-1] == b5 * 5 + 4 or last_min > b5 * 5 + 4):
            break
        c = blk["close"].iloc[-1]
        d = 1 if c > hi else (-1 if c < lo else 0)
        if d == 0:
            continue
        if d * bias <= 0:
            return []          # la primera ruptura va contra la media: ese día no se opera
        t = blk.index[-1] + pd.Timedelta(minutes=1)
        return [OpeningEvent("abrir", "orb15", f"orb15-{date:%Y%m%d}-1", d, t, lo if d > 0 else hi)]
    return []


def orb5(day: pd.DataFrame, date) -> list[OpeningEvent]:
    f = day[(day["mins"] >= OPEN_MIN) & (day["mins"] < OPEN_MIN + 5)]
    if len(f) != 5 or not (day["mins"] >= OPEN_MIN + 4).any():
        return []
    o, h, l, c = f["open"].iloc[0], f["high"].max(), f["low"].min(), f["close"].iloc[-1]
    if h <= l or abs(c - o) < ORB5_FLAT_FRAC * (h - l):
        return []
    d = 1 if c > o else -1
    t = f.index[-1] + pd.Timedelta(minutes=1)
    return [OpeningEvent("abrir", "orb5", f"orb5-{date:%Y%m%d}-1", d, t, l if d > 0 else h, ORB5_TARGET_R)]


def noise(day: pd.DataFrame, date, history: list[pd.DataFrame], prev_close: float) -> list[OpeningEvent]:
    """history: las 14 sesiones completas anteriores (velas 9:30-15:56 NY)."""
    if len(history) < NOISE_LOOKBACK or day.empty or day["mins"].iloc[0] != OPEN_MIN:
        return []
    mv = []
    for h in history[-NOISE_LOOKBACK:]:
        o = h["open"].iloc[0]
        mv.append(pd.Series(np.abs(h["close"].to_numpy() / o - 1), index=h["mins"].to_numpy()))
    sigma = pd.concat(mv, axis=1).mean(axis=1)
    o = day["open"].iloc[0]
    up_ref, lo_ref = max(o, prev_close), min(o, prev_close)
    g = day.set_index("mins")
    ev, pos, n, entry_ref, stop = [], 0, 0, 0.0, 0.0
    for c in NOISE_CHECKS:
        if c - 1 not in g.index or c not in sigma.index:
            continue
        # el stop de protección pudo saltar entre la entrada y esta revisión
        if pos != 0:
            seg = g.loc[(g.index >= entry_min) & (g.index < c)]
            hit = (seg["low"] <= stop) if pos > 0 else (seg["high"] >= stop)
            if hit.any():
                ev.append(OpeningEvent("cerrar", "noise", f"noise-{date:%Y%m%d}-{n}", pos,
                                       day.index[day["mins"] == hit.idxmax()][0] + pd.Timedelta(minutes=1), reason="stop"))
                pos = 0
        s = sigma.loc[c]
        U, L = up_ref * (1 + s), lo_ref * (1 - s)
        px = g.at[c - 1, "close"]
        t = day.index[day["mins"] == c - 1][0] + pd.Timedelta(minutes=1)
        if (pos > 0 and px < U) or (pos < 0 and px > L):
            ev.append(OpeningEvent("cerrar", "noise", f"noise-{date:%Y%m%d}-{n}", pos, t, reason="banda"))
            pos = 0
        if pos == 0:
            d = 1 if px > U else (-1 if px < L else 0)
            if d:
                n += 1
                unit = (U - L) / 2
                entry_ref, entry_min, pos = px, c, d
                stop = entry_ref - d * NOISE_HARD_STOP * unit
                ev.append(OpeningEvent("abrir", "noise", f"noise-{date:%Y%m%d}-{n}", d, t, stop))
    return ev


def day_events(m1: pd.DataFrame, now: pd.Timestamp | None = None) -> list[OpeningEvent]:
    """Eventos de la sesión de NY más reciente presente en `m1` (solo velas cerradas antes de `now`)."""
    if now is not None:
        m1 = m1[m1.index + pd.Timedelta(minutes=1) <= now]
    if m1.empty:
        return []
    x = _ny(m1)
    rth = x[(x["mins"] >= OPEN_MIN) & (x["mins"] < FLAT_MIN)]
    if rth.empty:
        return []
    date = rth["date"].iloc[-1]
    if pd.Timestamp(date) in NYSE_HOLIDAYS:
        return []
    day = rth[rth["date"] == date]
    prev_days = [g for k, g in rth[rth["date"] < date].groupby("date") if g["mins"].iloc[0] == OPEN_MIN and len(g) >= 350]
    first_t = day.index[0]
    ev = orb15(day, date, sma50_bias(m1, first_t)) + orb5(day, date)
    if prev_days:
        ev += noise(day, date, prev_days, prev_days[-1]["close"].iloc[-1])
    return sorted(ev, key=lambda e: (e.detected_time, e.kind != "cerrar"))


def flat_time_utc(date) -> pd.Timestamp:
    """Hora UTC (sin zona) de la salida forzada de las 15:57 NY de ese día."""
    return (pd.Timestamp(date).tz_localize(NY) + pd.Timedelta(minutes=FLAT_MIN)).tz_convert("UTC").tz_localize(None)
