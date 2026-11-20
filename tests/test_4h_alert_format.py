"""V94 — 4H structural alert caption (CHoCH/BOS + chart caption)."""
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
        'radar_4h_choch_bars_ago': 2,
        'poi_top': 166.0,
        'poi_bottom': 164.0,
        'take_profit': 162.0,
        'h4_sl_price': 166.5,
    }
    base.update(extra)
    return base


def _tf(**extra):
    defaults = dict(
        choch_detected=True,
        choch_direction='bearish',
        choch_price=165.0,
        choch_bars_ago=2,
        retrace_pct=0.42,
        signal_type='CHoCH',
        equilibrium=164.5,
    )
    defaults.update(extra)
    return SimpleNamespace(**defaults)


def test_choch_caption_v94_layout():
    cap = format_4h_structural_alert(_setup(), tf_data=_tf(), signal_type='CHoCH', live_price=165.234)
    assert 'EURJPY' in cap
    assert '🔴' in cap
    assert 'CHoCH 4H' in cap
    assert 'POI D1' in cap
    assert 'Semnal 4H' in cap
    assert '2 bare' in cap
    assert 'Zonă intrare (Retrace 60–80%)' in cap
    assert 'EXECUTE NOW' in cap


def test_bos_signal_type_in_header():
    cap = format_4h_structural_alert(
        _setup(strategy_type='continuation', d1_signal_type='BOS'),
        tf_data=_tf(signal_type='BOS', bos_bars_ago=1),
        signal_type='BOS',
        live_price=1.0845,
    )
    assert 'BOS 4H' in cap
    assert 'Continuare' in cap


def test_w1_nealiniat_suffix():
    cap = format_4h_structural_alert(
        _setup(w1_bias='BULLISH', direction='sell'),
        tf_data=_tf(),
        live_price=165.0,
    )
    assert 'W1' in cap
    assert '⚠️' in cap