"""Cruce de EMAs 20/50 en H1 (src/nsmb/strategies/ema_cross.py) en demo o papel. Por defecto OBSERVA: no envía órdenes.

Va en un proceso aparte de la cartera de apertura, con su propio número mágico (magic + 2), y puede funcionar a la vez.
La estrategia NO está aprobada (t < 2): el modo observación sirve para medirla en tiempo real sin arriesgar.

Uso:
  python scripts/run_demo_ema.py --once               # un ciclo y termina (prueba)
  python scripts/run_demo_ema.py                      # bucle cada 20 s; para detenerlo: Ctrl+C o crear logs/STOP_EMA
  python scripts/run_demo_ema.py --allow-orders       # envía órdenes SOLO a la cuenta DEMO
  python scripts/run_demo_ema.py --paper --once       # sin MT5: últimas velas guardadas y broker simulado
Registro: logs/ema_h1_AAAAMMDD.jsonl
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
from nsmb.strategies import ema_cross as C  # noqa: E402
from nsmb.memory.store import MemoryStore  # noqa: E402
from nsmb.risk.manager import RiskLimits, RiskState  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--once", action="store_true")
ap.add_argument("--paper", action="store_true")
ap.add_argument("--allow-orders", action="store_true")
ap.add_argument("--interval", type=int, default=20)
args = ap.parse_args()

cfg, risk_cfg = load_settings(), load_risk()
store = MemoryStore(ROOT / cfg["memory"]["db_path"])
journal = SqliteJournal(store.con)
(ROOT / "logs").mkdir(exist_ok=True)
log_path = ROOT / "logs" / f"ema_h1_{datetime.now(timezone.utc):%Y%m%d}.jsonl"
stop_file = ROOT / "logs" / "STOP_EMA"

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
    get_m1 = lambda: fetch_recent_m1(conn.mt5, spec.name, 100_000)  # noqa: E731  (~1.600 velas H1 para las EMAs)
    get_equity = lambda: conn.account()["equity"]  # noqa: E731
    mode = "demo"

risk = RiskState(RiskLimits.from_cfg(risk_cfg), get_equity())
executor = Executor(broker, spec, risk, journal, mode, cfg["execution"]["magic"] + 2, cfg["execution"]["max_retries"],
                    cfg["execution"]["retry_delay_s"], risk_cfg["max_spread_points_abs"] * spec.point)
loop = OpeningLoop(cfg, risk_cfg, spec, executor, log_path, allow_orders=args.allow_orders,
                   strategies=(C.NAME,), events_fn=C.cross_events, flat_close=False)
print(f"modo={mode} estrategia={C.NAME} órdenes={'sí (demo)' if args.allow_orders else 'no (observación)'} "
      f"registro={log_path}")
try:
    loop.run(get_m1, get_equity, args.interval, stop_file, once=args.once)
except KeyboardInterrupt:
    print("detenido por el usuario")
finally:
    if conn is not None:
        conn.shutdown()
