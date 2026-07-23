"""V60 MARKET_REPORT — grouped vertical layout helpers."""
from unittest.mock import patch

from telegram_notifier import (
    PHASE_D1_PULLBACK,
    PHASE_H4_CHOCH,
    PHASE_READY,
    PHASE_WD_SYNC,
    TelegramNotifier,
    _classify_setup_phase,
    _format_compact_line,
    _group_setups_by_phase,
    _render_grouped_setups,
)


def _sym(symbol, *, direction='buy', strategy='REVERSAL', status='WAITING_D1_PULLBACK', **extra):
    return {'symbol': symbol, 'direction': direction, 'strategy': strategy, 'status': status, **extra}


def test_classify_setup_phase_wd_sync():
    assert _classify_setup_phase(_sym('EURUSD', status='WAITING_W_D_SYNC', w_d_aligned=False)) == PHASE_WD_SYNC


def test_classify_setup_phase_d1_pullback():
    assert _classify_setup_phase(_sym('GBPCAD', status='WAITING_D1_PULLBACK')) == PHASE_D1_PULLBACK


def test_classify_setup_phase_ready_when_h4_locked():
    assert _classify_setup_phase(_sym('XAUUSD', status='MONITORING', h4_structure_locked=True)) == PHASE_READY


def test_format_compact_line_buy_reversal():
    line = _format_compact_line(_sym('GBPCAD', direction='buy', strategy='REVERSAL'))
    assert line == "🟢 GBPCAD · REV\n"


def test_format_compact_line_sell_continuation():
    line = _format_compact_line(_sym('AUDUSD', direction='sell', strategy='CONTINUATION'))
    assert line == "🔴 AUDUSD · CONT\n"


def test_render_grouped_setups_vertical_by_phase():
    setups = [
        _sym('EURUSD', status='WAITING_W_D_SYNC', w_d_aligned=False, strategy='CONTINUATION'),
        _sym('GBPCAD', status='WAITING_D1_PULLBACK'),
        _sym('USDJPY', status='WAITING_D1_PULLBACK', direction='buy'),
    ]
    rendered = _render_grouped_setups(setups)
    assert "⏳ W+D nealiniat · 1\n" in rendered
    assert "⏳ Pullback D1 · 2\n" in rendered
    assert "🟢 EURUSD · CONT\n" in rendered
    assert "🟢 GBPCAD · REV\n" in rendered
    assert "Daily Bias" not in rendered
    assert rendered.index("⏳ W+D nealiniat") < rendered.index("⏳ Pullback D1")


def test_group_setups_preserves_phase_order():
    grouped = _group_setups_by_phase([
        _sym('A', status='WAITING_4H_CHOCH'),
        _sym('B', status='WAITING_W_D_SYNC', w_d_aligned=False),
    ])
    assert grouped[PHASE_WD_SYNC][0]['symbol'] == 'B'
    assert grouped[PHASE_H4_CHOCH][0]['symbol'] == 'A'


@patch.object(TelegramNotifier, 'send_message', return_value=True)
def test_send_scan_report_compact_header_no_duplicate_json(mock_send):
    notifier = TelegramNotifier()
    setups = [
        {**_sym('GBPCAD'), 'bias_fallback': False},
        {**_sym('USDJPY', direction='sell', strategy='CONTINUATION'), 'bias_fallback': True},
    ]
    notifier.send_scan_report(
        total_pairs=16,
        new_setups_found=2,
        truly_new=1,
        re_detected=1,
        monitoring_count=16,
        watching_count=16,
        open_positions=0,
        setup_symbols=setups,
    )
    body = mock_send.call_args[0][0]
    assert "CONTEXT PORTOFOLIU" not in body
    assert "Scan complet" in body
    assert "Total JSON" not in body
    assert "Setup-uri cu POI" in body
    assert "Bias D1 fără FVG" in body
    assert "AUTHORED BY" not in body
    assert "🔱 ФорексГод · Глитч Ин Матрикс" in body
    assert mock_send.call_args[1]['add_signature'] is False


@patch.object(TelegramNotifier, 'send_message', return_value=True)
def test_send_scan_report_shows_json_when_counts_differ(mock_send):
    notifier = TelegramNotifier()
    notifier.send_scan_report(
        total_pairs=16,
        new_setups_found=0,
        truly_new=0,
        re_detected=0,
        monitoring_count=11,
        watching_count=16,
        open_positions=0,
        setup_symbols=[],
    )
    body = mock_send.call_args[0][0]
    assert "Total JSON: 11" in body
