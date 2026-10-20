"""Fase 7: estrategias publicadas en la web, probadas con nuestros datos y costes (2026-10-20).

No se ejecuta código de terceros: cada regla se reprogramó aquí a partir de su descripción pública.
La rejilla y la regla de selección se fijaron y se guardaron en git ANTES de ejecutar por primera vez.

Familias (fuente entre paréntesis):
  W1 orb5_zarattini   (Zarattini y Aziz 2023, "Can Day Trading Really Be Profitable?", SSRN 4416622)
                      Vela de 9:30-9:35 NY: si cierra arriba, compra a las 9:35; si cierra abajo, vende; si cierra
                      igual, nada. Stop {extremo de la primera vela, 0,10 ATR diario}; objetivo {10 R, ninguno};
                      salida a las 15:57 NY.                                                             = 4
  W2 noise_area       (Zarattini, Aziz y Barbon 2024, "Beat the Market", intraday momentum en SPY)
                      sigma(t) = media de 14 días de |precio(t)/apertura - 1| a la misma hora.
                      Banda superior = max(apertura, cierre previo) x (1 + VM sigma), inferior = min(...) x (1 - VM sigma).
                      Se mira cada media hora de 10:00 a 15:30: por encima de la banda superior, compra; por debajo
                      de la inferior, venta. Stop dinámico: compra sale si el precio < max(banda sup., VWAP);
                      venta sale si > min(banda inf., VWAP). Puede girarse. Cierre a las 15:57.
                      VM {1,0; 1,5} x dirección {ambas, solo compras}                                    = 4
  W3 rebote_gap       (github.com/talalmalikllc-debug/nq-post-open-rebound)
                      Caída nocturna z = (apertura 9:30 / cierre previo - 1) / desviación de 60 días <= umbral y
                      la vela 9:34 cierra por encima de la apertura: compra a las 9:35, sale a las 10:00, sin stop.
                      Umbral {-2,0; -1,5} + espejo exploratorio (venta tras subida z >= 2)               = 3
  W4 orb90_brusco     (github.com/giovannibrusco/nq-intraday-breakout)
                      Rango 9:30-11:00 NY; de 11:00 a 15:30, orden stop en la ruptura del máximo (compra) o del
                      mínimo (venta); máximo 2 operaciones al día, una a la vez. Stop/objetivo {100/200 puntos,
                      0,5/1,0 ATR diario}. Ventas cierran a las 15:57; compras {hasta 5 sesiones con swap, 15:57}. = 4
  W5 momento_intradia (Gao, Han, Li y Zhou 2018; Baltussen et al. 2021)
                      Dirección = signo del rendimiento {cierre previo -> 10:00, cierre previo -> 15:30}; se opera de
                      15:30 a 15:57. Variante extra: solo si |rend. 10:00| >= mediana de los 60 días previos.    = 3
  W6 deriva_nocturna  (anomalía overnight) Compra a las 15:55, vende en la apertura siguiente, con swap.
                      {siempre, solo con la media de 50 días alcista}                                   = 2
                                                                                                    Total = 20
  W7 reversion_diaria (Connors RSI(2); IBS de QuantifiedStrategies, ambos en QQQ) solo compras, velas diarias de la
                      sesión 9:30-16:00. Entrada a las 15:55 NY. IBS: IBS = (cierre-mín)/(máx-mín) < 0,2; salida
                      a las 15:55 del día en que el cierre supera el máximo de la víspera, máximo 5 sesiones.
                      RSI2: RSI(2) < 10 y cierre > media 200; salida cuando cierre > media 5, máximo 5 sesiones.
                      Con swap. {IBS, RSI2} x {siempre, con media 200 alcista}                            = 4
  W8 fvg_ny           (ICT, fair value gap; repos de GitHub "silver-bullet-backtest" y similares)
                      Velas M5 de 9:30 a 11:00 NY. FVG alcista: mínimo(vela 3) > máximo(vela 1); bajista al revés.
                      Primer FVG del día: orden limitada en el borde del hueco (mín. vela 3 en compras) válida 30 min,
                      stop al otro lado de la vela 1, objetivo {2 R, 15:57}; dirección {ambas, media 50 a favor}.  = 4
                                                                                            Total con W7-W8 = 28
  REF orb15_media50   Nuestra pista anterior (rango 15 min, media 50 D1), como referencia; no cuenta.

Costes: spread fijo 1,12 puntos + 0,5 puntos de deslizamiento por lado (también en stops y objetivos). Las compras
que pasan la noche pagan swap: -6,555 puntos por noche y lote unidad, triple el viernes.

Unidad: resultado neto por operación en ATR diario (ATR de 14 días ya cerrado), para comparar familias y sumarlas en
cartera. Se informa también en puntos.

Periodos y selección (iguales a fases anteriores): desarrollo 2021-11..2023, validación 2024, 2025-26 solo
diagnóstico. t agrupado por día. desarrollo: n >= 100 (W3: 10, W7: 40), media > 0, t >= 2 · validación: n >= 50 (W3: 5, W7: 15),
media > 0, t >= 1. Si nada cumple: NO OPERAR.

Cartera: por familia se toma la variante con mayor t en desarrollo (sin mirar validación); se calcula la
correlación de sus resultados diarios y una cartera con el mismo riesgo para cada una.

Uso: python scripts/run_web_candidates.py
"""
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PERIODS = {"dev": ("2021-11-01", "2023-12-31"), "val": ("2024-01-01", "2024-12-31"), "hol": ("2025-01-01", "2026-12-31")}
SPREAD = 1.12
SLIP = 0.5
RT_COST = SPREAD + 2 * SLIP
SWAP_LONG_PER_NIGHT = 6.555
NY = "America/New_York"
RTH0, RTH1 = 570, 960          # 9:30 y 16:00 NY en minutos
FLAT = 957                     # 15:57 NY


