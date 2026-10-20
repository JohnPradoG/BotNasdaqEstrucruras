"""Motor de estructura de mercado, causal (vela a vela).

Para cada vela t se procesan, en este orden y SOLO con datos de velas <= t:
  1. rupturas, barridos, retesteos, falsas rupturas y figuras pendientes (con niveles conocidos antes de t);
  2. pivotes que se confirman al cierre de t (ver pivots.py);
  3. FVG e impulsos de la vela t.
Cada evento lleva `t` = índice de la vela en cuyo CIERRE se conoce. Ver docs/estructuras.md para
las definiciones matemáticas, tolerancias, confirmación e invalidación de cada detector.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .pivots import Pivot, fractal_pivots


@dataclass
class StructureParams:
    pivot_left: int = 3
    pivot_right: int = 3
    min_swing_atr: float = 0.5
    break_buffer_atr: float = 0.0
    retest_tolerance_atr: float = 0.25
    retest_max_bars: int = 12
    false_break_bars: int = 3
    fvg_min_atr: float = 0.3
    impulse_range_atr: float = 1.8
    impulse_body_ratio: float = 0.6
    double_tolerance_atr: float = 0.35
    double_min_bars: int = 6
    double_min_depth_atr: float = 1.0
    hs_shoulder_tolerance_atr: float = 0.6
    hs_head_min_atr: float = 0.3

    @classmethod
    def from_cfg(cls, s: dict) -> "StructureParams":
        keys = cls.__dataclass_fields__.keys()
        return cls(**{k: v for k, v in s.items() if k in keys})


@dataclass
class _Level:
    price: float
    idx: int
    broken: bool = False
    swept: bool = False


@dataclass
class _Pending:
    kind: str
    direction: int
    level: float
    start: int
    expire: int
    data: dict = field(default_factory=dict)


class StructureEngine:
    def __init__(self, params: StructureParams | None = None):
        self.p = params or StructureParams()

    def run(self, df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        p = self.p
        o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        a = df["atr"].to_numpy(float)
        r = df["rsi"].to_numpy(float) if "rsi" in df else np.full(len(df), np.nan)
        n = len(df)
        by_confirm: dict[int, list[Pivot]] = {}
        for pv in fractal_pivots(h, l, p.pivot_left, p.pivot_right):
            by_confirm.setdefault(pv.confirm_idx, []).append(pv)

        swings: list[Pivot] = []
        hi_lv: _Level | None = None
        lo_lv: _Level | None = None
        trend = 0  # +1 alcista, -1 bajista, 0 rango/indefinido
        pend: list[_Pending] = []
        ev: list[dict] = []
        st_trend = np.zeros(n, dtype=np.int8)
        st_hi = np.full(n, np.nan)
        st_lo = np.full(n, np.nan)
        st_hi_lab = np.empty(n, dtype=object)
        st_lo_lab = np.empty(n, dtype=object)
        last_h_lab = last_l_lab = ""

        def emit(t, typ, d, level=np.nan, extreme=np.nan, protective=np.nan, **aux):
            ev.append({"t": t, "type": typ, "direction": d, "level": level, "extreme": extreme,
                       "protective": protective, "trend_before": int(trend), **aux})

        for t in range(n):
            at = a[t]
            if not np.isfinite(at) or at <= 0:
                st_trend[t] = trend
                st_hi_lab[t], st_lo_lab[t] = last_h_lab, last_l_lab
                continue

            # ---- 1. rupturas y barridos de los niveles vigentes ------------------------------
            if hi_lv is not None and not hi_lv.broken:
                if c[t] > hi_lv.price + p.break_buffer_atr * at:
                    typ = "choch" if trend == -1 else "bos"
                    prot = lo_lv.price if lo_lv is not None else np.nan
                    emit(t, typ, +1, hi_lv.price, h[t], prot, level_idx=hi_lv.idx,
                         break_size_atr=(c[t] - hi_lv.price) / at,
                         break_body_ratio=abs(c[t] - o[t]) / max(h[t] - l[t], 1e-12))
                    hi_lv.broken = True
                    pend.append(_Pending("retest", +1, hi_lv.price, t, t + p.retest_max_bars,
                                         {"origin": typ, "protective": prot, "break_t": t, "ext": l[t]}))
                    pend.append(_Pending("false_break", -1, hi_lv.price, t, t + p.false_break_bars,
                                         {"ext": h[t], "origin": typ}))
                elif h[t] > hi_lv.price and not hi_lv.swept:
                    hi_lv.swept = True
                    emit(t, "sweep", -1, hi_lv.price, h[t], h[t], level_idx=hi_lv.idx,
                         sweep_depth_atr=(h[t] - hi_lv.price) / at, close_back_atr=(hi_lv.price - c[t]) / at)
            if lo_lv is not None and not lo_lv.broken:
                if c[t] < lo_lv.price - p.break_buffer_atr * at:
                    typ = "choch" if trend == +1 else "bos"
                    prot = hi_lv.price if hi_lv is not None else np.nan
                    emit(t, typ, -1, lo_lv.price, l[t], prot, level_idx=lo_lv.idx,
                         break_size_atr=(lo_lv.price - c[t]) / at,
                         break_body_ratio=abs(c[t] - o[t]) / max(h[t] - l[t], 1e-12))
                    lo_lv.broken = True
                    pend.append(_Pending("retest", -1, lo_lv.price, t, t + p.retest_max_bars,
                                         {"origin": typ, "protective": prot, "break_t": t, "ext": h[t]}))
                    pend.append(_Pending("false_break", +1, lo_lv.price, t, t + p.false_break_bars,
                                         {"ext": l[t], "origin": typ}))
                elif l[t] < lo_lv.price and not lo_lv.swept:
                    lo_lv.swept = True
                    emit(t, "sweep", +1, lo_lv.price, l[t], l[t], level_idx=lo_lv.idx,
                         sweep_depth_atr=(lo_lv.price - l[t]) / at, close_back_atr=(c[t] - lo_lv.price) / at)

            # ---- pendientes: retesteo, falsa ruptura, figuras -----------------------------------
            keep: list[_Pending] = []
            for q in pend:
                if q.start == t:
                    keep.append(q)
                    continue
                tol = p.retest_tolerance_atr * at
                done = False
                if q.kind == "retest":
                    if q.direction == +1:
                        q.data["ext"] = min(q.data["ext"], l[t])
                        if c[t] < q.level - tol:
                            done = True
                        elif l[t] <= q.level + tol and c[t] > q.level:
                            emit(t, "retest", +1, q.level, q.data["ext"], q.data["protective"], origin=q.data["origin"],
                                 bars_since_break=t - q.data["break_t"],
                                 retest_depth_atr=(q.level - q.data["ext"]) / at)
                            done = True
                    else:
                        q.data["ext"] = max(q.data["ext"], h[t])
                        if c[t] > q.level + tol:
                            done = True
                        elif h[t] >= q.level - tol and c[t] < q.level:
                            emit(t, "retest", -1, q.level, q.data["ext"], q.data["protective"], origin=q.data["origin"],
                                 bars_since_break=t - q.data["break_t"],
                                 retest_depth_atr=(q.data["ext"] - q.level) / at)
                            done = True
                elif q.kind == "false_break":
                    if q.direction == -1:
                        q.data["ext"] = max(q.data["ext"], h[t])
                        if c[t] < q.level:
                            emit(t, "false_break", -1, q.level, q.data["ext"], q.data["ext"], origin=q.data["origin"],
                                 bars_since_break=t - q.start)
                            done = True
                    else:
                        q.data["ext"] = min(q.data["ext"], l[t])
                        if c[t] > q.level:
                            emit(t, "false_break", +1, q.level, q.data["ext"], q.data["ext"], origin=q.data["origin"],
                                 bars_since_break=t - q.start)
                            done = True
                elif q.kind in ("double_top", "head_shoulders"):
                    if h[t] > q.data["top"] + p.double_tolerance_atr * at:
                        done = True
                    elif c[t] < q.level:
                        emit(t, q.kind, -1, q.level, q.data["top"], q.data["top"],
                             pattern_height_atr=(q.data["top"] - q.level) / at)
                        done = True
                elif q.kind in ("double_bottom", "inv_head_shoulders"):
                    if l[t] < q.data["bottom"] - p.double_tolerance_atr * at:
                        done = True
                    elif c[t] > q.level:
                        emit(t, q.kind, +1, q.level, q.data["bottom"], q.data["bottom"],
                             pattern_height_atr=(q.level - q.data["bottom"]) / at)
                        done = True
                if not done and t < q.expire:
                    keep.append(q)
            pend = keep

            # ---- 2. pivotes confirmados al cierre de t -------------------------------------------
            for pv in by_confirm.get(t, []):
                accepted = False
                if not swings:
                    swings.append(pv)
                    accepted = True
                else:
                    last = swings[-1]
                    if pv.kind == last.kind:
                        if (pv.kind == "H" and pv.price > last.price) or (pv.kind == "L" and pv.price < last.price):
                            swings[-1] = pv
                            accepted = True
                    elif abs(pv.price - last.price) >= p.min_swing_atr * at:
                        swings.append(pv)
                        accepted = True
                if not accepted:
                    continue
                prev_same = next((s for s in reversed(swings[:-1]) if s.kind == pv.kind), None)
                if pv.kind == "H":
                    pv.label = "" if prev_same is None else ("HH" if pv.price > prev_same.price else "LH")
                    last_h_lab = pv.label
                    hi_lv = _Level(pv.price, pv.idx)
                    if prev_same is not None and pv.label == "HH" and np.isfinite(r[pv.idx]) \
                            and r[pv.idx] < r[prev_same.idx]:
                        emit(t, "rsi_divergence", -1, pv.price, pv.price, pv.price,
                             rsi_now=r[pv.idx], rsi_prev=r[prev_same.idx])
                    self._check_tops(swings, t, at, pend)
                else:
                    pv.label = "" if prev_same is None else ("HL" if pv.price > prev_same.price else "LL")
                    last_l_lab = pv.label
                    lo_lv = _Level(pv.price, pv.idx)
                    if prev_same is not None and pv.label == "LL" and np.isfinite(r[pv.idx]) \
                            and r[pv.idx] > r[prev_same.idx]:
                        emit(t, "rsi_divergence", +1, pv.price, pv.price, pv.price,
                             rsi_now=r[pv.idx], rsi_prev=r[prev_same.idx])
                    self._check_bottoms(swings, t, at, pend)
                if last_h_lab == "HH" and last_l_lab == "HL":
                    trend = 1
                elif last_h_lab == "LH" and last_l_lab == "LL":
                    trend = -1
                elif last_h_lab and last_l_lab:
                    trend = 0

            # ---- 3. FVG e impulsos de la vela t -----------------------------------------------
            if t >= 2:
                if l[t] - h[t - 2] >= p.fvg_min_atr * at:
                    emit(t, "fvg", +1, h[t - 2], l[t], l[t - 1], gap_atr=(l[t] - h[t - 2]) / at)
                elif l[t - 2] - h[t] >= p.fvg_min_atr * at:
                    emit(t, "fvg", -1, l[t - 2], h[t], h[t - 1], gap_atr=(l[t - 2] - h[t]) / at)
            rng = h[t] - l[t]
            if rng >= p.impulse_range_atr * at and abs(c[t] - o[t]) >= p.impulse_body_ratio * rng:
                emit(t, "impulse", 1 if c[t] > o[t] else -1, o[t], c[t], l[t] if c[t] > o[t] else h[t],
                     range_atr=rng / at)

            st_trend[t] = trend
            st_hi[t] = hi_lv.price if hi_lv else np.nan
            st_lo[t] = lo_lv.price if lo_lv else np.nan
            st_hi_lab[t], st_lo_lab[t] = last_h_lab, last_l_lab

        events = pd.DataFrame(ev)
        if len(events):
            times = df["close_time"].to_numpy() if "close_time" in df else df.index.to_numpy()
            events["time"] = times[events["t"].to_numpy()]
        state = pd.DataFrame({"trend": st_trend, "swing_high": st_hi, "swing_low": st_lo,
                              "high_label": st_hi_lab, "low_label": st_lo_lab}, index=df.index)
        return events, state

    # --- doble techo/suelo y hombro-cabeza-hombro --------------------------------------------
    def _check_tops(self, swings, t, at, pend):
        p = self.p
        swings = swings[-12:]   # solo las oscilaciones recientes (evita coste cuadrático)
        hs = [s for s in swings if s.kind == "H"]
        if len(hs) >= 2:
            h1, h2 = hs[-2], hs[-1]
            lows = [s for s in swings if s.kind == "L" and h1.idx < s.idx < h2.idx]
            if lows and abs(h2.price - h1.price) <= p.double_tolerance_atr * at and h2.idx - h1.idx >= p.double_min_bars:
                neck = min(s.price for s in lows)
                top = max(h1.price, h2.price)
                if top - neck >= p.double_min_depth_atr * at:
                    pend.append(_Pending("double_top", -1, neck, t, t + 2 * (h2.idx - h1.idx), {"top": top}))
        if len(hs) >= 3:
            a_, b_, c_ = hs[-3], hs[-2], hs[-1]
            l1 = [s for s in swings if s.kind == "L" and a_.idx < s.idx < b_.idx]
            l2 = [s for s in swings if s.kind == "L" and b_.idx < s.idx < c_.idx]
            if l1 and l2 and b_.price - max(a_.price, c_.price) >= p.hs_head_min_atr * at \
                    and abs(a_.price - c_.price) <= p.hs_shoulder_tolerance_atr * at:
                neck = min(min(s.price for s in l1), min(s.price for s in l2))
                pend.append(_Pending("head_shoulders", -1, neck, t, t + (c_.idx - a_.idx), {"top": b_.price}))

    def _check_bottoms(self, swings, t, at, pend):
        p = self.p
        swings = swings[-12:]
        ls = [s for s in swings if s.kind == "L"]
        if len(ls) >= 2:
            l1, l2 = ls[-2], ls[-1]
            highs = [s for s in swings if s.kind == "H" and l1.idx < s.idx < l2.idx]
            if highs and abs(l2.price - l1.price) <= p.double_tolerance_atr * at and l2.idx - l1.idx >= p.double_min_bars:
                neck = max(s.price for s in highs)
                bottom = min(l1.price, l2.price)
                if neck - bottom >= p.double_min_depth_atr * at:
                    pend.append(_Pending("double_bottom", +1, neck, t, t + 2 * (l2.idx - l1.idx), {"bottom": bottom}))
        if len(ls) >= 3:
            a_, b_, c_ = ls[-3], ls[-2], ls[-1]
            h1 = [s for s in swings if s.kind == "H" and a_.idx < s.idx < b_.idx]
            h2 = [s for s in swings if s.kind == "H" and b_.idx < s.idx < c_.idx]
            if h1 and h2 and min(a_.price, c_.price) - b_.price >= p.hs_head_min_atr * at \
                    and abs(a_.price - c_.price) <= p.hs_shoulder_tolerance_atr * at:
                neck = max(max(s.price for s in h1), max(s.price for s in h2))
                pend.append(_Pending("inv_head_shoulders", +1, neck, t, t + (c_.idx - a_.idx), {"bottom": b_.price}))


def detect_structures(df: pd.DataFrame, params: StructureParams | None = None):
    return StructureEngine(params).run(df)
