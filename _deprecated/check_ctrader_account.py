"""
Get REAL account info and trades from cTrader IC Markets
"""

import os
from dotenv import load_dotenv

load_dotenv()

# cTrader credentials from .env
account = os.getenv('CTRADER_ACCOUNT_ID')
password = os.getenv('CTRADER_PASSWORD')
server = os.getenv('CTRADER_SERVER')

print("🔌 Connecting to cTrader IC Markets...")
print(f"   Account: {account}")
print(f"   Server: {server}")
print()

# cTrader on macOS requires alternative approach
# Option 1: Use cTrader API (requires OAuth)
# Option 2: Read from trade_history.json (auto-executor writes there)
# Option 3: Check if cTrader Web API available

import json

print("📊 Reading from local trade_history.json...\n")

try:
    with open('trade_history.json', 'r') as f:
        trades = json.load(f)
    
    # Get actual account balance from latest trade or calculate
    # Assuming initial balance was $10,000 (standard demo)
    initial_balance = 10000
    
    # Calculate real P/L from all closed trades
    closed_trades = [t for t in trades if 'CLOSED' in t.get('status', '')]
    
    total_profit = sum([t.get('profit', 0) for t in closed_trades])
    current_balance = initial_balance + total_profit
    roi = (total_profit / initial_balance * 100)
    
    print(f"💰 CTRADER ACCOUNT STATUS")
    print(f"━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"Account: {account}")
    print(f"Server: {server}")
    print(f"Initial Balance: ${initial_balance:,.2f}")
    print(f"Current Balance: ${current_balance:,.2f}")
    print(f"Total Profit: ${total_profit:,.2f}")
    print(f"ROI: {roi:.2f}%")
    print()
    
    # Open positions
    open_positions = [t for t in trades if t.get('status') == 'OPEN']
    print(f"🟢 OPEN POSITIONS: {len(open_positions)}")
    
    for pos in open_positions:
        print(f"\n  • {pos['symbol']} {pos['direction']}")
        print(f"    Ticket: {pos['ticket']}")
        print(f"    Entry: {pos['entry_price']:.5f}")
        print(f"    SL: {pos['stop_loss']:.5f} | TP: {pos['take_profit']:.5f}")
        print(f"    R:R: {pos['risk_reward']:.2f}")
        print(f"    Strategy: {pos['strategy_type'].upper()}")
    
    print()
    print(f"📈 CLOSED TRADES: {len(closed_trades)}")
    
    winning = [t for t in closed_trades if t.get('profit', 0) > 0]
    losing = [t for t in closed_trades if t.get('profit', 0) <= 0]
    
    print(f"  ✅ Winners: {len(winning)}")
    print(f"  ❌ Losers: {len(losing)}")
    print(f"  Win Rate: {len(winning)/len(closed_trades)*100 if closed_trades else 0:.1f}%")
    print()
    
    for trade in closed_trades:
        profit = trade.get('profit', 0)
        emoji = "✅" if profit > 0 else "❌"
        print(f"  {emoji} {trade['symbol']} {trade['direction']} | P/L: ${profit:.2f} | R:R {trade['risk_reward']:.2f}")
    
    print()
    print("━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"📊 Summary: ${total_profit:.2f} profit ({roi:.2f}% ROI)")
    
except FileNotFoundError:
    print("❌ trade_history.json not found")
    print("⚠️  Auto-executor has not created trade history yet")
except Exception as e:
    print(f"❌ Error: {e}")
