"""Gestión de riesgo, separada del modelo. El modelo no puede cambiar estos límites."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..config.loader import SymbolSpec


@dataclass(frozen=True)
class RiskLimits:
    risk_per_trade_pct: float = 0.25
    max_daily_loss_pct: float = 1.0
    max_open_positions: int = 1
    max_total_drawdown_pct: float = 10.0
    max_consecutive_losses: int = 6
    max_execution_errors: int = 3
    max_spread_multiple: float = 3.0
    max_spread_points_abs: float = 1500
    cost_buffer_multiple: float = 1.0
    allow_martingale: bool = False
    allow_hedging: bool = False

    @classmethod
    def from_cfg(cls, d: dict) -> "RiskLimits":
        lim = cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
        if lim.allow_martingale or lim.allow_hedging:
            raise ValueError("Martingala y cobertura están prohibidas")
        # Hasta 3 posiciones: una por estrategia de la cartera de apertura (0,25 % cada una => 0,75 % abierto como máximo)
        if lim.risk_per_trade_pct > 1.0 or lim.max_open_positions > 3 or lim.risk_per_trade_pct * lim.max_open_positions > 1.0:
            raise ValueError("Límites de riesgo fuera de lo autorizado")
        return lim


def position_size(equity: float, risk_pct: float, stop_distance: float, spec: SymbolSpec,
                  cost_per_unit: float = 0.0, cost_buffer_multiple: float = 1.0) -> float:
    """Lote tal que la pérdida al stop (más costes estimados) no supere `risk_pct` del equity.
    Devuelve 0.0 si el lote mínimo ya supera el riesgo autorizado (=> no operar)."""
    if stop_distance <= 0 or equity <= 0:
        return 0.0
    money = equity * risk_pct / 100.0
    loss_per_lot = (stop_distance + cost_buffer_multiple * cost_per_unit) * spec.value_per_price_unit
    raw = money / loss_per_lot
    steps = math.floor(raw / spec.volume_step + 1e-9)
    lot = round(steps * spec.volume_step, 8)
    if lot < spec.volume_min:
        return 0.0
    return min(lot, spec.volume_max)


@dataclass
class RiskState:
    limits: RiskLimits
    equity: float
    peak_equity: float = 0.0
    day: object = None
    day_start_equity: float = 0.0
    consecutive_losses: int = 0
    execution_errors: int = 0
    open_positions: int = 0
    blocked_reason: str | None = None
    log: list = field(default_factory=list)

    def __post_init__(self):
        self.peak_equity = max(self.peak_equity, self.equity)
        self.day_start_equity = self.equity

    def new_day(self, day) -> None:
        if day != self.day:
            self.day = day
            self.day_start_equity = self.equity
            self.consecutive_losses = 0 if self.blocked_reason == "perdidas_consecutivas" else self.consecutive_losses
            if self.blocked_reason in ("perdida_diaria", "perdidas_consecutivas"):
                self.blocked_reason = None

    def can_open(self, spread_ok: bool = True, data_fresh: bool = True) -> tuple[bool, str]:
        lim = self.limits
        if self.blocked_reason:
            return False, self.blocked_reason
        if not data_fresh:
            return False, "datos_obsoletos"
        if not spread_ok:
            return False, "spread_anormal"
        if self.open_positions >= lim.max_open_positions:
            return False, "max_posiciones"
        if self.equity <= self.day_start_equity * (1 - lim.max_daily_loss_pct / 100):
            self.blocked_reason = "perdida_diaria"
            return False, self.blocked_reason
        if self.equity <= self.peak_equity * (1 - lim.max_total_drawdown_pct / 100):
            self.blocked_reason = "drawdown_total"
            return False, self.blocked_reason
        if self.consecutive_losses >= lim.max_consecutive_losses:
            self.blocked_reason = "perdidas_consecutivas"
            return False, self.blocked_reason
        if self.execution_errors >= lim.max_execution_errors:
            self.blocked_reason = "errores_ejecucion"
            return False, self.blocked_reason
        return True, "ok"

    def daily_room(self) -> float:
        """Dinero que aún se puede perder hoy sin superar el límite diario."""
        return self.equity - self.day_start_equity * (1 - self.limits.max_daily_loss_pct / 100)

    def on_open(self) -> None:
        self.open_positions += 1

    def on_close(self, pnl: float) -> None:
        self.open_positions = max(0, self.open_positions - 1)
        self.equity += pnl
        self.peak_equity = max(self.peak_equity, self.equity)
        self.consecutive_losses = self.consecutive_losses + 1 if pnl < 0 else 0

    def on_execution_error(self) -> None:
        self.execution_errors += 1

    def on_execution_ok(self) -> None:
        self.execution_errors = 0
