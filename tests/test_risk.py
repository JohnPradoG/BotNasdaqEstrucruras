import pandas as pd
import pytest

from nsmb.backtesting.portfolio import run_portfolio
from nsmb.config import SymbolSpec
from nsmb.risk.manager import RiskLimits, RiskState, position_size

SPEC = SymbolSpec("USTECm", 2, 0.01, 0.01, 0.01, 1.0, 0.05, 500.0, 0.01)


def test_position_size_respects_risk():
    lot = position_size(10000, 0.25, stop_distance=20.0, spec=SPEC, cost_per_unit=1.5)
    assert lot == pytest.approx(1.16)                     # 25 / 21.5 = 1.1627 -> 1.16
    assert (20.0 + 1.5) * lot * SPEC.value_per_price_unit <= 25.0


def test_position_size_zero_when_min_lot_exceeds_risk():
    # 543,93 USD * 0,25 % = 1,36 USD; stop de 40 puntos con 0,05 lotes = 2 USD > 1,36
    assert position_size(543.93, 0.25, 40.0, SPEC) == 0.0


def test_volume_step_rounding_down():
    lot = position_size(10000, 0.25, 33.3, SPEC)
    assert round(lot / SPEC.volume_step, 6) == int(round(lot / SPEC.volume_step))
    assert lot * 33.3 <= 25.0


def test_forbidden_settings_raise():
    with pytest.raises(ValueError):
        RiskLimits.from_cfg({"allow_martingale": True})
    with pytest.raises(ValueError):
        RiskLimits.from_cfg({"max_open_positions": 3})


def test_daily_loss_blocks_and_resets_next_day():
    st = RiskState(RiskLimits(), 10000)
    st.new_day("d1")
    st.on_open(); st.on_close(-101)
    ok, why = st.can_open()
    assert not ok and why == "perdida_diaria"
    st.new_day("d2")
    assert st.can_open()[0]


def test_consecutive_losses_and_drawdown():
    st = RiskState(RiskLimits(max_consecutive_losses=3, max_daily_loss_pct=100), 10000)
    st.new_day("d1")
    for _ in range(3):
        st.on_open(); st.on_close(-10)
    assert st.can_open() == (False, "perdidas_consecutivas")
    st2 = RiskState(RiskLimits(max_daily_loss_pct=100), 10000)
    st2.new_day("x")
    st2.on_open(); st2.on_close(-1001)
    assert st2.can_open() == (False, "drawdown_total")


def test_one_position_at_a_time_and_no_risk_increase_after_losses():
    rows = []
    t0 = pd.Timestamp("2024-03-05 14:00")
    for i in range(6):
        rows.append({"entry_time": t0 + pd.Timedelta(minutes=10 * i), "risk_price": 20.0, "res_2r": -1.0,
                     "dur_2r_min": 15, "spread_points": 100, "structure_type": "retest", "direction": 1,
                     "session": "ny", "mae_r": 1.0, "mfe_r": 0.2, "exit_reason_2r": "stop"})
    tr, sk = run_portfolio(pd.DataFrame(rows), SPEC, RiskLimits(max_daily_loss_pct=100), 10000, 0.0)
    assert len(tr) == 3 and (sk["reason"] == "posicion_abierta").sum() == 3   # cada operación dura 15 min
    assert tr["lot"].is_monotonic_decreasing                                 # el lote nunca sube tras perder


def test_execution_errors_block():
    st = RiskState(RiskLimits(max_execution_errors=2), 10000)
    st.on_execution_error(); st.on_execution_error()
    assert st.can_open() == (False, "errores_ejecucion")


def test_stale_data_and_spread_block():
    st = RiskState(RiskLimits(), 10000)
    assert st.can_open(data_fresh=False) == (False, "datos_obsoletos")
    assert st.can_open(spread_ok=False) == (False, "spread_anormal")