# ---------------------------------------------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------------------------------------------
class Data:
    def __init__(self, m1: pd.DataFrame):
        self.t = m1.index.to_numpy().astype("datetime64[ns]")
        self.o, self.h = m1["open"].to_numpy(float), m1["high"].to_numpy(float)
        self.l, self.c = m1["low"].to_numpy(float), m1["close"].to_numpy(float)
        self.v = np.maximum(m1["tickvol"].to_numpy(float), 1.0)
        ny = m1.index.tz_localize("UTC").tz_convert(NY)
        mins = np.asarray(ny.hour * 60 + ny.minute)
        cal = np.asarray(ny.normalize().tz_localize(None))
        rth = (mins >= RTH0) & (mins < RTH1)
        days, inv = np.unique(cal[rth], return_inverse=True)
        self.grid = np.full((len(days), RTH1 - RTH0), -1, dtype=np.int64)      # índice M1 por día y minuto
        self.grid[inv, mins[rth] - RTH0] = np.flatnonzero(rth)
        cnt = (self.grid >= 0).sum(1)
        keep = cnt >= 150
        self.days, self.grid, cnt = days[keep], self.grid[keep], cnt[keep]
        self.full = cnt >= 300                                                   # sin medias sesiones
        self.n = len(self.days)
        # cierre previo de la sesión (última vela antes de las 16:00 del día anterior con datos)
        last = np.array([g[g >= 0][-1] for g in self.grid])
        self.rth_close = self.c[last]
        self.prev_close = np.r_[np.nan, self.rth_close[:-1]]
        # diario de trading (cierre 17:00 NY): ATR 14 y media 50, conocidos antes de abrir (shift 1)
        tday = np.asarray((ny + pd.Timedelta(hours=7)).normalize().tz_localize(None))
        d = m1.groupby(tday).agg(high=("high", "max"), low=("low", "min"), close=("close", "last"), k=("close", "size"))
        d = d[d["k"] >= 120]
        pc = d["close"].shift(1)
        tr = np.maximum(d["high"] - d["low"], np.maximum((d["high"] - pc).abs(), (d["low"] - pc).abs()))
        atr = tr.rolling(14).mean().shift(1)
        bias = np.sign(d["close"] - d["close"].rolling(50).mean()).shift(1)
        self.atr = atr.reindex(self.days).to_numpy()
        self.bias = bias.reindex(self.days).to_numpy()

    def at(self, k: int, minute: int, forward: bool = True, span: int = 5) -> int:
        """Índice de la vela que empieza en `minute` (o la siguiente/anterior con datos, hasta `span` min)."""
        j = minute - RTH0
        rng = range(j, min(j + span, RTH1 - RTH0)) if forward else range(j, max(j - span, -1), -1)
        for q in rng:
            if 0 <= q < RTH1 - RTH0 and self.grid[k, q] >= 0:
                return int(self.grid[k, q])
        return -1

    def price_at(self, k: int, minute: int) -> float:
        """Precio (BID) en el instante `minute`: cierre de la última vela que empezó antes."""
        i = self.at(k, minute - 1, forward=False)
        return self.c[i] if i >= 0 else np.nan


