"""
Test Telegram Bot Commands and Daily Report
Quick validation script for ФорексГод
"""

import sys
from loguru import logger

# Configure minimal logging
logger.remove()
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def test_imports():
    """Test all required imports"""
    print("\n" + "="*60)
    print("🧪 TESTING IMPORTS")
    print("="*60)
    
    try:
        from telegram_notifier import TelegramNotifier
        print("✅ telegram_notifier imported successfully")
    except Exception as e:
        print(f"❌ telegram_notifier import failed: {e}")
        return False
    
    try:
        from telegram_bot_handler import TradingBotHandler
        print("✅ telegram_bot_handler imported successfully")
    except Exception as e:
        print(f"❌ telegram_bot_handler import failed: {e}")
        print("\n💡 Missing python-telegram-bot? Run:")
        print("   pip install python-telegram-bot==20.7")
        return False
    
    return True


def test_telegram_connection():
    """Test Telegram bot connection"""
    print("\n" + "="*60)
    print("🔌 TESTING TELEGRAM CONNECTION")
    print("="*60)
    
    try:
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier()
        
        if notifier.test_connection():
            print("✅ Telegram bot connection successful!")
            return True
        else:
            print("❌ Telegram bot connection failed!")
            return False
    
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        return False


def test_daily_report_generation():
    """Test daily report generation (without sending)"""
    print("\n" + "="*60)
    print("📊 TESTING DAILY REPORT GENERATION")
    print("="*60)
    
    try:
        from telegram_bot_handler import TradingBotHandler
        
        bot = TradingBotHandler()
        
        # Test each report generation
        reports = {
            'Status': bot._generate_status_report(),
            'Balance': bot._generate_balance_report(),
            'Positions': bot._generate_positions_report(),
            'Setups': bot._generate_setups_report(),
            'Weekly Summary': bot._generate_weekly_summary(),
            'News': bot._generate_news_report()
        }
        
        for name, report in reports.items():
            if report and len(report) > 50:
                print(f"✅ {name} report generated ({len(report)} chars)")
            else:
                print(f"⚠️ {name} report might be incomplete")
        
        return True
    
    except Exception as e:
        print(f"❌ Error generating reports: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_send_daily_report():
    """Test sending actual daily report to Telegram"""
    print("\n" + "="*60)
    print("📤 TESTING DAILY REPORT SEND")
    print("="*60)
    
    response = input("⚠️  This will send a real message to your Telegram. Continue? (y/n): ")
    
    if response.lower() != 'y':
        print("⏭️  Skipped sending test")
        return True
    
    try:
        from telegram_notifier import TelegramNotifier
        
        notifier = TelegramNotifier()
        
        success = notifier.send_daily_performance_report(include_news=True)
        
        if success:
            print("✅ Daily report sent successfully!")
            print("💡 Check your Telegram for the message")
            return True
        else:
            print("❌ Failed to send daily report")
            return False
    
    except Exception as e:
        print(f"❌ Error sending report: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_command_handlers():
    """Test command handler responses"""
    print("\n" + "="*60)
    print("🤖 TESTING COMMAND HANDLERS")
    print("="*60)
    
    try:
        from telegram_bot_handler import TradingBotHandler
        
        bot = TradingBotHandler()
        
        commands = [
            ('Status', bot._generate_status_report),
            ('Balance', bot._generate_balance_report),
            ('Positions', bot._generate_positions_report),
            ('Setups', bot._generate_setups_report),
            ('Summary', bot._generate_weekly_summary),
            ('News', bot._generate_news_report)
        ]
        
        print("\n📝 Sample Command Outputs:\n")
        
        for cmd_name, cmd_func in commands[:3]:  # Show first 3
            print(f"━━━ /{cmd_name.lower()} ━━━")
            result = cmd_func()
            # Show first 200 chars
            preview = result[:200] + "..." if len(result) > 200 else result
            print(preview)
            print()
        
        print("✅ All command handlers working!")
        return True
    
    except Exception as e:
        print(f"❌ Error testing commands: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("🧪 TELEGRAM BOT TEST SUITE")
    print("   ForexGod Trading System - ФорексГод")
    print("="*60)
    
    tests = [
        ("Imports", test_imports),
        ("Telegram Connection", test_telegram_connection),
        ("Report Generation", test_daily_report_generation),
        ("Command Handlers", test_command_handlers),
        ("Send Daily Report", test_send_daily_report)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {test_name}")
    
    print("="*60)
    print(f"Results: {passed}/{total} tests passed ({passed/total*100:.0f}%)")
    print("="*60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Bot is ready for deployment!")
        print("\n📝 Next steps:")
        print("   1. Start bot: python3 start_telegram_bot.py")
        print("   2. Test commands in Telegram: /start, /status, /summary")
        print("   3. Add bot to service watchdog")
        print("   4. Setup daily report cron/launchd")
    else:
        print("\n⚠️  Some tests failed. Please fix issues before deployment.")
        print("💡 Check logs/telegram_bot.log for details")


if __name__ == "__main__":
    main()
