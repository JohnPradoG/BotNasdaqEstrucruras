"""Pivotes (máximos y mínimos de oscilación) confirmados sin anticipación.

Definición: la vela i es máximo fractal si high[i] > max(high[i-L..i-1]) y high[i] >= max(high[i+1..i+R]).
Solo se conoce al CERRAR la vela i+R, así que `confirm_idx = i + R`. Ninguna decisión puede usar
el pivote antes de esa vela.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class Pivot:
    idx: int            # vela donde está el extremo
    confirm_idx: int    # vela en cuyo cierre se conoce
    price: float
    kind: str           # "H" o "L"
    label: str = ""     # HH, LH, HL, LL (respecto al pivote previo del mismo tipo)


def fractal_pivots(high: np.ndarray, low: np.ndarray, left: int, right: int) -> list[Pivot]:
    n = len(high)
    out: list[Pivot] = []
    for i in range(left, n - right):
        h = high[i]
        if h > high[i - left:i].max() and h >= high[i + 1:i + right + 1].max():
            out.append(Pivot(i, i + right, float(h), "H"))
        lo = low[i]
        if lo < low[i - left:i].min() and lo <= low[i + 1:i + right + 1].min():
            out.append(Pivot(i, i + right, float(lo), "L"))
    out.sort(key=lambda p: (p.confirm_idx, p.idx))
    return out
