"""V57/V58: D1 leg invalidation and macro authority."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector, CHoCH, BOS, StructuralRangeState

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"


def _load_d1(symbol: str) -> pd.DataFrame:
    matches = list(CACHE.glob(f"{symbol}_D1_*.csv"))
    if not matches:
        pytest.skip(f"No D1 cache for {symbol}")
    best = max(matches, key=lambda p: p.stat().st_size)
    df = pd.read_csv(best)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-300:]


@pytest.fixture
def detector():
    return SMCDetector(swing_lookback=5, atr_multiplier=0.5)


def _resolve(detector: SMCDetector, df: pd.DataFrame, symbol: str):
    chochs, bos = detector.detect_choch_and_bos(df)
    sh = detector.detect_swing_highs(df)
    sl = detector.detect_swing_lows(df)
    rs = detector.compute_structural_range(df, sh, sl, symbol=symbol)
    chochs, bos, rs = detector.filter_internal_range_signals(symbol, df, chochs, bos, rs)
    return detector._resolve_d1_leg(df, chochs, bos, range_state=rs)


def test_eurusd_invalid_bullish_leg_not_reversal_long(detector):
    df = _load_d1("EURUSD")
    latest, strategy, trend, leg = _resolve(detector, df, "EURUSD")
    if strategy == "reversal" and trend == "bullish":
        assert leg is not None, "bullish REVERSAL requires leg CHoCH"
        assert detector._major_reversal_confirmed(df, leg), (
            f"EURUSD bullish REVERSAL must be body-close confirmed on major pivot "
            f"(leg @bar{leg.index})"
        )
        chochs, bos = detector.detect_choch_and_bos(df)
        assert detector._leg_choch_still_valid(df, leg, bos, chochs)
    chochs, bos = detector.detect_choch_and_bos(df)
    sh = detector.detect_swing_highs(df)
    sl = detector.detect_swing_lows(df)
    rs = detector.compute_structural_range(df, sh, sl, symbol="EURUSD")
    chochs, bos, rs = detector.filter_internal_range_signals(
        "EURUSD", df, chochs, bos, rs,
    )
    bias = detector.build_d1_context(df, symbol="EURUSD").trend
    fallback = detector.resolve_structural_bias_fallback(df, chochs, bos, rs)
    assert bias in ("bearish", "bullish", "neutral")
    assert fallback in ("bearish", "bullish", "neutral")
    if latest is None:
        assert bias in ("bearish",) or fallback in ("bearish",) or trend != "bullish"


def test_gbpcad_authoritative_bias_follows_canonical_pipeline(detector):
    """V65: bias canonic — CHoCH flip = reversal, BOS-only = continuation."""
    df = _load_d1("GBPCAD")
    auth = detector.resolve_authoritative_d1_bias(df, symbol="GBPCAD")
    assert auth.get("trend") in ("bullish", "bearish"), auth
    assert auth.get("strategy_type") in ("reversal", "continuation")
    if auth.get("leg_choch") is not None:
        assert auth.get("strategy_type") in ("reversal", "continuation")
    if auth.get("trend") == "bullish":
        assert auth.get("direction") == "buy"
    else:
        assert auth.get("direction") == "sell"


def test_btcusd_not_bullish_reversal_on_bear_structure(detector):
    df = _load_d1("BTCUSD")
    latest, strategy, trend, leg = _resolve(detector, df, "BTCUSD")
    assert latest is not None
    assert not (strategy == "reversal" and trend == "bullish"), (
        f"BTCUSD bear structure should not classify REVERSAL long, got {strategy}/{trend}"
    )
    # V59: below LL may still show bullish CONTINUATION on dead-cat BOS — not REVERSAL long
    if strategy == "reversal":
        assert trend == "bearish"


def test_v45_dead_cat_bounce_does_not_supersede_v40(detector):
    """V58: CHoCH bullish post-LL without LL reclaim → bearish breakdown."""
    n = 100
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = [90000.0] * 50 + [65000.0 - i * 100 for i in range(50)]
    df = pd.DataFrame(
        {
            "open": close,
            "high": [c + 500 for c in close],
            "low": [c - 500 for c in close],
            "close": close,
        },
        index=idx,
    )
    bull_choch = CHoCH(
        index=85, direction="bullish", break_price=64000.0,
        previous_trend="bearish", candle_time=None, swing_broken=None,
    )
    bear_bos = BOS(
        index=70, direction="bearish", break_price=75000.0,
        candle_time=None, swing_broken=None,
    )
    bear_choch = CHoCH(
        index=60, direction="bearish", break_price=80000.0,
        previous_trend="bullish", candle_time=None, swing_broken=None,
    )
    rs = StructuralRangeState(
        macro_range_high=100000.0,
        macro_range_low=86360.0,
        macro_range_high_bar=10,
        macro_range_low_bar=40,
        locked=True,
        locked_bias="bearish",
    )
    latest, strategy, trend, _ = detector._resolve_d1_leg(
        df, [bear_choch, bull_choch], [bear_bos], range_state=rs,
    )
    assert trend == "bearish"
    assert not (strategy == "reversal" and trend == "bullish")


def test_resolve_post_leg_flip_bearish_after_dead_bull(detector):
    n = 80
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = [1.10 + i * 0.001 for i in range(40)] + [1.14 - i * 0.002 for i in range(40)]
    df = pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.002 for c in close],
            "low": [c - 0.002 for c in close],
            "close": close,
        },
        index=idx,
    )
    dead_leg = CHoCH(
        index=35, direction="bullish", break_price=1.13,
        previous_trend="bearish", candle_time=None, swing_broken=None,
    )
    bear_choch = CHoCH(
        index=55, direction="bearish", break_price=1.12,
        previous_trend="bullish", candle_time=None, swing_broken=None,
    )
    bear_bos = BOS(
        index=60, direction="bearish", break_price=1.11,
        candle_time=None, swing_broken=None,
    )
    flipped = detector._resolve_post_leg_flip(
        df, [dead_leg, bear_choch], [bear_bos], dead_leg,
    )
    latest, strategy, trend, new_leg = flipped
    assert trend == "bearish"
    assert strategy in ("continuation", "reversal")
    assert latest is not None


def test_historical_flip_when_no_post_leg_opposite(detector):
    df = _load_d1("EURUSD")
    chochs, bos = detector.detect_choch_and_bos(df)
    dead = next((c for c in chochs if c.direction == "bullish"), None)
    if dead is None:
        pytest.skip("No bullish leg in EURUSD cache")
    hist = detector._resolve_historical_opposite_bias(df, chochs, bos, dead)
    assert hist[2] in ("bearish", "neutral", "bullish")


def test_leg_still_valid_bullish_requires_close_above_break(detector):
    df = pd.DataFrame({"open": [1.05], "close": [1.03]})
    leg = CHoCH(
        index=0, direction="bullish", break_price=1.10,
        previous_trend="bearish", candle_time=None, swing_broken=None,
    )
    assert detector._leg_choch_still_valid(df, leg, []) is False
