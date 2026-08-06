"""V63 golden tests — canonical D1 bias on major pivots."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector

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
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-300:]


def _detector() -> SMCDetector:
    return SMCDetector(swing_lookback=5, atr_multiplier=0.5)


def _canonical_pipeline(detector: SMCDetector, symbol: str, df: pd.DataFrame):
    chochs, bos = detector.detect_choch_and_bos(df)
    sh = detector.detect_swing_highs(df)
    sl = detector.detect_swing_lows(df)
    rs = detector.compute_structural_range(df, sh, sl, symbol=symbol)
    chochs, bos, rs = detector.filter_internal_range_signals(symbol, df, chochs, bos, rs)
    return chochs, bos, rs


def _auth(symbol: str, df: pd.DataFrame) -> dict:
    return _detector().resolve_authoritative_d1_bias(df, symbol=symbol)


def test_eurjpy_canonical_reversal_sell():
    """EURJPY: spargere sub HL major → SELL; REVERSAL la CHoCH (V42.6 fără BOS post-leg)."""
    df = _load_d1("EURJPY")
    detector = _detector()
    auth = _auth("EURJPY", df)
    assert auth["direction"] == "sell", auth
    assert auth["trend"] == "bearish", auth
    leg = auth.get("leg_choch")
    assert leg is not None and leg.direction == "bearish", auth

    _, strategy, trend, _ = detector._resolve_d1_leg(df, [leg], [])
    assert trend == "bearish"
    assert strategy == "reversal"

    chochs, bos, _ = _canonical_pipeline(detector, "EURJPY", df)
    post_leg = [b for b in bos if b.index > leg.index and b.direction == leg.direction]
    if post_leg:
        assert auth["strategy_type"] == "continuation"


def test_audjpy_canonical_reversal_sell():
    df = _load_d1("AUDJPY")
    detector = _detector()
    auth = _auth("AUDJPY", df)
    assert auth["direction"] == "sell", auth
    assert auth["trend"] == "bearish", auth
    leg = auth.get("leg_choch")
    assert leg is not None and leg.direction == "bearish", auth

    _, strategy, trend, _ = detector._resolve_d1_leg(df, [leg], [])
    assert trend == "bearish"
    assert strategy == "reversal"

    chochs, bos, _ = _canonical_pipeline(detector, "AUDJPY", df)
    post_leg = [b for b in bos if b.index > leg.index and b.direction == leg.direction]
    if post_leg:
        assert auth["strategy_type"] == "continuation"


def test_usdchf_canonical_continuation_buy():
    df = _load_d1("USDCHF")
    auth = _auth("USDCHF", df)
    assert auth["direction"] == "buy", auth
    assert auth["strategy_type"] == "continuation", auth
    assert auth["trend"] == "bullish", auth
