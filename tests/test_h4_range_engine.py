"""V95 — motor 4H dedicat (synthetic, fără historical_cache)."""
from __future__ import annotations

import pandas as pd

from multi_tf_radar import (
    PullbackStatus,
    _RETRACE_ENTRY_MAX,
    _RETRACE_ENTRY_MIN,
    _choch_premium_discount_zone,
)
from smc_detector.h4_engine import h4_impulse_retrace_pct, run_h4_range_engine


def _body_df(closes, spread=0.005, low_extra=None, high_extra=None):
    highs, lows = [], []
    for i, c in enumerate(closes):
        hu = high_extra[i] if high_extra and i < len(high_extra) else spread
        lo = low_extra[i] if low_extra and i < len(low_extra) else spread
        highs.append(c + hu)
        lows.append(c - lo)
    return pd.DataFrame(
        {
            "open": closes,
            "close": closes,
            "high": highs,
            "low": lows,
            "time": pd.date_range("2025-06-01", periods=len(closes), freq="4h"),
        }
    )


def _usdjpy_pullback_fixture() -> pd.DataFrame:
    """Bullish 4H range → bearish CHoCH la HL 159.05, impuls ancorat (≠ 0 pips)."""
    closes = [
        159.50,
        159.40,
        159.30,
        159.20,
        159.10,
        159.05,
        159.15,
        159.25,
        159.35,
        159.45,
        159.55,
        159.65,
        159.75,
        159.85,
        159.95,
        160.05,
        160.19,
        159.95,
        159.80,
        159.65,
        159.50,
        159.35,
        159.20,
        159.05,
        159.25,
        159.55,
        159.75,
        159.95,
        158.74,
    ]
    return _body_df(closes)


def test_usdjpy_style_bearish_choch_at_hl_impulse_anchored():
    df = _usdjpy_pullback_fixture()
    out = run_h4_range_engine(df, "bearish", fw=2)
    assert out["signal_type"] == "CHoCH"
    ev = out["latest_event"]
    assert ev is not None and ev.direction == "bearish"
    assert abs(float(ev.break_price) - 159.05) < 0.02
    assert abs(float(ev.swing_broken.price) - 159.05) < 0.02
    assert out["impulse_origin"] is not None
    assert out["impulse_extreme"] is not None
    impulse = abs(float(out["impulse_origin"]) - float(out["impulse_extreme"]))
    assert impulse > 0.35
    assert float(out["impulse_origin"]) > float(out["impulse_extreme"])


def test_wick_below_hl_without_body_close_no_choch():
    pre = _usdjpy_pullback_fixture().iloc[:-1].reset_index(drop=True)
    times = pd.date_range("2025-06-01", periods=len(pre) + 1, freq="4h")
    wick = pd.DataFrame(
        {
            "open": [159.40],
            "close": [159.15],
            "high": [159.45],
            "low": [158.85],
            "time": [times[-1]],
        }
    )
    wick_df = pd.concat([pre, wick], ignore_index=True)
    out = run_h4_range_engine(wick_df, "bearish", fw=2)
    assert not out["aligned_chochs"]
    assert out.get("signal_type") is None or out["signal_type"] != "CHoCH"


def test_pullback_70pct_in_entry_band_execute_now():
    origin, extreme = 159.95, 158.55
    current = 159.53
    retrace, impulse = h4_impulse_retrace_pct(origin, extreme, current, "bearish")
    assert impulse > 0
    assert 0.65 <= retrace <= 0.75
    lo, hi, _mid = _choch_premium_discount_zone(extreme, impulse, "bearish")
    in_band = lo <= current <= hi and _RETRACE_ENTRY_MIN <= retrace <= _RETRACE_ENTRY_MAX
    assert in_band
    assert _RETRACE_ENTRY_MIN <= retrace <= _RETRACE_ENTRY_MAX


def test_impulse_retrace_fixture_15995_15855():
    """Pullback ~70% din [159.95, 158.55] la ~159.53."""
    retrace, size = h4_impulse_retrace_pct(159.95, 158.55, 159.53, "bearish")
    assert abs(size - 1.40) < 0.02
    assert abs(retrace - 0.70) < 0.06