"""Ejecución de órdenes: modo papel (simulado) y modo demo (MT5). La operativa REAL está bloqueada:
- la configuración no puede activarla (config/loader.py lanza error);
- el ejecutor rechaza cualquier cuenta que no sea DEMO (account_info().trade_mode);
- no existe ningún camino de código que envíe órdenes a una cuenta real.

Garantías:
- idempotencia: cada señal tiene un client_id; una segunda solicitud con el mismo id se rechaza (registro en SQLite);
- validación de volumen, distancia de stops y spread antes de enviar;
- reintentos limitados solo ante errores transitorios;
- una solicitud enviada NO se da por ejecutada: se verifica la posición en el terminal;
- reconciliación periódica: posiciones del terminal (magic del bot) frente al registro.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from ..config.loader import SymbolSpec
from ..risk.manager import RiskState


class LiveTradingBlocked(RuntimeError):
    pass


@dataclass
class OrderIntent:
    client_id: str
    symbol: str
    direction: int        # +1 compra, -1 venta
    volume: float
    stop: float
    target: float | None
    comment: str = ""


@dataclass
class ExecResult:
    ok: bool
    status: str           # filled | duplicate | blocked | rejected | unverified | error
    detail: str = ""
    ticket: int | None = None
    price: float | None = None
    attempts: int = 0
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------------------------
class PaperBroker:
    """Broker simulado en memoria (para el modo papel y para las pruebas)."""
    TRADE_MODE_DEMO = 0

    def __init__(self, bid: float = 100.0, spread: float = 1.0, demo: bool = True):
        self.bid, self.spread, self.demo = bid, spread, demo
        self.positions: dict[int, dict] = {}
        self._ticket = 1000
        self.connected = True
        self.fail_next: list[str] = []      # p. ej. ["requote", "reject"] para pruebas

    def is_demo(self) -> bool:
        return self.demo

    def tick(self, symbol):
        if not self.connected:
            return None
        return {"bid": self.bid, "ask": self.bid + self.spread, "time": time.time()}

    def bot_positions(self, symbol, magic):
        if not self.connected:
            raise ConnectionError("desconectado")
        return [p for p in self.positions.values() if p["magic"] == magic and p["symbol"] == symbol]

    def send(self, req: dict) -> dict:
        if not self.connected:
            return {"retcode": "connection", "comment": "sin conexión"}
        if self.fail_next:
            what = self.fail_next.pop(0)
            return {"retcode": what, "comment": f"simulado: {what}"}
        self._ticket += 1
        px = self.bid + self.spread if req["direction"] > 0 else self.bid
        self.positions[self._ticket] = {**req, "ticket": self._ticket, "price": px}
        return {"retcode": "done", "order": self._ticket, "price": px}

    def close_position(self, ticket: int, symbol, magic) -> dict:
        if not self.connected:
            return {"retcode": "connection", "comment": "sin conexión"}
        p = self.positions.get(ticket)
        if p is None or p["magic"] != magic:
            return {"retcode": "reject", "comment": "posición no encontrada"}
        self.positions.pop(ticket)
        return {"retcode": "done", "order": ticket, "price": self.bid if p["direction"] > 0 else self.bid + self.spread}

    def close_all(self, symbol, magic):
        for k in [k for k, p in self.positions.items() if p["magic"] == magic]:
            self.positions.pop(k)


class MT5Broker:
    """Adaptador del paquete MetaTrader5. Solo se usa con cuentas DEMO."""

    def __init__(self, mt5_module: Any, deviation_points: int = 30):
        self.mt5, self.dev = mt5_module, deviation_points

    def is_demo(self) -> bool:
        a = self.mt5.account_info()
        return a is not None and a.trade_mode == self.mt5.ACCOUNT_TRADE_MODE_DEMO

    def tick(self, symbol):
        t = self.mt5.symbol_info_tick(symbol)
        return None if t is None else {"bid": t.bid, "ask": t.ask, "time": t.time}

    def bot_positions(self, symbol, magic):
        ps = self.mt5.positions_get(symbol=symbol)
        if ps is None:
            raise ConnectionError(f"positions_get falló: {self.mt5.last_error()}")
        return [p._asdict() for p in ps if p.magic == magic]

    def send(self, req: dict) -> dict:
        m = self.mt5
        t = m.symbol_info_tick(req["symbol"])
        if t is None:
            return {"retcode": "connection", "comment": str(m.last_error())}
        buy = req["direction"] > 0
        r = {"action": m.TRADE_ACTION_DEAL, "symbol": req["symbol"], "volume": req["volume"],
             "type": m.ORDER_TYPE_BUY if buy else m.ORDER_TYPE_SELL, "price": t.ask if buy else t.bid,
             "sl": req["stop"], "tp": req["target"] or 0.0, "deviation": self.dev, "magic": req["magic"],
             "comment": req["comment"][:31], "type_time": m.ORDER_TIME_GTC, "type_filling": m.ORDER_FILLING_IOC}
        chk = m.order_check(r)
        if chk is None or chk.retcode not in (0, m.TRADE_RETCODE_DONE):
            return {"retcode": "reject", "comment": f"order_check: {None if chk is None else chk.comment}"}
        res = m.order_send(r)
        if res is None:
            return {"retcode": "connection", "comment": str(m.last_error())}
        code = {m.TRADE_RETCODE_DONE: "done", m.TRADE_RETCODE_REQUOTE: "requote",
                m.TRADE_RETCODE_PRICE_CHANGED: "requote", m.TRADE_RETCODE_TIMEOUT: "timeout",
                m.TRADE_RETCODE_CONNECTION: "connection"}.get(res.retcode, "reject")
        return {"retcode": code, "order": res.order, "price": res.price, "comment": res.comment, "mt5_retcode": res.retcode}


    def close_position(self, ticket: int, symbol, magic) -> dict:
        m = self.mt5
        ps = m.positions_get(ticket=ticket)
        if ps is None:
            return {"retcode": "connection", "comment": str(m.last_error())}
        if not ps or ps[0].magic != magic:
            return {"retcode": "reject", "comment": "posición no encontrada"}
        p = ps[0]
        t = m.symbol_info_tick(symbol)
        if t is None:
            return {"retcode": "connection", "comment": str(m.last_error())}
        buy = p.type == m.POSITION_TYPE_BUY
        r = {"action": m.TRADE_ACTION_DEAL, "symbol": symbol, "volume": p.volume, "position": ticket,
             "type": m.ORDER_TYPE_SELL if buy else m.ORDER_TYPE_BUY, "price": t.bid if buy else t.ask,
             "deviation": self.dev, "magic": magic, "comment": "NSMB cierre", "type_time": m.ORDER_TIME_GTC,
             "type_filling": m.ORDER_FILLING_IOC}
        res = m.order_send(r)
        if res is None:
            return {"retcode": "connection", "comment": str(m.last_error())}
        code = {m.TRADE_RETCODE_DONE: "done", m.TRADE_RETCODE_REQUOTE: "requote",
                m.TRADE_RETCODE_PRICE_CHANGED: "requote", m.TRADE_RETCODE_TIMEOUT: "timeout",
                m.TRADE_RETCODE_CONNECTION: "connection"}.get(res.retcode, "reject")
        return {"retcode": code, "order": ticket, "price": res.price, "comment": res.comment, "mt5_retcode": res.retcode}


# ---------------------------------------------------------------------------------------------
TRANSIENT = {"requote", "timeout", "connection"}


class Executor:
    def __init__(self, broker, spec: SymbolSpec, risk: RiskState, journal, mode: str, magic: int,
                 max_retries: int = 2, retry_delay_s: float = 0.0, max_spread_price: float | None = None,
                 live_trading_enabled: bool = False):
        if live_trading_enabled or mode not in ("paper", "demo"):
            raise LiveTradingBlocked("Solo se permiten los modos 'paper' y 'demo'")
        if mode == "demo" and not broker.is_demo():
            raise LiveTradingBlocked("La cuenta conectada NO es demo: ejecución bloqueada")
        self.broker, self.spec, self.risk, self.journal = broker, spec, risk, journal
        self.mode, self.magic = mode, magic
        self.max_retries, self.retry_delay_s = max_retries, retry_delay_s
        self.max_spread_price = max_spread_price
        self.blocked: str | None = None

    # --- utilidades ------------------------------------------------------------------------
    def _log(self, client_id: str, kind: str, payload: dict) -> bool:
        return self.journal.log(self.mode, client_id, kind, payload)

    def normalize_volume(self, v: float) -> float:
        s = self.spec
        v = math.floor(v / s.volume_step + 1e-9) * s.volume_step
        return round(min(v, s.volume_max), 8) if v >= s.volume_min else 0.0

    # --- envío ---------------------------------------------------------------------------
    def submit(self, intent: OrderIntent) -> ExecResult:
        if not self.broker.is_demo() and self.mode == "demo":
            self.blocked = "cuenta_no_demo"
            return ExecResult(False, "blocked", "cuenta no demo")
        if self.journal.has_request(intent.client_id):
            return ExecResult(False, "duplicate", "señal ya enviada")
        if self.blocked:
            return ExecResult(False, "blocked", self.blocked)
        try:
            mine = self.broker.bot_positions(intent.symbol, self.magic)
        except ConnectionError as e:
            self.risk.on_execution_error()
            return ExecResult(False, "error", f"sin conexión: {e}")
        if len(mine) >= self.risk.limits.max_open_positions:
            return ExecResult(False, "blocked", "max_posiciones")
        tick = self.broker.tick(intent.symbol)
        if tick is None:
            return ExecResult(False, "blocked", "sin_precio")
        spread = tick["ask"] - tick["bid"]
        ok, why = self.risk.can_open(spread_ok=self.max_spread_price is None or spread <= self.max_spread_price)
        if not ok:
            self._log(intent.client_id, "block", {"reason": why})
            return ExecResult(False, "blocked", why)
        vol = self.normalize_volume(intent.volume)
        if vol <= 0:
            return ExecResult(False, "blocked", "volumen_menor_que_minimo")
        ref = tick["ask"] if intent.direction > 0 else tick["bid"]
        min_dist = self.spec.stops_level * self.spec.point
        if (intent.direction > 0 and intent.stop >= ref - min_dist) or (intent.direction < 0 and intent.stop <= ref + min_dist):
            return ExecResult(False, "rejected", "stop_demasiado_cerca_o_del_lado_incorrecto")
        req = {"symbol": intent.symbol, "direction": intent.direction, "volume": vol, "stop": round(intent.stop, self.spec.digits),
               "target": None if intent.target is None else round(intent.target, self.spec.digits),
               "magic": self.magic, "comment": intent.comment or intent.client_id[:31]}
        if not self._log(intent.client_id, "request", req):
            return ExecResult(False, "duplicate", "señal ya enviada")
        attempts, resp = 0, {}
        while attempts <= self.max_retries:
            attempts += 1
            resp = self.broker.send(req)
            if resp.get("retcode") in TRANSIENT and attempts <= self.max_retries:
                time.sleep(self.retry_delay_s)
                continue
            break
        self._log(intent.client_id, "response", {**resp, "attempts": attempts})
        if resp.get("retcode") != "done":
            self.risk.on_execution_error()
            st = "error" if resp.get("retcode") in TRANSIENT else "rejected"
            return ExecResult(False, st, str(resp.get("comment")), attempts=attempts, raw=resp)
        # verificación: la posición debe existir en el terminal
        try:
            live = self.broker.bot_positions(intent.symbol, self.magic)
        except ConnectionError:
            live = []
        found = [p for p in live if p.get("ticket") == resp.get("order") or p.get("identifier") == resp.get("order")]
        if not found:
            self.risk.on_execution_error()
            return ExecResult(False, "unverified", "orden enviada pero posición no encontrada", resp.get("order"),
                              resp.get("price"), attempts, resp)
        self.risk.on_execution_ok()
        self.risk.on_open()
        return ExecResult(True, "filled", "ok", resp.get("order"), resp.get("price"), attempts, resp)

    # --- cierre ----------------------------------------------------------------------------
    def close(self, client_id: str, ticket: int, symbol: str) -> ExecResult:
        """Cierra una posición del bot (salida por regla o fin del día). Idempotente por client_id."""
        cid = f"cierre-{client_id}"
        if self.journal.has_request(cid):
            return ExecResult(False, "duplicate", "cierre ya enviado")
        if not self._log(cid, "request", {"ticket": ticket}):
            return ExecResult(False, "duplicate", "cierre ya enviado")
        attempts, resp = 0, {}
        while attempts <= self.max_retries:
            attempts += 1
            resp = self.broker.close_position(ticket, symbol, self.magic)
            if resp.get("retcode") in TRANSIENT and attempts <= self.max_retries:
                time.sleep(self.retry_delay_s)
                continue
            break
        self._log(cid, "response", {**resp, "attempts": attempts})
        if resp.get("retcode") != "done":
            self.risk.on_execution_error()
            return ExecResult(False, "error", str(resp.get("comment")), ticket, attempts=attempts, raw=resp)
        self.risk.open_positions = max(0, self.risk.open_positions - 1)
        return ExecResult(True, "closed", "ok", ticket, resp.get("price"), attempts, resp)

    # --- reconciliación ------------------------------------------------------------------
    def reconcile(self, symbol: str, expected_tickets: set[int]) -> dict:
        try:
            live = self.broker.bot_positions(symbol, self.magic)
        except ConnectionError as e:
            self.blocked = "desconectado"
            return {"ok": False, "reason": f"desconectado: {e}"}
        tickets = {int(p.get("ticket")) for p in live}
        unknown, missing = tickets - expected_tickets, expected_tickets - tickets
        rep = {"ok": not unknown, "terminal": sorted(tickets), "desconocidas": sorted(unknown), "cerradas": sorted(missing)}
        self.risk.open_positions = len(tickets)
        if unknown:
            self.blocked = "posiciones_desconocidas"
        elif self.blocked in ("desconectado", "posiciones_desconocidas"):
            self.blocked = None
        self._log(f"reconcile-{datetime.now(timezone.utc).isoformat()}", "reconcile", rep)
        return rep


class SqliteJournal:
    """Registro de solicitudes y respuestas en la tabla execution_journal (índice único por client_id)."""

    def __init__(self, con):
        self.con = con

    def has_request(self, client_id: str) -> bool:
        return self.con.execute("SELECT 1 FROM execution_journal WHERE client_id=? AND kind='request'", (client_id,)).fetchone() is not None

    def log(self, mode: str, client_id: str, kind: str, payload: dict) -> bool:
        try:
            self.con.execute("INSERT INTO execution_journal (ts, mode, client_id, kind, payload_json) VALUES (?,?,?,?,?)",
                             (datetime.now(timezone.utc).isoformat(), mode, client_id, kind, json.dumps(payload, default=str)))
            self.con.commit()
            return True
        except Exception as e:  # noqa: BLE001  (violación del índice único => duplicado)
            if "UNIQUE" in str(e):
                return False
            raise
