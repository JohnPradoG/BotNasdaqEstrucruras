import numpy as np
import pandas as pd
import pytest

from nsmb.backtesting.simulator import M1Arrays, simulate, simulate_multi


def m1(rows, start="2024-03-05 14:00", spread_pts=100, point=0.01):
    idx = pd.date_range(start, periods=len(rows), freq="1min", name="time")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["tickvol"], df["spread"] = 10, spread_pts
    return M1Arrays.from_frame(df, point, flat_before_rollover=False)


def test_long_target_hit_includes_spread_and_slippage():
    m = m1([[100, 100.5, 99.8, 100.2], [100.2, 103.5, 100.1, 103.0]])
    r = simulate(m, 0, +1, stop=99.0, target=103.0, max_minutes=10, slippage=0.1)
    assert r.reason == "target"
    assert r.entry_price == pytest.approx(100 + 1.0 + 0.1)        # ask (spread 100 pts = 1.0) + deslizamiento
    assert r.pnl_price == pytest.approx(103.0 - 0.1 - 101.1)


def test_conservative_when_stop_and_target_same_bar():
    m = m1([[100, 100.1, 99.9, 100], [100, 106, 95, 100]], spread_pts=0)
    r = simulate(m, 0, +1, stop=97, target=103, max_minutes=10, conservative=True)
    assert r.reason == "stop" and r.pnl_price == pytest.approx(-3)


def test_gap_through_stop_fills_at_open():
    m = m1([[100, 100.2, 99.9, 100], [96, 96.5, 95.5, 96]], spread_pts=0)
    r = simulate(m, 0, +1, stop=98, target=110, max_minutes=10)
    assert r.reason == "stop" and r.exit_price == pytest.approx(96)


def test_short_stop_evaluated_on_ask():
    # bid máximo 100.6 + spread 0.5 = ask 101.1 >= stop 101 -> stop
    m = m1([[100, 100.1, 99.9, 100], [100, 100.6, 99.5, 100]], spread_pts=50)
    r = simulate(m, 0, -1, stop=101.0, target=95, max_minutes=10)
    assert r.reason == "stop"
    assert r.pnl_price == pytest.approx(100 - 101.0)


def test_time_exit_and_multi():
    m = m1([[100, 100.4, 99.8, 100.1]] * 5, spread_pts=0)
    res = simulate_multi(m, 0, +1, stop=99, targets_r=[1.0, 2.0], max_minutes=3)
    assert res["time"].reason == "time"
    assert res["time"].exit_i == 2           # 3 minutos: velas 0,1,2
    assert res[1.0].reason == "time"


def test_entry_refused_when_stop_on_wrong_side():
    m = m1([[100, 100.1, 99.9, 100]] * 3, spread_pts=0)
    assert simulate(m, 0, +1, stop=101, target=None, max_minutes=3) is None


def test_flat_window_forces_exit():
    # 16:50 NY (= 20:50 UTC en verano): a las 16:55 debe cerrarse
    rows = [[100, 100.2, 99.9, 100.1]] * 10
    idx = pd.date_range("2024-06-04 20:50", periods=10, freq="1min", name="time")
    df = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx)
    df["tickvol"], df["spread"] = 10, 0
    m = M1Arrays.from_frame(df, 0.01, flat_before_rollover=True)
    r = simulate(m, 0, +1, stop=90, target=120, max_minutes=60)
    assert r.reason == "flat" and pd.Timestamp(m.time[r.exit_i]) == pd.Timestamp("2024-06-04 20:54")


def test_spread_override_sets_cost():
    idx = pd.date_range("2024-03-05 14:00", periods=3, freq="1min", name="time")
    df = pd.DataFrame([[100, 100.5, 99.8, 100.2]] * 3, columns=["open", "high", "low", "close"], index=idx)
    df["tickvol"], df["spread"] = 10, 500          # spread histórico 5 puntos
    m = M1Arrays.from_frame(df, 0.01, flat_before_rollover=False, spread_override_points=112)
    r = simulate(m, 0, +1, stop=99.0, target=None, max_minutes=3)
    assert r.entry_price == pytest.approx(100 + 1.12)
