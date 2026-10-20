"""Aprendizaje controlado: versiones del modelo de decisión, promoción con validación y reversión.

- Las estadísticas solo se recalculan con episodios MADURADOS (desenlace conocido).
- Cada versión nueva es "candidate"; solo pasa a "active" si su walk-forward cumple los criterios y no es
  peor que la versión activa. Las reglas no cambian después de cada operación.
- Si el rendimiento reciente de la versión activa se deteriora (cota superior del IC 90 % de la expectativa
  < umbral), se revierte a la versión validada anterior y se bloquean nuevas entradas hasta revisión.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import numpy as np


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ModelRegistry:
    def __init__(self, con):
        self.con = con

    def register(self, params: dict, train_end: str, metrics: dict, parent_id: str | None = None) -> str:
        vid = hashlib.sha1(json.dumps([params, train_end], sort_keys=True, default=str).encode()).hexdigest()[:12]
        self.con.execute("INSERT OR REPLACE INTO model_versions VALUES (?,?,?,?,?,?,?)",
                         (vid, _now(), parent_id, json.dumps(params, default=str), train_end,
                          json.dumps(metrics, default=str), "candidate"))
        self.con.commit()
        return vid

    def active(self) -> dict | None:
        r = self.con.execute("SELECT version_id, params_json, metrics_json, parent_id FROM model_versions "
                             "WHERE status='active' ORDER BY created_at DESC LIMIT 1").fetchone()
        return None if r is None else {"version_id": r[0], "params": json.loads(r[1]), "metrics": json.loads(r[2] or "{}"),
                                       "parent_id": r[3]}

    def _set(self, vid: str, status: str) -> None:
        self.con.execute("UPDATE model_versions SET status=? WHERE version_id=?", (status, vid))
        self.con.commit()

    def promote(self, vid: str, min_n: int = 30, min_t: float = 1.0) -> tuple[bool, str]:
        """Promueve si el walk-forward del candidato cumple los criterios y no es peor que el activo."""
        m = json.loads(self.con.execute("SELECT metrics_json FROM model_versions WHERE version_id=?", (vid,)).fetchone()[0])
        if m.get("n", 0) < min_n or (m.get("t") or 0) < min_t or (m.get("exp_r") or -1) <= 0:
            self._set(vid, "rejected")
            return False, "no_cumple_criterios"
        cur = self.active()
        if cur and (cur["metrics"].get("exp_r") or 0) > (m.get("exp_r") or 0) and (cur["metrics"].get("t") or 0) > (m.get("t") or 0):
            self._set(vid, "rejected")
            return False, "peor_que_activa"
        if cur:
            self._set(cur["version_id"], "retired")
        self._set(vid, "active")
        return True, "promovida"

    def check_degradation(self, recent_r: list[float], min_n: int = 20, floor_r: float = 0.0) -> tuple[bool, str]:
        """True si hay deterioro: con ≥ min_n operaciones, la cota superior del IC 90 % de la media < floor_r."""
        r = np.asarray(recent_r, float)
        if len(r) < min_n:
            return False, "pocas_operaciones"
        ucb = r.mean() + 1.645 * r.std(ddof=1) / np.sqrt(len(r))
        return bool(ucb < floor_r), f"ucb90={ucb:.3f}"

    def revert(self) -> str | None:
        """Retira la versión activa (deteriorada) y reactiva su padre validado, si existe."""
        cur = self.active()
        if not cur:
            return None
        self._set(cur["version_id"], "retired")
        if cur["parent_id"]:
            self._set(cur["parent_id"], "active")
        return cur["parent_id"]
