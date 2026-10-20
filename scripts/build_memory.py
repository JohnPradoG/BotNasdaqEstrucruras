"""Fase 4: construye la memoria histórica (episodios + desenlaces + agregados) en SQLite.

Uso:  python scripts/build_memory.py [--combos 0 1 2] [--start 2021-11-01] [--end 2026-12-31]
Las combinaciones son las de settings.yaml -> backtest.combos (0 = H4/H1/M15, 1 = H1/M15/M5, 2 = M15/M5/M1).
"""
import argparse
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nsmb.backtesting.simulator import M1Arrays  # noqa: E402
from nsmb.config import SymbolSpec, load_settings  # noqa: E402
from nsmb.data.pipeline import load_m1  # noqa: E402
from nsmb.data.providers import M1Cache  # noqa: E402
from nsmb.market_structure import StructureParams  # noqa: E402
from nsmb.memory.builder import FrameCache, aggregate, build_episodes, compute_outcomes  # noqa: E402
from nsmb.memory.store import MemoryStore  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--combos", type=int, nargs="*", default=[0, 1])
ap.add_argument("--start", default=None)
ap.add_argument("--end", default=None)
args = ap.parse_args()

cfg = load_settings()
spec = SymbolSpec.from_settings(cfg)
m1 = load_m1(cfg)
if args.start:
    m1 = m1[m1.index >= pd.Timestamp(args.start)]
if args.end:
    m1 = m1[m1.index < pd.Timestamp(args.end)]
_, meta = M1Cache(ROOT / cfg["data"]["cache_dir"]).load(cfg["symbol"]["name"])
store = MemoryStore(ROOT / cfg["memory"]["db_path"])
ds = store.upsert_dataset(meta)
m1a = M1Arrays.from_frame(m1, spec.point, cfg["backtest"]["flat_before_rollover"], cfg["backtest"].get("cost_spread_points"))
cache = FrameCache(m1, StructureParams.from_cfg(cfg["structure"]), cfg["structure"]["atr_period"], cfg["structure"]["rsi_period"])

for ci in args.combos:
    combo = cfg["backtest"]["combos"][ci]
    t0 = time.time()
    ep = build_episodes(cache, combo, spec, m1a, cfg["backtest"], cfg["memory"], ds, spec.name)
    out = compute_outcomes(ep, m1a, combo[2], cfg["backtest"], cfg["memory"], spec)
    store.write_episodes(ep)
    store.write_outcomes(out)
    full = ep.merge(out, on="episode_id")
    agg = aggregate(full, f"{m1.index[0].date()}..{m1.index[-1].date()}", pd.Timedelta(minutes=30))
    store.write_aggregates(agg)
    full.to_parquet(ROOT / "data" / "processed" / f"episodes_{'_'.join(combo)}.parquet")
    print(f"{combo}: {len(ep):,} episodios, {int((out.status == 'ok').sum()):,} con desenlace, "
          f"{len(agg):,} agregados, {time.time() - t0:.0f}s", flush=True)
print(store.counts())
