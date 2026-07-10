"""V57: D1 leg invalidation — no false LONG REVERSAL on dead bullish legs."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector, CHoCH, BOS

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"


def _load_d1(symbol: str) -> pd.DataFrame:
    matches = sorted(CACHE.glob(f"{symbol}_D1_*.csv"), key=lambda p: p.stat().st_mtime)
    if not matches:
        pytest.skip(f"No D1 cache for {symbol}")
    df = pd.read_csv(matches[-1])
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
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
    assert not (strategy == "reversal" and trend == "bullish"), (
        f"EURUSD must not be REVERSAL long (got {strategy}/{trend}, latest={latest})"
    )
    if leg and leg.direction == "bullish":
        bos = detector.detect_choch_and_bos(df)[1]
        if not detector._leg_choch_still_valid(df, leg, bos):
            assert trend != "bullish"


def test_btcusd_not_bullish_reversal_on_bear_structure(detector):
    df = _load_d1("BTCUSD")
    latest, strategy, trend, leg = _resolve(detector, df, "BTCUSD")
    assert latest is not None
    assert not (strategy == "reversal" and trend == "bullish"), (
        f"BTCUSD bear structure should not classify REVERSAL long, got {strategy}/{trend}"
    )


def test_resolve_post_leg_flip_bearish_after_dead_bull(detector):
    """Synthetic: dead bullish leg with bearish CHoCH after."""
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


def test_leg_still_valid_bullish_requires_close_above_break(detector):
    df = pd.DataFrame({"close": [1.05, 1.04, 1.03]})
    leg = CHoCH(
        index=0, direction="bullish", break_price=1.10,
        previous_trend="bearish", candle_time=None, swing_broken=None,
    )
    assert detector._leg_choch_still_valid(df, leg, []) is False
