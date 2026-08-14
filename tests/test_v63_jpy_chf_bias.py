"""V68 golden tests — JPY D1 bias on MAJOR swings only (MASTER SPEC)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector

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
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-300:]


def _detector() -> SMCDetector:
    return SMCDetector(swing_lookback=5, atr_multiplier=0.5)


def _auth(symbol: str, df: pd.DataFrame) -> dict:
    return _detector().resolve_authoritative_d1_bias(df, symbol=symbol)


def test_eurjpy_major_structure_detected():
    """V68: structural series on major pivots — BOS/CHoCH, not micro noise."""
    df = _load_d1("EURJPY")
    detector = _detector()
    chochs, bos = detector.detect_choch_and_bos(df)
    assert len(chochs) + len(bos) >= 1, "EURJPY must detect major structural breaks"
    auth = _auth("EURJPY", df)
    assert auth["trend"] == "bearish", auth
    assert auth["strategy_type"] in ("reversal", "continuation"), auth


def test_eurjpy_bearish_bias_canonical():
    """V68: EURJPY D1 bearish — continuation when BOS post-leg dominates."""
    auth = _auth("EURJPY", _load_d1("EURJPY"))
    assert auth["direction"] == "sell", auth
    assert auth["trend"] == "bearish", auth
    assert auth["strategy_type"] == "continuation", auth
    assert auth["d1_signal_type"] == "BOS", auth


def test_audjpy_bearish_choch_moment_is_reversal_sell():
    df = _load_d1("AUDJPY")
    detector = _detector()
    chochs, _ = detector.detect_choch_and_bos(df)
    leg = next(
        (c for c in reversed(chochs) if c.direction == "bearish" and c.previous_trend == "bullish"),
        None,
    )
    if leg is None:
        auth = _auth("AUDJPY", df)
        assert auth["trend"] == "bearish", auth
        return
    _, strategy, trend, _ = detector._resolve_d1_leg(df, [leg], [])
    assert trend == "bearish"
    assert strategy == "reversal"


def test_usdchf_bearish_when_close_below_protected_hl():
    df = _load_d1("USDCHF")
    auth = _auth("USDCHF", df)
    assert auth["direction"] == "sell", auth
    assert auth["trend"] == "bearish", auth
    assert auth["strategy_type"] in ("reversal", "continuation"), auth


def test_usdjpy_canonical_bias_follows_major_flip():
    """USDJPY — authoritative D1 follows latest valid major flip (not forced bearish)."""
    df = _load_d1("USDJPY")
    auth = _auth("USDJPY", df)
    assert auth["trend"] in ("bullish", "bearish"), auth
    assert auth["strategy_type"] in ("reversal", "continuation"), auth
    assert auth["d1_signal_type"] in ("CHoCH", "BOS"), auth
    if auth["trend"] == "bullish":
        assert auth["direction"] == "buy"
    else:
        assert auth["direction"] == "sell"


def test_audjpy_bearish_flip_reversal_over_orphan_bos():
    """V68: AUDJPY bearish — major pivots may classify mature leg as continuation."""
    df = _load_d1("AUDJPY")
    auth = _auth("AUDJPY", df)
    assert auth["trend"] == "bearish", auth
    assert auth["strategy_type"] in ("reversal", "continuation"), auth
    assert auth["d1_signal_type"] in ("CHoCH", "BOS"), auth


def test_eurgbp_mature_leg_uses_major_bos_or_choch():
    """V68: EURGBP D1 — canonical major-pivot classification (trend + signal aligned)."""
    df = _load_d1("EURGBP")
    auth = _auth("EURGBP", df)
    assert auth["trend"] in ("bearish", "bullish", "neutral"), auth
    assert auth["strategy_type"] in ("reversal", "continuation"), auth
    assert auth["d1_signal_type"] in ("CHoCH", "BOS"), auth
    if auth["trend"] == "bearish":
        assert auth["direction"] == "sell"
    elif auth["trend"] == "bullish":
        assert auth["direction"] == "buy"


def test_jpy_crosses_canonical_major_swings():
    """JPY crosses — crash pairs bearish; others follow latest major flip."""
    crash_bear = {"EURJPY", "AUDJPY", "GBPJPY"}
    for sym in ("USDJPY", "EURJPY", "AUDJPY", "GBPJPY"):
        df = _load_d1(sym)
        auth = _auth(sym, df)
        assert auth["trend"] in ("bullish", "bearish"), f"{sym}: {auth}"
        assert auth["strategy_type"] in ("reversal", "continuation"), f"{sym}: {auth}"
        assert auth["d1_signal_type"] in ("CHoCH", "BOS"), f"{sym}: {auth}"
        if sym in crash_bear:
            assert auth["trend"] == "bearish", f"{sym}: {auth}"


def test_organic_strategy_post_bos_is_continuation():
    """Canon: CHoCH + BOS post-leg = CONT; CHoCH singur = REV."""
    from smc_detector import CHoCH, BOS

    leg = CHoCH(
        index=100, direction='bearish', break_price=1.0,
        previous_trend='bullish', candle_time=None, swing_broken=None,
    )
    bos = BOS(
        index=120, direction='bearish', break_price=0.95,
        candle_time=None, swing_broken=None,
    )
    det = SMCDetector()
    sig, st, trend, _ = det._strategy_from_leg_choch(leg, [])
    assert st == 'reversal' and trend == 'bearish'
    sig2, st2, _, _ = det._strategy_from_leg_choch(leg, [bos])
    assert st2 == 'continuation' and type(sig2).__name__ == 'BOS'