# ---------------------------------------------------------------------------------------------------------------
# Simulación (velas BID; compras cierran contra BID, ventas contra ASK = BID + spread)
# ---------------------------------------------------------------------------------------------------------------
def fill_market(D: Data, i: int, d: int) -> float:
    return D.o[i] + SPREAD + SLIP if d > 0 else D.o[i] - SLIP


def sim(D: Data, i0: int, d: int, entry: float, stop: float | None, target: float | None, i_end: int,
        target_on_entry_bar: bool = True):
    """Desde la vela i0 (incluida) hasta i_end (excluida); salida por tiempo al cierre de i_end - 1.
    Stop antes que objetivo en la misma vela. Devuelve (pnl_puntos, índice_salida, motivo)."""
    i_end = max(i_end, i0 + 1)
    sl = slice(i0, i_end)
    o, h, l, c = D.o[sl], D.h[sl], D.l[sl], D.c[sl]
    L = len(o)
    if d > 0:
        hs = (l <= stop) if stop is not None else np.zeros(L, bool)
        ht = (h >= target) if target is not None else np.zeros(L, bool)
    else:
        hs = (h + SPREAD >= stop) if stop is not None else np.zeros(L, bool)
        ht = (l + SPREAD <= target) if target is not None else np.zeros(L, bool)
    if not target_on_entry_bar and L:
        ht[0] = False
    i_s = int(np.argmax(hs)) if hs.any() else L
    i_t = int(np.argmax(ht)) if ht.any() else L
    if i_s == L and i_t == L:
        k, why = L - 1, "tiempo"
        px = c[k] if d > 0 else c[k] + SPREAD
    elif i_s <= i_t:
        k, why = i_s, "stop"
        px = stop if k == 0 else (min(o[k], stop) if d > 0 else max(o[k] + SPREAD, stop))
    else:
        k, why = i_t, "objetivo"
        px = target
    px = px - SLIP if d > 0 else px + SLIP
    return (px - entry) * d, i0 + k, why


def swap_cost(D: Data, i0: int, i1: int) -> float:
    """Swap de una compra entre las velas i0 e i1: una noche por cada 17:00 NY cruzado; viernes x3."""
    a = pd.Timestamp(D.t[i0]).tz_localize("UTC").tz_convert(NY)
    b = pd.Timestamp(D.t[i1]).tz_localize("UTC").tz_convert(NY)
    total, day = 0.0, (a + pd.Timedelta(hours=7)).normalize()
    while True:
        roll = day + pd.Timedelta(hours=17)
        if roll > b:
            return total
        if roll > a and roll.weekday() < 5:
            total += SWAP_LONG_PER_NIGHT * (3 if roll.weekday() == 4 else 1)
        day += pd.Timedelta(days=1)


def rec(D: Data, k: int, d: int, i0: int, res, risk: float | None = None, swap: float = 0.0) -> dict:
    pnl, ix, why = res
    net = pnl - swap
    return {"day": pd.Timestamp(D.days[k]), "entry_time": pd.Timestamp(D.t[i0]), "exit_time": pd.Timestamp(D.t[ix]),
            "direction": d, "pts": net, "pts_bruto": net + RT_COST + swap, "atr": D.atr[k],
            "r_atr": net / D.atr[k], "r_riesgo": net / risk if risk else np.nan, "motivo": why}


def tradable(D: Data, k: int) -> bool:
    return bool(D.full[k]) and np.isfinite(D.atr[k]) and np.isfinite(D.prev_close[k])


