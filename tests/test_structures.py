import numpy as np
import pandas as pd
import pytest

from nsmb.market_structure import StructureEngine, StructureParams, fractal_pivots
from synthetic import prepared, zigzag, random_frame

P = StructureParams(pivot_left=2, pivot_right=2, min_swing_atr=0.3, retest_tolerance_atr=0.6,
                    retest_max_bars=10, double_tolerance_atr=1.0, double_min_bars=4, double_min_depth_atr=0.5)


def run(closes, params=P, **kw):
    df = prepared(closes, **kw)
    ev, st = StructureEngine(params).run(df)
    return df, ev, st


def test_pivots_are_confirmed_only_after_right_bars():
    h = np.array([1, 2, 3, 5, 3, 2, 1, 2, 3], float)
    l = h - 0.5
    piv = fractal_pivots(h, l, 2, 2)
    highs = [p for p in piv if p.kind == "H"]
    assert len(highs) == 1 and highs[0].idx == 3 and highs[0].confirm_idx == 5 and highs[0].price == 5


def test_pivot_not_detected_without_right_side():
    h = np.array([1, 2, 3, 5, 4], float)        # falta una vela a la derecha
    assert not [p for p in fractal_pivots(h, h - 0.5, 2, 2) if p.kind == "H"]


def test_uptrend_labels_and_bos_up():
    closes = zigzag([100, 110, 105, 115, 110, 120, 114, 126])
    df, ev, st = run(closes)
    assert (st["trend"].iloc[-5:] == 1).any()
    bos = ev[(ev.type == "bos") & (ev.direction == 1)]
    assert len(bos) >= 2
    first = bos.iloc[0]
    # la ruptura ocurre en la primera vela que CIERRA por encima del nivel
    t = int(first.t)
    assert df["close"].iloc[t] > first.level and df["close"].iloc[t - 1] <= first.level


def test_choch_after_downtrend_reversal():
    closes = zigzag([130, 120, 125, 112, 118, 104, 109, 100, 112, 106, 120])
    df, ev, st = run(closes)
    ch = ev[(ev.type == "choch") & (ev.direction == 1)]
    assert len(ch) >= 1
    assert (ev[(ev.type == "bos") & (ev.direction == -1)].t < ch.t.iloc[0]).any()


def test_sweep_detected_when_wick_breaks_but_close_does_not():
    closes = zigzag([100, 110, 104, 109.5, 103])
    df = prepared(closes)
    # forzamos una mecha por encima del máximo 110 sin cerrar por encima
    k = 6 + 6 + 5
    df.iloc[k, df.columns.get_loc("high")] = 111.0
    ev, _ = StructureEngine(P).run(df)
    sw = ev[(ev.type == "sweep") & (ev.direction == -1)]
    assert len(sw) == 1 and sw.iloc[0].t == k and sw.iloc[0].level == pytest.approx(110.2)


def test_false_breakout_detected():
    closes = list(zigzag([100, 110, 104])) + [107, 109, 111, 108, 106, 104]
    df, ev, _ = run(np.array(closes))
    fb = ev[(ev.type == "false_break") & (ev.direction == -1)]
    assert len(fb) == 1
    assert fb.iloc[0].bars_since_break <= P.false_break_bars


def test_retest_after_break():
    closes = list(zigzag([100, 110, 104])) + [108, 112, 115, 113, 110.6, 113, 116]
    df, ev, _ = run(np.array(closes))
    rt = ev[(ev.type == "retest") & (ev.direction == 1)]
    assert len(rt) == 1
    assert rt.iloc[0].origin in ("bos", "choch")


def test_double_top_confirmed_on_neckline_close():
    closes = zigzag([100, 110, 104, 110.1, 100])
    df, ev, _ = run(closes)
    dt = ev[ev.type == "double_top"]
    assert len(dt) == 1
    t = int(dt.iloc[0].t)
    assert df["close"].iloc[t] < dt.iloc[0].level


def test_fvg_and_impulse():
    closes = np.r_[np.full(30, 100.0) + np.sin(np.arange(30)) * 0.3, [100.5, 104, 108, 108.5, 108.4]]
    df, ev, _ = run(closes)
    assert len(ev[(ev.type == "fvg") & (ev.direction == 1)]) >= 1
    assert len(ev[(ev.type == "impulse") & (ev.direction == 1)]) >= 1


def test_rsi_divergence_bullish():
    # calentamiento + caída brusca a 100 + caída suave a 99: mínimo inferior con RSI más alto
    warm = np.full(10, 120.0) + np.sin(np.arange(10)) * 0.2
    closes = np.r_[warm, zigzag([120, 100, 112], 4)[1:], zigzag([112, 99, 104], 12)[1:]]
    df, ev, _ = run(closes, params=StructureParams(pivot_left=2, pivot_right=2, min_swing_atr=0.3))
    dv = ev[(ev.type == "rsi_divergence") & (ev.direction == 1)]
    assert len(dv) == 1
    assert dv.iloc[0].rsi_now > dv.iloc[0].rsi_prev
    assert dv.iloc[0].t == 29 + 2   # mínimo en la vela 29, conocido 2 velas después


@pytest.mark.parametrize("cut", [500, 1200, 2500])
def test_no_lookahead_prefix_invariance(cut):
    """Los eventos conocidos hasta la vela `cut` no cambian al añadir datos futuros."""
    df = random_frame("M15", n=60000, seed=3)
    full, st_full = StructureEngine().run(df)
    part, st_part = StructureEngine().run(df.iloc[:cut])
    a = full[full.t < cut].reset_index(drop=True)
    b = part.reset_index(drop=True)
    pd.testing.assert_frame_equal(a[["t", "type", "direction", "level"]], b[["t", "type", "direction", "level"]])
    assert (st_full["trend"].iloc[:cut].to_numpy() == st_part["trend"].to_numpy()).all()


def test_events_never_reference_future_prices():
    df = random_frame("M15", n=60000, seed=11)
    ev, _ = StructureEngine().run(df)
    for _, e in ev[ev.type.isin(["bos", "choch", "sweep"])].head(300).iterrows():
        t = int(e.t)
        if e.type in ("bos", "choch") and e.direction == 1:
            assert df["close"].iloc[t] > e.level
        if e.type == "sweep" and e.direction == -1:
            assert df["high"].iloc[t] > e.level >= df["close"].iloc[t]
