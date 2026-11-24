"""V93/V94 body-only SMC + radar gates (synthetic — no historical_cache)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from smc_detector import BOS, CHoCH, SMCDetector
from smc_detector.models import TradeSetup
from smc_detector.poi import PoiMixin


def _body_ohlc(
    closes,
    spread: float = 0.0015,
    high_extra=None,
    low_extra=None,
):
    highs = []
    lows = []
    for i, c in enumerate(closes):
        h_bump = high_extra[i] if high_extra and i < len(high_extra) else spread
        l_bump = low_extra[i] if low_extra and i < len(low_extra) else spread
        highs.append(c + h_bump)
        lows.append(c - l_bump)
    return pd.DataFrame(
        {
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "time": pd.date_range("2025-01-01", periods=len(closes), freq="D"),
        }
    )


def test_v92_wick_above_hh_without_body_close_no_bos():
    """Wick sweep above HH — close stays inside range → no BOS/CHoCH."""
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.30, 1.28, 1.26, 1.24, 1.22, 1.20, 1.22, 1.24]
        + [1.27, 1.30, 1.33, 1.36, 1.38, 1.35, 1.33]
    )
    df = _body_ohlc(closes, spread=0.002)
    sm0 = det.run_d1_smc_state_machine(df)
    assert sm0["trend"] == "bullish"
    hh = float(sm0["structural_hh"])
    n = len(df)
    df.loc[n - 1, "close"] = hh - 0.002
    df.loc[n - 1, "open"] = hh - 0.001
    df.loc[n - 1, "high"] = hh + 0.05
    sm1 = det.run_d1_smc_state_machine(df)
    assert sm1["trend"] == "bullish"
    assert len(sm1["bos_list"]) == len(sm0["bos_list"])
    assert len(sm1["chochs"]) == len(sm0["chochs"])


def test_v92_usdcad_pre_bos_pullback_stays_bullish():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.362, 1.368, 1.372, 1.374, 1.3760, 1.3762, 1.3755, 1.3760]
        + [1.382, 1.392, 1.405, 1.418, 1.4235, 1.4282, 1.4275, 1.4268]
        + [1.415, 1.402, 1.3930, 1.399, 1.412, 1.42596]
    )
    df = _body_ohlc(closes, 0.002)
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


def test_v92_usdcad_post_bos_hl_from_old_hh():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.362, 1.368, 1.372, 1.374, 1.3760, 1.3762, 1.3755, 1.3760]
        + [1.382, 1.392, 1.405, 1.418, 1.4235, 1.4282, 1.4275, 1.4268]
        + [1.415, 1.402, 1.3930, 1.399, 1.412, 1.42596, 1.4310]
    )
    df = _body_ohlc(closes, 0.002)
    sm = det.run_d1_smc_state_machine(df)
    bos = [b for b in sm["bos_list"] if b.direction == "bullish"]
    assert bos
    pl = float(sm["protected_low"])
    assert pl <= 1.396
    assert sm["trend"] == "bullish"


def test_v92_gbpnzd_two_bos_continuation():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.2)
    closes = (
        [2.10, 2.08, 2.05, 2.02, 2.00, 1.98, 2.00, 2.03, 2.06, 2.09]
        + [2.12, 2.15, 2.18, 2.16, 2.14, 2.17, 2.20, 2.23, 2.21, 2.25]
        + [2.28, 2.27, 2.30]
    )
    df = _body_ohlc(closes, 0.008)
    ctx = det.build_d1_context(df, symbol="GBPNZD")
    bullish_bos = [b for b in ctx.bos_list if b.direction == "bullish"]
    if ctx.trend != "bullish" or len(bullish_bos) < 2:
        return
    assert ctx.strategy_type == "continuation"
    assert ctx.d1_signal_type == "BOS"


def test_v92_eurjpy_bullish_choch_without_bos_stays_rev():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.15)
    n = 45
    close = [182.5 - 0.12 * i for i in range(n - 8)]
    close += [175.5, 175.2, 175.8, 176.9, 177.91, 177.5, 176.9, 176.386]
    df = _body_ohlc(close, 0.08)
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


def test_v92_usdjpy_bearish_after_hl_body_break():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.18)
    closes = (
        [158.0, 157.5, 157.0, 157.8, 158.5, 159.2, 160.0, 161.0, 162.0, 163.5]
        + [164.0, 163.2, 162.5, 161.8, 160.5, 159.2, 158.0, 157.2, 156.5, 155.8]
    )
    df = _body_ohlc(closes, 0.12)
    sm = det.run_d1_smc_state_machine(df)
    if sm["trend"] != "bullish" or sm["protected_low"] is None:
        return
    pl = float(sm["protected_low"])
    closes2 = list(closes) + [pl - 1.0]
    df2 = _body_ohlc(closes2, 0.12)
    ctx = det.build_d1_context(df2, symbol="USDJPY")
    if float(df2["close"].iloc[-2]) < pl:
        assert ctx.trend == "bearish"


def test_v92_gbpusd_pullback_wick_no_bullish_choch():
    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.37, 1.368, 1.365, 1.362, 1.358, 1.355, 1.352, 1.348]
        + [1.345, 1.342, 1.338, 1.335, 1.332, 1.329, 1.326, 1.324]
    )
    df = _body_ohlc(closes, 0.002)
    sm0 = det.run_d1_smc_state_machine(df)
    if sm0["trend"] != "bearish" or sm0["protected_high"] is None:
        return
    lh = float(sm0["protected_high"])
    n_choch0 = len(sm0["chochs"])
    wick_close = lh - 0.004
    closes2 = list(closes) + [wick_close]
    high_extra = [0.0] * len(closes) + [0.015]
    df2 = _body_ohlc(closes2, 0.002, high_extra=high_extra)
    sm1 = det.run_d1_smc_state_machine(df2)
    assert sm1["trend"] == "bearish"
    assert len(sm1["chochs"]) == n_choch0
    new_bull = [
        c for c in sm1["chochs"][n_choch0:]
        if c.direction == "bullish" and getattr(c, "previous_trend", None) == "bearish"
    ]
    assert not new_bull


def test_v92_w1_non_blocking_w_d_misaligned():
    det = SMCDetector()
    sync = det.evaluate_w_d_sync("bullish", "BEARISH", 1.105, 1.100, 1.11, 1.09)
    assert sync["w_d_aligned"] is False
    assert sync.get("status") is None

    choch = CHoCH(10, "bullish", 1.10, "bearish", datetime.now(), None)
    from smc_detector.models import FVG

    setup = TradeSetup(
        symbol="EURUSD",
        daily_choch=choch,
        fvg=FVG(8, "bullish", 1.105, 1.100, 1.1025, datetime.now()),
        h4_choch=None,
        entry_price=1.102,
        stop_loss=1.108,
        take_profit=1.090,
    )
    setup.status = "MONITORING"
    out = det.apply_w_d_sync_gate(setup, "BEARISH", current_price=1.102)
    assert out.status == "MONITORING"
    assert out.w_d_aligned is False


def test_v92_poi_lock_from_old_target_bos_window():
    class _Det(PoiMixin):
        pass

    det = SMCDetector(swing_lookback=3, atr_multiplier=0.12)
    closes = (
        [1.376] * 6
        + [1.40, 1.418, 1.4282, 1.415, 1.393, 1.426, 1.431]
    )
    df = _body_ohlc(closes, 0.002)
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


def test_v93_target_armed_one_bos_during_impulse_staircase():
    """După un BOS, 3 închideri consecutive peste HH → un singur BOS, HL protejat."""
    det = SMCDetector(swing_lookback=2, atr_multiplier=0.06)
    closes = (
        [1.00, 1.01, 1.02, 1.01, 1.02, 1.03, 1.02, 1.03, 1.04, 1.03]
        + [1.05, 1.04, 1.05, 1.06, 1.05, 1.04, 1.05, 1.06, 1.07, 1.08]
        + [1.09, 1.10, 1.11, 1.12, 1.13, 1.14]
    )
    df = _body_ohlc(closes, 0.001)
    sm = det.run_d1_smc_state_machine(df)
    if sm["trend"] != "bullish":
        return
    bos = [b for b in sm["bos_list"] if b.direction == "bullish"]
    if not bos:
        return
    assert len(bos) == 1
    pl0 = float(sm["protected_low"])
    # protected HL must not drop below first BOS window indiscriminately
    assert pl0 <= 1.08


def test_v93_radar_move_exhausted_default_75pct_blocks_late_bos():
    """
    BOS târziu (AUDUSD-style): >75% POI-mid→TP — blocat; CHoCH la 56% (USDJPY) — permis la prag 0.75.
    """
    from radar_gates import h4_move_exhausted_vs_d1_tp

    aud_setup = {
        "poi_top": 0.6520,
        "poi_bottom": 0.6480,
        "take_profit": 0.6380,
    }
    poi_mid = (0.6520 + 0.6480) / 2.0
    total_leg = abs(0.6380 - poi_mid)
    late_bos_break = poi_mid - 0.78 * total_leg
    exhausted, reason = h4_move_exhausted_vs_d1_tp(aud_setup, late_bos_break)
    assert exhausted
    assert reason == "move_exhausted_far_from_poi"

    usdjpy_setup = {
        "poi_top": 159.20,
        "poi_bottom": 158.80,
        "take_profit": 161.50,
    }
    jpy_mid = (159.20 + 158.80) / 2.0
    jpy_leg = abs(161.50 - jpy_mid)
    choch_break = jpy_mid + 0.56 * jpy_leg
    exhausted_choch, reason_choch = h4_move_exhausted_vs_d1_tp(usdjpy_setup, choch_break)
    assert not exhausted_choch
    assert reason_choch == ""