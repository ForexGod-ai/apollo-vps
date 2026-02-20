"""
Live Telegram Test - Daily Summary TypeError Fix
Sends actual daily summary to verify None handling
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from telegram_notifier import TelegramNotifier

def send_live_daily_summary_test():
    notifier = TelegramNotifier()
    
    # Realistic test data with some None values
    test_setups = [
        {
            'symbol': 'GBPJPY',
            'direction': 'buy',
            'entry_price': 208.674,
            'risk_reward': 2.5,
            'status': 'MONITORING'
        },
        {
            'symbol': 'EURUSD',
            'direction': 'sell',
            'entry_price': 1.18365,
            'risk_reward': 3.0,
            'status': 'MONITORING'
        },
        {
            'symbol': 'BTCUSD',
            'direction': 'buy',
            'entry_price': 67000.00,
            'risk_reward': 4.0,
            'profit': 250.00,
            'status': 'EXECUTED'
        }
    ]
    
    success = notifier.send_daily_summary(
        scanned_pairs=15,
        setups_found=3,
        active_setups=test_setups
    )
    
    if success:
        print("✅ Daily Summary TEST sent to Telegram!")
        print("📱 Check your phone - you should see:")
        print("   • Clean HTML formatting (no markdown)")
        print("   • Separator: ──────────────────  (18 chars)")
        print("   • MONITORING SETUPS section")
        print("   • ACTIVE TRADES section")
        print("   • No TypeError crash on None values")
        print("   • Professional signature at bottom")
    else:
        print("❌ Failed to send test message")

if __name__ == "__main__":
    send_live_daily_summary_test()
