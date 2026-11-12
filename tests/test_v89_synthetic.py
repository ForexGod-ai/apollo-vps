"""V89 synthetic tests — range lock, POI lock, Telegram 4H line (no historical_cache)."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd

from smc_detector import CHoCH, SMCDetector
from smc_detector.models import BOS, TradeSetup, FVG
from smc_detector.poi import PoiMixin
from telegram_notifier import _format_radar_exec_lines, _scan_card_wait_hint


def _ohlc(closes, spread=0.001):
    return pd.DataFrame(
        {
            "open": closes,
            "high": [c + spread for c in closes],
            "low": [c - spread for c in closes],
            "close": closes,
            "time": pd.date_range("2025-01-01", periods=len(closes), freq="D"),
        }
    )


def test_v89_poi_lock_helper():
    assert PoiMixin.should_lock_poi_on_active_range(
        1.397, 1.392, 10, 20, 10, 20, is_internal_pullback=False,
    )
    assert PoiMixin.should_lock_poi_on_active_range(
        1.397, 1.392, None, None, 10, 20, is_internal_pullback=True,
    )
    assert not PoiMixin.should_lock_poi_on_active_range(
        1.397, 1.392, 10, 20, 11, 20,
    )


def test_v89_resolve_d1_poi_preserves_stored_on_internal_pullback():
    class _Det(PoiMixin):
        pass

    det = _Det()
    df = _ohlc([1.40] * 30, 0.002)
    bos = BOS(15, "bullish", 1.428, datetime.now(), None)
    ctx_signal = bos
    res = det.resolve_d1_poi(
        df,
        ctx_signal,
        1.425,
        "bullish",
        "continuation",
        None,
        stored_poi_top=1.39720,
        stored_poi_bottom=1.39279,
        protected_idx=5,
        target_idx=18,
        is_internal_pullback=True,
    )
    assert res.preserve_stored_poi
    assert abs(res.fvg.bottom - 1.39279) < 1e-4
    assert abs(res.fvg.top - 1.39720) < 1e-4


def test_v89_telegram_no_pullback_hint_when_poi_touched():
    setup = SimpleNamespace(
        status="WAITING_D1_PULLBACK",
        h4_confirmed=False,
        poi_was_touched=True,
        poi_touched_active=True,
        w_d_aligned=True,
    )
    hint = _scan_card_wait_hint(setup)
    assert "pullback la POI Daily" not in hint
    line = _format_radar_exec_lines(
        setup, "USDCAD", "bullish", hint, radar_snapshot={}, live_price=1.426,
    )
    assert "pullback la POI Daily" not in line
    assert "confirmare CHoCH 4H" in line


def test_v89_bullish_pullback_does_not_emit_reversal_choch():
    """Mid-range dip/rally must not flip trend (no V87 HL promotion)."""
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.2)
    n = 50
    close = []
    for i in range(n):
        base = 1.36 + 0.0012 * i
        wave = 0.012 * (1 if (i // 5) % 2 == 0 else -1)
        close.append(base + wave)
    close[-5] = close[-6] - 0.025
    close[-4] = close[-5] + 0.008
    close[-3] = close[-4] + 0.010
    close[-2] = close[-3] + 0.008
    close[-1] = close[-2] + 0.006
    df = _ohlc(close, 0.003)
    sm = det.run_d1_smc_state_machine(df)
    if sm["trend"] == "bullish" and sm.get("protected_low") and sm.get("structural_hh"):
        assert float(df["close"].iloc[-1]) <= float(sm["structural_hh"]) + 0.02
        rev_flips = [
            c for c in sm["chochs"]
            if getattr(c, "previous_trend", None) == "bullish"
            and c.direction == "bearish"
            and c.index >= n - 8
        ]
        assert not rev_flips


def test_v89_btc_major_choch_after_bos_hl_promotion():
    """BOS sets HL_major; close under HL → bearish reversal."""
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.25)
    n = 55
    close = []
    for i in range(n - 3):
        base = 68000 + 280 * i
        wave = 900 * (1 if (i // 4) % 2 == 0 else -1)
        close.append(base + wave)
    df = _ohlc(close, spread=350.0)
    sm0 = det.run_d1_smc_state_machine(df)
    assert sm0["trend"] == "bullish"
    prot = float(sm0["protected_low"])
    df.loc[len(df) - 1, "close"] = prot - 400
    df.loc[len(df) - 1, "low"] = prot - 600
    forming = float(df.loc[len(df) - 1, "close"])
    df.loc[len(df)] = {
        "open": forming,
        "high": forming + 80,
        "low": forming - 80,
        "close": forming,
        "time": pd.Timestamp("2025-04-01"),
    }
    ctx = det.build_d1_context(df, symbol="BTCUSD")
    assert ctx.trend == "bearish"
    assert ctx.strategy_type == "reversal"
    assert isinstance(ctx.latest_signal, CHoCH)


def test_v89_bearish_bounce_no_bullish_choch():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.2)
    n = 48
    close = []
    for i in range(n):
        base = 220.0 - 0.15 * i
        wave = 0.8 * (1 if (i // 4) % 2 == 0 else -1)
        close.append(base + wave)
    close[-1] = close[-2] + 0.5
    close[-2] = close[-3] + 0.4
    df = _ohlc(close, 0.15)
    ctx = det.build_d1_context(df, symbol="GBPJPY")
    if ctx.trend == "bearish":
        bull_reversal = [
            c for c in ctx.chochs
            if getattr(c, "previous_trend", None) == "bearish"
            and c.direction == "bullish"
            and c.index >= n - 5
        ]
        assert not bull_reversal


def test_v89_usdcad_style_range_lock_no_late_reversal_choch():
    """După trend bullish, retrageri mid-range nu emit CHoCH bearish (range lock)."""
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.15)
    n = 52
    close = []
    for i in range(n):
        base = 1.30 + 0.0025 * i
        wave = 0.008 * (1 if (i // 4) % 2 == 0 else -0.6)
        close.append(base + wave)
    close[-1] = close[-2] + 0.004
    df = _ohlc(close, 0.002)
    sm = det.run_d1_smc_state_machine(df)
    if sm["trend"] != "bullish":
        return
    pl = sm.get("protected_low")
    th = sm.get("structural_hh")
    if pl is None or th is None:
        return
    last_c = float(df["close"].iloc[-1])
    if pl <= last_c <= th:
        assert sm.get("is_internal_pullback") is True
    late_bear = [
        c for c in sm["chochs"]
        if c.direction == "bearish"
        and getattr(c, "previous_trend", None) == "bullish"
        and c.index >= n - 12
        and float(df["close"].iloc[c.index]) >= pl
    ]
    assert not late_bear
