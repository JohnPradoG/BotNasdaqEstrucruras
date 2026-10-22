"""Cartera de apertura de NY (orb15, orb5, noise) en demo o papel. Por defecto OBSERVA: no envía órdenes.

Uso:
  python scripts/run_demo_opening.py --once               # un ciclo y termina (prueba)
  python scripts/run_demo_opening.py                      # bucle cada 20 s; para detenerlo: Ctrl+C o crear logs/STOP
  python scripts/run_demo_opening.py --allow-orders       # envía órdenes SOLO a la cuenta DEMO
  python scripts/run_demo_opening.py --paper --once       # sin MT5: últimas velas guardadas y broker simulado
Registro: logs/apertura_AAAAMMDD.jsonl
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nsmb.config import SymbolSpec, load_risk, load_settings  # noqa: E402
from nsmb.execution.executor import Executor, MT5Broker, PaperBroker, SqliteJournal  # noqa: E402
from nsmb.execution.live_loop import fetch_recent_m1  # noqa: E402
from nsmb.execution.opening_loop import OpeningLoop  # noqa: E402
from nsmb.memory.store import MemoryStore  # noqa: E402
from nsmb.risk.manager import RiskLimits, RiskState  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--once", action="store_true")
ap.add_argument("--paper", action="store_true")
ap.add_argument("--allow-orders", action="store_true")
ap.add_argument("--interval", type=int, default=20)
ap.add_argument("--estrategias", default="orb15,orb5,noise")
args = ap.parse_args()

cfg, risk_cfg = load_settings(), load_risk()
store = MemoryStore(ROOT / cfg["memory"]["db_path"])
journal = SqliteJournal(store.con)
(ROOT / "logs").mkdir(exist_ok=True)
log_path = ROOT / "logs" / f"apertura_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
stop_file = ROOT / "logs" / "STOP"

if args.paper:
    from nsmb.data.pipeline import load_m1
    spec = SymbolSpec.from_settings(cfg)
    hist = load_m1(cfg).iloc[-100_000:]
    broker = PaperBroker(bid=float(hist["close"].iloc[-1]), spread=float(hist["spread"].iloc[-1]) * spec.point)
    get_m1 = lambda: hist  # noqa: E731
    get_equity = lambda: cfg["backtest"]["initial_equity"]  # noqa: E731
    mode, conn = "paper", None
else:
    from nsmb.mt5.connector import MT5Connector
    conn = MT5Connector(r"C:\Program Files\MetaTrader 5\terminal64.exe")
    conn.connect()
    if not conn.is_demo_account():
        conn.shutdown()
        sys.exit("La cuenta conectada no es DEMO: el bot no se ejecuta.")
    spec, _ = conn.symbol_spec(cfg["symbol"]["name"])
    broker = MT5Broker(conn.mt5)
    get_m1 = lambda: fetch_recent_m1(conn.mt5, spec.name, 100_000)  # noqa: E731  (~70 sesiones: media 50 y 14 días)
    get_equity = lambda: conn.account()["equity"]  # noqa: E731
    mode = "demo"

risk = RiskState(RiskLimits.from_cfg(risk_cfg), get_equity())
executor = Executor(broker, spec, risk, journal, mode, cfg["execution"]["magic"] + 1, cfg["execution"]["max_retries"],
                    cfg["execution"]["retry_delay_s"], risk_cfg["max_spread_points_abs"] * spec.point)
loop = OpeningLoop(cfg, risk_cfg, spec, executor, log_path, allow_orders=args.allow_orders,
                   strategies=tuple(args.estrategias.split(",")))
print(f"modo={mode} estrategias={args.estrategias} órdenes={'sí (demo)' if args.allow_orders else 'no (observación)'} "
      f"registro={log_path}")
try:
    loop.run(get_m1, get_equity, args.interval, stop_file, once=args.once)
except KeyboardInterrupt:
    print("detenido por el usuario")
finally:
    if conn is not None:
        conn.shutdown()
