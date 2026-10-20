"""Series sintéticas con estructuras conocidas para probar los detectores."""
from __future__ import annotations

import numpy as np
import pandas as pd

from nsmb.indicators import add_indicators
from nsmb.data.timeframes import resample


def path_to_ohlc(closes, start="2024-01-02 14:00", freq="15min", wick=0.2, spread=100) -> pd.DataFrame:
    """Velas cuyo cierre sigue `closes`; la apertura es el cierre anterior y las mechas son `wick`."""
    closes = np.asarray(closes, float)
    opens = np.r_[closes[0], closes[:-1]]
    high = np.maximum(opens, closes) + wick
    low = np.minimum(opens, closes) - wick
    idx = pd.date_range(start, periods=len(closes), freq=freq, name="time")
    df = pd.DataFrame({"open": opens, "high": high, "low": low, "close": closes,
                       "tickvol": 100, "spread": spread}, index=idx)
    df["close_time"] = df.index + pd.Timedelta(freq)
    df["complete"] = True
    return df


def zigzag(points, steps=6):
    """Une los puntos con rectas de `steps` velas."""
    out = [points[0]]
    for a, b in zip(points[:-1], points[1:]):
        out.extend(np.linspace(a, b, steps + 1)[1:])
    return np.array(out)


def prepared(closes, **kw) -> pd.DataFrame:
    df = path_to_ohlc(closes, **kw)
    return add_indicators(df, atr_n=5, rsi_n=5)


def random_walk_m1(n=20000, seed=7, start="2024-01-02 00:00") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    c = 15000 + np.cumsum(rng.normal(0, 3, n))
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + rng.uniform(0, 2, n)
    l = np.minimum(o, c) - rng.uniform(0, 2, n)
    idx = pd.date_range(start, periods=n, freq="1min", name="time")
    return pd.DataFrame({"open": o, "high": h, "low": l, "close": c, "tickvol": rng.integers(10, 500, n),
                         "spread": 120}, index=idx)


def random_frame(tf="M15", n=20000, seed=7) -> pd.DataFrame:
    return add_indicators(resample(random_walk_m1(n, seed), tf))
