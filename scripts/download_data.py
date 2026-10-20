"""Fase 2: descarga (MT5 o CSV), audita y guarda en caché las velas M1. Genera reports/datos.md.

Uso:  python scripts/download_data.py [--source mt5|csv]
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from nsmb.config import load_settings  # noqa: E402
from nsmb.data.pipeline import refresh_m1, write_data_report  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--source", choices=["mt5", "csv"], default=None)
args = ap.parse_args()
cfg = load_settings()
try:
    df, meta = refresh_m1(cfg, prefer=args.source)
except Exception as e:  # noqa: BLE001
    if args.source == "mt5" or (args.source is None and cfg["data"]["source"] == "mt5"):
        print(f"MT5 no disponible ({e}); uso el CSV local")
        df, meta = refresh_m1(cfg, prefer="csv")
    else:
        raise
write_data_report(meta, ROOT / "reports" / "datos.md")
print(f"{meta['rows']:,} velas {meta['start']} -> {meta['end']} fuente={meta['source']['provider']}")
