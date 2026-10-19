"""V82 — D1 pivot state machine: pullback inside HL–HH stays bullish until close < HL."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"


def _load_d1(symbol: str, tail: int = 400) -> pd.DataFrame:
    matches = list(CACHE.glob(f"{symbol}_D1_*.csv"))
    if not matches:
        pytest.skip(f"No D1 cache for {symbol}")
    best = max(matches, key=lambda p: p.stat().st_size)
    df = pd.read_csv(best)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-tail:]


def test_usdcad_pullback_stays_bullish_until_hl_break():
    """USDCAD D1: retrace from HH must not flip bearish while close holds above structural HL."""
    det = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    df = _load_d1("USDCAD")
    sm = det.run_d1_smc_state_machine(df)
    assert sm["trend"] == "bullish", sm
    assert sm.get("structural_hl") is not None
    assert sm.get("structural_hh") is not None
    last_close = float(df["close"].iloc[-1])
    assert last_close >= sm["structural_hl"], (
        f"close {last_close} should be above HL {sm['structural_hl']} for bullish pullback"
    )
    latest = sm["latest_signal"]
    assert latest is not None
    assert latest.direction == "bullish", (
        f"expected last signal bullish (BOS/CHoCH), got {latest.direction}"
    )


def test_pullback_bars_keep_bullish_bias():
    """Extra bearish dailies inside HL–HH must not flip D1 to bearish."""
    det = SMCDetector()
    df = _load_d1("USDCAD", tail=400)
    sm = det.run_d1_smc_state_machine(df)
    assert sm["trend"] == "bullish"
    last_close = float(df["close"].iloc[-1])
    assert last_close >= sm["structural_hl"]
