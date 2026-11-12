"""V87 synthetic in-memory tests (no historical_cache)."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from smc_detector import CHoCH, SMCDetector
from smc_detector.fvg import FvgMixin
from smc_detector.models import BOS, FVG


def _ohlc_frame(closes, spread=0.02):
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
            "time": pd.date_range("2025-01-01", periods=len(closes), freq="D"),
        }
    )


def test_v87_btc_style_hl_break_flips_bearish_reversal():
    """HL promoted then body close below HL → bearish CHoCH (reversal), not stale bullish BOS."""
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.25)
    n = 51
    close = []
    for i in range(n - 1):
        base = 70000 + 250 * i
        wave = 1200 * (1 if (i // 4) % 2 == 0 else -1)
        close.append(base + wave)
    df = _ohlc_frame(close, spread=400.0)
    sm0 = det.run_d1_smc_state_machine(df)
    assert sm0["trend"] == "bullish"
    prot = float(sm0["protected_low"])
    # Break on last **closed** bar; final row = forming candle (V72 trim).
    df.loc[len(df) - 1, "close"] = prot - 500.0
    df.loc[len(df) - 1, "low"] = prot - 800.0
    df.loc[len(df) - 1, "open"] = prot - 200.0
    forming_close = float(df.loc[len(df) - 1, "close"])
    df.loc[len(df)] = {
        "open": forming_close,
        "high": forming_close + 100,
        "low": forming_close - 100,
        "close": forming_close,
        "time": pd.Timestamp("2025-03-01"),
    }

    ctx = det.build_d1_context(df, symbol="BTCUSD")
    assert ctx.trend == "bearish", f"expected bearish flip, got {ctx.trend}"
    assert ctx.strategy_type == "reversal"
    assert isinstance(ctx.latest_signal, CHoCH)
    assert ctx.latest_signal.direction == "bearish"
    assert ctx.d1_signal_type == "CHoCH"
    assert ctx.protected_idx is not None


def test_v87_bos_promotes_protected_idx():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.25)
    n = 50
    close = []
    for i in range(n):
        close.append(1.30 + 0.008 * i + 0.012 * (1 if (i // 4) % 2 == 0 else -0.5))
    close[-1] = close[-2] + 0.025
    df = _ohlc_frame(close, spread=0.004)
    sm_before = det.run_d1_smc_state_machine(df.iloc[:-1])
    sm_after = det.run_d1_smc_state_machine(df)
    assert sm_after.get("protected_idx") is not None
    if sm_before.get("protected_idx") is not None and len(sm_after.get("bos_list", [])) > len(
        sm_before.get("bos_list", [])
    ):
        assert sm_after["protected_idx"] >= sm_before["protected_idx"]


def test_v87_reversal_fvg_index_floor_leg_anchor_minus_two():
    class _Det(FvgMixin):
        pass

    det = _Det()
    choch = CHoCH(
        index=10,
        direction="bearish",
        break_price=98.0,
        previous_trend="bullish",
        candle_time=datetime(2026, 1, 1),
        swing_broken=SimpleNamespace(price=95.0),
    )
    n = 25
    close = [100.0 + 0.05 * i for i in range(n)]
    df = _ohlc_frame(close, spread=0.2)
    # Recent bearish FVG at 8 (within leg_anchor-2)
    df.loc[7, "low"] = 102.5
    df.loc[9, "high"] = 101.0
    # Stale FVG at 3 (pre-impuls, excluded)
    df.loc[2, "low"] = 104.0
    df.loc[4, "high"] = 102.8

    audit: dict = {}
    det.detect_fvg(
        df,
        choch,
        strategy_type="reversal",
        leg_anchor_index=10,
        audit_out=audit,
        current_price=99.0,
    )
    mitigated = audit.get("after_mitigation") or []
    indices = [int(x["index"]) for x in mitigated]
    assert indices, "expected at least one FVG after V87 floor"
    assert all(i >= 8 for i in indices), f"stale pre-impulse FVG leaked: {indices}"
    assert 3 not in indices


def test_v87_continuation_fvg_respects_protected_bar():
    class _Det(FvgMixin):
        pass

    det = _Det()
    sig = BOS(
        index=20,
        direction="bullish",
        break_price=110.0,
        candle_time=datetime(2026, 1, 1),
        swing_broken=None,
    )
    n = 30
    close = [100.0 + 0.2 * i for i in range(n)]
    df = _ohlc_frame(close, spread=0.15)
    df.loc[5, "high"] = 99.0
    df.loc[7, "low"] = 101.5
    df.loc[18, "high"] = 108.0
    df.loc[20, "low"] = 109.5

    selected = det.detect_fvg(
        df,
        sig,
        strategy_type="continuation",
        protected_bar=15,
        leg_anchor_index=12,
    )
    if selected is not None:
        assert selected.index >= 15


def test_v87_w1_gate_continuation_daily_poi_inside_not_blocked():
    det = SMCDetector()
    sync = det.evaluate_w_d_sync(
        "bullish",
        "BULLISH",
        daily_poi_top=1.105,
        daily_poi_bottom=1.100,
        w1_poi_top=1.110,
        w1_poi_bottom=1.095,
        current_price=1.118,
        d1_strategy_type="continuation",
    )
    assert sync.get("status") is None


def test_v87_w1_gate_reversal_price_outside_not_blocked():
    det = SMCDetector()
    sync = det.evaluate_w_d_sync(
        "bearish",
        "BEARISH",
        daily_poi_top=1.105,
        daily_poi_bottom=1.100,
        w1_poi_top=1.110,
        w1_poi_bottom=1.095,
        current_price=1.080,
        d1_strategy_type="reversal",
    )
    assert sync.get("status") is None


def test_v87_authority_reversal_beats_same_dir_bos():
    det = SMCDetector()
    n = 48
    close = []
    for i in range(n):
        close.append(1.20 + 0.01 * (i // 3) - 0.005 * (i % 2))
    close[-1] = close[-3] - 0.03
    close[-2] = close[-1] + 0.005
    df = _ohlc_frame(close, spread=0.006)
    ctx = det.build_d1_context(df, symbol="SYNTH")
    if ctx.trend == "bearish" and isinstance(ctx.latest_signal, CHoCH):
        assert ctx.strategy_type == "reversal"
        assert ctx.d1_signal_type == "CHoCH"
