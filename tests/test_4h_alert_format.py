"""V62 — 4H structural alert caption (CHoCH/BOS + chart caption)."""
from __future__ import annotations

from types import SimpleNamespace

from telegram_notifier import format_4h_structural_alert


def _setup(**extra):
    base = {
        'symbol': 'EURJPY',
        'direction': 'sell',
        'strategy_type': 'reversal',
        'd1_signal_type': 'CHoCH',
        'w1_bias': 'NEUTRAL',
        'radar_4h_choch_price': 165.0,
        'radar_4h_choch_bars_ago': 5,
    }
    base.update(extra)
    return base


def _tf(**extra):
    defaults = dict(
        choch_detected=True,
        choch_direction='bearish',
        choch_price=165.0,
        choch_bars_ago=5,
        retrace_pct=0.42,
        signal_type='CHoCH',
    )
    defaults.update(extra)
    return SimpleNamespace(**defaults)


def test_choch_caption_hybrid_ro():
    cap = format_4h_structural_alert(_setup(), tf_data=_tf(), signal_type='CHoCH', live_price=165.234)
    assert 'EURJPY' in cap
    assert '🔴 SHORT' in cap
    assert 'CHoCH 4H confirmat' in cap
    assert 'REV (CHoCH)' in cap
    assert 'Preț cTrader' in cap
    assert '165.234' in cap
    assert '5 bare post-POI' in cap
    assert 'Strategy:' not in cap
    assert 'POI Daily atins' not in cap


def test_no_duplicate_poi_break():
    cap = format_4h_structural_alert(_setup(), tf_data=_tf(), live_price=165.0)
    assert cap.count('post-POI') == 1
    assert cap.count('-5b') == 0


def test_retrace_pct_shown():
    cap = format_4h_structural_alert(_setup(), tf_data=_tf(retrace_pct=0.42), live_price=165.0)
    assert 'Retrace impuls: 42%' in cap
    assert '60–80%' in cap


def test_bos_header_and_chip():
    cap = format_4h_structural_alert(
        _setup(strategy_type='continuation', d1_signal_type='BOS'),
        tf_data=_tf(signal_type='BOS', bos_bars_ago=3),
        signal_type='BOS',
        live_price=1.0845,
    )
    assert 'BOS 4H confirmat' in cap
    assert 'CONT (BOS)' in cap
    assert 'INVERSARE STRUCTURĂ' not in cap


def test_disclaimer_single_line():
    cap = format_4h_structural_alert(_setup(), tf_data=_tf(), live_price=165.0)
    assert 'fără nivele fantomă D1' in cap
    assert 'valorile din scan D1' not in cap
    assert cap.count('EXECUTE NOW') >= 1


def test_w1_counter_in_block1_only():
    cap = format_4h_structural_alert(
        _setup(w1_bias='BULLISH'),
        tf_data=_tf(),
        live_price=165.0,
    )
    assert cap.count('nealiniat') == 1
    assert 'COUNTER' not in cap


def test_live_price_omitted_when_none():
    cap = format_4h_structural_alert(_setup(), tf_data=_tf(), live_price=None)
    assert 'Preț cTrader' not in cap
    assert 'Break 4H' in cap
