"""Estrategias de apertura: reglas, ausencia de anticipación y bucle con varias posiciones."""
import numpy as np
import pandas as pd
import pytest

from nsmb.config import SymbolSpec
from nsmb.execution.executor import Executor, PaperBroker, SqliteJournal
from nsmb.execution.opening_loop import OpeningLoop
from nsmb.memory.store import MemoryStore
from nsmb.risk.manager import RiskLimits, RiskState
from nsmb.strategies import opening as O

SPEC = SymbolSpec("USTECm", 2, 0.01, 0.01, 0.01, 1.0, 0.05, 500.0, 0.01)


def sessions(n_days=70, seed=3, last_day_path=None) -> pd.DataFrame:
    """Velas M1 (UTC) de días laborables, 13:00-21:00 UTC; el último día puede tener un camino fijo de cierres."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2025-03-17", periods=n_days)        # horario de verano de EE. UU.: 9:30 NY = 13:30 UTC
    frames, px = [], 20000.0
    for k, d in enumerate(days):
        idx = pd.date_range(d + pd.Timedelta(hours=13), d + pd.Timedelta(hours=21), freq="1min", inclusive="left")
        if k == n_days - 1 and last_day_path is not None:
            c = np.full(len(idx), px)
            c[30:30 + len(last_day_path)] = px + last_day_path          # camino relativo al último precio
            c[30 + len(last_day_path):] = px + last_day_path[-1]
        else:
            c = px + np.cumsum(rng.normal(0.4, 6, len(idx)))
        o = np.r_[px, c[:-1]]
        frames.append(pd.DataFrame({"open": o, "high": np.maximum(o, c) + 1, "low": np.minimum(o, c) - 1, "close": c,
                                    "tickvol": 50, "spread": 112}, index=idx))
        px = c[-1]
    df = pd.concat(frames)
    df.index.name = "time"
    return df


def test_orb5_long_with_stop_at_low():
    m1 = sessions(last_day_path=np.r_[np.arange(1, 6) * 4.0, np.full(10, 20.0)])
    ev = O.day_events(m1)
    e = [x for x in ev if x.strategy == "orb5"][0]
    assert e.direction == 1 and e.target_r == 10.0
    first_open = m1.loc["2025-06-20 13:30", "open"]
    assert e.stop == pytest.approx(first_open - 1, abs=1e-6)        # mínimo de la 1.ª vela de 5 min (apertura - mecha)
    assert e.detected_time == pd.Timestamp("2025-06-20 13:35")


def test_orb5_skips_flat_first_candle():
    path = np.r_[5.0, -5.0, 5.0, -5.0, 0.0, np.zeros(10)]
    ev = O.day_events(sessions(last_day_path=path))
    assert not [x for x in ev if x.strategy == "orb5"]


@pytest.mark.parametrize("cut", ["14:00", "14:31", "15:30", "17:05", "19:30", "20:10"])
def test_no_lookahead_truncated_equals_full(cut):
    m1 = sessions(seed=5)          # día con orb5, orb15 y tres entradas/salidas de noise
    full = O.day_events(m1)
    assert len(full) >= 8
    T = m1.index[-1].normalize() + pd.Timedelta(cut + ":00")
    part = O.day_events(m1, now=T)
    assert part == [e for e in full if e.detected_time <= T]


def test_noise_has_protective_stop_and_unique_ids():
    m1 = sessions(seed=11)
    ev = [e for e in O.day_events(m1) if e.strategy == "noise"]
    opens = [e for e in ev if e.kind == "abrir"]
    assert all(e.stop is not None and (e.stop < 30000) for e in opens)
    assert len({e.client_id for e in opens}) == len(opens)
    for e in ev:
        if e.kind == "cerrar":
            assert any(o.client_id == e.client_id and o.detected_time <= e.detected_time for o in opens)


def test_holiday_is_skipped():
    m1 = sessions()
    hol = m1.index[-1].normalize()
    O_h = O.NYSE_HOLIDAYS
    try:
        O.NYSE_HOLIDAYS = frozenset({hol})
        assert O.day_events(m1) == []
    finally:
        O.NYSE_HOLIDAYS = O_h


def make_loop(tmp_path, allow=True, equity=20000):
    store = MemoryStore(tmp_path / "j.sqlite")
    broker = PaperBroker(bid=20000.0, spread=1.12)
    risk = RiskState(RiskLimits(max_open_positions=3), equity)
    risk.new_day("d")
    ex = Executor(broker, SPEC, risk, SqliteJournal(store.con), "demo", magic=9, max_spread_price=15.0)
    cfg = {"execution": {"max_data_age_s": 180}}
    rcfg = {"risk_per_trade_pct": 0.25, "cost_buffer_multiple": 1.0}
    return OpeningLoop(cfg, rcfg, SPEC, ex, tmp_path / "log.jsonl", allow_orders=allow), broker


def test_loop_observation_sends_nothing(tmp_path):
    loop, broker = make_loop(tmp_path, allow=False)
    m1 = sessions()
    T = m1.index[-1] + pd.Timedelta(minutes=1)
    loop.cycle(m1, 20000, T)
    assert broker.positions == {}


def test_loop_opens_in_real_time_and_flattens_at_1557(tmp_path):
    loop, broker = make_loop(tmp_path)
    m1 = sessions(seed=5)
    day0 = m1.index[-1].normalize()
    for t in pd.date_range(day0 + pd.Timedelta("13:31:00"), day0 + pd.Timedelta("20:10:00"), freq="1min"):
        part = m1[m1.index < t]
        broker.bid = float(part["close"].iloc[-1])
        loop.cycle(part, 20000, t)
        assert len(broker.positions) <= 3
        assert len({p["comment"].split("-")[0] for p in broker.positions.values()}) == len(broker.positions)
    assert broker.positions == {}                     # todo cerrado tras las 15:57 NY (19:57 UTC)
    stale = make_loop(tmp_path / "b", allow=True)[0] if (tmp_path / "b").mkdir() is None else None
    stale.cycle(m1, 20000, day0 + pd.Timedelta("20:10:00"))     # arranca tarde: no ejecuta señales viejas
    assert stale.executor.broker.positions == {}
