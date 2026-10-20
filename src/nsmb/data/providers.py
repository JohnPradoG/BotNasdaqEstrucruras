"""Proveedores de datos desacoplados: CSV exportado de MT5 y paquete MetaTrader5.

Todos devuelven un DataFrame M1 con índice `time` (apertura de la vela, UTC naive) y columnas
open, high, low, close, tickvol, spread (spread en points, tal como lo da MT5).
Los precios de MT5 son BID; el ASK se aproxima como bid + spread*point.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

COLS = ["open", "high", "low", "close", "tickvol", "spread"]


class DataProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    def load_m1(self, symbol: str, start: str | None = None, end: str | None = None) -> pd.DataFrame: ...

    def describe(self) -> dict:
        return {"provider": self.name}


class CsvMT5Provider(DataProvider):
    """Lee el CSV tabulado que genera el script MQL5 de exportación (<DATE> <TIME> <OPEN> ...)."""
    name = "csv_mt5_export"

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load_m1(self, symbol: str, start=None, end=None) -> pd.DataFrame:
        df = pd.read_csv(self.path, sep="\t")
        df.columns = [c.strip("<>").lower() for c in df.columns]
        df["time"] = pd.to_datetime(df["date"] + " " + df["time"], format="%Y.%m.%d %H:%M:%S")
        df = df.rename(columns={"vol": "realvol"}).set_index("time")[COLS].astype(
            {"open": "float64", "high": "float64", "low": "float64", "close": "float64",
             "tickvol": "int64", "spread": "int64"})
        if start:
            df = df[df.index >= pd.Timestamp(start)]
        if end:
            df = df[df.index <= pd.Timestamp(end)]
        return df

    def describe(self) -> dict:
        st = self.path.stat()
        return {"provider": self.name, "path": str(self.path), "size": st.st_size,
                "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat()}


class MT5Provider(DataProvider):
    """Descarga velas con el paquete MetaTrader5 (requiere terminal abierto o lanzable)."""
    name = "mt5_python"

    def __init__(self, connector):
        self.conn = connector

    def load_m1(self, symbol: str, start=None, end=None) -> pd.DataFrame:
        mt5 = self.conn.mt5
        start_dt = pd.Timestamp(start or "2015-01-01").to_pydatetime().replace(tzinfo=timezone.utc)
        end_dt = pd.Timestamp(end or datetime.now(timezone.utc).replace(tzinfo=None)).to_pydatetime().replace(tzinfo=timezone.utc)
        rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start_dt, end_dt)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"MT5 no devolvió velas para {symbol}: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.rename(columns={"tick_volume": "tickvol"}).set_index("time")
        return df[COLS].astype({"tickvol": "int64", "spread": "int64"})


def frame_hash(df: pd.DataFrame) -> str:
    h = hashlib.sha256(pd.util.hash_pandas_object(df, index=True).values.tobytes()).hexdigest()
    return h[:16]


class M1Cache:
    """Caché local en parquet + metadatos (fuente, periodo, hash). Permite descarga incremental."""

    def __init__(self, cache_dir: str | Path):
        self.dir = Path(cache_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def paths(self, symbol: str) -> tuple[Path, Path]:
        return self.dir / f"{symbol}_M1.parquet", self.dir / f"{symbol}_M1.meta.json"

    def load(self, symbol: str) -> tuple[pd.DataFrame | None, dict | None]:
        p, m = self.paths(symbol)
        if not p.exists():
            return None, None
        return pd.read_parquet(p), json.loads(m.read_text(encoding="utf-8")) if m.exists() else None

    def save(self, symbol: str, df: pd.DataFrame, source: dict, quality: dict) -> dict:
        p, m = self.paths(symbol)
        df.to_parquet(p)
        meta = {"symbol": symbol, "rows": int(len(df)), "start": str(df.index[0]), "end": str(df.index[-1]),
                "hash": frame_hash(df), "source": source, "quality": quality,
                "saved_at": datetime.now(timezone.utc).isoformat()}
        m.write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        return meta

    def update_incremental(self, symbol: str, provider: DataProvider) -> pd.DataFrame:
        old, _ = self.load(symbol)
        start = None if old is None else str(old.index[-1])
        new = provider.load_m1(symbol, start=start)
        if old is None:
            return new
        merged = pd.concat([old, new])
        return merged[~merged.index.duplicated(keep="last")].sort_index()
