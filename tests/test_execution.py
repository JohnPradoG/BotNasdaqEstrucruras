import pytest

from nsmb.config import SymbolSpec
from nsmb.config.loader import load_settings
from nsmb.execution.executor import Executor, LiveTradingBlocked, OrderIntent, PaperBroker, SqliteJournal
from nsmb.memory.store import MemoryStore
from nsmb.risk.manager import RiskLimits, RiskState

SPEC = SymbolSpec("USTECm", 2, 0.01, 0.01, 0.01, 1.0, 0.05, 500.0, 0.01)


@pytest.fixture
def setup(tmp_path):
    store = MemoryStore(tmp_path / "j.sqlite")
    broker = PaperBroker(bid=20000.0, spread=1.0)
    risk = RiskState(RiskLimits(), 10000)
    risk.new_day("d")
    ex = Executor(broker, SPEC, risk, SqliteJournal(store.con), "demo", magic=7, max_retries=2, max_spread_price=5.0)
    return ex, broker, risk, store


def intent(cid="sig-1", d=1, vol=0.5, stop=19980.0):
    return OrderIntent(cid, "USTECm", d, vol, stop, 20050.0 if d > 0 else 19950.0)


def test_live_mode_is_impossible(tmp_path):
    store = MemoryStore(tmp_path / "x.sqlite")
    with pytest.raises(LiveTradingBlocked):
        Executor(PaperBroker(), SPEC, RiskState(RiskLimits(), 1), SqliteJournal(store.con), "live", 1)
    with pytest.raises(LiveTradingBlocked):
        Executor(PaperBroker(), SPEC, RiskState(RiskLimits(), 1), SqliteJournal(store.con), "demo", 1, live_trading_enabled=True)
    with pytest.raises(LiveTradingBlocked):     # cuenta real => bloqueo
        Executor(PaperBroker(demo=False), SPEC, RiskState(RiskLimits(), 1), SqliteJournal(store.con), "demo", 1)


def test_config_cannot_enable_live(tmp_path):
    p = tmp_path / "s.yaml"
    p.write_text("execution:\n  mode: live\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(p)


def test_fill_is_verified(setup):
    ex, broker, risk, _ = setup
    r = ex.submit(intent())
    assert r.ok and r.status == "filled" and r.ticket in broker.positions
    assert risk.open_positions == 1


def test_duplicate_signal_rejected(setup):
    ex, broker, risk, _ = setup
    assert ex.submit(intent("same")).ok
    broker.positions.clear(); risk.open_positions = 0
    r = ex.submit(intent("same"))
    assert r.status == "duplicate" and not broker.positions


def test_max_one_position(setup):
    ex, *_ = setup
    assert ex.submit(intent("a")).ok
    r = ex.submit(intent("b"))
    assert r.status == "blocked" and r.detail == "max_posiciones"


def test_transient_errors_retry_limited(setup):
    ex, broker, risk, _ = setup
    broker.fail_next = ["requote", "requote"]
    r = ex.submit(intent("r1"))
    assert r.ok and r.attempts == 3
    broker.positions.clear(); risk.open_positions = 0
    broker.fail_next = ["timeout"] * 5
    r = ex.submit(intent("r2"))
    assert not r.ok and r.status == "error" and r.attempts == 3


def test_rejection_counts_errors_and_blocks(setup):
    ex, broker, risk, _ = setup
    for i in range(3):
        broker.fail_next = ["reject"]
        assert ex.submit(intent(f"x{i}")).status == "rejected"
    r = ex.submit(intent("x9"))
    assert r.status == "blocked" and r.detail == "errores_ejecucion"


def test_stop_on_wrong_side_and_volume_checks(setup):
    ex, *_ = setup
    assert ex.submit(intent("w", stop=20005.0)).status == "rejected"
    assert ex.submit(intent("v", vol=0.01)).detail == "volumen_menor_que_minimo"
    assert ex.normalize_volume(0.537) == pytest.approx(0.53)


def test_abnormal_spread_blocks(setup):
    ex, broker, *_ = setup
    broker.spread = 50.0
    r = ex.submit(intent("s"))
    assert r.status == "blocked" and r.detail == "spread_anormal"


def test_disconnection_and_recovery(setup):
    ex, broker, risk, _ = setup
    broker.connected = False
    assert ex.submit(intent("d1")).status == "error"
    rep = ex.reconcile("USTECm", set())
    assert not rep["ok"] and ex.blocked == "desconectado"
    assert ex.submit(intent("d2")).status == "blocked"
    broker.connected = True
    assert ex.reconcile("USTECm", set())["ok"] and ex.blocked is None
    risk.execution_errors = 0
    assert ex.submit(intent("d3")).ok


def test_reconcile_detects_unknown_positions(setup):
    ex, broker, *_ = setup
    broker.positions[1] = {"ticket": 1, "magic": 7, "symbol": "USTECm"}
    rep = ex.reconcile("USTECm", set())
    assert rep["desconocidas"] == [1] and ex.blocked == "posiciones_desconocidas"
    assert ex.submit(intent("u")).status == "blocked"