# ---------------------------------------------------------------------------------------------------------------
# Familias
# ---------------------------------------------------------------------------------------------------------------
def w1_orb5(D: Data) -> list[dict]:
    out = []
    for stop_kind in ("vela", "atr10"):
        for tgt_r in (10.0, None):
            rows = []
            for k in range(D.n):
                if not tradable(D, k):
                    continue
                i_a, i_b, i0, i_e = D.at(k, 570, span=1), D.at(k, 574, span=1), D.at(k, 575), D.at(k, FLAT)
                if min(i_a, i_b, i0, i_e) < 0:
                    continue
                d = int(np.sign(D.c[i_b] - D.o[i_a]))
                if d == 0:
                    continue
                px = fill_market(D, i0, d)
                if stop_kind == "vela":
                    stop = D.l[i_a:i_b + 1].min() if d > 0 else D.h[i_a:i_b + 1].max() + SPREAD
                else:
                    stop = px - d * 0.10 * D.atr[k]
                risk = (px - stop) * d
                if risk <= 0:
                    continue
                tgt = px + d * tgt_r * risk if tgt_r else None
                rows.append(rec(D, k, d, i0, sim(D, i0, d, px, stop, tgt, i_e), risk))
            out.append({"familia": "W1_orb5_zarattini", "clave": f"W1|stop_{stop_kind}|obj_{tgt_r or 'fin_dia'}",
                        "df": pd.DataFrame(rows)})
    return out


def w2_noise(D: Data) -> list[dict]:
    checks = list(range(600, 931, 30))                      # 10:00 ... 15:30
    opens = np.array([D.o[D.at(k, 570, span=1)] if D.at(k, 570, span=1) >= 0 else np.nan for k in range(D.n)])
    P = np.array([[D.price_at(k, m) for m in checks] for k in range(D.n)])
    move = np.abs(P / opens[:, None] - 1)
    sigma = pd.DataFrame(move).rolling(14, min_periods=14).mean().shift(1).to_numpy()
    # VWAP de la sesión en cada control (precio típico x volumen de ticks)
    vw = np.full_like(P, np.nan)
    for k in range(D.n):
        i_a = D.at(k, 570, span=1)
        if i_a < 0:
            continue
        for j, m in enumerate(checks):
            i_b = D.at(k, m - 1, forward=False)
            if i_b < i_a:
                continue
            tp = (D.h[i_a:i_b + 1] + D.l[i_a:i_b + 1] + D.c[i_a:i_b + 1]) / 3
            vv = D.v[i_a:i_b + 1]
            vw[k, j] = (tp * vv).sum() / vv.sum()
    out = []
    for vm in (1.0, 1.5):
        for dirs in ("ambas", "solo_compras"):
            rows = []
            for k in range(D.n):
                if not tradable(D, k) or not np.isfinite(sigma[k]).all() or not np.isfinite(opens[k]):
                    continue
                ub = max(opens[k], D.prev_close[k]) * (1 + vm * sigma[k])
                lb = min(opens[k], D.prev_close[k]) * (1 - vm * sigma[k])
                i_e = D.at(k, FLAT)
                pos, i_in, px_in = 0, -1, 0.0

                def close_pos(i_x: int, why: str):
                    px = (D.o[i_x] - SLIP) if pos > 0 else (D.o[i_x] + SPREAD + SLIP)
                    rows.append(rec(D, k, pos, i_in, ((px - px_in) * pos, i_x, why)))

                for j, m in enumerate(checks):
                    p = P[k, j]
                    i_x = D.at(k, m)
                    if not np.isfinite(p) or i_x < 0:
                        continue
                    if pos > 0 and p < max(ub[j], vw[k, j]):
                        close_pos(i_x, "stop_dinamico")
                        pos = 0
                    elif pos < 0 and p > min(lb[j], vw[k, j]):
                        close_pos(i_x, "stop_dinamico")
                        pos = 0
                    if pos == 0:
                        d = 1 if p > ub[j] else (-1 if (p < lb[j] and dirs == "ambas") else 0)
                        if d:
                            pos, i_in, px_in = d, i_x, fill_market(D, i_x, d)
                if pos and i_e > 0:
                    px = D.c[i_e - 1] - SLIP if pos > 0 else D.c[i_e - 1] + SPREAD + SLIP
                    rows.append(rec(D, k, pos, i_in, ((px - px_in) * pos, i_e - 1, "tiempo")))
            out.append({"familia": "W2_noise_area", "clave": f"W2|VM{vm}|{dirs}", "df": pd.DataFrame(rows)})
    return out


