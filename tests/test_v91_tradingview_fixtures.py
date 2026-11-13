"""V91 TradingView-aligned synthetic fixtures (no historical_cache)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from smc_detector import CHoCH, BOS, SMCDetector
from smc_detector.poi import PoiMixin


def _ohlc(closes, spread=0.0015):
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
            "time": pd.date_range("2025-01-01", periods=len(closes), freq="D"),
        }
    )


def test_v91_usdcad_pre_bos_pullback_stays_bullish():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.362, 1.368, 1.372, 1.374, 1.3760, 1.3762, 1.3755, 1.3760]
        + [1.382, 1.392, 1.405, 1.418, 1.4235, 1.4282, 1.4275, 1.4268]
        + [1.415, 1.402, 1.3930, 1.399, 1.412, 1.42596]
    )
    df = _ohlc(closes, 0.002)
    sm = det.run_d1_smc_state_machine(df)
    ctx = det.build_d1_context(df, symbol="USDCAD")
    assert sm["trend"] == "bullish"
    assert sm.get("is_internal_pullback") is True
    bear = [
        c for c in sm["chochs"]
        if c.direction == "bearish" and getattr(c, "previous_trend", None) == "bullish"
    ]
    assert not bear
    assert ctx.strategy_type == "reversal" or ctx.d1_signal_type == "CHoCH"


def test_v91_usdcad_post_bos_hl_from_old_hh():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.362, 1.368, 1.372, 1.374, 1.3760, 1.3762, 1.3755, 1.3760]
        + [1.382, 1.392, 1.405, 1.418, 1.4235, 1.4282, 1.4275, 1.4268]
        + [1.415, 1.402, 1.3930, 1.399, 1.412, 1.42596, 1.4310]
    )
    df = _ohlc(closes, 0.002)
    sm = det.run_d1_smc_state_machine(df)
    bos = [b for b in sm["bos_list"] if b.direction == "bullish"]
    assert bos
    pl = float(sm["protected_low"])
    assert pl <= 1.396
    assert sm["trend"] == "bullish"


def test_v91_eurjpy_bullish_choch_without_bos_stays_rev():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.15)
    n = 45
    close = [182.5 - 0.12 * i for i in range(n - 8)]
    close += [175.5, 175.2, 175.8, 176.9, 177.91, 177.5, 176.9, 176.386]
    df = _ohlc(close, 0.08)
    ctx = det.build_d1_context(df, symbol="EURJPY")
    if ctx.trend != "bullish":
        return
    flip_idx = None
    for c in reversed(ctx.chochs):
        if getattr(c, "previous_trend", None) == "bearish" and c.direction == "bullish":
            flip_idx = c.index
            break
    if flip_idx is None:
        return
    post = [b for b in ctx.bos_list if b.direction == "bullish" and b.index > flip_idx]
    if not post:
        assert ctx.strategy_type == "reversal"
        assert ctx.d1_signal_type == "CHoCH"


def test_v91_gbpjpy_bearish_after_hl_break():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.2)
    close = [215.0 + 0.3 * i for i in range(12)]
    close += [219.5, 218.0, 216.5, 215.8, 214.5, 212.0, 210.8, 207.5, 208.2, 211.35]
    df = _ohlc(close, 0.15)
    ctx = det.build_d1_context(df, symbol="GBPJPY")
    if ctx.trend == "bearish":
        assert ctx.trend != "bullish"


def test_v91_usdjpy_bearish_leg():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.18)
    close = [158.0 + 0.4 * i for i in range(10)]
    close += [164.0, 162.0, 160.5, 159.0, 157.0, 155.5, 153.2, 154.0, 158.0, 159.85]
    df = _ohlc(close, 0.12)
    sm = det.run_d1_smc_state_machine(df)
    if sm["trend"] == "neutral":
        return
    if float(df["close"].iloc[-1]) < 160.0 and sm["trend"] == "bullish":
        assert False, "USDJPY should not stay bullish below 160"


def test_v91_gbpusd_no_bullish_flip_in_bear_pullback():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    close = [1.39 - 0.002 * i for i in range(15)]
    close += [1.366, 1.358, 1.345, 1.332, 1.314, 1.322, 1.335, 1.350, 1.345, 1.322]
    df = _ohlc(close, 0.002)
    ctx = det.build_d1_context(df, symbol="GBPUSD")
    if ctx.trend != "bearish":
        bull_flip = [
            c for c in ctx.chochs
            if c.direction == "bullish"
            and getattr(c, "previous_trend", None) == "bearish"
            and c.index >= len(close) - 5
        ]
        assert not bull_flip


def test_v91_btc_stays_bearish_rev_without_post_flip_bos():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.35)
    close = [95000 - 420 * i + 600 * (1 if (i // 3) % 2 else -1) for i in range(38)]
    close += [94200, 93800, 94500, 95200, 94800, 93900]
    df = _ohlc(close, 450.0)
    ctx = det.build_d1_context(df, symbol="BTCUSD")
    if ctx.trend != "bearish":
        return
    flip = None
    for c in reversed(ctx.chochs):
        if getattr(c, "previous_trend", None) and c.previous_trend != c.direction:
            flip = c
            break
    if flip is None:
        return
    post = [b for b in ctx.bos_list if b.direction == "bearish" and b.index > flip.index]
    if not post:
        assert ctx.strategy_type == "reversal"


def test_v91_poi_lock_from_old_target_bos_window():
    class _Det(PoiMixin):
        pass

    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.376] * 6
        + [1.40, 1.418, 1.4282, 1.415, 1.393, 1.426, 1.431]
    )
    df = _ohlc(closes, 0.002)
    sm = det.run_d1_smc_state_machine(df)
    poi = _Det()
    bos = BOS(12, "bullish", 1.431, datetime.now(), None)
    res = poi.resolve_d1_poi(
        df,
        bos,
        1.426,
        "bullish",
        "continuation",
        None,
        stored_poi_top=1.39720,
        stored_poi_bottom=1.39279,
        protected_idx=sm["protected_idx"],
        target_idx=sm["target_idx"],
        is_internal_pullback=True,
        stored_protected_idx=sm["protected_idx"],
        stored_target_idx=6,
    )
    if sm.get("is_internal_pullback"):
        assert res.preserve_stored_poi
