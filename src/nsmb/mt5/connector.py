"""Conexión con el terminal MetaTrader 5 (solo lectura de datos y especificaciones).

El paquete MetaTrader5 es opcional: si no está instalado o el terminal no responde, el resto
del proyecto sigue funcionando con datos locales.
"""
from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any

from ..config.loader import SymbolSpec


class MT5Unavailable(RuntimeError):
    pass


class MT5Connector:
    def __init__(self, terminal_path: str | None = None, mt5_module: Any = None, timeout_ms: int = 60000):
        if mt5_module is None:
            try:
                import MetaTrader5 as mt5_module  # type: ignore
            except ImportError as e:  # pragma: no cover - depende del entorno
                raise MT5Unavailable("Paquete MetaTrader5 no instalado") from e
        self.mt5 = mt5_module
        self.terminal_path = terminal_path or os.environ.get("MT5_TERMINAL_PATH")
        self.timeout_ms = timeout_ms
        self.connected = False

    def connect(self) -> None:
        kw = {"timeout": self.timeout_ms}
        ok = self.mt5.initialize(self.terminal_path, **kw) if self.terminal_path else self.mt5.initialize(**kw)
        if not ok:
            raise MT5Unavailable(f"initialize() falló: {self.mt5.last_error()}")
        self.connected = True

    def shutdown(self) -> None:
        if self.connected:
            self.mt5.shutdown()
            self.connected = False

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.shutdown()

    # --- consultas -------------------------------------------------------------------------
    def account(self) -> dict:
        a = self.mt5.account_info()
        if a is None:
            raise MT5Unavailable(f"account_info() vacío: {self.mt5.last_error()}")
        d = a._asdict()
        return {k: d.get(k) for k in ("login", "server", "company", "currency", "balance", "equity",
                                       "leverage", "trade_mode", "trade_allowed", "margin_mode")}

    def is_demo_account(self) -> bool:
        a = self.mt5.account_info()
        return a is not None and a.trade_mode == self.mt5.ACCOUNT_TRADE_MODE_DEMO

    def terminal(self) -> dict:
        t = self.mt5.terminal_info()
        d = t._asdict() if t is not None else {}
        return {k: d.get(k) for k in ("name", "company", "path", "build", "connected", "trade_allowed",
                                       "maxbars", "community_account")}

    def nasdaq_symbols(self) -> list[dict]:
        out = []
        for s in self.mt5.symbols_get() or []:
            text = f"{s.name} {s.description} {s.path}".upper()
            if any(k in text for k in ("USTEC", "NAS", "NDX", "US100", "TEC")):
                out.append({"name": s.name, "description": s.description, "path": s.path})
        return out

    def symbol_spec(self, symbol: str) -> tuple[SymbolSpec, dict]:
        if not self.mt5.symbol_select(symbol, True):
            raise MT5Unavailable(f"symbol_select({symbol}) falló: {self.mt5.last_error()}")
        s = self.mt5.symbol_info(symbol)
        if s is None:
            raise MT5Unavailable(f"symbol_info({symbol}) vacío")
        d = s._asdict()
        spec = SymbolSpec(name=symbol, digits=d["digits"], point=d["point"], tick_size=d["trade_tick_size"],
                          tick_value=d["trade_tick_value"], contract_size=d["trade_contract_size"],
                          volume_min=d["volume_min"], volume_max=d["volume_max"], volume_step=d["volume_step"],
                          stops_level=d["trade_stops_level"], swap_long_points=d["swap_long"],
                          swap_short_points=d["swap_short"], swap_3day=d.get("swap_rollover3days", 3))
        extra = {k: d.get(k) for k in ("spread", "spread_float", "trade_mode", "trade_exemode", "filling_mode",
                                       "order_mode", "trade_freeze_level", "swap_mode", "currency_profit",
                                       "session_deals", "time")}
        return spec, {"spec": asdict(spec), **extra}

    def latest_tick(self, symbol: str) -> dict | None:
        t = self.mt5.symbol_info_tick(symbol)
        return None if t is None else t._asdict()
