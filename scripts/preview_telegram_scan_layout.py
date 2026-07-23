#!/usr/bin/env python3
"""
V43.6 / V60 — Preview scan card + MARKET_REPORT layout in console (no Telegram send).
Usage:
  python3 scripts/preview_telegram_scan_layout.py
  python3 scripts/preview_telegram_scan_layout.py --market-report
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'preview-token')
os.environ.setdefault('TELEGRAM_CHAT_ID', 'preview-chat')

from pip_utils import format_telegram_price, format_swap_line, format_telegram_fvg_range
from telegram_notifier import TelegramNotifier, UNIVERSAL_SEPARATOR

MOBILE_WIDTH = 40


def _strip_html(text: str) -> str:
    return re.sub(r'</?[^>]+>', '', text)


def _mock_setup(
    symbol: str,
    *,
    direction: str = 'bearish',
    fvg_bottom: float,
    fvg_top: float,
    swap_val: float = 0.0,
    strategy_type: str = 'continuation',
    w1_bias: str = 'BEARISH',
    ml_score: int = 37,
    ai_prob: float = 0.37,
    ml_rec: str = 'SKIP',
):
    return SimpleNamespace(
        symbol=symbol,
        daily_choch=SimpleNamespace(direction=direction),
        fvg=SimpleNamespace(bottom=fvg_bottom, top=fvg_top),
        h4_choch=None,
        h1_choch=None,
        status='MONITORING',
        strategy_type=strategy_type,
        confidence='NORMAL',
        w1_bias=w1_bias,
        swap_long=swap_val if direction == 'bullish' else None,
        swap_short=swap_val if direction == 'bearish' else None,
        swap_triple_day='Fri',
        ml_score=ml_score,
        ai_probability_score=ai_prob,
        ml_recommendation=ml_rec,
        liquidity_sweep=None,
        choch_1h_detected=False,
    )


FIXTURES = [
    ('BTCUSD — crypto INT + swap NEUTRAL', _mock_setup(
        'BTCUSD', fvg_bottom=72377.35, fvg_top=78018.30, swap_val=0.0,
    )),
    ('XAUUSD — metals 1dp', _mock_setup(
        'XAUUSD', fvg_bottom=4173.12, fvg_top=4226.61, swap_val=-1.25,
    )),
    ('EURUSD — forex 5dp', _mock_setup(
        'EURUSD', fvg_bottom=1.08432, fvg_top=1.08510, swap_val=0.45,
        direction='bullish', w1_bias='BULLISH', ml_rec='REVIEW',
    )),
    ('USDJPY — JPY 3dp', _mock_setup(
        'USDJPY', fvg_bottom=157.420, fvg_top=158.115, swap_val=0.0,
        direction='bullish', w1_bias='NEUTRAL', ml_score=0, ai_prob=0,
    )),
    ('XTIUSD — energy 2dp', _mock_setup(
        'XTIUSD', fvg_bottom=65.814, fvg_top=67.230, swap_val=0.12,
    )),
]


MARKET_REPORT_FIXTURE = [
    {'symbol': 'EURUSD', 'direction': 'buy', 'strategy': 'CONTINUATION', 'status': 'WAITING_W_D_SYNC', 'w_d_aligned': False, 'bias_fallback': False},
    {'symbol': 'NZDUSD', 'direction': 'buy', 'strategy': 'CONTINUATION', 'status': 'WAITING_W_D_SYNC', 'w_d_aligned': False, 'bias_fallback': False},
    {'symbol': 'GBPNZD', 'direction': 'buy', 'strategy': 'CONTINUATION', 'status': 'WAITING_W_D_SYNC', 'w_d_aligned': False, 'bias_fallback': False},
    {'symbol': 'GBPCAD', 'direction': 'buy', 'strategy': 'REVERSAL', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': False},
    {'symbol': 'GBPUSD', 'direction': 'buy', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': False},
    {'symbol': 'AUDUSD', 'direction': 'sell', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': False},
    {'symbol': 'AUDJPY', 'direction': 'buy', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': False},
    {'symbol': 'EURJPY', 'direction': 'buy', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': False},
    {'symbol': 'GBPJPY', 'direction': 'sell', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': False},
    {'symbol': 'XTIUSD', 'direction': 'buy', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': False},
    {'symbol': 'USDCAD', 'direction': 'sell', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': False},
    {'symbol': 'USDJPY', 'direction': 'buy', 'strategy': 'REVERSAL', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': True},
    {'symbol': 'XAUUSD', 'direction': 'sell', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': True},
    {'symbol': 'USDCHF', 'direction': 'sell', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': True},
    {'symbol': 'BTCUSD', 'direction': 'sell', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': True},
    {'symbol': 'XTIUSD', 'direction': 'sell', 'strategy': 'CONTINUATION', 'status': 'WAITING_D1_PULLBACK', 'bias_fallback': True},
]


def _print_mobile_wrap(plain: str, width: int = MOBILE_WIDTH) -> None:
    """Simulate narrow Telegram viewport — flag lines that exceed width."""
    print(f'\n── Mobile width check (~{width} chars) ──')
    long_lines = []
    for i, line in enumerate(plain.splitlines(), 1):
        n = len(line)
        marker = ' ⚠️ WRAP' if n > width else ''
        if n > width:
            long_lines.append((i, n, line))
        print(f'  L{i:02d} ({n:2d}){marker}: {line}')
    if long_lines:
        print(f'\n  {len(long_lines)} line(s) exceed {width} chars')
    else:
        print(f'\n  All lines fit within {width} chars')


def preview_scan_cards() -> None:
    print('=' * 72)
    print('V43.6 TELEGRAM PREMIUM FORMATTING — PREVIEW')
    print('=' * 72)
    print(f'Separator: {UNIVERSAL_SEPARATOR!r} ({len(UNIVERSAL_SEPARATOR)} chars)\n')

    print('── Price precision samples ──')
    samples = [
        ('BTCUSD', 72377.35),
        ('XAUUSD', 4190.44),
        ('XTIUSD', 65.814),
        ('USDJPY', 157.420),
        ('EURUSD', 1.08432),
    ]
    for sym, px in samples:
        print(f'  {sym:8} {px:>12} → {format_telegram_price(sym, px)}')

    print('\n── FVG range samples ──')
    print(f'  BTCUSD: {format_telegram_fvg_range("BTCUSD", 72377.35, 78018.30)}')
    print(f'  XAUUSD: {format_telegram_fvg_range("XAUUSD", 4173.12, 4226.61)}')

    print('\n── Swap lines ──')
    print(_strip_html(format_swap_line(0.0, triple_day='Fri')))
    print(_strip_html(format_swap_line(0.45, triple_day='Wed')))
    print(_strip_html(format_swap_line(-1.25, triple_day='Wed')))

    notifier = TelegramNotifier()

    for title, setup in FIXTURES:
        if 'USDJPY' in title:
            setup.ml_score = None
            setup.ai_probability_score = None
        raw = notifier.format_setup_alert(setup)
        plain = _strip_html(raw)
        print('\n' + '=' * 72)
        print(title)
        print('=' * 72)
        print(plain)


def preview_market_report() -> None:
    print('=' * 72)
    print('V60 MARKET_REPORT — GROUPED VERTICAL PREVIEW')
    print('=' * 72)

    notifier = TelegramNotifier()
    captured = {}

    def _capture(text, parse_mode='HTML', add_signature=True):
        captured['text'] = text
        return True

    full_setups = [s for s in MARKET_REPORT_FIXTURE if not s.get('bias_fallback')]
    bias_only = [s for s in MARKET_REPORT_FIXTURE if s.get('bias_fallback')]

    with patch.object(TelegramNotifier, 'send_message', side_effect=_capture):
        notifier.send_scan_report(
            total_pairs=16,
            new_setups_found=len(full_setups),
            truly_new=9,
            re_detected=2,
            monitoring_count=16,
            watching_count=16,
            open_positions=0,
            setup_symbols=MARKET_REPORT_FIXTURE,
        )

    plain = _strip_html(captured['text'])
    print(plain)
    _print_mobile_wrap(plain)
    print(f'\n  Lines: {len(plain.splitlines())} | Full POI: {len(full_setups)} | Bias fallback: {len(bias_only)}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Preview Telegram layouts without sending.')
    parser.add_argument(
        '--market-report',
        action='store_true',
        help='Preview V60 MARKET_REPORT grouped layout + mobile width check',
    )
    args = parser.parse_args()

    if args.market_report:
        preview_market_report()
    else:
        preview_scan_cards()

    print('\n✅ Preview complete — no Telegram messages sent.')


if __name__ == '__main__':
    main()
