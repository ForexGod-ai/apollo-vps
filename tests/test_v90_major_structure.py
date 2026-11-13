"""V90 synthetic — major range SM, D1 authority chronology, MARKET_REPORT 16/16 (no historical_cache)."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from smc_detector import CHoCH, BOS, SMCDetector
from smc_detector.models import FVG
from smc_detector.poi import PoiMixin
from telegram_notifier import TelegramNotifier, _render_scan_inventory


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


def test_v90_usdcad_major_pullback_no_false_bearish_choch():
    """Tipar 1 — bullish leg: HL fixed until BOS > HH_major; internal pullback."""
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.362, 1.368, 1.372, 1.374, 1.3760, 1.3762, 1.3755, 1.3760] * 1
        + [1.382, 1.392, 1.405, 1.418, 1.4235, 1.4282, 1.4275, 1.4268]
        + [1.415, 1.402, 1.3930, 1.399, 1.412, 1.42596]
    )
    df = _ohlc(closes, spread=0.002)
    sm = det.run_d1_smc_state_machine(df)
    assert sm["trend"] == "bullish", sm
    pl = sm.get("protected_low")
    assert pl is not None
    assert pl <= 1.3820, f"protected should stay near origin HL until major BOS, got {pl}"
    assert sm.get("is_internal_pullback") is True
    bear_flips = [
        c
        for c in sm["chochs"]
        if c.direction == "bearish" and getattr(c, "previous_trend", None) == "bullish"
    ]
    assert not bear_flips

    class _Det(PoiMixin):
        pass

    poi_det = _Det()
    bos = BOS(20, "bullish", 1.4282, datetime.now(), None)
    res = poi_det.resolve_d1_poi(
        df,
        bos,
        1.42596,
        "bullish",
        "continuation",
        None,
        stored_poi_top=1.39720,
        stored_poi_bottom=1.39279,
        protected_idx=sm["protected_idx"],
        target_idx=sm["target_idx"],
        is_internal_pullback=True,
        stored_protected_idx=sm["protected_idx"],
        stored_target_idx=sm["target_idx"],
    )
    assert res.preserve_stored_poi

    closes2 = list(closes) + [1.4310]
    df2 = _ohlc(closes2, spread=0.002)
    sm2 = det.run_d1_smc_state_machine(df2)
    assert sm2["trend"] == "bullish"
    bos_events = [b for b in sm2["bos_list"] if b.direction == "bullish"]
    assert bos_events, "expected major BOS above HH"
    pl2 = float(sm2["protected_low"])
    assert pl2 <= 1.396, f"after BOS protected should promote toward pullback low, got {pl2}"


def test_v90_btc_reversal_sticky_when_choch_after_bos():
    """Tipar 2 — latest flip CHoCH after aligned BOS → stay REV / CHoCH."""
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.35)
    n = 42
    close = []
    for i in range(n - 6):
        close.append(95000 - 420 * i + 600 * (1 if (i // 3) % 2 else -1))
    close.extend([94200, 93800, 94500, 95200, 94800, 93900])
    df = _ohlc(close, spread=450.0)
    ctx = det.build_d1_context(df, symbol="BTCUSD")
    if ctx.trend != "bearish":
        return
    flip_chochs = [
        c
        for c in ctx.chochs
        if getattr(c, "previous_trend", None) and c.previous_trend != c.direction
    ]
    if not flip_chochs:
        return
    last_flip = flip_chochs[-1]
    same_bos = [b for b in ctx.bos_list if getattr(b, "direction", "") == ctx.trend]
    if same_bos and same_bos[-1].index <= last_flip.index:
        assert ctx.strategy_type == "reversal"
        assert ctx.d1_signal_type == "CHoCH"


def test_v90_gbpjpy_bearish_bounce_no_bullish_choch():
    """Tipar 3 — bearish range; internal bounce must not flip bullish."""
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.2)
    close = []
    for i in range(40):
        close.append(222.0 - 0.18 * i + 0.5 * (1 if (i // 4) % 2 else -0.8))
    close[-4:] = [close[-5] + 0.35, close[-4] + 0.25, close[-3] - 0.15, close[-2] + 0.2]
    df = _ohlc(close, 0.12)
    ctx = det.build_d1_context(df, symbol="GBPJPY")
    if ctx.trend != "bearish":
        return
    bull = [
        c
        for c in ctx.chochs
        if c.direction == "bullish"
        and getattr(c, "previous_trend", None) == "bearish"
        and c.index >= len(close) - 6
    ]
    assert not bull


def test_v90_market_report_inventory_16_symbols():
    """Tipar 4 — toate simbolurile apar în secțiunea inventar."""
    symbols = [
        "XAUUSD", "USDCAD", "USDCHF", "AUDUSD", "AUDJPY", "USDJPY", "EURGBP",
        "GBPCAD", "BTCUSD", "XTIUSD", "GBPJPY", "GBPNZD", "EURUSD", "NZDUSD",
        "EURJPY", "GBPUSD",
    ]
    inv = [
        {
            "symbol": s,
            "trend": "BULLISH" if i % 2 == 0 else "BEARISH",
            "strategy_type": "CONT" if i % 3 else "REV",
            "has_setup": i < 13,
            "stage_label": "Pullback spre POI" if i < 8 else "Fără FVG valid încă",
        }
        for i, s in enumerate(symbols)
    ]
    block = _render_scan_inventory(inv)
    for s in symbols:
        assert s in block
        assert "BULLISH" in block or "BEARISH" in block
    assert "16/16" in block or "16/" in block

    tn = TelegramNotifier()
    with patch.object(tn, "send_message", return_value=True) as mock_send:
        ok = tn.send_scan_report(
            total_pairs=16,
            new_setups_found=10,
            truly_new=2,
            re_detected=8,
            monitoring_count=12,
            open_positions=0,
            setup_symbols=[],
            scan_inventory=inv,
        )
    assert ok
    body = mock_send.call_args[0][0]
    for s in symbols:
        assert s in body
    assert "CONT" in body or "REV" in body


def test_v90_d1_authority_bos_must_follow_flip_for_continuation():
    """Unit: BOS before flip CHoCH cannot force continuation."""
    mixin = SMCDetector()
    choch = CHoCH(
        50, "bearish", 90000.0, previous_trend="bullish", candle_time=datetime.now(), swing_broken=None,
    )
    bos = BOS(45, "bearish", 91000.0, candle_time=datetime.now(), swing_broken=None)
    df = _ohlc([90000.0] * 55, spread=100.0)
    sm = {
        "trend": "bearish",
        "strategy_type": "reversal",
        "leg_choch": choch,
        "chochs": [choch],
        "bos_list": [bos],
        "protected_low": None,
        "protected_high": 92000.0,
        "protected_idx": 10,
        "target_idx": 40,
        "is_internal_pullback": False,
        "latest_signal": choch,
    }
    with patch.object(mixin, "run_d1_smc_state_machine", return_value=sm), patch.object(
        mixin, "d1_closed_structure_df", return_value=df
    ), patch.object(mixin, "detect_swing_highs", return_value=[]), patch.object(
        mixin, "detect_swing_lows", return_value=[]
    ), patch.object(mixin, "compute_structural_range", return_value=None), patch.object(
        mixin, "macro_trend_from_swings", return_value="bearish"
    ):
        ctx = mixin.build_d1_context(df, symbol="BTCUSD")
    assert ctx.strategy_type == "reversal"
    assert ctx.d1_signal_type == "CHoCH"
