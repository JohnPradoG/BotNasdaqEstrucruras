"""Fase 1: inspección del entorno. Escribe reports/entorno.json y reports/entorno.md.

Uso:  python scripts/inspect_env.py [--no-mt5]
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nsmb.config import load_settings  # noqa: E402


def run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception as e:  # noqa: BLE001
        return f"no disponible ({e.__class__.__name__})"


def main() -> None:
    cfg = load_settings()
    rep: dict = {"generated_at": datetime.now(timezone.utc).isoformat()}
    rep["os"] = f"{platform.system()} {platform.release()} ({platform.version()})"
    rep["python"] = sys.version.split()[0]
    rep["python_exe"] = sys.executable
    rep["git"] = run(["git", "--version"])
    du = shutil.disk_usage(ROOT)
    rep["disk_free_gb"] = round(du.free / 1e9, 1)
    term = Path(r"C:\Program Files\MetaTrader 5\terminal64.exe")
    rep["mt5_terminal_installed"] = term.exists()
    try:
        import MetaTrader5 as mt5  # noqa: F401
        rep["mt5_package"] = getattr(mt5, "__version__", "instalado")
    except ImportError:
        rep["mt5_package"] = None
    csv = (ROOT / cfg["data"]["csv_m1_path"]).resolve()
    rep["local_csv_m1"] = {"path": str(csv), "exists": csv.exists(), "size_mb": round(csv.stat().st_size / 1e6, 1) if csv.exists() else None}

    rep["mt5_connection"] = {"attempted": False}
    if "--no-mt5" not in sys.argv and rep["mt5_package"]:
        from nsmb.mt5.connector import MT5Connector, MT5Unavailable
        rep["mt5_connection"]["attempted"] = True
        try:
            with MT5Connector(str(term) if term.exists() else None) as c:
                rep["mt5_connection"].update(ok=True, terminal=c.terminal(), account=c.account(),
                                             is_demo=c.is_demo_account(), nasdaq_symbols=c.nasdaq_symbols())
                spec, extra = c.symbol_spec(cfg["symbol"]["name"])
                rep["mt5_connection"]["symbol_spec"] = extra
                rep["mt5_connection"]["tick"] = c.latest_tick(cfg["symbol"]["name"])
                # Historia M1 disponible en el terminal
                import pandas as pd
                r = c.mt5.copy_rates_from_pos(cfg["symbol"]["name"], c.mt5.TIMEFRAME_M1, 0, 10)
                rep["mt5_connection"]["m1_last"] = str(pd.to_datetime(r[-1]["time"], unit="s")) if r is not None and len(r) else None
        except MT5Unavailable as e:
            rep["mt5_connection"].update(ok=False, error=str(e))
    out = ROOT / "reports" / "entorno.json"
    out.write_text(json.dumps(rep, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps(rep, indent=2, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
