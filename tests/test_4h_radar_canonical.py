"""V68: 4H radar canonical — major swings, opposite invalidation, EXECUTE_NOW flush."""
from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

import multi_tf_radar as mtr
from smc_detector import CHoCH, SMCDetector, SwingPoint


def _make_ohlc(closes, spread=0.08):
    """Build minimal OHLC from close series."""
    rows = []
    for i, c in enumerate(closes):
        o = closes[i - 1] if i else c
        h = max(o, c) + spread
        l = min(o, c) - spread
        rows.append({'open': o, 'high': h, 'low': l, 'close': c})
    return pd.DataFrame(rows)


def _eurjpy_bullish_reversal_df() -> pd.DataFrame:
    """
    Bearish structure then strong bullish body-close HH (EURJPY-like).
    Last bars rally above prior major LH body-high.
    """
    base = 168.0
    closes = []
    # Downtrend / bearish structure
    for i in range(35):
        closes.append(base - i * 0.05)
    # Stabilize + minor bounce
    for i in range(10):
        closes.append(closes[-1] + (0.02 if i % 2 else -0.01))
    # Strong bullish impulse — body-close above earlier highs
    impulse_start = closes[-1]
    for i in range(8):
        closes.append(impulse_start + (i + 1) * 0.35)
    return _make_ohlc(closes, spread=0.06)


def test_eurjpy_bullish_impulse_invalidates_bearish_choch():
    df = _eurjpy_bullish_reversal_df()
    det = SMCDetector(swing_lookback=3, atr_multiplier=1.0)
    sh = det.detect_swing_highs(df)
    sl = det.detect_swing_lows(df)
    mh, ml = det.filter_major_swings(df, sh, sl)

    # Explicit major pivots when synthetic series is too short for filter_major_swings
    if not mh:
        mh = [SwingPoint(12, float(df['high'].iloc[12]), 'high', datetime(2026, 8, 1))]
    if not ml:
        ml = [SwingPoint(8, float(df['low'].iloc[8]), 'low', datetime(2026, 8, 1))]

    broken = ml[0]
    stale_bearish = CHoCH(
        index=min(len(df) - 10, broken.index + 5),
        direction='bearish',
        break_price=float(df['close'].iloc[min(len(df) - 10, broken.index + 5)]),
        previous_trend='bullish',
        candle_time=datetime(2026, 8, 5),
        swing_broken=broken,
    )

    assert mtr._opposite_bullish_invalidation_after(stale_bearish, df, mh) is True
    purged = mtr._purge_chochs_invalidated_by_opposite_impulse(
        [stale_bearish], df, mh, ml,
    )
    assert purged == []

    chochs, _ = det.detect_choch_and_bos(df)
    chochs = mtr._purge_chochs_invalidated_by_opposite_impulse(
        chochs, df, mh, ml,
    )
    bearish_recent = mtr._filter_events_in_recent_window(
        [c for c in chochs if c.direction == 'bearish'], df,
    )
    bearish_recent = mtr._filter_structurally_valid_events(bearish_recent, df)
    assert bearish_recent == []


def test_choch_must_use_major_swings_only():
    """Micro wiggles must not produce CHoCH — only major pivot breaks."""
    # Tiny noise around flat price — geometric swings exist, majors should not break structure
    noise = [100.0 + (0.01 if i % 2 else -0.01) for i in range(40)]
    df_flat = _make_ohlc(noise, spread=0.005)
    det = SMCDetector(swing_lookback=3, atr_multiplier=1.0)
    chochs_flat, bos_flat = det.detect_choch_and_bos(df_flat)
    assert chochs_flat == []
    assert bos_flat == []

    # One clear major down-leg then body-close bullish break above major LH
    closes = [100.0 - i * 0.4 for i in range(20)]
    closes += [closes[-1] + i * 0.5 for i in range(1, 15)]
    df_trend = _make_ohlc(closes, spread=0.05)
    chochs, bos = det.detect_choch_and_bos(df_trend)
    sh = det.detect_swing_highs(df_trend)
    sl = det.detect_swing_lows(df_trend)
    mh, ml = det.filter_major_swings(df_trend, sh, sl)
    for c in chochs:
        assert c.swing_broken.index in {s.index for s in mh + ml}


def test_analyze_timeframe_rejects_stale_bearish_after_bullish_hh():
    df = _eurjpy_bullish_reversal_df()
    radar = mtr.MultiTFRadar.__new__(mtr.MultiTFRadar)
    radar.smc_4h = SMCDetector(swing_lookback=3, atr_multiplier=1.0)

    with patch.object(radar, 'get_historical_data', return_value=df):
        tf = radar.analyze_timeframe(
            symbol='EURJPY',
            timeframe='H4',
            required_direction='bearish',
            current_price=float(df['close'].iloc[-1]),
            smc_detector=radar.smc_4h,
            poi_touch_latched=True,
        )
    assert tf.choch_detected is False
    assert tf.choch_direction is None


def test_execute_now_pipeline_flush():
    radar = mtr.MultiTFRadar.__new__(mtr.MultiTFRadar)
    radar.smc_4h = SMCDetector()
    radar._execute_now_alert_keys = set()
    radar.ctrader = SimpleNamespace(is_available=lambda **kwargs: True)
    flushed = []

    def _capture_flush(setup):
        flushed.append({
            'EXECUTE_NOW': setup.get('EXECUTE_NOW'),
            'execute_now_trigger_tf': setup.get('execute_now_trigger_tf'),
        })

    setup = {
        'symbol': 'EURUSD',
        'direction': 'buy',
        'd1_bias_direction': 'bullish',
        'w_d_aligned': True,
        'status': 'MONITORING',
        'poi_touch_latched': True,
    }
    result = SimpleNamespace(
        symbol='EURUSD',
        direction='LONG',
        current_price=1.1050,
        daily_zone_validated=True,
        tf_4h=SimpleNamespace(
            fvg_top=1.1060,
            fvg_bottom=1.1040,
            equilibrium=1.1050,
            h4_sl_price=1.1020,
            retrace_pct=0.70,
            in_poi_entry_zone=True,
        ),
    )
    with patch.object(radar, '_flush_execute_now_to_json', side_effect=_capture_flush):
        with patch.object(radar, '_v423_ltf_misalignment', return_value=('bullish', [])):
            with patch.object(mtr, 'logger'):
                with patch.object(radar, '_send_radar_telegram_alert'):
                    radar._arm_execute_now(setup, result, '4H', source='test')

    assert setup.get('EXECUTE_NOW') is True
    assert setup.get('execute_now_trigger_tf') == '4H'
    assert flushed
    assert flushed[0]['EXECUTE_NOW'] is True
    assert flushed[0]['execute_now_trigger_tf'] == '4H'


def test_filter_events_in_recent_window():
    df = _make_ohlc([100 + i * 0.1 for i in range(80)], spread=0.05)
    old = CHoCH(
        index=5,
        direction='bearish',
        break_price=99.0,
        previous_trend='bullish',
        candle_time=datetime(2026, 1, 1),
        swing_broken=SwingPoint(3, 99.5, 'low', datetime(2026, 1, 1)),
    )
    recent = CHoCH(
        index=70,
        direction='bearish',
        break_price=105.0,
        previous_trend='bullish',
        candle_time=datetime(2026, 2, 1),
        swing_broken=SwingPoint(65, 106.0, 'low', datetime(2026, 2, 1)),
    )
    out = mtr._filter_events_in_recent_window([old, recent], df, max_bars=50)
    assert old not in out
    assert recent in out
