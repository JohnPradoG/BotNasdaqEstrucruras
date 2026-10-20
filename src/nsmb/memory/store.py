"""Memoria persistente en SQLite con esquema versionado y migraciones."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ..config.loader import project_root

MIGRATIONS_DIR = project_root() / "database" / "migrations"


def _sql_rows(df: pd.DataFrame, cols: list[str]) -> list[list]:
    d = df[cols].copy()
    for c in cols:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime("%Y-%m-%d %H:%M:%S")
    return d.astype(object).where(d.notna(), None).values.tolist()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path, timeout=120)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA foreign_keys=ON")
        self.migrate()

    # --- migraciones ---------------------------------------------------------------------------
    def schema_version(self) -> int:
        self.con.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
        row = self.con.execute("SELECT MAX(version) FROM schema_version").fetchone()
        return int(row[0] or 0)

    def migrate(self) -> int:
        cur = self.schema_version()
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            v = int(f.name.split("_")[0])
            if v > cur:
                self.con.executescript(f.read_text(encoding="utf-8"))
                self.con.execute("INSERT INTO schema_version VALUES (?, ?)", (v, _now()))
                self.con.commit()
                cur = v
        return cur

    def close(self) -> None:
        self.con.close()

    # --- escritura ---------------------------------------------------------------------------
    def upsert_dataset(self, meta: dict) -> str:
        self.con.execute("INSERT OR REPLACE INTO datasets VALUES (?,?,?,?,?,?,?,?)",
                         (meta["hash"], meta["symbol"], meta["source"].get("provider"), meta["start"], meta["end"],
                          meta["rows"], json.dumps(meta.get("quality"), default=str), _now()))
        self.con.commit()
        return meta["hash"]

    def write_episodes(self, rows: pd.DataFrame) -> int:
        cols = ["episode_id", "dataset_id", "params_hash", "symbol", "tf", "context_tfs", "structure_type",
                "direction", "origin", "bar_index", "detected_time", "level", "extreme", "protective", "entry_ref",
                "invalidation", "atr", "spread_points", "session", "trend_tf", "trend_ctx1", "trend_ctx2",
                "features_json", "confirmations_json", "data_quality"]
        data = _sql_rows(rows, cols)
        self.con.executemany(f"INSERT OR REPLACE INTO episodes ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", data)
        self.con.commit()
        return len(data)

    def write_outcomes(self, rows: pd.DataFrame) -> int:
        cols = ["episode_id", "status", "entry_time", "entry_price", "risk_price", "risk_atr", "matured_time",
                "mfe_r", "mae_r", "mfe_atr", "mae_atr", "duration_min", "res_1r", "res_1_5r", "res_2r", "res_time",
                "exit_reason_2r", "cost_r", "dur_2r_min"]
        data = _sql_rows(rows.reindex(columns=cols), cols)
        self.con.executemany(f"INSERT OR REPLACE INTO outcomes ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", data)
        self.con.commit()
        return len(data)

    def write_aggregates(self, rows: pd.DataFrame) -> None:
        rows = rows.assign(updated_at=_now())
        cols = list(rows.columns)
        self.con.executemany(f"INSERT OR REPLACE INTO aggregates ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                             rows.astype(object).where(rows.notna(), None).values.tolist())
        self.con.commit()

    def log_experiment(self, run_id: str, code_version: str, config: dict, seed: int, results_path: str, summary: dict) -> None:
        self.con.execute("INSERT OR REPLACE INTO experiments VALUES (?,?,?,?,?,?,?)",
                         (run_id, _now(), code_version, json.dumps(config, default=str), seed, results_path,
                          json.dumps(summary, default=str)))
        self.con.commit()

    # --- lectura -----------------------------------------------------------------------------
    def episodes_with_outcomes(self, tf: str | None = None, types: list[str] | None = None,
                               matured_before: str | None = None) -> pd.DataFrame:
        q = ("SELECT e.*, o.status, o.entry_time, o.entry_price, o.risk_price, o.risk_atr, o.matured_time, o.mfe_r, o.mae_r, "
             "o.mfe_atr, o.mae_atr, o.duration_min, o.res_1r, o.res_1_5r, o.res_2r, o.res_time, o.exit_reason_2r, o.cost_r, o.dur_2r_min "
             "FROM episodes e JOIN outcomes o USING (episode_id) WHERE 1=1")
        args: list = []
        if tf:
            q += " AND e.tf = ?"
            args.append(tf)
        if types:
            q += f" AND e.structure_type IN ({','.join('?' * len(types))})"
            args += types
        if matured_before:
            q += " AND o.matured_time <= ?"
            args.append(matured_before)
        df = pd.read_sql_query(q + " ORDER BY e.detected_time", self.con, params=args)
        for c in ("detected_time", "entry_time", "matured_time"):
            df[c] = pd.to_datetime(df[c])
        return df

    def counts(self) -> dict:
        out = {}
        for t in ("datasets", "episodes", "outcomes", "aggregates", "model_versions", "experiments", "execution_journal"):
            out[t] = self.con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        return out
