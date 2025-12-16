"""
ForexGod AI - LIVE Performance Report
Based on LIVE cTrader data from /history endpoint
"""

from datetime import datetime
from telegram_notifier import TelegramNotifier
from loguru import logger
import requests

def generate_live_report():
    """Generate report based on real cTrader data from /history endpoint"""
    
    # Get LIVE data from MarketDataProvider /history endpoint
    try:
        response = requests.get('http://localhost:8767/history', timeout=10)
        data = response.json()
        
        account = data['account']
        balance = account['balance']
        equity = account['equity']
        floating_profit = account['open_pl']
        open_positions_data = data['open_positions']
        
        # Calculate from initial balance
        initial_balance = 1000.00
        total_profit = balance - initial_balance
        roi = (total_profit / initial_balance * 100)
        
    except Exception as e:
        logger.error(f"❌ Error fetching live data: {e}")
        return
    
    report = f"""
🤖 **FOREXGOD AI - LIVE PERFORMANCE REPORT**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 **Date:** {datetime.now().strftime('%B %d, %Y %H:%M')}
🏦 **Account:** IC Markets Demo #{account['number']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 **ACCOUNT PERFORMANCE**

Initial Balance: ${initial_balance:,.2f}
**Current Balance: ${balance:,.2f}**
**Equity: ${equity:,.2f}**

**Total Profit: ${total_profit:,.2f}**
**ROI: {roi:.1f}%** 🔥

Floating P/L: ${floating_profit:,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟢 **OPEN POSITIONS: {len(open_positions_data)}**

"""
    
    if len(open_positions_data) == 0:
        report += "No open positions currently.\n\n"
    else:
        for i, pos in enumerate(open_positions_data, 1):
            profit_emoji = "💚" if pos.get('profit', 0) > 0 else "❤️"
            report += f"""
{i}. **{pos['symbol']}** {pos['direction']}
   Entry: {pos['entry_price']:.5f} | Lots: {pos['lot_size']:.2f}
   TP: {pos.get('take_profit', 'N/A')} | SL: {pos.get('stop_loss', 'N/A')}
   {profit_emoji} Profit: ${pos.get('profit', 0):.2f}
"""
    
    report += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **STATISTICS**

Total Open Trades: {len(open_positions_data)}
Total Floating P/L: ${floating_profit:.2f}
Account Growth: {roi:.1f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 **FOREXGOD AI STATUS**

✅ Auto-execution: ACTIVE
✅ Live data: IC Markets cTrader
✅ Risk management: 2% per trade
✅ 24/7 monitoring: RUNNING

🔥 **+{roi:.1f}% in active trading!** 🔥

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Next scan: Morning 09:00 EET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Next scan: Morning 09:00 EET
"""
    
    return report, {
        'balance': balance,
        'equity': equity,
        'profit': total_profit,
        'roi': roi,
        'open_positions': len(open_positions_data),
        'floating_pl': floating_profit
    }


if __name__ == "__main__":
    logger.info("📊 Generating LIVE ForexGod AI Report...\n")
    
    report, stats = generate_live_report()
    
    if report is None:
        logger.error("❌ Failed to generate report!")
        exit(1)
    
    # Print to console
    print(report)
    
    # Send to Telegram
    telegram = TelegramNotifier()
    telegram.send_message(report)
    
    logger.success("✅ LIVE Report sent to Telegram!")
    logger.success(f"💰 Balance: ${stats['balance']:,.2f}")
    logger.success(f"📈 Profit: ${stats['profit']:,.2f} ({stats['roi']:.1f}% ROI)")
    logger.success(f"🟢 Open Positions: {stats['open_positions']}")
    logger.success(f"💵 Floating P/L: ${stats['floating_pl']:.2f}")