def w3_gap(D: Data) -> list[dict]:
    opens = np.array([D.o[D.at(k, 570, span=1)] if D.at(k, 570, span=1) >= 0 else np.nan for k in range(D.n)])
    ret = opens / D.prev_close - 1
    sd = pd.Series(ret).rolling(60, min_periods=60).std().shift(1).to_numpy()
    z = ret / sd
    out = []
    for thr, side in ((-2.0, 1), (-1.5, 1), (2.0, -1)):
        rows = []
        for k in range(D.n):
            if not tradable(D, k) or not np.isfinite(z[k]):
                continue
            if (side > 0 and z[k] > thr) or (side < 0 and z[k] < thr):
                continue
            i_b, i0, i_e = D.at(k, 574, span=1), D.at(k, 575), D.at(k, 600)
            if min(i_b, i0, i_e) < 0 or (D.c[i_b] - opens[k]) * side <= 0:
                continue
            px = fill_market(D, i0, side)
            rows.append(rec(D, k, side, i0, sim(D, i0, side, px, None, None, i_e)))
        name = f"W3|z<={thr}|compra" if side > 0 else f"W3|z>={thr}|venta_espejo"
        out.append({"familia": "W3_rebote_gap", "clave": name, "df": pd.DataFrame(rows)})
    return out


def w4_orb90(D: Data) -> list[dict]:
    out = []
    for size in ("fijo", "atr"):
        for longs in ("multidia", "intradia"):
            rows = []
            busy_until = np.datetime64("1970-01-01")
            for k in range(D.n):
                if not tradable(D, k):
                    continue
                i_a, i_b = D.at(k, 570, span=1), D.at(k, 659, forward=False)
                i_s, i_last, i_e = D.at(k, 660), D.at(k, 929, forward=False), D.at(k, FLAT)
                if min(i_a, i_b, i_s, i_last, i_e) < 0:
                    continue
                hi, lo = D.h[i_a:i_b + 1].max(), D.l[i_a:i_b + 1].min()
                sd, td = (100.0, 200.0) if size == "fijo" else (0.5 * D.atr[k], 1.0 * D.atr[k])
                n_tr, i = 0, i_s
                while n_tr < 2 and i <= i_last:
                    if D.t[i] < busy_until:
                        i += 1
                        continue
                    up = D.h[i] + SPREAD >= hi
                    dn = D.l[i] <= lo
                    if not (up or dn):
                        i += 1
                        continue
                    d = 1 if up and not dn else (-1 if dn and not up else (1 if D.o[i] + SPREAD >= hi else -1))
                    px = (max(D.o[i] + SPREAD, hi) + SLIP) if d > 0 else (min(D.o[i], lo) - SLIP)
                    stop, tgt = px - d * sd, px + d * td
                    if d > 0 and longs == "multidia":
                        k5 = min(k + 4, D.n - 1)
                        i_end = D.at(k5, FLAT)
                        i_end = i_end if i_end > i else i_e
                    else:
                        i_end = i_e
                    res = sim(D, i, d, px, stop, tgt, i_end, target_on_entry_bar=False)
                    sw = swap_cost(D, i, res[1]) if d > 0 else 0.0
                    rows.append(rec(D, k, d, i, res, sd, sw))
                    n_tr += 1
                    busy_until = D.t[res[1]] + np.timedelta64(1, "m")
                    i = res[1] + 1
            out.append({"familia": "W4_orb90_brusco", "clave": f"W4|{size}|compras_{longs}", "df": pd.DataFrame(rows)})
    return out


def w5_momentum(D: Data) -> list[dict]:
    r10 = np.array([D.price_at(k, 600) for k in range(D.n)]) / D.prev_close - 1
    r1530 = np.array([D.price_at(k, 930) for k in range(D.n)]) / D.prev_close - 1
    med = pd.Series(np.abs(r10)).rolling(60, min_periods=60).median().shift(1).to_numpy()
    out = []
    for name, sig, filt in (("gao_10h", r10, False), ("gao_10h_fuerte", r10, True), ("baltussen_1530", r1530, False)):
        rows = []
        for k in range(D.n):
            if not tradable(D, k) or not np.isfinite(sig[k]) or sig[k] == 0:
                continue
            if filt and not (np.isfinite(med[k]) and abs(r10[k]) >= med[k]):
                continue
            i0, i_e = D.at(k, 930), D.at(k, FLAT)
            if min(i0, i_e) < 0:
                continue
            d = int(np.sign(sig[k]))
            rows.append(rec(D, k, d, i0, sim(D, i0, d, fill_market(D, i0, d), None, None, i_e)))
        out.append({"familia": "W5_momento_intradia", "clave": f"W5|{name}", "df": pd.DataFrame(rows)})
    return out


