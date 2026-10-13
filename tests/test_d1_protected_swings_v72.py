"""V72 — closed D1 bars + Protected HL/LH dealing-range gate."""
from __future__ import annotations

import pandas as pd
import pytest

from smc_detector import SMCDetector


def _det() -> SMCDetector:
    return SMCDetector(swing_lookback=5, atr_multiplier=0.5)


def test_forming_bar_excluded_from_d1_authority():
    det = _det()
    idx = pd.date_range("2026-01-05", periods=40, freq="B")
    base = pd.DataFrame(
        {
            "open": [1.40 + i * 0.001 for i in range(40)],
            "high": [1.402 + i * 0.001 for i in range(40)],
            "low": [1.398 + i * 0.001 for i in range(40)],
            "close": [1.401 + i * 0.001 for i in range(40)],
            "volume": [80000] * 40,
        },
        index=idx,
    )
    full = base.copy()
    full.iloc[-1, full.columns.get_loc("close")] = 1.30
    full.iloc[-1, full.columns.get_loc("low")] = 1.29

    ctx_full = det.build_d1_context(full, symbol="TEST")
    ctx_trim = det.build_d1_context(base, symbol="TEST")
    assert ctx_full.trend == ctx_trim.trend
    assert ctx_full.d1_bias_direction == ctx_trim.d1_bias_direction


def test_protected_gate_drops_post_flip_bearish_on_usdcad_cache():
    """Regression: micro bearish BOS after last bullish flip must not win without HL break."""
    from pathlib import Path

    det = _det()
    cache = Path(__file__).resolve().parent.parent / "data" / "historical_cache"
    matches = list(cache.glob("USDCAD_D1_*.csv"))
    if not matches:
        pytest.skip("no USDCAD cache")
    df = pd.read_csv(max(matches, key=lambda p: p.stat().st_size))
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.set_index("timestamp").iloc[-300:]
    df_s = det.d1_closed_structure_df(df)
    ch, bo = det.detect_choch_and_bos(df_s)
    flips = det._true_choch_flips(ch)
    if not flips or flips[-1].direction != "bullish":
        pytest.skip("need active bullish flip in slice")
    floor = det._protected_hl_impulse_origin(df_s, flips[-1])
    if floor is None:
        pytest.skip("no protected HL")
    post_bear = [b for b in bo if b.index > flips[-1].index and b.direction == "bearish"]
    if not post_bear:
        pytest.skip("no post-flip bearish BOS in slice")
    _, kept_b = det.filter_choch_bos_by_protected_swings(df_s, ch, bo)
    close = float(df_s["close"].iloc[-1])
    if close >= floor:
        assert all(b.direction != "bearish" for b in kept_b if b.index > flips[-1].index)


def test_usdcad_cache_stays_bullish_with_v72():
    from pathlib import Path

    cache = Path(__file__).resolve().parent.parent / "data" / "historical_cache"
    matches = list(cache.glob("USDCAD_D1_*.csv"))
    if not matches:
        pytest.skip("no USDCAD cache")
    path = max(matches, key=lambda p: p.stat().st_size)
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
    df = df.iloc[-300:]
    auth = _det().build_d1_context(df, symbol="USDCAD")
    assert auth.trend == "bullish", auth
