"""
cTrader Account Statistics - Live sync check
Extrage statistici complete din contul IC Markets cTrader
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
from dotenv import load_dotenv
import requests

load_dotenv()


class CTraderAccountStats:
    """Extrage și afișează statistici complete cont cTrader"""
    
    def __init__(self):
        self.account_id = os.getenv('CTRADER_ACCOUNT_ID', '9709773')
        self.trade_history_file = Path("trade_history.json")
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
    def load_trade_history(self):
        """Încarcă trade history din JSON"""
        if not self.trade_history_file.exists():
            logger.error("❌ trade_history.json not found!")
            return []
        
        try:
            with open(self.trade_history_file, 'r') as f:
                trades = json.load(f)
            logger.success(f"✅ Loaded {len(trades)} trades from history")
            return trades
        except Exception as e:
            logger.error(f"Error loading trade history: {e}")
            return []
    
    def calculate_statistics(self, trades):
        """Calculează statistici complete"""
        if not trades:
            return None
        
        # Separate open vs closed
        open_trades = [t for t in trades if t.get('status') == 'OPEN']
        closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
        
        # Calculate P/L
        total_profit = sum(t.get('profit', 0) for t in closed_trades)
        open_profit = sum(t.get('profit', 0) for t in open_trades if 'profit' in t)
        
        # Win/Loss stats
        winning_trades = [t for t in closed_trades if t.get('profit', 0) > 0]
        losing_trades = [t for t in closed_trades if t.get('profit', 0) < 0]
        breakeven_trades = [t for t in closed_trades if t.get('profit', 0) == 0]
        
        win_rate = (len(winning_trades) / len(closed_trades) * 100) if closed_trades else 0
        
        # Average stats
        avg_win = sum(t['profit'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['profit'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # Profit factor
        total_wins = sum(t['profit'] for t in winning_trades)
        total_losses = abs(sum(t['profit'] for t in losing_trades))
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Balance tracking
        current_balance = 1200.00  # Default starting
        if closed_trades:
            last_closed = max(closed_trades, key=lambda t: t.get('close_time', ''))
            current_balance = last_closed.get('balance_after', current_balance)
        
        # Equity (balance + open profit)
        equity = current_balance + open_profit
        
        # Best & Worst trade
        best_trade = max(closed_trades, key=lambda t: t.get('profit', 0)) if closed_trades else None
        worst_trade = min(closed_trades, key=lambda t: t.get('profit', 0)) if closed_trades else None
        
        # Trading frequency
        if closed_trades:
            first_trade_time = min(t.get('open_time', '') for t in closed_trades)
            last_trade_time = max(t.get('close_time', '') for t in closed_trades)
            
            try:
                first_dt = datetime.fromisoformat(first_trade_time.replace('Z', '+00:00'))
                last_dt = datetime.fromisoformat(last_trade_time.replace('Z', '+00:00'))
                days_trading = (last_dt - first_dt).days + 1
                trades_per_day = len(closed_trades) / days_trading if days_trading > 0 else 0
            except:
                days_trading = 0
                trades_per_day = 0
        else:
            days_trading = 0
            trades_per_day = 0
        
        # Symbols traded
        symbols_traded = {}
        for t in closed_trades:
            symbol = t.get('symbol', 'N/A')
            symbols_traded[symbol] = symbols_traded.get(symbol, 0) + 1
        
        return {
            'account_id': self.account_id,
            'total_trades': len(trades),
            'open_positions': len(open_trades),
            'closed_trades': len(closed_trades),
            'balance': current_balance,
            'equity': equity,
            'total_profit': total_profit,
            'open_profit': open_profit,
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'breakeven_trades': len(breakeven_trades),
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'days_trading': days_trading,
            'trades_per_day': trades_per_day,
            'symbols': symbols_traded,
            'open_trades_detail': open_trades,
            'last_update': datetime.now().isoformat()
        }
    
    def print_statistics(self, stats):
        """Afișează statistici în terminal"""
        if not stats:
            print("\n❌ No statistics available")
            return
        
        print("\n" + "="*60)
        print("📊 CTRADER ACCOUNT STATISTICS - IC MARKETS")
        print("="*60)
        print(f"\n🔑 Account ID: {stats['account_id']}")
        print(f"⏰ Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        print("\n💰 BALANCE & EQUITY")
        print(f"   Balance:     ${stats['balance']:,.2f}")
        print(f"   Equity:      ${stats['equity']:,.2f}")
        print(f"   Total P/L:   ${stats['total_profit']:+,.2f}")
        print(f"   Open P/L:    ${stats['open_profit']:+,.2f}")
        
        print("\n📈 TRADING PERFORMANCE")
        print(f"   Total Trades:     {stats['total_trades']}")
        print(f"   Closed Trades:    {stats['closed_trades']}")
        print(f"   Open Positions:   {stats['open_positions']}")
        print(f"   Win Rate:         {stats['win_rate']:.1f}%")
        print(f"   Profit Factor:    {stats['profit_factor']:.2f}")
        
        print("\n✅ WIN/LOSS BREAKDOWN")
        print(f"   Winners:   {stats['winning_trades']} (Avg: ${stats['avg_win']:+.2f})")
        print(f"   Losers:    {stats['losing_trades']} (Avg: ${stats['avg_loss']:+.2f})")
        print(f"   Breakeven: {stats['breakeven_trades']}")
        
        if stats['best_trade']:
            bt = stats['best_trade']
            print(f"\n🏆 BEST TRADE")
            print(f"   {bt['symbol']} {bt['direction']} - ${bt['profit']:+.2f} ({bt.get('pips', 0):+.1f} pips)")
        
        if stats['worst_trade']:
            wt = stats['worst_trade']
            print(f"\n💀 WORST TRADE")
            print(f"   {wt['symbol']} {wt['direction']} - ${wt['profit']:+.2f} ({wt.get('pips', 0):+.1f} pips)")
        
        print(f"\n📅 TRADING FREQUENCY")
        print(f"   Days Trading:     {stats['days_trading']}")
        print(f"   Trades per Day:   {stats['trades_per_day']:.2f}")
        
        print(f"\n🎯 SYMBOLS TRADED")
        sorted_symbols = sorted(stats['symbols'].items(), key=lambda x: x[1], reverse=True)
        for symbol, count in sorted_symbols[:10]:  # Top 10
            print(f"   {symbol:12} {count:3} trades")
        
        if stats['open_trades_detail']:
            print(f"\n🔓 OPEN POSITIONS ({len(stats['open_trades_detail'])})")
            for trade in stats['open_trades_detail']:
                symbol = trade.get('symbol', 'N/A')
                direction = trade.get('direction', 'N/A')
                lot = trade.get('lot_size', 0)
                entry = trade.get('entry_price', 0)
                profit = trade.get('profit', 0)
                emoji = "📈" if direction == 'BUY' else "📉"
                profit_emoji = "✅" if profit >= 0 else "❌"
                print(f"   {emoji} {direction:4} {lot:.2f} {symbol:8} @ {entry:.5f}  {profit_emoji} ${profit:+.2f}")
        
        print("\n" + "="*60)
    
    def send_telegram_report(self, stats):
        """Trimite raport pe Telegram"""
        if not stats:
            return False
        
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials missing")
            return False
        
        sep = "────────────────"
        # Build message — V8.4 FOOTER ONLY
        message = f"""
