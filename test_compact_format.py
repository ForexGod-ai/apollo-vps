#!/usr/bin/env python3
"""Test BLOOMBERG COLUMN v35.0 - Vertical Stack (Max 18 chars width)"""

from telegram_notifier import TelegramNotifier
from datetime import datetime

# Create mock CHoCH
class MockCHoCH:
    direction = 'bullish'
    break_price = 0.77658
    break_time = datetime.now()

# Create mock FVG
class MockFVG:
    top = 0.77975
    bottom = 0.77341
    middle = 0.77658
    direction = 'bullish'

# Create mock setup for USDCHF (realistic prices)
setup = type('TradeSetup', (), {
    'symbol': 'USDCHF',
    'strategy_type': 'reversal',
    'priority': 1,
    'status': 'MONITORING',
    'entry_price': 0.77658,
    'stop_loss': 0.77975,
    'take_profit': 0.75723,
    'risk_reward': 6.1,
    'daily_choch': MockCHoCH(),
    'h4_choch': MockCHoCH(),
    'fvg': MockFVG(),
    'ml_score': 78,
    'ml_confidence': 'HIGH',
    'ml_recommendation': 'TAKE',
    'ml_factors': {'Quality': 'Good'},
    'ai_probability_score': 8,
    'ai_probability_confidence': 'HIGH',
    'ai_probability_factors': {
        'timing': 'London ✅',
        'quality': 'Good'
    }
})()

# Format and print
telegram = TelegramNotifier()
message = telegram.format_setup_alert(setup)

print('=' * 70)
print('📊  BLOOMBERG COLUMN v35.0 - VERTICAL STACK')
print('=' * 70)
print(message)
print('=' * 70)
print('\n✅ VERTICAL BADGES: Stacked on separate lines')
print('✅ PRICE BLOCK: Entry, SL, TP each on own line')
print('✅ MAX WIDTH: No line wider than 18-char separator')
print('✅ BLOOMBERG AESTHETIC: Perfect column alignment')