def w6_overnight(D: Data) -> list[dict]:
    out = []
    for filt in ("siempre", "media50"):
        rows = []
        for k in range(D.n - 1):
            if not tradable(D, k) or (filt == "media50" and not D.bias[k] > 0):
                continue
            i0, i1 = D.at(k, 955), D.at(k + 1, 570, span=1)
            if min(i0, i1) < 0:
                continue
            px = fill_market(D, i0, 1)
            res = sim(D, i0, 1, px, None, None, i1 + 1)
            rows.append(rec(D, k, 1, i0, res, None, swap_cost(D, i0, i1)))
        out.append({"familia": "W6_deriva_nocturna", "clave": f"W6|{filt}", "df": pd.DataFrame(rows)})
    return out


def rsi(x: pd.Series, n: int) -> pd.Series:
    dlt = x.diff()
    up = dlt.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-dlt.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn)


def w7_daily_reversion(D: Data) -> list[dict]:
    hi = np.array([D.h[g[g >= 0]].max() for g in D.grid])
    lo = np.array([D.l[g[g >= 0]].min() for g in D.grid])
    cl = pd.Series(np.array([D.price_at(k, 955) for k in range(D.n)]))   # precio a las 15:55, cuando se decide
    ibs = (cl - lo) / (hi - lo)
    r2, s5, s200 = rsi(cl, 2), cl.rolling(5).mean(), cl.rolling(200).mean()
    out = []
    for name in ("IBS", "RSI2"):
        for filt in ("siempre", "media200"):
            rows, k = [], 200
            while k < D.n - 1:
                ok = tradable(D, k) and D.at(k, 955) >= 0
                sig = (ibs[k] < 0.2) if name == "IBS" else (r2[k] < 10)
                if filt == "media200":                       # en RSI2 es la regla original de Connors
                    sig = sig and cl[k] > s200[k]
                if not (ok and sig):
                    k += 1
                    continue
                i0 = D.at(k, 955)
                px = fill_market(D, i0, 1)
                j = k + 1
                while j < min(k + 5, D.n - 1):
                    done = cl[j] > hi[j - 1] if name == "IBS" else cl[j] > s5[j]
                    if done and D.at(j, 955) >= 0:
                        break
                    j += 1
                i1 = D.at(j, 955)
                if i1 < 0:
                    k += 1
                    continue
                res = (D.o[i1] - SLIP - px, i1, "regla")
                rows.append(rec(D, k, 1, i0, res, None, swap_cost(D, i0, i1)))
                k = j + 1
            out.append({"familia": "W7_reversion_diaria", "clave": f"W7|{name}|{filt}", "df": pd.DataFrame(rows)})
    return out


def w8_fvg(D: Data) -> list[dict]:
    out = []
    for tgt_kind in ("2R", "fin_dia"):
        for dirs in ("ambas", "media50"):
            rows = []
            for k in range(D.n):
                if not tradable(D, k):
                    continue
                bars = []                                    # velas M5 cerradas: (h, l, minuto de cierre)
                for m in range(570, 660, 5):
                    i_a, i_b = D.at(k, m, span=1), D.at(k, m + 4, forward=False, span=1)
                    if i_a < 0 or i_b < 0:
                        bars = None
                        break
                    bars.append((D.h[i_a:i_b + 1].max(), D.l[i_a:i_b + 1].min(), m + 5))
                if not bars:
                    continue
                for q in range(2, len(bars)):
                    h1, l1, _ = bars[q - 2]
                    h3, l3, t3 = bars[q]
                    d = 1 if l3 > h1 else (-1 if h3 < l1 else 0)
                    if not d:
                        continue
                    if dirs == "media50" and not d * (D.bias[k] if np.isfinite(D.bias[k]) else 0) > 0:
                        break
                    lim = l3 if d > 0 else h3                # borde del hueco más cercano al precio
                    stop = l1 if d > 0 else h1 + SPREAD
                    i0, i_e = D.at(k, t3), D.at(k, FLAT)
                    if min(i0, i_e) < 0:
                        break
                    i_lim = min(i0 + 30, i_e)
                    hit = (D.l[i0:i_lim] + SPREAD <= lim) if d > 0 else (D.h[i0:i_lim] >= lim)
                    if not hit.any():
                        break
                    i = i0 + int(np.argmax(hit))
                    px = min(lim, D.o[i] + SPREAD) if d > 0 else max(lim, D.o[i])
                    risk = (px - stop) * d
                    if risk <= 0:
                        break
                    tgt = px + d * 2 * risk if tgt_kind == "2R" else None
                    res = sim(D, i, d, px, stop, tgt, i_e, target_on_entry_bar=False)
                    r = rec(D, k, d, i, res, risk)
                    r["pts_bruto"] = r["pts"] + SPREAD + SLIP          # entrada limitada: sin deslizamiento
                    rows.append(r)
                    break
            out.append({"familia": "W8_fvg_ny", "clave": f"W8|{tgt_kind}|{dirs}", "df": pd.DataFrame(rows)})
    return out


