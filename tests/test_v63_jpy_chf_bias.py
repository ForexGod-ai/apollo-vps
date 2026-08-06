"""V63/V64 golden tests — JPY D1 bias on geometric swings + major leg authority."""
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
    tc = "timestamp" if "timestamp" in df.columns else "time"
    df[tc] = pd.to_datetime(df[tc])
    df = df.set_index(tc)
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-300:]


def _detector() -> SMCDetector:
    return SMCDetector(swing_lookback=5, atr_multiplier=0.5)


def _auth(symbol: str, df: pd.DataFrame) -> dict:
    return _detector().resolve_authoritative_d1_bias(df, symbol=symbol)


def test_eurjpy_detects_choch_not_zero():
    """V64: CHoCH trebuie detectat (nu 0) — filter_major pe iteration era bug-ul JPY."""
    df = _load_d1("EURJPY")
    detector = _detector()
    chochs, _ = detector.detect_choch_and_bos(df)
    assert len(chochs) >= 5, f"EURJPY must detect CHoCH series, got {len(chochs)}"
    bearish = [c for c in chochs if c.direction == "bearish" and c.previous_trend == "bullish"]
    assert bearish, "Expected bearish CHoCH after bullish trend on EURJPY"


def test_eurjpy_bearish_choch_moment_is_reversal_sell():
    """La bariera CHoCH bearish (fără BOS post-leg) → REVERSAL SELL."""
    df = _load_d1("EURJPY")
    detector = _detector()
    chochs, _ = detector.detect_choch_and_bos(df)
    leg = next(
        (c for c in reversed(chochs) if c.direction == "bearish" and c.previous_trend == "bullish"),
        None,
    )
    assert leg is not None
    _, strategy, trend, _ = detector._resolve_d1_leg(df, [leg], [])
    assert trend == "bearish"
    assert strategy == "reversal"


def test_audjpy_bearish_choch_moment_is_reversal_sell():
    df = _load_d1("AUDJPY")
    detector = _detector()
    chochs, _ = detector.detect_choch_and_bos(df)
    leg = next(
        (c for c in reversed(chochs) if c.direction == "bearish" and c.previous_trend == "bullish"),
        None,
    )
    assert leg is not None
    _, strategy, trend, _ = detector._resolve_d1_leg(df, [leg], [])
    assert trend == "bearish"
    assert strategy == "reversal"


def test_usdchf_bearish_when_close_below_protected_hl():
    """Close sub HL protejat → leg bullish mort, bearish@246 cu BOS → CONTINUATION SELL."""
    df = _load_d1("USDCHF")
    auth = _auth("USDCHF", df)
    assert auth["direction"] == "sell", auth
    assert auth["strategy_type"] == "continuation", auth
    assert auth["trend"] == "bearish", auth
