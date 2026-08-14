"""Golden tests — D1 pullback vs BOS + symmetric bullish/bearish mix."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"
PAIRS_CONFIG = ROOT / "pairs_config.json"

POST_CRASH_CUTOFF = "2025-08-14"
CRASH_PAIRS = ("GBPJPY", "AUDJPY", "EURGBP", "EURUSD")
BULLISH_PAIRS = ("XAUUSD", "USDCAD")


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


def _scanner_symbols() -> list[str]:
    if not PAIRS_CONFIG.exists():
        pytest.skip("pairs_config.json missing")
    with PAIRS_CONFIG.open(encoding="utf-8") as fh:
        return [p["symbol"] for p in json.load(fh)["pairs"]]


@pytest.mark.parametrize("symbol", CRASH_PAIRS)
def test_post_crash_pullback_not_bullish_bos(symbol: str):
    """Post-August crash window — no false BULLISH BOS / LONG on pullbacks."""
    auth = _auth(symbol, _load_d1(symbol, cutoff=POST_CRASH_CUTOFF))
    assert auth["trend"] == "bearish", auth
    assert auth["direction"] == "sell", auth


@pytest.mark.parametrize("symbol", ("GBPJPY", "AUDJPY", "EURUSD"))
def test_latest_crash_pairs_remain_bearish(symbol: str):
    auth = _auth(symbol, _load_d1(symbol))
    assert auth["trend"] == "bearish", auth
    assert auth["direction"] == "sell", auth


@pytest.mark.parametrize("symbol", BULLISH_PAIRS)
def test_bullish_impulse_pairs_not_forced_bearish(symbol: str):
    auth = _auth(symbol, _load_d1(symbol))
    assert auth["trend"] == "bullish", auth
    assert auth["direction"] == "buy", auth


def test_scanner_panel_not_monochrome_bearish():
    """Regression: overcorrection forced 16/16 bearish — expect a realistic mix."""
    det = _detector()
    trends = []
    for sym in _scanner_symbols():
        auth = _auth(sym, _load_d1(sym))
        trends.append(auth["trend"])
    assert trends.count("bullish") >= 3, trends
    assert trends.count("bearish") >= 3, trends
    assert len(set(trends)) > 1


def test_gbpcrash_orphan_not_range_lock_bullish():
    df = _load_d1("GBPJPY", cutoff=POST_CRASH_CUTOFF)
    auth = det.build_d1_context(df, symbol="GBPJPY") if (det := _detector()) else None
    assert auth.trend == "bearish", auth
    assert auth.direction == "sell", auth


def test_pullback_bullish_bos_does_not_flip_without_origin_reclaim():
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
    last_bear = bear_bos[-1]
    last_bull = bull_bos[-1]
    assert last_bull.index > last_bear.index
    assert det._bear_crash_leg_still_active(df, last_bear)
    auth = det.build_d1_context(df, symbol="EURGBP")
    assert auth.trend == "bearish", auth
    assert auth.direction == "sell", auth