def ref_orb15(D: Data) -> list[dict]:
    rows = []
    for k in range(D.n):
        if not tradable(D, k) or not np.isfinite(D.bias[k]) or D.bias[k] == 0:
            continue
        i_a, i_b, i_e = D.at(k, 570, span=1), D.at(k, 584, forward=False), D.at(k, FLAT)
        if min(i_a, i_b, i_e) < 0:
            continue
        hi, lo = D.h[i_a:i_b + 1].max(), D.l[i_a:i_b + 1].min()
        for m in range(589, 690, 5):                       # cierres M5 de 9:50 a 11:30
            i_c = D.at(k, m, forward=False, span=1)
            if i_c < 0:
                continue
            d = 1 if D.c[i_c] > hi else (-1 if D.c[i_c] < lo else 0)
            if d:
                if d * D.bias[k] > 0:
                    i0 = D.at(k, m + 1)
                    if i0 > 0:
                        px = fill_market(D, i0, d)
                        stop = lo if d > 0 else hi + SPREAD
                        risk = (px - stop) * d
                        if risk > 0:
                            rows.append(rec(D, k, d, i0, sim(D, i0, d, px, stop, None, i_e), risk))
                break
    return [{"familia": "REF_orb15_media50", "clave": "REF|orb15|media50|fin_dia", "df": pd.DataFrame(rows)}]


# ---------------------------------------------------------------------------------------------------------------
# Estadística y cartera
# ---------------------------------------------------------------------------------------------------------------
def cluster_stats(df: pd.DataFrame, col: str) -> dict:
    x = df.dropna(subset=[col])
    n = len(x)
    if n < 2:
        return {"n": n, "r": float(x[col].mean()) if n else None, "t": None}
    g = x.groupby(x["day"])[col]
    S, N = g.sum(), g.count()
    mean = S.sum() / N.sum()
    se = np.sqrt(((S - mean * N) ** 2).sum()) / N.sum()
    return {"n": n, "r": round(float(mean), 4), "t": round(float(mean / se), 2) if se > 0 else None,
            "aciertos": round(float((x[col] > 0).mean()), 3)}


def in_period(df: pd.DataFrame, p: str) -> pd.DataFrame:
    a, b = PERIODS[p]
    return df[(df["day"] >= pd.Timestamp(a)) & (df["day"] <= pd.Timestamp(b))]


def passes(res: dict, fam: str) -> bool:
    dn, vn = (10, 5) if fam.startswith("W3") else ((40, 15) if fam.startswith("W7") else (100, 50))
    d, v = res["dev"], res["val"]
    return (d.get("n", 0) >= dn and (d.get("r") or -1) > 0 and (d.get("t") or 0) >= 2.0
            and v.get("n", 0) >= vn and (v.get("r") or -1) > 0 and (v.get("t") or 0) >= 1.0)


