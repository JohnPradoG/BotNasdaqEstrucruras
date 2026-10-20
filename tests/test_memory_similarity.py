import json

import numpy as np
import pandas as pd
import pytest

from nsmb.backtesting.simulator import M1Arrays
from nsmb.config import SymbolSpec
from nsmb.market_structure import StructureParams
from nsmb.memory.builder import FrameCache, build_episodes, compute_outcomes, effective_n, wilson
from nsmb.memory.features import FEATURES
from nsmb.memory.store import MemoryStore
from nsmb.similarity.knn import SimilarityIndex
from nsmb.strategies.decision import DecisionConfig, MemoryDecision
from synthetic import random_walk_m1

SPEC = SymbolSpec("TEST", 2, 0.01, 0.01, 0.01, 1.0, 0.05, 500.0, 0.01)
BT = {"stop_buffer_atr": 0.1, "slippage_points": 50, "max_hold_bars": 24}
MEM = {"targets_r": [1.0, 1.5, 2.0]}


@pytest.fixture(scope="module")
def episodes():
    m1 = random_walk_m1(n=40000, seed=5)
    cache = FrameCache(m1, StructureParams())
    m1a = M1Arrays.from_frame(m1, 0.01)
    ep = build_episodes(cache, ["H1", "M15", "M5"], SPEC, m1a, BT, MEM, "ds", "TEST")
    out = compute_outcomes(ep, m1a, "M5", BT, MEM, SPEC)
    return ep, out, ep.merge(out, on="episode_id")


def test_episodes_have_features_and_ids(episodes):
    ep, out, full = episodes
    assert len(ep) > 100 and ep["episode_id"].is_unique
    f = json.loads(ep["features_json"].iloc[0])
    assert set(f) == set(FEATURES)
    assert (full.loc[full.status == "ok", "matured_time"] > full.loc[full.status == "ok", "detected_time"]).all()


def test_outcome_entry_after_detection(episodes):
    _, _, full = episodes
    ok = full[full.status == "ok"]
    assert (ok["entry_time"] >= ok["detected_time"]).all()
    assert ok["res_2r"].between(-3, 2.01).all()
    assert (ok["mae_r"] >= 0).all() and (ok["mfe_r"] >= 0).all()


def test_store_roundtrip_and_migrations(tmp_path, episodes):
    ep, out, _ = episodes
    st = MemoryStore(tmp_path / "m.sqlite")
    assert st.schema_version() >= 2
    st.upsert_dataset({"hash": "ds", "symbol": "TEST", "source": {"provider": "sintetico"}, "start": "a", "end": "b", "rows": 1})
    st.write_episodes(ep)
    st.write_outcomes(out)
    back = st.episodes_with_outcomes(tf="M5")
    assert len(back) == len(ep)
    st.close()
    st2 = MemoryStore(tmp_path / "m.sqlite")          # persistente: se reabre con los mismos datos
    assert st2.counts()["episodes"] == len(ep)
    cutoff = back["detected_time"].median()
    part = st2.episodes_with_outcomes(matured_before=str(cutoff))
    assert (part["matured_time"] <= cutoff).all()


def test_similarity_only_uses_matured_episodes(episodes):
    _, _, full = episodes
    ok = full[full.status == "ok"].sort_values("detected_time")
    idx = SimilarityIndex(k=10, min_separation=pd.Timedelta(0)).fit(ok).set_pool(ok)
    q = ok.iloc[len(ok) // 2]
    ans = idx.query(q[FEATURES].to_numpy(float), q["detected_time"])
    assert ans is not None
    assert ans.n_candidates == int((ok["matured_time"] <= q["detected_time"]).sum())
    nb = idx.neighbors(q[FEATURES].to_numpy(float), q["detected_time"])
    assert (nb["matured_time"] <= q["detected_time"]).all()
    assert q["episode_id"] not in set(nb["episode_id"])     # nunca se usa a sí mismo


def test_similarity_recovers_identical_case():
    rng = np.random.default_rng(1)
    n = 300
    df = pd.DataFrame(rng.normal(size=(n, len(FEATURES))), columns=FEATURES)
    df["detected_time"] = pd.date_range("2023-01-01", periods=n, freq="h")
    df["matured_time"] = df["detected_time"] + pd.Timedelta(minutes=30)
    df["status"], df["res_2r"], df["mae_r"], df["mfe_r"], df["duration_min"] = "ok", rng.normal(size=n), 0.5, 1.0, 30
    df["episode_id"] = [str(i) for i in range(n)]
    idx = SimilarityIndex(k=1, min_separation=pd.Timedelta(0)).fit(df).set_pool(df)
    target = df.iloc[10]
    nb = idx.neighbors(target[FEATURES].to_numpy(float), df["detected_time"].iloc[-1], k=1)
    assert nb["episode_id"].iloc[0] == "10" and nb["distance"].iloc[0] == pytest.approx(0)


def test_overlapping_neighbors_count_once():
    t = pd.Series(pd.to_datetime(["2024-01-01 10:00", "2024-01-01 10:05", "2024-01-01 10:20", "2024-01-01 12:00"]))
    assert effective_n(t, pd.Timedelta(minutes=30)) == 2


def test_wilson_interval():
    lo, hi = wilson(30, 100)
    assert 0.22 < lo < 0.30 < hi < 0.38
    lo2, hi2 = wilson(3, 10)
    assert hi2 - lo2 > hi - lo          # muestras pequeñas => intervalos anchos


def test_decision_says_no_trade_without_enough_cases(episodes):
    _, _, full = episodes
    ok = full[full.status == "ok"]
    md = MemoryDecision(ok, ok, DecisionConfig(k=50, min_effective_n=10_000))
    ev = md.evaluate(ok.head(20))
    assert not ev["take"].any() and (ev["reason"] == "pocos_casos").all()