📊 <b>CTRADER ACCOUNT STATISTICS</b>
🏦 IC Markets - Account {stats['account_id']}

💰 <b>BALANCE & EQUITY</b>
   Balance: ${stats['balance']:,.2f}
   Equity: ${stats['equity']:,.2f}
   Total P/L: <b>${stats['total_profit']:+,.2f}</b>
   Open P/L: ${stats['open_profit']:+,.2f}

📈 <b>PERFORMANCE</b>
   Win Rate: {stats['win_rate']:.1f}%
   Profit Factor: {stats['profit_factor']:.2f}
   Total Trades: {stats['total_trades']}
   Closed: {stats['closed_trades']} | Open: {stats['open_positions']}

✅ <b>RESULTS</b>
   Winners: {stats['winning_trades']} (Avg: ${stats['avg_win']:+.2f})
   Losers: {stats['losing_trades']} (Avg: ${stats['avg_loss']:+.2f})
"""
        
        # Add best trade
        if stats['best_trade']:
            bt = stats['best_trade']
            message += f"\n🏆 <b>Best Trade</b>: {bt['symbol']} ${bt['profit']:+.2f}"
        
        # Add open positions
        if stats['open_trades_detail']:
            message += f"\n\n🔓 <b>Open Positions ({len(stats['open_trades_detail'])})</b>:\n"
            for trade in stats['open_trades_detail'][:5]:  # Max 5
                symbol = trade.get('symbol', 'N/A')
                direction = trade.get('direction', 'N/A')
                lot = trade.get('lot_size', 0)
                entry = trade.get('entry_price', 0)
                profit = trade.get('profit', 0)
                emoji = "📈" if direction == 'BUY' else "📉"
                message += f"   {emoji} {direction} {lot} {symbol} @ {entry:.5f} (${profit:+.2f})\n"
        
        message += f"\n⏰ <i>Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        message += f"\n\n  {sep}"
        message += f"\n  🔱 AUTHORED BY ФорексГод 🔱"
        message += f"\n  {sep}"
        message += f"\n  🏛️ INSTITUTIONAL TERMINAL 🏛️"
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message.strip(),
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.success("✅ Statistics sent to Telegram!")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram: {e}")
            return False
    
    def run(self, send_telegram=False):
        """Run complete statistics"""
        logger.info("🔍 Fetching cTrader account statistics...")
        
        trades = self.load_trade_history()
        stats = self.calculate_statistics(trades)
        
        if stats:
            self.print_statistics(stats)
            
            if send_telegram:
                self.send_telegram_report(stats)
            
            return stats
        else:
            logger.error("❌ Could not generate statistics")
            return None


if __name__ == "__main__":
    import sys
    
    # Check for --telegram flag
    send_telegram = '--telegram' in sys.argv or '-t' in sys.argv
    
    stats_tool = CTraderAccountStats()
    stats_tool.run(send_telegram=send_telegram)
    
    if send_telegram:
        print("\n✅ Statistics sent to Telegram!")
    else:
        print("\n💡 To send to Telegram: python3 ctrader_account_stats.py --telegram")
