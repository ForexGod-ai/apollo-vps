"""V0b: 4H structural alert dedup — file lock + POI flicker guard."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import multi_tf_radar as mtr
import telegram_alert_dedup as dedup


def _make_radar():
    return mtr.MultiTFRadar.__new__(mtr.MultiTFRadar)


def test_claim_4h_structural_alert_cooldown_24h(tmp_path, monkeypatch):
    dedup_file = tmp_path / "telegram_4h_structural_alerts.json"
    lock_file = tmp_path / "telegram_4h_structural_alerts.lock"
    monkeypatch.setattr(dedup, "_H4_DEDUP_PATH", dedup_file)
    monkeypatch.setattr(dedup, "_H4_LOCK_PATH", lock_file)

    bk = "CHOCH|2026-07-01T12:00:00+00:00|165.0"
    assert dedup.claim_4h_structural_alert("EURJPY", "sell", bk) is True
    assert dedup.claim_4h_structural_alert("EURJPY", "sell", bk) is False


def test_poi_flicker_exit_preserves_alert_cycle():
    setup = {
        'symbol': 'EURJPY',
        'h4_choch_alert_sent': True,
        'h4_alert_cycle_complete': True,
        'poi_cycle_anchor': '2026-07-01T08:00:00+00:00',
        'poi_first_touch_time': '2026-07-01T08:00:00+00:00',
        'radar_panda_active': True,
    }
    mtr._track_mitigation_touch(
        setup,
        {'in_poi': False, 'validated': False},
    )
    assert setup.get('poi_cycle_anchor') == '2026-07-01T08:00:00+00:00'
    assert setup.get('h4_choch_alert_sent') is True
    assert setup.get('h4_alert_cycle_complete') is True
    assert setup.get('poi_touch_latched') is True
    assert setup.get('radar_panda_active') is True


def test_poi_reentry_same_cycle_does_not_reset_alert_flags():
    setup = {
        'symbol': 'EURJPY',
        '_poi_occupied': False,
        'h4_choch_alert_sent': True,
        'h4_alert_cycle_complete': True,
        'poi_cycle_anchor': '2026-07-01T08:00:00+00:00',
        'poi_first_touch_time': '2026-07-01T08:00:00+00:00',
        'poi_touch_latched': True,
        'radar_panda_active': True,
    }
    anchor = '2026-07-01T08:00:00+00:00'
    mtr._track_mitigation_touch(
        setup,
        {'in_poi': True, 'validated': True},
        d1_touch_time=anchor,
    )
    assert setup.get('h4_choch_alert_sent') is True
    assert setup.get('h4_alert_cycle_complete') is True
    assert setup.get('poi_cycle_anchor') == anchor


def test_maybe_send_choch_alerts_skips_duplicate_break_key(tmp_path, monkeypatch):
    dedup_file = tmp_path / "telegram_4h_structural_alerts.json"
    lock_file = tmp_path / "telegram_4h_structural_alerts.lock"
    monkeypatch.setattr(dedup, "_H4_DEDUP_PATH", dedup_file)
    monkeypatch.setattr(dedup, "_H4_LOCK_PATH", lock_file)

    radar = _make_radar()
    setup = {
        'symbol': 'EURJPY',
        'direction': 'sell',
        'radar_panda_active': True,
        'poi_first_touch_time': '2026-07-01T08:00:00+00:00',
        'h4_choch_alert_sent': False,
    }
    tf_4h = SimpleNamespace(
        signal_type='CHoCH',
        choch_detected=True,
        choch_direction='bearish',
        choch_time='2026-07-01T12:00:00+00:00',
        choch_bars_ago=2,
        choch_price=165.0,
        bos_detected=False,
        bos_direction=None,
        bos_bars_ago=9999,
        retrace_pct=0.7,
    )
    result = SimpleNamespace(symbol='EURJPY', tf_4h=tf_4h)

    with patch.object(mtr, '_v47_break_post_poi_touch', return_value=True):
        with patch.object(radar, '_flush_choch_alerts_to_json'):
            with patch('telegram_notifier.TelegramNotifier') as mock_tn:
                mock_tn.return_value.send_4h_structural_alert.return_value = True
                with patch.object(radar, 'get_historical_data', return_value=None):
                    radar._maybe_send_choch_alerts(setup, result, 'bearish')
                    assert mock_tn.return_value.send_4h_structural_alert.call_count == 1

                    setup['h4_choch_alert_sent'] = False
                    radar._maybe_send_choch_alerts(setup, result, 'bearish')
                    assert mock_tn.return_value.send_4h_structural_alert.call_count == 1

    assert setup.get('h4_alert_cycle_complete') is True
    assert setup.get('h4_alert_break_key') == 'CHOCH|2026-07-01T12:00:00+00:00|165.0'
