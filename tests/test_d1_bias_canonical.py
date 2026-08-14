"""Golden tests — D1 pullback vs BOS misclassification fix (post-August crash)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"

POST_CRASH_CUTOFF = "2025-08-14"
CANONICAL_PAIRS = ("GBPJPY", "AUDJPY", "EURGBP", "EURUSD")


def _load_d1(symbol: str, *, cutoff: str | None = None, tail: int = 300) -> pd.DataFrame:
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
    df = df.dropna(subset=["close"])
    if cutoff is not None:
        df = df.loc[:cutoff]
    return df.iloc[-tail:]


def _detector() -> SMCDetector:
    return SMCDetector(swing_lookback=5, atr_multiplier=0.5)


def _auth(symbol: str, df: pd.DataFrame) -> dict:
    return _detector().resolve_authoritative_d1_bias(df, symbol=symbol)


@pytest.mark.parametrize("symbol", CANONICAL_PAIRS)
def test_post_crash_pullback_not_bullish_bos(symbol: str):
    """GBPJPY cutoff 2025-08-14 was bullish bug — must stay bearish after fix."""
    auth = _auth(symbol, _load_d1(symbol, cutoff=POST_CRASH_CUTOFF))
    assert auth["trend"] == "bearish", auth
    assert auth["direction"] == "sell", auth
    assert not (auth["trend"] == "bullish" and auth["d1_signal_type"] == "BOS"), auth


@pytest.mark.parametrize("symbol", CANONICAL_PAIRS)
def test_latest_300_bars_bearish_sell(symbol: str):
    auth = _auth(symbol, _load_d1(symbol))
    assert auth["trend"] == "bearish", auth
    assert auth["direction"] == "sell", auth
    assert auth["strategy_type"] in ("reversal", "continuation"), auth
    assert auth["d1_signal_type"] in ("CHoCH", "BOS"), auth


def test_gbpcrash_orphan_not_range_lock_bullish():
    """Orphan path must not blindly follow locked_bias bullish above range high."""
    df = _load_d1("GBPJPY", cutoff=POST_CRASH_CUTOFF)
    det = _detector()
    auth = det.build_d1_context(df, symbol="GBPJPY")
    rs = auth.range_state
    assert rs is not None and rs.locked, rs
    assert float(df["close"].iloc[-1]) > float(rs.macro_range_high)
    assert auth.trend == "bearish", auth
    assert auth.direction == "sell", auth


def test_pullback_bullish_bos_does_not_flip_without_origin_reclaim():
    """Countertrend bullish BOS during bear crash cannot flip bias alone."""
    df = _load_d1("EURGBP", cutoff=POST_CRASH_CUTOFF)
    det = _detector()
    chochs, bos = det.detect_choch_and_bos(df)
    sh = det.detect_swing_highs(df)
    sl = det.detect_swing_lows(df)
    rs = det.compute_structural_range(df, sh, sl, symbol="EURGBP")
    chochs, bos, rs = det.filter_internal_range_signals("EURGBP", df, chochs, bos, rs)
    bear_bos = [b for b in bos if b.direction == "bearish"]
    bull_bos = [b for b in bos if b.direction == "bullish"]
    assert bear_bos and bull_bos
    assert bull_bos[-1].index > bear_bos[-1].index
    pseudo = det._pseudo_leg_from_bos(bear_bos[-1])
    assert not det._body_reclaimed_origin_high(df, pseudo) or not [
        c for c in chochs
        if c.direction == "bullish" and c.previous_trend == "bearish"
    ]
    auth = det.build_d1_context(df, symbol="EURGBP")
    assert auth.trend == "bearish", auth
    assert auth.direction == "sell", auth
