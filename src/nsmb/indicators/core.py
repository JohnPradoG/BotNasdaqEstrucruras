"""Indicadores causales: el valor en la vela t usa solo velas <= t (ya cerradas)."""
from __future__ import annotations

import numpy as np
import pandas as pd

_NY = "America/New_York"


def _wilder(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    out[n - 1] = np.nanmean(x[:n])
    a = 1.0 / n
    for i in range(n, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    return pd.Series(_wilder(tr, n), index=df.index, name="atr")


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = np.diff(close.to_numpy(), prepend=np.nan)
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    up[0] = dn[0] = 0.0
    au, ad = _wilder(up[1:], n), _wilder(dn[1:], n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = au / ad
        r = np.where(ad == 0, 100.0, 100 - 100 / (1 + rs))
    return pd.Series(np.r_[np.nan, r], index=close.index, name="rsi")


def relative_volume(tickvol: pd.Series, n: int = 50) -> pd.Series:
    """Volumen de ticks de la vela / mediana de las n velas ANTERIORES."""
    med = tickvol.shift(1).rolling(n, min_periods=n // 2).median()
    return (tickvol / med).rename("rel_vol")


def candle_shape(df: pd.DataFrame) -> pd.DataFrame:
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    body = (df["close"] - df["open"]).abs()
    upper = df["high"] - df[["open", "close"]].max(axis=1)
    lower = df[["open", "close"]].min(axis=1) - df["low"]
    return pd.DataFrame({"body_ratio": body / rng, "upper_wick": upper / rng, "lower_wick": lower / rng,
                         "bull_rejection": lower / rng >= 0.5,
                         "bear_rejection": upper / rng >= 0.5}, index=df.index)


def session_of(times: pd.DatetimeIndex) -> np.ndarray:
    """Sesión según la hora de Nueva York (con horario de verano): asia, londres, ny_apertura, ny, tarde."""
    ny = times.tz_localize("UTC").tz_convert(_NY)
    m = ny.hour * 60 + ny.minute
    out = np.full(len(times), "asia", dtype=object)
    out[(m >= 3 * 60) & (m < 9 * 60 + 30)] = "londres"
    out[(m >= 9 * 60 + 30) & (m < 11 * 60)] = "ny_apertura"
    out[(m >= 11 * 60) & (m < 16 * 60)] = "ny"
    out[(m >= 16 * 60) & (m < 18 * 60)] = "tarde"
    return out


def add_indicators(df: pd.DataFrame, atr_n: int = 14, rsi_n: int = 14) -> pd.DataFrame:
    out = df.copy()
    out["atr"] = atr(df, atr_n)
    out["rsi"] = rsi(df["close"], rsi_n)
    out["rel_vol"] = relative_volume(df["tickvol"])
    out = out.join(candle_shape(df))
    # volatilidad relativa: ATR actual / mediana del ATR de las 500 velas previas
    out["atr_rel"] = out["atr"] / out["atr"].shift(1).rolling(500, min_periods=100).median()
    out["session"] = session_of(df.index)
    out["ret_20_atr"] = (df["close"] - df["close"].shift(20)) / out["atr"]   # fuerza/velocidad previa
    return out
