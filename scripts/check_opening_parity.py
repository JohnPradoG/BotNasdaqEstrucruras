"""Comprueba que el módulo del bot (src/nsmb/strategies/opening.py) da las mismas entradas que el backtest.

Recorre cada sesión de un periodo, le pasa al módulo solo las velas hasta el final de ese día (como en vivo)
y compara estrategia, dirección y hora de cada entrada con las operaciones del backtest (run_profundo.build).

Uso: python scripts/check_opening_parity.py [desde] [hasta]     (por defecto 2025-01-01 2025-12-31)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_ideas as I  # noqa: E402
import run_profundo as P  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.indicators.core import add_indicators  # noqa: E402
from nsmb.market_structure.engine import StructureEngine, StructureParams  # noqa: E402
from nsmb.strategies import opening as O  # noqa: E402


def main(a="2025-01-01", b="2025-12-31") -> int:
    cfg = load_settings()
    spec = SymbolSpec.from_settings(cfg)
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    d1 = I.daily_bars(m1)
    _, st = StructureEngine(StructureParams.from_cfg(cfg["structure"])).run(add_indicators(d1))
    bias = I.daily_bias(d1, st)
    S = P.build(m1, spec, bias, d1, 1.12, 0.5)
    bt = pd.concat([S[k] for k in ("orb15", "orb5", "noise")], ignore_index=True)
    bt = bt[(bt["entry_time"] >= a) & (bt["entry_time"] < pd.Timestamp(b) + pd.Timedelta(days=1))]
    bt_set = {(r.estrategia, int(r.direction), pd.Timestamp(r.entry_time)) for r in bt.itertuples()}

    x = O._ny(m1)
    dates = sorted(x.loc[(x.index >= a) & (x.index < pd.Timestamp(b) + pd.Timedelta(days=2)), "date"].unique())
    mod_set = set()
    for dt in dates:
        end = O.flat_time_utc(dt)
        win = m1[(m1.index >= end - pd.Timedelta(days=110)) & (m1.index < end)]
        for e in O.day_events(win):
            if e.kind == "abrir":
                mod_set.add((e.strategy, e.direction, e.detected_time))
    mod_set = {k for k in mod_set if pd.Timestamp(a) <= k[2] < pd.Timestamp(b) + pd.Timedelta(days=1)}
    only_bt, only_mod = bt_set - mod_set, mod_set - bt_set
    print(f"backtest {len(bt_set)} entradas, módulo {len(mod_set)}, coinciden {len(bt_set & mod_set)}")
    for name in ("orb15", "orb5", "noise"):
        nb = sum(k[0] == name for k in bt_set)
        nc = sum(k[0] == name for k in bt_set & mod_set)
        print(f"  {name}: {nc}/{nb} del backtest; solo en módulo {sum(k[0] == name for k in only_mod)}")
    for k in sorted(only_bt)[:10]:
        print("  solo backtest:", k)
    for k in sorted(only_mod)[:10]:
        print("  solo módulo:  ", k)
    return 0 if len(bt_set & mod_set) >= 0.97 * max(len(bt_set), 1) and len(only_mod) <= 0.03 * max(len(bt_set), 1) else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
