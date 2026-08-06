"""V56: 4H structural alert gates — no retrace block on confirmation alert."""
from types import SimpleNamespace
from unittest.mock import patch

import multi_tf_radar as mtr


def _make_radar():
    radar = mtr.MultiTFRadar.__new__(mtr.MultiTFRadar)
    return radar


def test_4h_alert_passes_with_high_retrace_post_poi():
    """Alert path must not block on retrace >200% — that's EXECUTE_NOW only."""
    radar = _make_radar()
    setup = {
        'symbol': 'EURJPY',
        'radar_panda_active': True,
        'poi_first_touch_time': '2026-07-01T08:00:00+00:00',
        'h4_choch_alert_sent': False,
    }
    tf_4h = SimpleNamespace(
        signal_type='CHoCH',
        choch_detected=True,
        choch_direction='bearish',
        choch_time='2026-07-01T12:00:00+00:00',
        choch_bars_ago=5,
        choch_price=165.0,
        bos_detected=False,
        bos_direction=None,
        bos_bars_ago=9999,
        retrace_pct=2.5,  # 250% — would fail _retrace_is_alert_valid
    )
    result = SimpleNamespace(symbol='EURJPY', tf_4h=tf_4h)

    with patch.object(mtr, '_v47_break_post_poi_touch', return_value=True):
        with patch.object(radar, '_flush_choch_alerts_to_json'):
            with patch('telegram_alert_dedup.claim_4h_structural_alert', return_value=True):
                with patch('telegram_notifier.TelegramNotifier') as mock_tn:
                    mock_tn.return_value.send_4h_structural_alert.return_value = True
                    with patch.object(radar, 'get_historical_data', return_value=None):
                        radar._maybe_send_choch_alerts(setup, result, 'bearish')

    assert setup.get('h4_choch_alert_sent') is True


def test_4h_alert_blocked_when_choch_opposes_daily_bias():
    """Daily SHORT + 4H bullish CHoCH → alert must be blocked (direction mismatch)."""
    radar = _make_radar()
    setup = {
        'symbol': 'EURUSD',
        'direction': 'SHORT',
        'radar_panda_active': True,
        'poi_first_touch_time': '2026-07-01T08:00:00+00:00',
        'h4_choch_alert_sent': False,
    }
    tf_4h = SimpleNamespace(
        signal_type='CHoCH',
        choch_detected=True,
        choch_direction='bullish',
        choch_time='2026-07-01T12:00:00+00:00',
        choch_bars_ago=2,
        choch_price=1.0850,
        bos_detected=False,
        bos_direction=None,
        bos_bars_ago=9999,
        retrace_pct=0.7,
    )
    result = SimpleNamespace(symbol='EURUSD', direction='SHORT', tf_4h=tf_4h)

    with patch.object(mtr, '_v47_break_post_poi_touch', return_value=True):
        with patch.object(radar, '_flush_choch_alerts_to_json'):
            with patch('telegram_alert_dedup.claim_4h_structural_alert', return_value=True):
                with patch('telegram_notifier.TelegramNotifier') as mock_tn:
                    mock_tn.return_value.send_4h_structural_alert.return_value = True
                    radar._maybe_send_choch_alerts(setup, result, 'bearish')

    assert setup.get('h4_choch_alert_sent') is not True
    mock_tn.return_value.send_4h_structural_alert.assert_not_called()


def test_4h_alert_passes_when_daily_long_and_choch_bullish_aligned():
    """V62: LONG Daily + bullish 4H CHoCH → alert must pass (GBPCAD-class)."""
    radar = _make_radar()
    setup = {
        'symbol': 'GBPCAD',
        'direction': 'LONG',
        'radar_panda_active': True,
        'poi_first_touch_time': '2026-07-01T08:00:00+00:00',
        'h4_choch_alert_sent': False,
    }
    tf_4h = SimpleNamespace(
        signal_type='CHoCH',
        choch_detected=True,
        choch_direction='bullish',
        choch_time='2026-07-01T12:00:00+00:00',
        choch_bars_ago=2,
        choch_price=1.8250,
        bos_detected=False,
        bos_direction=None,
        bos_bars_ago=9999,
        retrace_pct=0.7,
    )
    result = SimpleNamespace(symbol='GBPCAD', direction='LONG', tf_4h=tf_4h)

    with patch.object(mtr, '_v47_break_post_poi_touch', return_value=True):
        with patch.object(radar, '_flush_choch_alerts_to_json'):
            with patch('telegram_alert_dedup.claim_4h_structural_alert', return_value=True):
                with patch('telegram_notifier.TelegramNotifier') as mock_tn:
                    mock_tn.return_value.send_4h_structural_alert.return_value = True
                    radar._maybe_send_choch_alerts(setup, result, 'bullish')

    assert setup.get('h4_choch_alert_sent') is True
