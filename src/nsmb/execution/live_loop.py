"""Bucle del modo demo/papel: datos recientes -> estructuras -> regla -> memoria -> riesgo -> ejecutor.

Por defecto funciona en modo OBSERVACIÓN: registra las señales y lo que habría decidido, sin enviar órdenes.
Solo envía órdenes a la cuenta DEMO si se pasa allow_orders=True y la selección congelada no es NO_OPERAR.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ..backtesting.simulator import M1Arrays
from ..config.loader import SymbolSpec
from ..market_structure import StructureParams
from ..memory.builder import FrameCache, build_episodes
from ..risk.manager import position_size
from ..strategies.decision import DecisionConfig, MemoryDecision
from ..strategies.rules import STRATEGIES, common_exclusions
from .executor import OrderIntent


def fetch_recent_m1(mt5, symbol: str, bars: int = 20000) -> pd.DataFrame:
    r = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M1, 0, bars)
    if r is None or len(r) == 0:
        raise ConnectionError(f"copy_rates_from_pos falló: {mt5.last_error()}")
    df = pd.DataFrame(r)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.rename(columns={"tick_volume": "tickvol"}).set_index("time")
    df = df[["open", "high", "low", "close", "tickvol", "spread"]]
    return df.iloc[:-1]          # la última vela M1 está abierta: se descarta


class LiveLoop:
    def __init__(self, cfg: dict, risk_cfg: dict, spec: SymbolSpec, combo: list[str], selection: str,
                 pool: pd.DataFrame, train: pd.DataFrame, executor, log_path: Path, allow_orders: bool = False):
        self.cfg, self.risk_cfg, self.spec, self.combo = cfg, risk_cfg, spec, combo
        self.selection, self.executor, self.log_path = selection, executor, log_path
        self.allow_orders = allow_orders and selection != "NO_OPERAR"
        self.seen: set[str] = set()
        self.open_tickets: set[int] = set()
        self.strategy, self.dcfg = None, None
        if selection != "NO_OPERAR":
            name, conf = selection.split("|")
            self.strategy = name
            if conf != "base":
                k = int(conf.split("_k")[1].split("_")[0])
                crit = "lcb" if "lcb" in conf else "mean"
                thr = float(conf.split(crit)[1])
                self.dcfg = DecisionConfig(k=k, criterion=crit, threshold_r=thr)
        self.decider = MemoryDecision(pool, train, self.dcfg) if self.dcfg is not None and len(pool) else None

    def log(self, rec: dict) -> None:
        rec = {"ts": datetime.now(timezone.utc).isoformat(), **rec}
        with open(self.log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    def cycle(self, m1: pd.DataFrame, equity: float, now_utc: datetime) -> list[dict]:
        out = []
        age = (pd.Timestamp(now_utc).tz_localize(None) - (m1.index[-1] + pd.Timedelta(minutes=1))).total_seconds()
        fresh = age <= self.cfg["execution"]["max_data_age_s"]
        cache = FrameCache(m1, StructureParams.from_cfg(self.cfg["structure"]), complete_only=True)
        m1a = M1Arrays.from_frame(m1, self.spec.point)
        ep = build_episodes(cache, self.combo, self.spec, m1a, self.cfg["backtest"], self.cfg["memory"], "live", self.spec.name)
        if ep.empty:
            return out
        df_tf = cache.get(self.combo[2])[0]
        last_t = len(df_tf) - 1
        new = ep[(ep["t"] == last_t) & ~ep["episode_id"].isin(self.seen)]
        for e in new.to_dict("records"):
            self.seen.add(e["episode_id"])
            rec = {"episode_id": e["episode_id"], "tipo": e["structure_type"], "dir": int(e["direction"]),
                   "detectada": e["detected_time"], "stop": e["stop"], "ref": e["entry_ref"], "datos_frescos": fresh}
            row = pd.DataFrame([e]).assign(status="ok", risk_atr=abs(e["entry_ref"] - e["stop"]) / e["atr"])
            matches = {n: bool(rule(row).iloc[0]) for n, rule in STRATEGIES.items()}
            rec["estrategias"] = [n for n, v in matches.items() if v]
            excluded = bool(common_exclusions(row, self.risk_cfg["max_spread_multiple"], self.risk_cfg["max_spread_points_abs"]).iloc[0])
            rec["excluida"] = excluded
            if self.strategy and matches.get(self.strategy) and not excluded:
                take, mem = True, {}
                if self.decider is not None:
                    d = self.decider.evaluate(row)
                    take = bool(d["take"].iloc[0])
                    mem = d[["mem_n", "mem_exp", "mem_exp_lo", "mem_hit", "mem_mae", "mem_mfe"]].iloc[0].to_dict()
                rec.update(decision="operar" if take else "no_operar", memoria=mem)
                if take and self.allow_orders and fresh:
                    risk_px = abs(e["entry_ref"] - e["stop"])
                    lot = position_size(equity, self.risk_cfg["risk_per_trade_pct"], risk_px, self.spec,
                                        e["spread_points"] * self.spec.point, self.risk_cfg["cost_buffer_multiple"])
                    tgt = e["entry_ref"] + e["direction"] * self.cfg["backtest"]["target_r"] * risk_px
                    res = self.executor.submit(OrderIntent(e["episode_id"], self.spec.name, int(e["direction"]), lot,
                                                           float(e["stop"]), float(tgt), f"NSMB {e['structure_type']}"))
                    rec["orden"] = res.__dict__
                    if res.ok and res.ticket:
                        self.open_tickets.add(int(res.ticket))
            else:
                rec["decision"] = "sin_estrategia_activa" if not self.strategy else "no_aplica"
            self.log(rec)
            out.append(rec)
        return out

    def run(self, get_m1, get_equity, interval_s: int = 30, stop_file: Path | None = None, once: bool = False):
        while True:
            try:
                m1 = get_m1()
                recs = self.cycle(m1, get_equity(), datetime.now(timezone.utc))
                if self.executor is not None:
                    rep = self.executor.reconcile(self.spec.name, self.open_tickets)
                    self.open_tickets -= set(rep.get("cerradas", []))
                    self.log({"reconciliacion": rep})
                self.log({"ciclo": "ok", "ultima_vela": m1.index[-1], "senales": len(recs)})
            except Exception as e:  # noqa: BLE001  (desconexión, datos...) => se registra y se reintenta
                self.log({"ciclo": "error", "error": repr(e)})
            if once or (stop_file is not None and stop_file.exists()):
                break
            time.sleep(interval_s)
