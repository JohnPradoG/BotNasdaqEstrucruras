"""Fase 7: modo demo (o papel). Por defecto OBSERVA: registra señales y decisiones sin enviar órdenes.

Uso:
  python scripts/run_demo.py --once                 # un ciclo y termina (prueba)
  python scripts/run_demo.py                        # bucle cada 30 s; para detenerlo: Ctrl+C o crear logs/STOP
  python scripts/run_demo.py --allow-orders         # envía órdenes SOLO a la cuenta DEMO y solo si hay estrategia elegida
  python scripts/run_demo.py --paper                # sin MT5: broker simulado (no necesita terminal)
Registro: logs/demo_AAAAMMDD.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nsmb.config import SymbolSpec, load_risk, load_settings  # noqa: E402
from nsmb.execution.executor import Executor, MT5Broker, PaperBroker, SqliteJournal  # noqa: E402
from nsmb.execution.live_loop import LiveLoop, fetch_recent_m1  # noqa: E402
from nsmb.memory.store import MemoryStore  # noqa: E402
from nsmb.mt5.connector import MT5Connector  # noqa: E402
from nsmb.risk.manager import RiskLimits, RiskState  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--once", action="store_true")
ap.add_argument("--paper", action="store_true")
ap.add_argument("--allow-orders", action="store_true")
ap.add_argument("--interval", type=int, default=30)
ap.add_argument("--combo", type=int, default=0)
args = ap.parse_args()

cfg, risk_cfg = load_settings(), load_risk()
combo = cfg["backtest"]["combos"][args.combo]
tag = "_".join(combo)
sel_path = ROOT / "models" / f"seleccion_{tag}.json"
selection = json.loads(sel_path.read_text(encoding="utf-8"))["elegida"] if sel_path.exists() else "NO_OPERAR"
store = MemoryStore(ROOT / cfg["memory"]["db_path"])
journal = SqliteJournal(store.con)
log_path = ROOT / "logs" / f"demo_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
stop_file = ROOT / "logs" / "STOP"

ep_path = ROOT / "data" / "processed" / f"episodes_{tag}.parquet"
pool = pd.read_parquet(ep_path) if ep_path.exists() else pd.DataFrame()
train = pool[pool["detected_time"] <= pd.Timestamp(cfg["split"]["development"][1])] if len(pool) else pool

if args.paper:
    from nsmb.data.pipeline import load_m1
    spec = SymbolSpec.from_settings(cfg)
    hist = load_m1(cfg).iloc[-20000:]
    broker = PaperBroker(bid=float(hist["close"].iloc[-1]), spread=float(hist["spread"].iloc[-1]) * spec.point)
    get_m1 = lambda: hist  # noqa: E731
    get_equity = lambda: cfg["backtest"]["initial_equity"]  # noqa: E731
    mode, conn = "paper", None
else:
    conn = MT5Connector(r"C:\Program Files\MetaTrader 5\terminal64.exe")
    conn.connect()
    if not conn.is_demo_account():
        conn.shutdown()
        sys.exit("La cuenta conectada no es DEMO: el bot no se ejecuta.")
    spec, _ = conn.symbol_spec(cfg["symbol"]["name"])
    broker = MT5Broker(conn.mt5)
    get_m1 = lambda: fetch_recent_m1(conn.mt5, spec.name)  # noqa: E731
    get_equity = lambda: conn.account()["equity"]  # noqa: E731
    mode = "demo"

risk = RiskState(RiskLimits.from_cfg(risk_cfg), get_equity())
executor = Executor(broker, spec, risk, journal, mode, cfg["execution"]["magic"], cfg["execution"]["max_retries"],
                    cfg["execution"]["retry_delay_s"], risk_cfg["max_spread_points_abs"] * spec.point)
loop = LiveLoop(cfg, risk_cfg, spec, combo, selection, pool, train, executor, log_path, allow_orders=args.allow_orders)
print(f"modo={mode} selección={selection} órdenes={'sí (demo)' if loop.allow_orders else 'no (observación)'} registro={log_path}")
try:
    loop.run(get_m1, get_equity, args.interval, stop_file, once=args.once)
except KeyboardInterrupt:
    print("detenido por el usuario")
finally:
    if conn is not None:
        conn.shutdown()
