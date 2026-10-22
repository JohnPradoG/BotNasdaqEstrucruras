"""Comprueba que el módulo del bot (src/nsmb/strategies/ema_cross.py) da las mismas entradas que el backtest
(scripts/run_ema_cross.py, variante H1|20/50|2R|ambas).

Para cada día del periodo le pasa al módulo solo las últimas 100.000 velas M1 hasta el final de ese día (como en vivo,
donde las EMAs arrancan con menos historia) y compara dirección, hora y distancia del stop de cada entrada.

Uso: python scripts/check_ema_parity.py [desde] [hasta]     (por defecto 2025-01-01 2025-12-31)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_ema_cross as E  # noqa: E402
import run_ideas as I  # noqa: E402
from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.strategies import ema_cross as C  # noqa: E402


def main(a="2025-01-01", b="2025-12-31") -> int:
    spec = SymbolSpec.from_settings(load_settings())
    m1 = pd.read_parquet(ROOT / "data" / "processed" / "USTECm_M1.parquet")
    m1.index = m1.index.astype("datetime64[ns]")
    m = M1Arrays.from_frame(m1, spec.point, False, I.SPREAD_PTS / spec.point)
    m.flat_mask = np.zeros(len(m1), bool)
    hb = E.bars(m1, "H1")
    cx = E.crosses(hb, C.FAST, C.SLOW)
    bt = E.run(m, cx, "2R", (1, -1))
    end = pd.Timestamp(b) + pd.Timedelta(days=1)
    bt = bt[(bt["detected_time"] >= a) & (bt["detected_time"] < end)]
    bt_set = {(int(r.direction), pd.Timestamp(r.detected_time)) for r in bt.itertuples()}
    dist = dict(zip(pd.to_datetime(cx["t"]), C.STOP_ATR * cx["atr"]))

    mod, bad_stop = {}, 0
    times = m1.index.to_numpy()
    for day in pd.date_range(a, end, freq="D"):
        j = int(np.searchsorted(times, np.datetime64(day + pd.Timedelta(days=1))))
        win = m1.iloc[max(0, j - 100_000):j]
        for e in C.cross_events(win, last_n=10):
            # solo los cruces de ese día: en vivo el bot actúa sobre el cruce recién cerrado
            if e.kind == "abrir" and day <= e.detected_time < day + pd.Timedelta(days=1) and e.detected_time < end:
                mod[(e.direction, e.detected_time)] = e.stop_dist
    for k, sd in mod.items():
        if k[1] in dist and abs(dist[k[1]] - sd) > 1e-6:
            bad_stop += 1
    mod_set = set(mod)
    only_bt, only_mod = bt_set - mod_set, mod_set - bt_set
    print(f"backtest {len(bt_set)} entradas, módulo {len(mod_set)}, coinciden {len(bt_set & mod_set)}; "
          f"stops distintos {bad_stop}")
    for k in sorted(only_bt)[:10]:
        print("  solo backtest:", k)
    for k in sorted(only_mod)[:10]:
        print("  solo módulo:  ", k)
    n = max(len(bt_set), 1)
    return 0 if len(bt_set & mod_set) >= 0.97 * n and len(only_mod) <= 0.03 * n and bad_stop == 0 else 1


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
