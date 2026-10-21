"""Cruce de EMAs 20/50 H1: señales, ausencia de anticipación y bucle (stop por distancia, sin cierre de las 15:57)."""
import numpy as np
import pandas as pd
import pytest

from nsmb.config import SymbolSpec
from nsmb.execution.executor import Executor, PaperBroker, SqliteJournal
from nsmb.execution.opening_loop import OpeningLoop
from nsmb.memory.store import MemoryStore
from nsmb.risk.manager import RiskLimits, RiskState
from nsmb.strategies import ema_cross as C

SPEC = SymbolSpec("USTECm", 2, 0.01, 0.01, 0.01, 1.0, 0.05, 500.0, 0.01)


def m1_waves(hours=900, seed=1) -> pd.DataFrame:
    """M1 continuas con una onda lenta (varios cruces de EMA 20/50 en H1) y ruido."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-03-03", periods=hours * 60, freq="1min")
    t = np.arange(len(idx)) / 60.0
    c = 20000 + 300 * np.sin(2 * np.pi * t / 160) + np.cumsum(rng.normal(0, 1.5, len(idx)))
    o = np.r_[c[0], c[:-1]]
    df = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 2, "low": np.minimum(o, c) - 2, "close": c,
                       "tickvol": 50, "spread": 112}, index=idx)
    df.index.name = "time"
    return df


def test_crosses_alternate_and_close_previous():
    ev = C.cross_events(m1_waves(), last_n=None)
    opens = [e for e in ev if e.kind == "abrir"]
    assert len(opens) >= 6
    assert all(a.direction == -b.direction for a, b in zip(opens, opens[1:]))
    for prev, nxt in zip(opens, opens[1:]):
        cl = [e for e in ev if e.kind == "cerrar" and e.client_id == prev.client_id]
        assert len(cl) == 1 and cl[0].detected_time == nxt.detected_time
    assert all(e.stop is None and e.stop_dist > 0 and e.target_r == 2.0 for e in opens)
    assert all(e.detected_time.minute == 0 for e in opens)          # al cierre de una vela H1


def test_signal_matches_ema_definition():
    m1 = m1_waves()
    b = C.h1_bars(m1)
    e = [x for x in C.cross_events(m1, last_n=None) if x.kind == "abrir"][2]
    k = int(np.flatnonzero(b["close_time"].to_numpy() == np.datetime64(e.detected_time))[0])
    f, s = b["ema_f"].to_numpy(), b["ema_s"].to_numpy()
    assert np.sign(f[k] - s[k]) == e.direction and np.sign(f[k - 1] - s[k - 1]) != e.direction
    assert e.stop_dist == pytest.approx(1.5 * b["atr"].iloc[k])


@pytest.mark.parametrize("hours", [300, 451, 612, 777])
def test_no_lookahead_truncated_equals_full(hours):
    m1 = m1_waves()
    T = m1.index[0] + pd.Timedelta(hours=hours, minutes=17)
    full = [e for e in C.cross_events(m1, last_n=None) if e.detected_time <= T]
    part = C.cross_events(m1, now=T, last_n=None)
    assert part == full


def test_open_h1_bar_is_not_used():
    m1 = m1_waves()
    T = m1.index[0] + pd.Timedelta(hours=500, minutes=59)          # vela H1 a falta de su último minuto
    b = C.h1_bars(m1, now=T)
    assert b["close_time"].max() <= T and b["close_time"].max() == m1.index[0] + pd.Timedelta(hours=500)


def make_loop(tmp_path, allow=True):
    store = MemoryStore(tmp_path / "j.sqlite")
    broker = PaperBroker(bid=20000.0, spread=1.12)
    risk = RiskState(RiskLimits(max_open_positions=3), 20000)
    risk.new_day("d")
    ex = Executor(broker, SPEC, risk, SqliteJournal(store.con), "demo", magic=11, max_spread_price=15.0)
    loop = OpeningLoop({"execution": {"max_data_age_s": 180}}, {"risk_per_trade_pct": 0.25, "cost_buffer_multiple": 1.0},
                       SPEC, ex, tmp_path / "log.jsonl", allow_orders=allow, strategies=(C.NAME,),
                       events_fn=C.cross_events, flat_close=False)
    return loop, broker


def test_loop_reverses_on_cross_with_distance_stop(tmp_path):
    loop, broker = make_loop(tmp_path)
    m1 = m1_waves()
    opens = [e for e in C.cross_events(m1, last_n=None) if e.kind == "abrir"]
    first, second = opens[1], opens[2]
    for e in (first, second):
        part = m1[m1.index < e.detected_time]
        broker.bid = float(part["close"].iloc[-1])
        loop.cycle(part, 20000, e.detected_time + pd.Timedelta(seconds=20))
        assert len(broker.positions) == 1
        p = next(iter(broker.positions.values()))
        assert p["direction"] == e.direction
        assert abs(p["price"] - p["stop"]) == pytest.approx(e.stop_dist, abs=0.01)
        assert abs(p["target"] - p["price"]) == pytest.approx(2 * e.stop_dist, abs=0.02)


def test_loop_observation_and_wide_spread(tmp_path):
    loop, broker = make_loop(tmp_path, allow=False)
    m1 = m1_waves()
    e = [x for x in C.cross_events(m1, last_n=None) if x.kind == "abrir"][1]
    part = m1[m1.index < e.detected_time]
    loop.cycle(part, 20000, e.detected_time + pd.Timedelta(seconds=20))
    assert broker.positions == {}
    loop2, broker2 = make_loop(tmp_path / "b") if (tmp_path / "b").mkdir() is None else (None, None)
    broker2.spread = 9.0                                              # más de 8 puntos: no abre
    loop2.cycle(part, 20000, e.detected_time + pd.Timedelta(seconds=20))
    assert broker2.positions == {}
