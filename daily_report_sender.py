#!/usr/bin/env python3
"""
Daily Performance Report Sender
Sends comprehensive daily report to Telegram at 00:00 EET
"""
from telegram_notifier import send_daily_performance_report
import sys

if __name__ == "__main__":
    print("📊 Generating Daily Performance Report...")
    try:
        success = send_daily_performance_report(include_news=True)
        if success:
            print("✅ Daily report sent successfully!")
            sys.exit(0)
        else:
            print("❌ Failed to send daily report")
            sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
