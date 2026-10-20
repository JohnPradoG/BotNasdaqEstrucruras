"""Simulación de cartera: una posición a la vez, tamaño por riesgo y todos los límites de riesgo."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config.loader import SymbolSpec
from ..risk.manager import RiskLimits, RiskState, position_size


def run_portfolio(signals: pd.DataFrame, spec: SymbolSpec, limits: RiskLimits, initial_equity: float,
                  slippage_price: float, res_col: str = "res_2r", dur_col: str = "dur_2r_min",
                  extra_cost_price: float = 0.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    """`signals` ya filtradas (solo las que se quieren operar), con entry_time, risk_price, res_2r, dur_2r_min.

    `extra_cost_price`: coste adicional por operación (spread/deslizamiento extra) para pruebas de estrés;
    se resta del resultado por unidad (aproximación: no altera qué velas tocan stop u objetivo).
    Devuelve (operaciones, registro de señales descartadas)."""
    s = signals.dropna(subset=[res_col, "entry_time", "risk_price"]).sort_values("entry_time")
    st = RiskState(limits, initial_equity)
    busy_until = pd.Timestamp.min
    trades, skipped = [], []
    vpu = spec.value_per_price_unit
    for e in s.itertuples(index=False):
        et = pd.Timestamp(e.entry_time)
        ny_day = et.tz_localize("UTC").tz_convert("America/New_York").date()
        st.new_day(ny_day)
        if et < busy_until:
            skipped.append({"entry_time": et, "reason": "posicion_abierta"})
            continue
        ok, why = st.can_open()
        if not ok:
            skipped.append({"entry_time": et, "reason": why})
            continue
        cost_unit = getattr(e, 'cost_spread_points', e.spread_points) * spec.point + 2 * slippage_price + extra_cost_price
        lot = position_size(st.equity, limits.risk_per_trade_pct, e.risk_price, spec, cost_unit, limits.cost_buffer_multiple)
        if lot <= 0:
            skipped.append({"entry_time": et, "reason": "lote_minimo_supera_riesgo"})
            continue
        worst = (e.risk_price + cost_unit) * lot * vpu
        if worst > st.daily_room():
            skipped.append({"entry_time": et, "reason": "sin_margen_perdida_diaria"})
            continue
        st.on_open()
        r_net = getattr(e, res_col) - extra_cost_price / e.risk_price
        pnl = r_net * e.risk_price * lot * vpu
        exit_time = et + pd.Timedelta(minutes=int(getattr(e, dur_col)))
        st.on_close(pnl)
        busy_until = exit_time
        trades.append({"entry_time": et, "exit_time": exit_time, "strategy": getattr(e, "strategy", ""),
                       "structure_type": e.structure_type, "direction": e.direction, "session": e.session,
                       "lot": lot, "risk_price": e.risk_price, "r": r_net, "pnl": pnl, "equity": st.equity,
                       "cost": (getattr(e, 'cost_spread_points', e.spread_points) * spec.point + 2 * slippage_price + extra_cost_price) * lot * vpu,
                       "mae_r": e.mae_r, "mfe_r": e.mfe_r, "exit_reason": getattr(e, "exit_reason_2r", ""),
                       "atr_rel": getattr(e, "atr_rel", np.nan)})
    return pd.DataFrame(trades), pd.DataFrame(skipped)
