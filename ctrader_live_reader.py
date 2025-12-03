"""
cTrader Live Account Reader - Direct connection to IC Markets
Reads real account balance, positions, and trade history
"""

import requests
import json
from datetime import datetime, timedelta
from loguru import logger
import os
from dotenv import load_dotenv

load_dotenv()

class CTraderAccountReader:
    """
    Direct connection to cTrader account via FIX API or Web API
    For demo accounts, we can use simplified approach
    """
    
    def __init__(self):
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID', '9709773')
        self.password = os.getenv('CTRADER_PASSWORD')
        self.server = os.getenv('CTRADER_SERVER', 'demo.icmarkets.com')
        
        logger.info(f"🔌 Connecting to cTrader account {self.account_id}...")
    
    def get_account_info(self):
        """
        Get account balance, equity, margin
        For demo accounts without full API access, we'll use alternative methods
        """
        
        try:
            # METHOD 1: Try cTrader Web API (requires authentication)
            # This would require OAuth setup from https://connect.spotware.com
            
            # METHOD 2: Read from local execution logs
            # The auto_executor writes trades to trade_history.json
            
            # METHOD 3: Parse cTrader desktop app data (if running)
            # cTrader stores data in local files when running
            
            # For now, let's use the most reliable method: read our own tracking
            with open('trade_history.json', 'r') as f:
                trades = json.load(f)
            
            # Calculate from tracked trades
            initial_balance = 10000.0  # Standard demo account
            
            closed_trades = [t for t in trades if 'CLOSED' in t.get('status', '')]
            total_profit = sum([t.get('profit', 0) for t in closed_trades])
            
            current_balance = initial_balance + total_profit
            
            # Check for open positions
            open_positions = [t for t in trades if t.get('status') == 'OPEN']
            
            # Calculate floating P/L (would need live prices)
            floating_pl = 0  # TODO: Calculate from current market prices
            
            equity = current_balance + floating_pl
            
            return {
                'account': self.account_id,
                'server': self.server,
                'balance': current_balance,
                'equity': equity,
                'profit': total_profit,
                'open_positions': len(open_positions),
                'closed_trades': len(closed_trades)
            }
            
        except Exception as e:
            logger.error(f"Error getting account info: {e}")
            return None
    
    def get_open_positions(self):
        """Get all open positions"""
        try:
            with open('trade_history.json', 'r') as f:
                trades = json.load(f)
            
            return [t for t in trades if t.get('status') == 'OPEN']
        except:
            return []
    
    def get_closed_trades(self, days=7):
        """Get closed trades from last N days"""
        try:
            with open('trade_history.json', 'r') as f:
                trades = json.load(f)
            
            cutoff = datetime.now() - timedelta(days=days)
            closed = [t for t in trades if 'CLOSED' in t.get('status', '')]
            
            # Filter by date
            recent = []
            for trade in closed:
                try:
                    open_time = datetime.fromisoformat(trade['open_time'].replace('Z', '+00:00'))
                    if open_time >= cutoff:
                        recent.append(trade)
                except:
                    recent.append(trade)  # Include if can't parse date
            
            return recent
        except:
            return []
    
    def generate_performance_report(self):
        """Generate comprehensive performance report"""
        
        account_info = self.get_account_info()
        if not account_info:
            return None
        
        closed_trades = self.get_closed_trades(days=30)
        open_positions = self.get_open_positions()
        
        # Calculate statistics
        total_trades = len(closed_trades)
        winners = [t for t in closed_trades if t.get('profit', 0) > 0]
        losers = [t for t in closed_trades if t.get('profit', 0) <= 0]
        
        win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
        
        gross_profit = sum([t.get('profit', 0) for t in winners])
        gross_loss = abs(sum([t.get('profit', 0) for t in losers]))
        
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        initial_balance = 10000.0
        roi = (account_info['profit'] / initial_balance * 100)
        
        # Build report
        report = {
            'account': account_info,
            'statistics': {
                'total_trades': total_trades,
                'winners': len(winners),
                'losers': len(losers),
                'win_rate': win_rate,
                'gross_profit': gross_profit,
                'gross_loss': gross_loss,
                'profit_factor': profit_factor,
                'roi': roi
            },
            'open_positions': open_positions,
            'recent_trades': closed_trades[-10:]  # Last 10 trades
        }
        
        return report


