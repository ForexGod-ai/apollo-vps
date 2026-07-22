"""Faza 1/2: W1 macro POI + W+D soft sync gate."""
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import multi_tf_radar as mtr
from smc_detector import CHoCH, FVG, SMCDetector, TradeSetup


def _make_setup(direction='bullish'):
    choch = CHoCH(
        index=10,
        direction=direction,
        break_price=1.1000,
        previous_trend='bearish' if direction == 'bullish' else 'bullish',
        candle_time=datetime(2026, 7, 1),
        swing_broken=None,
    )
    fvg = FVG(
        index=8,
        direction=direction,
        top=1.1050,
        bottom=1.1020,
        middle=1.1035,
        candle_time=datetime(2026, 6, 28),
    )
    setup = TradeSetup(
        symbol='EURGBP',
        daily_choch=choch,
        fvg=fvg,
        h4_choch=None,
        entry_price=1.1035,
        stop_loss=1.1100,
        take_profit=1.0900,
    )
    return setup


def test_daily_poi_inside_weekly_zone_middle_contained():
    assert SMCDetector.daily_poi_inside_weekly_zone(1.105, 1.100, 1.110, 1.095) is True


def test_daily_poi_outside_weekly_zone():
    assert SMCDetector.daily_poi_inside_weekly_zone(1.120, 1.115, 1.110, 1.095) is False


def test_evaluate_w_d_sync_counter_trend_bearish_w1_bullish_d1():
    det = SMCDetector()
    sync = det.evaluate_w_d_sync(
        'bullish', 'BEARISH',
        1.105, 1.100, 1.110, 1.095,
        current_price=1.103,
    )
    assert sync['w_d_aligned'] is False
    assert sync['status'] == 'WAITING_W_D_SYNC'


def test_apply_w_d_sync_gate_blocks_long_when_w1_bearish():
    det = SMCDetector()
    setup = _make_setup('bullish')
    setup.status = 'MONITORING'
    out = det.apply_w_d_sync_gate(
        setup,
        'BEARISH',
        w1_poi={'w1_poi_top': 1.110, 'w1_poi_bottom': 1.095},
        current_price=1.103,
    )
    assert out.status == 'WAITING_W_D_SYNC'
    assert out.w_d_aligned is False
    assert out.confidence == 'LOW_W1_COUNTER_TREND'


def test_apply_w_d_sync_gate_aligned_bearish():
    det = SMCDetector()
    setup = _make_setup('bearish')
    setup.status = 'MONITORING'
    out = det.apply_w_d_sync_gate(
        setup,
        'BEARISH',
        w1_poi={'w1_poi_top': 1.110, 'w1_poi_bottom': 1.095},
        current_price=1.103,
    )
    assert out.w_d_aligned is True
    assert out.status == 'MONITORING'


def test_arm_execute_now_blocked_on_w_d_mismatch():
    radar = mtr.MultiTFRadar.__new__(mtr.MultiTFRadar)
    radar.smc_4h = SMCDetector()
    setup = {
        'symbol': 'EURGBP',
        'direction': 'buy',
        'daily_bias': 'BULLISH',
        'd1_bias_direction': 'bullish',
        'w1_bias': 'BEARISH',
        'w_d_aligned': False,
        'status': 'WAITING_W_D_SYNC',
        'poi_top': 1.105,
        'poi_bottom': 1.100,
        'w1_poi_top': 1.110,
        'w1_poi_bottom': 1.095,
        'poi_touch_latched': True,
    }
    result = SimpleNamespace(
        symbol='EURGBP',
        direction='LONG',
        current_price=1.103,
        tf_4h=SimpleNamespace(
            fvg_top=1.104, fvg_bottom=1.101, equilibrium=1.1025,
            h4_sl_price=1.098, retrace_pct=0.7, in_poi_entry_zone=True,
        ),
        daily_zone_validated=True,
    )
    with patch.object(radar, '_flush_execute_now_to_json'):
        with patch.object(radar, '_v423_ltf_misalignment', return_value=('bullish', [])):
            radar._arm_execute_now(setup, result, '4H', source='test')
    assert setup.get('EXECUTE_NOW') is not True


def test_w_d_sync_radar_blocks_execute():
    radar = mtr.MultiTFRadar.__new__(mtr.MultiTFRadar)
    radar.smc_4h = SMCDetector()
    setup = {
        'symbol': 'GBPUSD',
        'd1_bias_direction': 'bullish',
        'w1_bias': 'BEARISH',
        'poi_top': 1.265,
        'poi_bottom': 1.260,
        'w1_poi_top': 1.270,
        'w1_poi_bottom': 1.255,
        'status': 'MONITORING',
    }
    result = SimpleNamespace(symbol='GBPUSD', current_price=1.262)
    assert radar._w_d_sync_blocks_execute(setup, result) is True
    assert setup['status'] == 'WAITING_W_D_SYNC'


def test_resolve_status_promotes_waiting_w_d_sync_when_aligned():
    sync = {'w_d_aligned': True, 'status': None, 'reason': 'w_d_aligned'}
    assert SMCDetector.resolve_status_after_w_d_sync('WAITING_W_D_SYNC', sync) == 'MONITORING'
    assert SMCDetector.resolve_status_after_w_d_sync('WAITING_W_ZONE', sync) == 'MONITORING'
    assert SMCDetector.resolve_status_after_w_d_sync('MONITORING', sync) == 'MONITORING'


def test_apply_w_d_sync_gate_promotes_sticky_waiting_status():
    det = SMCDetector()
    setup = _make_setup('bullish')
    setup.status = 'WAITING_W_D_SYNC'
    setup.confidence = 'LOW_W1_COUNTER_TREND'
    setup.w_d_aligned = False
    out = det.apply_w_d_sync_gate(
        setup,
        'BULLISH',
        w1_poi={'w1_poi_top': 1.110, 'w1_poi_bottom': 1.095},
        current_price=1.103,
    )
    assert out.w_d_aligned is True
    assert out.status == 'MONITORING'
    assert out.confidence == 'NORMAL'


def test_arm_execute_now_allowed_after_w_d_promotion():
    radar = mtr.MultiTFRadar.__new__(mtr.MultiTFRadar)
    radar.smc_4h = SMCDetector()
    radar._execute_now_alert_keys = set()
    setup = {
        'symbol': 'USDCAD',
        'direction': 'buy',
        'daily_bias': 'BULLISH',
        'd1_bias_direction': 'bullish',
        'w1_bias': 'BULLISH',
        'w_d_aligned': True,
        'status': 'WAITING_W_D_SYNC',
        'poi_top': 1.365,
        'poi_bottom': 1.360,
        'w1_poi_top': 1.370,
        'w1_poi_bottom': 1.355,
        'poi_touch_latched': True,
    }
    result = SimpleNamespace(
        symbol='USDCAD',
        direction='LONG',
        current_price=1.362,
        tf_4h=SimpleNamespace(
            fvg_top=1.364, fvg_bottom=1.361, equilibrium=1.3625,
            h4_sl_price=1.358, retrace_pct=0.7, in_poi_entry_zone=True,
        ),
        daily_zone_validated=True,
    )
    assert radar._w_d_sync_blocks_execute(setup, result) is False
    assert setup['status'] == 'MONITORING'
    with patch.object(radar, '_flush_execute_now_to_json'):
        with patch.object(radar, '_v423_ltf_misalignment', return_value=('bullish', [])):
            with patch.object(mtr, 'logger'):
                radar._arm_execute_now(setup, result, '4H', source='test')
    assert setup.get('EXECUTE_NOW') is True
