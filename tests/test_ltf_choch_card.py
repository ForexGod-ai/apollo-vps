"""V51/W→D→4H: Telegram scan card LTF CHoCH — live gates aligned with radar V47/V50."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar_gates import ltf_choch_confirmed_for_card
from telegram_notifier import _format_radar_exec_lines, _ltf_choch_confirmed


class _FakeChoch:
    break_price = 1.31503


class _GbpusdScanSetup:
    """Simulates morning scan TradeSetup with stale scanner CHoCH objects."""

    symbol = 'GBPUSD'
    status = 'MONITORING'
    strategy_type = 'reversal'
    daily_choch = type('DC', (), {'direction': 'bearish'})()
    fvg = type('FVG', (), {'bottom': 1.33249, 'top': 1.33905})()
    h4_choch = _FakeChoch()


def test_scanner_h4_objects_do_not_confirm_without_radar():
    setup = _GbpusdScanSetup()
    assert _ltf_choch_confirmed(setup, {}, '4H', 'bearish') is False
    assert _ltf_choch_confirmed(setup, {}, '1H', 'bearish') is False


def test_waiting_pullback_status_does_not_confirm():
    merged = {
        'radar_4h_choch_detected': True,
        'radar_4h_choch_direction': 'bearish',
        'radar_4h_status': 'WAITING_4H_PULLBACK',
        'poi_first_touch_time': '2026-07-03T10:00:00+00:00',
        'radar_panda_active': True,
        'radar_4h_choch_time': '2026-07-03T11:00:00+00:00',
        'radar_4h_choch_bars_ago': 1,
        'h4_structure_locked': True,
    }
    assert ltf_choch_confirmed_for_card(merged, '4H', 'bearish') is True


def test_stale_historical_choch_not_live():
    merged = {
        'radar_4h_choch_detected': True,
        'radar_4h_choch_direction': 'bearish',
        'poi_first_touch_time': '2026-07-03T10:00:00+00:00',
        'radar_panda_active': True,
        'radar_4h_choch_time': '2026-06-01T08:00:00+00:00',
        'radar_4h_choch_bars_ago': 40,
        'h4_structure_locked': False,
    }
    assert ltf_choch_confirmed_for_card(merged, '4H', 'bearish') is False


def test_bullish_ltf_against_bearish_daily_not_confirmed():
    merged = {
        'radar_4h_choch_detected': True,
        'radar_4h_choch_direction': 'bullish',
        'poi_first_touch_time': '2026-07-03T10:00:00+00:00',
        'radar_panda_active': True,
        'radar_4h_choch_time': '2026-07-03T12:00:00+00:00',
        'radar_4h_choch_bars_ago': 2,
        'h4_structure_locked': True,
    }
    assert ltf_choch_confirmed_for_card(merged, '4H', 'bearish') is False


def test_h4_alert_sent_confirms():
    merged = {'h4_choch_alert_sent': True}
    assert ltf_choch_confirmed_for_card(merged, '4H', 'bearish') is True


def test_non_4h_tf_never_confirms():
    merged = {
        'radar_4h_choch_detected': True,
        'radar_4h_choch_direction': 'bearish',
        'poi_first_touch_time': '2026-07-03T10:00:00+00:00',
        'radar_4h_choch_time': '2026-07-03T13:00:00+00:00',
        'radar_4h_choch_bars_ago': 1,
    }
    assert ltf_choch_confirmed_for_card(merged, '1H', 'bearish') is False


def test_post_poi_26b_confirms_without_lock():
    """V52: post-POI CHoCH beyond 3 bars — card confirms (bars are informational only)."""
    merged = {
        'radar_4h_choch_detected': True,
        'radar_4h_choch_direction': 'bearish',
        'poi_first_touch_time': '2026-07-03T10:00:00+00:00',
        'radar_panda_active': True,
        'radar_4h_choch_time': '2026-07-05T14:00:00+00:00',
        'radar_4h_choch_bars_ago': 26,
        'h4_structure_locked': False,
    }
    assert ltf_choch_confirmed_for_card(merged, '4H', 'bearish') is True


def test_gbpusd_card_shows_waiting_line():
    setup = _GbpusdScanSetup()
    h4_line = _format_radar_exec_lines(
        setup, 'GBPUSD', 'bearish', 'Waiting 4H CHoCH',
    )
    assert '⏳' in h4_line
    assert 'Confirmat' not in h4_line


if __name__ == '__main__':
    test_scanner_h4_objects_do_not_confirm_without_radar()
    test_waiting_pullback_status_does_not_confirm()
    test_stale_historical_choch_not_live()
    test_bullish_ltf_against_bearish_daily_not_confirmed()
    test_h4_alert_sent_confirms()
    test_non_4h_tf_never_confirms()
    test_post_poi_26b_confirms_without_lock()
    test_gbpusd_card_shows_waiting_line()
    print('tests/test_ltf_choch_card.py: all passed')
