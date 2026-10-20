"""Carga de configuración (YAML) y especificación del símbolo."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_yaml(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_settings(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else project_root() / "config" / "settings.yaml"
    cfg = _read_yaml(path)
    # Salvaguarda: la operativa real no se puede activar por configuración.
    ex = cfg.setdefault("execution", {})
    if ex.get("mode") == "live" or ex.get("live_trading_enabled"):
        raise ValueError("La operativa real está deshabilitada en este proyecto (execution.mode/live_trading_enabled).")
    return cfg


def load_risk(path: str | Path | None = None) -> dict[str, Any]:
    path = Path(path) if path else project_root() / "config" / "risk.yaml"
    return _read_yaml(path)


@dataclass(frozen=True)
class SymbolSpec:
    name: str
    digits: int
    point: float
    tick_size: float
    tick_value: float          # dinero por tick y por lote
    contract_size: float
    volume_min: float
    volume_max: float
    volume_step: float
    stops_level: int = 0       # en points
    swap_long_points: float = 0.0
    swap_short_points: float = 0.0
    swap_3day: int = 3

    @property
    def value_per_price_unit(self) -> float:
        """Dinero que gana/pierde 1 lote por cada 1.0 de movimiento del precio."""
        return self.tick_value / self.tick_size

    @classmethod
    def from_settings(cls, cfg: dict[str, Any]) -> "SymbolSpec":
        fs = cfg["symbol"]["fallback_spec"]
        return cls(name=cfg["symbol"]["name"], **fs)
