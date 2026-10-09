"""Golden tests — V71 Glitch D1: last body-close CHoCH/BOS sets trend."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector
from smc_detector.models import CHoCH

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"
PAIRS_CONFIG = ROOT / "pairs_config.json"

POST_CRASH_CUTOFF = "2025-08-14"
CRASH_PAIRS = ("GBPJPY", "AUDJPY", "EURGBP", "EURUSD", "EURJPY")
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


def _major_lh_ceiling(det: SMCDetector, df: pd.DataFrame, symbol: str) -> float | None:
    """Major LH body — bearish range ceiling at last bar."""
    sh = det.detect_swing_highs(df)
    sl = det.detect_swing_lows(df)
    rs = det.compute_structural_range(df, sh, sl, symbol=symbol)
    if rs and rs.macro_range_high:
        return float(rs.macro_range_high)
    mh, ml = det.filter_major_swings(df, sh, sl)
    anchor = CHoCH(
        index=0,
        direction='bearish',
        break_price=0.0,
        previous_trend='bullish',
        candle_time=0,
        swing_broken=None,
    )
    return det._leg_invalidation_level_bearish(df, anchor, mh, ml, len(df) - 1)


def _last_event_direction(det: SMCDetector, df: pd.DataFrame, symbol: str) -> str | None:
    ctx = det.build_d1_context(df, symbol=symbol)
    sig = ctx.latest_signal
    return getattr(sig, "direction", None) if sig is not None else None


@pytest.mark.parametrize("symbol", CRASH_PAIRS)
def test_post_crash_trend_matches_last_d1_signal(symbol: str):
    """V71: authoritative trend follows last CHoCH/BOS, not frozen Major LH."""
    df = _load_d1(symbol, cutoff=POST_CRASH_CUTOFF)
    det = _detector()
    auth = _auth(symbol, df)
    last_dir = _last_event_direction(det, df, symbol)
    if last_dir and auth["trend"] in ("bullish", "bearish"):
        assert auth["trend"] == last_dir, auth


@pytest.mark.parametrize("symbol", ("GBPJPY", "AUDJPY", "EURUSD", "EURJPY"))
def test_latest_crash_pairs_trend_matches_last_signal(symbol: str):
    df = _load_d1(symbol)
    det = _detector()
    auth = _auth(symbol, df)
    last_dir = _last_event_direction(det, df, symbol)
    if last_dir and auth["trend"] in ("bullish", "bearish"):
        assert auth["trend"] == last_dir, auth


def _major_hl_floor(det: SMCDetector, df: pd.DataFrame, symbol: str) -> float | None:
    """Major HL body — bullish range floor at last bar."""
    sh = det.detect_swing_highs(df)
    sl = det.detect_swing_lows(df)
    mh, ml = det.filter_major_swings(df, sh, sl)
    anchor = CHoCH(
        index=0,
        direction='bullish',
        break_price=0.0,
        previous_trend='bearish',
        candle_time=0,
        swing_broken=None,
    )
    return det._leg_invalidation_level_bullish(df, anchor, mh, ml, len(df) - 1)


@pytest.mark.parametrize("symbol", BULLISH_PAIRS)
def test_bullish_impulse_pairs_not_forced_bearish(symbol: str):
    df = _load_d1(symbol)
    det = _detector()
    auth = _auth(symbol, df)
    macro = auth.get("macro_swings", "neutral")
    hl = _major_hl_floor(det, df, symbol)
    close = float(df["close"].iloc[-1])
    if macro == "bullish" and (hl is None or close >= hl):
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


def test_gbpcrash_orphan_trend_matches_last_signal():
    df = _load_d1("GBPJPY", cutoff=POST_CRASH_CUTOFF)
    det = _detector()
    auth = det.build_d1_context(df, symbol="GBPJPY")
    last_dir = _last_event_direction(det, df, "GBPJPY")
    if last_dir and auth.trend in ("bullish", "bearish"):
        assert auth.trend == last_dir, auth


def test_pullback_bullish_bos_flips_when_last_signal_bullish():
    """V71: later bullish BOS/CHoCH after bear leg → bullish trend."""
    df = _load_d1("EURGBP", cutoff=POST_CRASH_CUTOFF)
    det = _detector()
    chochs, bos = det.detect_choch_and_bos(df)
    bear_bos = [b for b in bos if b.direction == "bearish"]
    bull_bos = [b for b in bos if b.direction == "bullish"]
    if not bear_bos or not bull_bos:
        pytest.skip("Need both bearish and bullish BOS in slice")
    last_bear = bear_bos[-1]
    last_bull = bull_bos[-1]
    if last_bull.index <= last_bear.index:
        pytest.skip("Slice has no bullish BOS after bearish")
    auth = det.build_d1_context(df, symbol="EURGBP")
    assert auth.trend == "bullish", auth
    assert auth.direction == "buy", auth


def test_usdcad_not_stuck_bearish_on_full_history():
    """Regression: USDCAD must read bullish when last D1 impulse is up."""
    df = _load_d1("USDCAD")
    auth = _auth("USDCAD", df)
    assert auth["trend"] == "bullish", auth
    assert auth["direction"] == "buy", auth