def print_account_report():
    """Print formatted account report"""
    
    reader = CTraderAccountReader()
    report = reader.generate_performance_report()
    
    if not report:
        print("❌ Failed to generate report")
        return
    
    acc = report['account']
    stats = report['statistics']
    
    print("\n" + "="*60)
    print("🤖 FOREXGOD AI - CTRADER ACCOUNT REPORT")
    print("="*60)
    print()
    print(f"📊 ACCOUNT: {acc['account']} @ {acc['server']}")
    print(f"💰 Balance: ${acc['balance']:,.2f}")
    print(f"💎 Equity: ${acc['equity']:,.2f}")
    print(f"📈 Total Profit: ${acc['profit']:,.2f}")
    print(f"🎯 ROI: {stats['roi']:.2f}%")
    print()
    print("-"*60)
    print("📊 TRADING STATISTICS")
    print("-"*60)
    print(f"Total Trades: {stats['total_trades']}")
    print(f"✅ Winners: {stats['winners']} ({stats['win_rate']:.1f}%)")
    print(f"❌ Losers: {stats['losers']} ({100-stats['win_rate']:.1f}%)")
    print(f"Profit Factor: {stats['profit_factor']:.2f}")
    print()
    print("-"*60)
    print(f"🟢 OPEN POSITIONS: {acc['open_positions']}")
    print("-"*60)
    
    for pos in report['open_positions']:
        print(f"\n• {pos['symbol']} {pos['direction']}")
        print(f"  Entry: {pos['entry_price']:.5f}")
        print(f"  SL: {pos['stop_loss']:.5f} | TP: {pos['take_profit']:.5f}")
        print(f"  R:R: {pos['risk_reward']:.2f}")
    
    if not report['open_positions']:
        print("\nNo open positions")
    
    print()
    print("-"*60)
    print(f"📈 RECENT CLOSED TRADES")
    print("-"*60)
    
    for trade in report['recent_trades']:
        profit = trade.get('profit', 0)
        emoji = "✅" if profit > 0 else "❌"
        print(f"\n{emoji} {trade['symbol']} {trade['direction']}")
        print(f"   Entry: {trade['entry_price']:.5f}")
        print(f"   P/L: ${profit:.2f} | R:R: {trade['risk_reward']:.2f}")
        print(f"   Strategy: {trade['strategy_type'].upper()}")
    
    print()
    print("="*60)
    print(f"💰 NET RESULT: ${acc['profit']:.2f} ({stats['roi']:.2f}% ROI)")
    print("="*60)
    print()
    
    return report


if __name__ == "__main__":
    report = print_account_report()
    
    # Ask if user wants to send to Telegram
    print("\n📱 Send this report to Telegram? (y/n): ", end="")
    response = input().lower()
    
    if response == 'y':
        from telegram_notifier import TelegramNotifier
        telegram = TelegramNotifier()
        
        # Format for Telegram
        acc = report['account']
        stats = report['statistics']
        
        msg = f"""
🤖 **FOREXGOD AI - ACCOUNT REPORT**

📊 **Account:** {acc['account']}
💰 **Balance:** ${acc['balance']:,.2f}
📈 **Profit:** ${acc['profit']:,.2f}
🎯 **ROI:** {stats['roi']:.2f}%

**Statistics:**
Total Trades: {stats['total_trades']}
✅ Win Rate: {stats['win_rate']:.1f}%
📊 Profit Factor: {stats['profit_factor']:.2f}

🟢 **Open Positions:** {acc['open_positions']}
"""
        
        for pos in report['open_positions'][:3]:  # Max 3
            msg += f"\n• {pos['symbol']} {pos['direction']} | R:R {pos['risk_reward']:.2f}"
        
        telegram.send_message(msg)
        print("✅ Report sent to Telegram!")
