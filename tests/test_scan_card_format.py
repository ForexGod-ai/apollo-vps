"""V61 scan card — layout hibrid RO, preț live, radar snapshot."""
from __future__ import annotations

from types import SimpleNamespace

from pip_utils import format_poi_price_relation
from telegram_notifier import (
    TelegramNotifier,
    _format_radar_exec_lines,
    _is_w1_counter_trend,
    _scan_card_wait_hint,
)


def _eurjpy_setup(**extra):
    base = SimpleNamespace(
        symbol='EURJPY',
        status='MONITORING',
        strategy_type='continuation',
        daily_choch=SimpleNamespace(direction='bullish'),
        fvg=SimpleNamespace(bottom=184.496, top=185.664),
        ml_score=37,
        ai_probability_score=0.37,
        ml_recommendation='SKIP',
        w1_bias='NEUTRAL',
        confidence='NORMAL',
        w_d_aligned=True,
        swap_long=0.48,
        swap_short=None,
        swap_triple_day='Wed',
        live_price=185.664,
        liquidity_sweep=None,
    )
    for k, v in extra.items():
        setattr(base, k, v)
    return base


def test_ai_line_no_double_disclaimer():
    notifier = TelegramNotifier()
    card = notifier.format_setup_alert(_eurjpy_setup(), radar_snapshot={})
    assert 'nu blochează execuția' not in card
    assert 'informativ' in card
    assert 'SKIP' in card


def test_live_price_and_poi_relation():
    notifier = TelegramNotifier()
    card = notifier.format_setup_alert(_eurjpy_setup(), radar_snapshot={})
    assert 'Preț cTrader' in card
    assert '185.664' in card
    assert 'POI Daily' in card
    rel = format_poi_price_relation(185.664, 184.496, 185.664)
    assert rel == 'în zonă'
    assert rel in card


def test_w1_counter_only_once():
    setup = _eurjpy_setup(w1_bias='BEARISH', confidence='LOW_W1_COUNTER_TREND')
    notifier = TelegramNotifier()
    card = notifier.format_setup_alert(setup, radar_snapshot={})
    assert card.count('W1 nealiniat') == 1
    assert 'COUNTER-TREND W1' not in card


def test_block3_compact_single_exec_line():
    notifier = TelegramNotifier()
    card = notifier.format_setup_alert(_eurjpy_setup(), radar_snapshot={})
    assert 'Radar monitorizează 4H live' not in card
    assert 'Entry/SL/TP' in card
    assert 'EXECUTE NOW' in card
    assert card.count('radar 4H live') == 1


def test_radar_snapshot_empty_skips_json_confirm():
    setup = _eurjpy_setup()
    setup.h4_choch = SimpleNamespace(break_price=185.0, direction='bullish')
    line = _format_radar_exec_lines(
        setup, 'EURJPY', 'bullish', _scan_card_wait_hint(setup), radar_snapshot={},
    )
    assert 'confirmat' not in line.lower()
    assert 'Așteptăm' in line


def test_hybrid_ro_labels():
    notifier = TelegramNotifier()
    card = notifier.format_setup_alert(_eurjpy_setup(), radar_snapshot={})
    assert 'Scan OK' in card
    assert 'CONT (BOS)' in card
    assert 'D1:' in card
    assert 'pips/zi' in card


def test_pair_stats_labeled_istoric_bot(monkeypatch):
    notifier = TelegramNotifier()
    monkeypatch.setattr(
        notifier,
        '_load_pair_statistics',
        lambda _sym: {'win_rate': 50, 'total_trades': 9},
    )
    card = notifier.format_setup_alert(_eurjpy_setup(), radar_snapshot={})
    assert 'Istoric bot' in card


def test_is_w1_counter_trend_helper():
    setup = _eurjpy_setup(w1_bias='BEARISH')
    assert _is_w1_counter_trend(setup, 'bullish') is True
    assert _is_w1_counter_trend(setup, 'bearish') is False