def portfolio(variants: list[dict], tab: pd.DataFrame, days: np.ndarray) -> dict:
    """Mejor variante de cada familia por t de desarrollo; resultado diario en ATR y correlaciones."""
    best = (tab.dropna(subset=["dev_t"]).sort_values("dev_t", ascending=False).groupby("familia").head(1))
    series = {}
    for v in variants:
        if v["clave"] in set(best["clave"]) and len(v["df"]):
            series[v["clave"]] = v["df"].groupby("day")["r_atr"].sum()
    daily = pd.DataFrame(series).reindex(pd.DatetimeIndex(days)).fillna(0.0)
    out = {"variantes": list(series), "correlacion_diaria": daily.corr().round(2).to_dict()}
    for p in PERIODS:
        a, b = PERIODS[p]
        y = daily[(daily.index >= pd.Timestamp(a)) & (daily.index <= pd.Timestamp(b))]
        tot = y.mean(axis=1)                                 # mismo riesgo para cada estrategia
        cum = tot.cumsum()
        out[p] = {"dias": int(len(y)), "media_diaria_atr": round(float(tot.mean()), 5),
                  "t": round(float(tot.mean() / (tot.std(ddof=1) / np.sqrt(len(tot)))), 2) if len(tot) > 2 else None,
                  "max_caida_atr": round(float((cum.cummax() - cum).max()), 3),
                  "por_estrategia_atr_dia": y.mean().round(5).to_dict()}
    return out


def main() -> None:
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    D = Data(m1)
    print(f"{D.n} sesiones ({int(D.full.sum())} completas)", flush=True)
    variants: list[dict] = []
    for fn in (w1_orb5, w2_noise, w3_gap, w4_orb90, w5_momentum, w6_overnight, w7_daily_reversion, w8_fvg, ref_orb15):
        variants += fn(D)
        print(fn.__name__, "listo", flush=True)

    rows = []
    for v in variants:
        df = v["df"]
        r = {"familia": v["familia"], "clave": v["clave"]}
        res = {}
        for p in PERIODS:
            y = in_period(df, p) if len(df) else df
            st = cluster_stats(y, "r_atr") if len(y) else {"n": 0}
            res[p] = st
            r[f"{p}_n"], r[f"{p}_r"], r[f"{p}_t"] = st.get("n"), st.get("r"), st.get("t")
            r[f"{p}_aciertos"] = st.get("aciertos")
            r[f"{p}_pts"] = round(float(y["pts"].mean()), 2) if len(y) else None
            r[f"{p}_pts_bruto"] = round(float(y["pts_bruto"].mean()), 2) if len(y) else None
        if len(df):
            yr = df.groupby(df["day"].dt.year)["r_atr"].mean().round(4)
            r.update({f"año_{a}": x for a, x in yr.items()})
            cum = df.sort_values("exit_time")["r_atr"].cumsum()
            r["peor_racha_atr"] = round(float((cum.cummax() - cum).max()), 2)
        r["cumple"] = not v["familia"].startswith("REF") and passes(res, v["familia"])
        rows.append(r)
    tab = pd.DataFrame(rows)
    tested = tab[~tab["familia"].str.startswith("REF")]
    winners = tested[tested["cumple"]]
    summary = {"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "version_codigo": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                text=True).stdout.strip(),
               "coste": f"spread {SPREAD} + deslizamiento {SLIP} por lado; swap compras {SWAP_LONG_PER_NIGHT}/noche",
               "variantes_probadas": len(tested), "cumplen": len(winners),
               "elegidas": winners["clave"].tolist() or "NO_OPERAR",
               "las_tres_positivas": int(((tested.dev_r.fillna(-1) > 0) & (tested.val_r.fillna(-1) > 0)
                                          & (tested.hol_r.fillna(-1) > 0)).sum()),
               "cartera": portfolio(variants, tab, D.days[D.full])}
    run_id = f"{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_web"
    out = ROOT / "data" / "backtests" / run_id
    out.mkdir(parents=True, exist_ok=True)
    tab.to_csv(out / "variantes.csv", index=False)
    for v in variants:
        if len(v["df"]):
            v["df"].to_csv(out / (v["clave"].replace("|", "_").replace("<=", "le").replace(">=", "ge") + ".csv"),
                           index=False)
    (out / "resumen.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "web_candidatos.json").write_text(
        json.dumps({**summary, "tabla": tab.round(4).to_dict("records")}, indent=1, ensure_ascii=False, default=str),
        encoding="utf-8")
    pd.set_option("display.width", 250)
    cols = ["clave", "dev_n", "dev_r", "dev_t", "val_n", "val_r", "val_t", "hol_n", "hol_r", "hol_t",
            "hol_pts", "hol_pts_bruto", "peor_racha_atr", "cumple"]
    print(tab[cols].to_string(index=False))
    print(json.dumps(summary, indent=1, ensure_ascii=False, default=str))
    print("Guardado en", out)


if __name__ == "__main__":
    main()
