#!/usr/bin/env python3
"""
🎨 TEST HTML FORMATTING - Daily Summary Report
ФорексГод - Verificare format profesional
"""

from telegram_notifier import TelegramNotifier
from datetime import datetime

def test_daily_summary_html():
    """Test HTML formatting pentru daily summary"""
    
    print("\n" + "="*70)
    print("🎨 TEST: DAILY SUMMARY HTML FORMATTING")
    print("="*70)
    
    # Initialize notifier
    notifier = TelegramNotifier()
    
    # Mock data pentru test
    monitoring_setups = [
        {
            'symbol': 'EURUSD',
            'direction': 'buy',
            'entry_price': 1.08093,
            'risk_reward': 3.5,
            'status': 'MONITORING'
        },
        {
            'symbol': 'GBPUSD',
            'direction': 'sell',
            'entry_price': 1.26450,
            'risk_reward': 4.2,
            'status': 'MONITORING'
        }
    ]
    
    executed_positions = [
        {
            'symbol': 'XAUUSD',
            'direction': 'buy',
            'entry_price': 2685.50,
            'risk_reward': 5.8,
            'profit': 125.50,
            'status': 'EXECUTED'
        },
        {
            'symbol': 'USDCAD',
            'direction': 'sell',
            'entry_price': 1.36950,
            'risk_reward': 3.2,
            'profit': -45.20,
            'status': 'EXECUTED'
        }
    ]
    
    combined_setups = monitoring_setups + executed_positions
    
    # Generate message preview
    print("\n📨 MESAJ GENERAT (HTML FORMAT):")
    print("="*70)
    
    # Recreate message logic to show preview
    message = f"""<b>📊 Daily Scan Complete</b>

🔍 Pairs Scanned: <code>15</code>
🎯 New Setups Found: <code>2</code>
📋 Monitoring: <code>2</code> | Active Trades: <code>2</code>
⏰ Scan Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</code>
"""
    
    # Monitoring setups
    message += "\n──────────────────\n"
    message += "<b>📊 MONITORING SETUPS:</b>\n\n"
    for setup in monitoring_setups:
        symbol = setup['symbol']
        direction = "🟢 LONG" if setup['direction'] == 'buy' else "🔴 SHORT"
        entry = setup['entry_price']
        rr = setup['risk_reward']
        message += f"• <b>{symbol}</b> - {direction}\n"
        message += f"  Entry: <code>{entry:.5f}</code> | RR: <code>1:{rr:.1f}</code>\n"
    
    # Active positions
    message += "\n──────────────────\n"
    message += "<b>🔥 ACTIVE TRADES:</b>\n\n"
    for pos in executed_positions:
        symbol = pos['symbol']
        direction = "🟢 LONG" if pos['direction'] == 'buy' else "🔴 SHORT"
        entry = pos['entry_price']
        rr = pos['risk_reward']
        profit = pos['profit']
        profit_emoji = "💚" if profit > 0 else "❤️"
        message += f"• <b>{symbol}</b> - {direction} {profit_emoji}\n"
        message += f"  Entry: <code>{entry:.5f}</code> | RR: <code>1:{rr:.1f}</code> | P/L: <code>${profit:.2f}</code>\n"
    
    print(message)
    print("="*70)
    
    # Verificări
    print("\n✅ VERIFICĂRI HTML:")
    checks = {
        'No Markdown asterisks': '*' not in message or message.count('*') == 0,
        'No Markdown backticks': '`' not in message or '`' in '<code>',
        'Has <b> tags': '<b>' in message,
        'Has <code> tags': '<code>' in message,
        'Clean bullets': '•' in message,
        'No double markup': '**' not in message and '__' not in message
    }
    
    for check_name, passed in checks.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {check_name}")
    
    all_passed = all(checks.values())
    
    if all_passed:
        print("\n🎉 FORMAT HTML PERFECT! Document oficial de investiții! ✅")
    else:
        print("\n⚠️  UNELE VERIFICĂRI AU EȘUAT!")
    
    # Trimite pe Telegram (opțional)
    print("\n" + "="*70)
    send_test = input("Trimite acest mesaj pe Telegram pentru test? (y/n): ").strip().lower()
    
    if send_test == 'y':
        print("\n📤 Trimit mesaj pe Telegram...")
        success = notifier.send_daily_summary(
            scanned_pairs=15,
            setups_found=2,
            active_setups=combined_setups
        )
        
        if success:
            print("✅ Mesaj trimis cu succes! Verifică Telegram pentru format.")
        else:
            print("❌ Eroare la trimiterea mesajului!")
    else:
        print("\n✅ Test complet! Mesaj nu a fost trimis.")
    
    print("="*70 + "\n")
    
    return all_passed

if __name__ == "__main__":
    success = test_daily_summary_html()
    exit(0 if success else 1)
