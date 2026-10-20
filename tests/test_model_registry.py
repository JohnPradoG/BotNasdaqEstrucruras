import numpy as np

from nsmb.memory.store import MemoryStore
from nsmb.monitoring.model_registry import ModelRegistry


def test_promotion_rules_and_revert(tmp_path):
    reg = ModelRegistry(MemoryStore(tmp_path / "r.sqlite").con)
    bad = reg.register({"k": 10}, "2023-12-31", {"n": 12, "exp_r": 0.3, "t": 2.0})
    assert reg.promote(bad) == (False, "no_cumple_criterios")
    v1 = reg.register({"k": 30}, "2023-12-31", {"n": 80, "exp_r": 0.10, "t": 1.5})
    assert reg.promote(v1)[0] and reg.active()["version_id"] == v1
    worse = reg.register({"k": 60}, "2024-06-30", {"n": 90, "exp_r": 0.05, "t": 1.1}, parent_id=v1)
    assert reg.promote(worse) == (False, "peor_que_activa")
    v2 = reg.register({"k": 100}, "2024-06-30", {"n": 120, "exp_r": 0.12, "t": 1.8}, parent_id=v1)
    assert reg.promote(v2)[0]
    assert reg.revert() == v1 and reg.active()["version_id"] == v1


def test_degradation_detection():
    reg = ModelRegistry(None)
    assert reg.check_degradation([0.5] * 5)[0] is False                  # pocas operaciones
    rng = np.random.default_rng(0)
    assert reg.check_degradation(list(rng.normal(-0.4, 1, 80)))[0] is True
    assert reg.check_degradation(list(rng.normal(0.3, 1, 80)))[0] is False
