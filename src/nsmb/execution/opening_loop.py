"""Bucle de la cartera de apertura de NY (orb15, orb5, noise) en modo papel o demo.

Por defecto OBSERVA: registra cada señal y lo que habría hecho, sin enviar órdenes. Con allow_orders=True envía
órdenes solo a la cuenta DEMO (el ejecutor rechaza cualquier otra). Cada estrategia tiene como máximo una posición
abierta; el riesgo de cada operación es risk_per_trade_pct del equity y el stop va siempre en el bróker.
Una señal solo se ejecuta si se detecta a tiempo (max_signal_age_s); si el bot arranca tarde, las señales viejas
se registran pero no se operan.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..config.loader import SymbolSpec
from ..risk.manager import position_size
from ..strategies.opening import OpeningEvent, day_events, flat_time_utc
from .executor import OrderIntent


class OpeningLoop:
    def __init__(self, cfg: dict, risk_cfg: dict, spec: SymbolSpec, executor, log_path: Path,
                 allow_orders: bool = False, strategies=("orb15", "orb5", "noise"), max_signal_age_s: int = 180,
                 events_fn=day_events, flat_close: bool = True):
        self.cfg, self.risk_cfg, self.spec, self.executor, self.log_path = cfg, risk_cfg, spec, executor, log_path
        self.allow_orders = allow_orders
        self.strategies = set(strategies)
        self.max_signal_age_s = max_signal_age_s
        self.events_fn, self.flat_close = events_fn, flat_close     # otras estrategias (p. ej. cruce de EMAs H1)
        self.seen: set[tuple[str, str]] = set()
        self.tickets: dict[str, int] = {}          # client_id -> ticket de la posición abierta

    def log(self, rec: dict) -> None:
        rec = {"ts": datetime.now(timezone.utc).isoformat(), **rec}
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    def _open(self, e: OpeningEvent, equity: float) -> dict:
        tick = self.executor.broker.tick(self.spec.name)
        if tick is None:
            return {"orden": "sin_precio"}
        spread = tick["ask"] - tick["bid"]
        if e.max_spread is not None and spread > e.max_spread:
            return {"orden": "spread_alto", "spread": round(spread, 2)}
        ref = tick["ask"] if e.direction > 0 else tick["bid"]
        if e.stop is None:                                              # stop por distancia desde la entrada
            stop = ref - e.direction * e.stop_dist
        else:
            stop = e.stop if e.direction > 0 else e.stop + spread      # en ventas el stop se activa con el ASK
        risk_px = (ref - stop) * e.direction
        if risk_px <= 0:
            return {"orden": "stop_ya_superado"}
        lot = position_size(equity, self.risk_cfg["risk_per_trade_pct"], risk_px, self.spec, spread,
                            self.risk_cfg["cost_buffer_multiple"])
        if lot <= 0:
            return {"orden": "lote_minimo_supera_riesgo", "riesgo_puntos": round(risk_px, 2)}
        tgt = ref + e.direction * e.target_r * risk_px if e.target_r else None
        res = self.executor.submit(OrderIntent(e.client_id, self.spec.name, e.direction, lot, float(stop),
                                               None if tgt is None else float(tgt), f"NSMB {e.client_id}"))
        if res.ok and res.ticket:
            self.tickets[e.client_id] = int(res.ticket)
        return {"orden": res.__dict__, "lote": lot}

    def _close(self, client_id: str, why: str) -> dict:
        t = self.tickets.pop(client_id, None)
        if t is None:
            return {"cierre": "sin_posicion"}
        res = self.executor.close(client_id, t, self.spec.name)
        return {"cierre": res.__dict__, "motivo": why}

    def cycle(self, m1: pd.DataFrame, equity: float, now_utc: datetime) -> list[dict]:
        now = pd.Timestamp(now_utc).tz_localize(None) if pd.Timestamp(now_utc).tzinfo else pd.Timestamp(now_utc)
        age = (now - (m1.index[-1] + pd.Timedelta(minutes=1))).total_seconds()
        fresh = age <= self.cfg["execution"]["max_data_age_s"]
        out = []
        for e in self.events_fn(m1, now):
            if e.strategy not in self.strategies or (e.client_id, e.kind) in self.seen:
                continue
            self.seen.add((e.client_id, e.kind))
            late = (now - e.detected_time).total_seconds() > self.max_signal_age_s
            rec = {"evento": e.kind, "estrategia": e.strategy, "id": e.client_id, "dir": e.direction,
                   "detectada": e.detected_time, "stop": e.stop, "stop_dist": e.stop_dist, "motivo": e.reason, "datos_frescos": fresh,
                   "tarde": late}
            if not self.allow_orders:
                rec["decision"] = f"observacion: habría {'abierto' if e.kind == 'abrir' else 'cerrado'}"
            elif late or not fresh:
                rec["decision"] = "no_ejecutada_tarde_o_datos_viejos"
            elif e.kind == "abrir":
                rec.update(self._open(e, equity))
            elif e.reason != "stop":                  # si saltó el stop, el bróker ya la cerró
                rec.update(self._close(e.client_id, e.reason))
            else:
                self.tickets.pop(e.client_id, None)
            self.log(rec)
            out.append(rec)
        # salida forzada de las 15:57 NY (solo estrategias del día)
        if self.flat_close and self.tickets:
            today = pd.Timestamp(now).tz_localize("UTC").tz_convert("America/New_York").normalize().tz_localize(None)
            if now >= flat_time_utc(today):
                for cid in list(self.tickets):
                    rec = {"evento": "cerrar", "id": cid, **self._close(cid, "fin_del_dia")}
                    self.log(rec)
                    out.append(rec)
        return out

    def _sync(self) -> None:
        rep = self.executor.reconcile(self.spec.name, set(self.tickets.values()))
        closed = set(rep.get("cerradas", []))
        self.tickets = {k: v for k, v in self.tickets.items() if v not in closed}

    def run(self, get_m1, get_equity, interval_s: int = 20, stop_file: Path | None = None, once: bool = False):
        while True:
            try:
                self._sync()                          # quita las que ya cerró el bróker (stop u objetivo)
                m1 = get_m1()
                recs = self.cycle(m1, get_equity(), datetime.now(timezone.utc))
                self._sync()
                self.log({"ciclo": "ok", "ultima_vela": m1.index[-1], "eventos": len(recs), "abiertas": self.tickets})
            except Exception as e:  # noqa: BLE001  (desconexión, datos...) => se registra y se reintenta
                self.log({"ciclo": "error", "error": repr(e)})
            if once or (stop_file is not None and stop_file.exists()):
                break
            time.sleep(interval_s)
