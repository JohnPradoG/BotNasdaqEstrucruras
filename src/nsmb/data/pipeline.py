"""Obtención + auditoría + caché de datos. Punto de entrada único para el resto del proyecto."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ..config.loader import project_root
from .providers import CsvMT5Provider, M1Cache, MT5Provider
from .quality import audit_m1
from .timeframes import resample


def build_provider(cfg: dict, prefer: str | None = None):
    src = prefer or cfg["data"]["source"]
    if src == "mt5":
        from ..mt5.connector import MT5Connector
        conn = MT5Connector()
        conn.connect()
        return MT5Provider(conn), conn
    return CsvMT5Provider(project_root() / cfg["data"]["csv_m1_path"]), None


def refresh_m1(cfg: dict, prefer: str | None = None) -> tuple[pd.DataFrame, dict]:
    symbol = cfg["symbol"]["name"]
    cache = M1Cache(project_root() / cfg["data"]["cache_dir"])
    provider, conn = build_provider(cfg, prefer)
    try:
        raw = cache.update_incremental(symbol, provider)
    finally:
        if conn is not None:
            conn.shutdown()
    clean, rep = audit_m1(raw)
    meta = cache.save(symbol, clean, provider.describe(), rep)
    return clean, meta


def load_m1(cfg: dict) -> pd.DataFrame:
    df, meta = M1Cache(project_root() / cfg["data"]["cache_dir"]).load(cfg["symbol"]["name"])
    if df is None:
        df, _ = refresh_m1(cfg, prefer="csv")
    return df


def load_frames(cfg: dict, tfs: list[str] | None = None, start: str | None = None, end: str | None = None) -> dict[str, pd.DataFrame]:
    m1 = load_m1(cfg)
    if start:
        m1 = m1[m1.index >= pd.Timestamp(start)]
    if end:
        m1 = m1[m1.index < pd.Timestamp(end)]
    tfs = tfs or cfg["data"]["timeframes"]
    return {tf: resample(m1, tf) for tf in tfs}


def write_data_report(meta: dict, path: Path) -> None:
    q = meta["quality"]
    lines = ["# Auditoría de datos M1", "", f"- Símbolo: **{meta['symbol']}**",
             f"- Fuente: `{meta['source'].get('provider')}` {meta['source'].get('path', '')}",
             f"- Periodo: {meta['start']} → {meta['end']} (hora del servidor = UTC)",
             f"- Velas: {meta['rows']:,} (entrada {q['rows_in']:,}); hash `{meta['hash']}`",
             f"- Duplicadas eliminadas: {q['duplicates']}; OHLC incoherentes: {q['bad_ohlc']}; precios ≤0: {q['non_positive']}",
             f"- Saltos de rentabilidad extremos (>12 MAD): {q['return_spikes']} (se conservan, solo se marcan)",
             f"- Spread (points): mediana {q['spread_points']['median']:.0f}, p95 {q['spread_points']['p95']:.0f}, p99 {q['spread_points']['p99']:.0f}, máx {q['spread_points']['max']}",
             f"- Velas con volumen de ticks 0: {q['zero_tickvol']}", "", "## Huecos", ""]
    for k, v in sorted(q["gaps_by_kind"].items()):
        lines.append(f"- {k}: {v}")
    lines += ["", f"Huecos largos (>30 min, no fin de semana ni pausa diaria): {q['long_gaps_count']}. Muestra:", ""]
    for s, e, h, k in q["long_gaps_sample"]:
        lines.append(f"- {s} → {e} ({h} h, {k})")
    lines += ["", "## Velas por año", ""] + [f"- {y}: {n:,}" for y, n in q["rows_per_year"].items()]
    lines += ["", "## Limitaciones", "",
              "- Solo hay velas M1 (precio BID + spread de la vela). Los ticks históricos del bróker solo existen para fechas recientes (comprobado: 2026-10-19 sí, 2025-06-02 y anteriores no), así que el orden intravela dentro de un minuto es desconocido.",
              "- El spread de cada vela M1 es el que registra MT5 (normalmente el mínimo o el de apertura), no el máximo: los costes reales pueden ser algo mayores.",
              "- No se inventan velas: los huecos se clasifican pero no se rellenan."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
