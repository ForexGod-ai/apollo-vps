"""
Trade Monitor - monitorizează trade_history.json pentru TP/SL hits
Trimite notifications pe Telegram cu account status
"""
import json
import time
import os
from pathlib import Path
from loguru import logger
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()


class TradeMonitor:
    """Monitorizează trades și trimite notifications când TP/SL sunt hit"""
    
    def __init__(self):
        self.trade_history_file = Path("trade_history.json")
        self.last_check_file = Path(".last_trade_check.json")
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.processed_trades = self._load_processed_trades()
        
        logger.info("🔍 Trade Monitor initialized")
    
    def _load_processed_trades(self):
        """Încarcă lista de trades procesate"""
        if self.last_check_file.exists():
            try:
                with open(self.last_check_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('processed_tickets', []))
            except Exception as e:
                logger.warning(f"Could not load processed trades: {e}")
        return set()
    
    def _save_processed_trades(self):
        """Salvează lista de trades procesate"""
        try:
            with open(self.last_check_file, 'w') as f:
                json.dump({
                    'processed_tickets': list(self.processed_trades),
                    'last_update': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save processed trades: {e}")
    
    def _get_account_summary(self, trades):
        """Generează summary cont din trade history"""
        if not trades:
            return "📊 No trades yet"
        
        # Calculează stats
        total_profit = sum(t.get('profit', 0) for t in trades)
        closed_trades = [t for t in trades if t.get('status') == 'CLOSED']
        open_trades = [t for t in trades if t.get('status') == 'OPEN']
        
        winning_trades = len([t for t in closed_trades if t.get('profit', 0) > 0])
        losing_trades = len([t for t in closed_trades if t.get('profit', 0) < 0])
        
        win_rate = (winning_trades / len(closed_trades) * 100) if closed_trades else 0
        
        # Ultimul balance
        balance = 1200.00  # Default
        if closed_trades:
            last_trade = max(closed_trades, key=lambda t: t.get('close_time', ''))
            balance = last_trade.get('balance_after', balance)
        
        summary = f"""
📊 <b>ACCOUNT STATUS - IC Markets cTrader</b>

💰 <b>Balance</b>: ${balance:.2f}
📈 <b>Total P/L</b>: ${total_profit:+.2f}

📋 <b>Trade Statistics</b>:
   • Open Positions: {len(open_trades)}
   • Closed Trades: {len(closed_trades)}
   • Win Rate: {win_rate:.1f}%
   • Winners: {winning_trades} | Losers: {losing_trades}
"""
        
        # Pozițiile deschise
        if open_trades:
            summary += "\n🔓 <b>Open Positions</b>:\n"
            for trade in open_trades[:5]:  # Max 5
                symbol = trade.get('symbol', 'N/A')
                direction = trade.get('direction', 'N/A')
                lot = trade.get('lot_size', 0)
                entry = trade.get('entry_price', 0)
                emoji = "📈" if direction == 'BUY' else "📉"
                summary += f"   {emoji} {direction} {lot} {symbol} @ {entry:.5f}\n"
        
        return summary.strip()
    
    def _send_telegram(self, message):
        """Trimite mesaj pe Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("Telegram credentials missing")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'HTML',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.success("✅ Telegram notification sent!")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram: {e}")
            return False
    
    def check_for_closed_trades(self):
        """Verifică dacă sunt trades închise (TP/SL hit)"""
        if not self.trade_history_file.exists():
            logger.warning("trade_history.json not found")
            return
        
        try:
            with open(self.trade_history_file, 'r') as f:
                trades = json.load(f)
            
            # Găsește trades închise recent (nu procesate)
            new_closed_trades = []
            for trade in trades:
                ticket = trade.get('ticket')
                status = trade.get('status')
                
                if ticket and status == 'CLOSED' and ticket not in self.processed_trades:
                    new_closed_trades.append(trade)
                    self.processed_trades.add(ticket)
            
            # Trimite notification pentru fiecare trade închis
            for trade in new_closed_trades:
                self._send_trade_closed_notification(trade, trades)
            
            if new_closed_trades:
                self._save_processed_trades()
            
        except Exception as e:
            logger.error(f"Error checking trades: {e}")
    
    def _send_trade_closed_notification(self, trade, all_trades):
        """Trimite notification când trade e închis (TP/SL hit)"""
        symbol = trade.get('symbol', 'N/A')
        direction = trade.get('direction', 'N/A')
        entry = trade.get('entry_price', 0)
        close = trade.get('closing_price', 0)
        profit = trade.get('profit', 0)
        pips = trade.get('pips', 0)
        lot = trade.get('lot_size', 0)
        
        # Determină TP sau SL
        outcome = "🎯 <b>TAKE PROFIT HIT</b>" if profit > 0 else "🛑 <b>STOP LOSS HIT</b>"
        emoji_direction = "📈" if direction == 'BUY' else "📉"
        emoji_result = "✅" if profit > 0 else "❌"
        
        message = f"""
{outcome}

{emoji_result} <b>Trade Closed</b> {emoji_result}

{emoji_direction} <b>{direction}</b> {lot} {symbol}
💰 Entry: {entry:.5f}
🔚 Exit: {close:.5f}
📊 Pips: {pips:+.1f}
💵 P/L: ${profit:+.2f}

⏰ Closed: {trade.get('close_time', 'N/A')}

<i>💎 "Another one for the books"</i>
"""
        
        # Adaugă account summary
        account_summary = self._get_account_summary(all_trades)
        full_message = message + "\n" + "─" * 30 + "\n" + account_summary
        
        self._send_telegram(full_message)
        logger.success(f"✅ Sent TP/SL notification for {symbol} ({profit:+.2f})")
    
    def monitor_loop(self, interval=30):
        """Loop continuu de monitorizare"""
        logger.info(f"🔄 Starting monitor loop (check every {interval}s)")
        
        try:
            while True:
                self.check_for_closed_trades()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("⏹️  Monitor stopped by user")
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")


if __name__ == "__main__":
    import sys
    
    monitor = TradeMonitor()
    
    # Check for --loop argument
    if len(sys.argv) > 1 and sys.argv[1] == '--loop':
        monitor.monitor_loop(interval=30)
    else:
        # Test mode
        print("\n🧪 Testing with sample closed trade...\n")
        
        test_trade = {
            "ticket": 999999999,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.27500,
            "closing_price": 1.28100,
            "lot_size": 0.1,
            "profit": 57.50,
            "pips": 60.0,
            "status": "CLOSED",
            "open_time": "2025-12-09T13:00:00",
            "close_time": "2025-12-09T13:17:00",
            "balance_after": 1257.50
        }
        
        monitor._send_trade_closed_notification(test_trade, [test_trade])
        
        print("\n✅ Test complete! Check Telegram for notification.")
        print("\n💡 To run continuous monitoring:")
        print("   python3 trade_monitor.py --loop")
