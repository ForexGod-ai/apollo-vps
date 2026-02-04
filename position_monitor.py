"""
Position Monitor - detectează NOUL TRADE OPEN și trimite ARMAGEDDON notification
Monitorizează trade_history.json pentru poziții noi deschise
"""
import json
import time
import os
import subprocess
import sys
from pathlib import Path
from loguru import logger
from datetime import datetime
import requests
from dotenv import load_dotenv

load_dotenv()


class PositionMonitor:
    """Monitorizează noi poziții deschise și trimite ARMAGEDDON notifications"""
    
    def __init__(self):
        self.trade_history_file = Path("trade_history.json")
        self.seen_positions_file = Path(".seen_positions.json")
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.seen_open_tickets = self._load_seen_tickets('seen_open_tickets')
        self.seen_closed_tickets = self._load_seen_tickets('seen_closed_tickets')
        
        logger.info("👀 Position Monitor initialized")
    
    def _load_seen_tickets(self, key):
        """Încarcă ticket-urile deja procesate (separate pentru open și closed)"""
        if self.seen_positions_file.exists():
            try:
                with open(self.seen_positions_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get(key, []))
            except Exception as e:
                logger.warning(f"Could not load seen tickets: {e}")
        return set()
    
    def _save_seen_tickets(self):
        """Salvează ticket-urile procesate (separate pentru open și closed)"""
        try:
            with open(self.seen_positions_file, 'w') as f:
                json.dump({
                    'seen_open_tickets': list(self.seen_open_tickets),
                    'seen_closed_tickets': list(self.seen_closed_tickets),
                    'last_update': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save seen tickets: {e}")
    
    def _send_closed_trade_notification(self, trade):
        """Trimite notificare pentru trade închis cu profit/loss + account status"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("⚠️  Telegram credentials missing")
            return False
        
        symbol = trade.get('symbol', 'N/A')
        direction = trade.get('direction', 'N/A')
        profit = trade.get('profit', 0)
        lot = trade.get('lot_size', 0)
        ticket = trade.get('ticket', 'N/A')
        entry = trade.get('entry_price', 0)
        close_price = trade.get('close_price', 0)
        close_time = trade.get('close_time', 'N/A')
        
        # Get account info from trade_history.json
        account_balance = 0
        account_equity = 0
        open_positions_count = 0
        total_open_pl = 0
        
        try:
            with open(self.trade_history_file, 'r') as f:
                data = json.load(f)
                account_balance = data.get('account', {}).get('balance', 0)
                account_equity = data.get('account', {}).get('equity', 0)
                open_positions = data.get('open_positions', [])
                open_positions_count = len(open_positions)
                total_open_pl = sum(p.get('profit', 0) for p in open_positions)
        except Exception as e:
            logger.warning(f"Could not load account info: {e}")
        
        # Profit/Loss styling
        if profit > 0:
            profit_emoji = "✅ 💰"
            profit_text = f"+${profit:.2f}"
            title = "🎯 <b>TRADE WINNER!</b> 🎯"
            conclusion = "<i>💎 'Another one bites the dust'</i>"
        else:
            profit_emoji = "❌ 📉"
            profit_text = f"-${abs(profit):.2f}"
            title = "⚠️ <b>TRADE CLOSED</b> ⚠️"
            conclusion = "<i>📊 'We learn and adapt'</i>"
        
        direction_emoji = "📈" if direction == 'BUY' else "📉"
        
        # Open P/L emoji
        pl_emoji = "📈" if total_open_pl >= 0 else "📉"
        
        message = f"""
{title}

{profit_emoji} <b>POSITION CLOSED</b>

{direction_emoji} {direction} {lot} {symbol}
💵 Profit/Loss: <b>{profit_text}</b>
📊 Entry: {entry:.5f}
🎯 Close: {close_price:.5f}
🎫 Ticket: #{ticket}
⏰ Closed: {close_time}

{conclusion}

━━━━━━━━━━━━━━━━━━━━━━━━
💼 <b>ACCOUNT STATUS</b>
━━━━━━━━━━━━━━━━━━━━━━━━
💰 Balance: <b>${account_balance:.2f}</b>
💎 Equity: <b>${account_equity:.2f}</b>
{pl_emoji} Open P/L: <b>${total_open_pl:+.2f}</b>
📊 Open Positions: <b>{open_positions_count}</b>

━━━━━━━━━━━━━━━━━━━━━━━━
✨ <b>Strategy by ForexGod</b> ✨
🧠 Glitch in Matrix Trading System
💎 + AI Validation
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
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
                logger.success(f"✅ Closed trade notification sent for {symbol} #{ticket} (Profit: ${profit:.2f})!")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram: {e}")
            return False
    
    def _send_armageddon_notification(self, trade):
        """Trimite EPIC ARMAGEDDON notification pentru poziție nouă"""
        if not self.telegram_token or not self.telegram_chat_id:
            logger.warning("⚠️  Telegram credentials missing")
            return False
        
        symbol = trade.get('symbol', 'N/A')
        direction = trade.get('direction', 'N/A')
        entry = trade.get('entry_price', 0)
        lot = trade.get('lot_size', 0)
        ticket = trade.get('ticket', 'N/A')
        stop_loss = trade.get('stop_loss')
        take_profit = trade.get('take_profit')
        
        direction_emoji = "📈" if direction == 'BUY' else "📉"
        
        # Epic ARMAGEDDON messages
        import random
        armageddon_messages = [
            "⚔️ <b>THE ARMAGEDDON BEGINS</b> ⚔️",
            "💥 <b>MARKET DOMINATION MODE</b> 💥",
            "🔥 <b>BEAST MODE UNLEASHED</b> 🔥",
            "⚡ <b>GODMODE ACTIVATED</b> ⚡",
            "🎯 <b>SNIPER ELITE • TARGET LOCKED</b> 🎯",
            "💀 <b>NO MERCY • FULL AGGRO</b> 💀",
            "🚀 <b>TO THE MOON WE GO</b> 🚀",
            "👑 <b>KING'S GAMBIT • CHECKMATE</b> 👑",
            "⚡ <b>GLITCH ACTIVATED • MATRIX BREACHED</b> ⚡",
            "🔮 <b>PROPHECY FULFILLED</b> 🔮"
        ]
        epic_title = random.choice(armageddon_messages)
        
        # Direction arrows
        direction_arrow = "📈 ↗️" if direction == 'BUY' else "📉 ↘️"
        
        # Calculate risk metrics if SL available
        risk_pips = ""
        reward_pips = ""
        rr_ratio = ""
        if stop_loss and take_profit:
            pip_value = 0.01 if 'JPY' in symbol else 0.0001
            risk_p = abs(entry - stop_loss) / pip_value
            reward_p = abs(take_profit - entry) / pip_value
            risk_pips = f"\n🛑 <b>Risk:</b> {risk_p:.1f} pips"
            reward_pips = f"\n🎯 <b>Reward:</b> {reward_p:.1f} pips"
            if risk_p > 0:
                rr = reward_p / risk_p
                rr_ratio = f"\n📊 <b>R:R Ratio:</b> 1:{rr:.2f}"
        
        # Build message with TP/SL
        message = f"""
{epic_title}

🔥 <b>GLITCH IN MATRIX • POSITION LIVE</b> 🔥
━━━━━━━━━━━━━━━━━━━━━━━━

💎 <b>{symbol}</b> • {direction_arrow} <b>{direction}</b>
📦 <b>Volume:</b> {lot} lots
💰 <b>Entry:</b> {entry:.5f}
🎫 <b>Ticket:</b> #{ticket}
"""
        
        # Add SL/TP if available
        if stop_loss:
            message += f"\n🛑 <b>Stop Loss:</b> {stop_loss:.5f}"
        if take_profit:
            message += f"\n🎯 <b>Take Profit:</b> {take_profit:.5f}"
        
        # Add risk metrics
        message += risk_pips + reward_pips + rr_ratio
        
        message += """

━━━━━━━━━━━━━━━━━━━━━━━━
🧠 <b>AI Validation:</b> ✅ CONFIRMED
⚡ <b>Risk Level:</b> CALCULATED
🤖 <b>Execution:</b> AUTOMATED
💯 <b>Confidence:</b> HIGH

<i>💎 "The Matrix cannot hold us" 💎</i>

━━━━━━━━━━━━━━━━━━━━━━━━
✨ <b>Glitch in Matrix</b> by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
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
                logger.success(f"✅ ARMAGEDDON notification sent for {symbol} #{ticket}!")
                return True
            else:
                logger.error(f"Telegram API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Telegram: {e}")
            return False
    
    def check_for_new_positions(self):
        """Verifică dacă sunt poziții noi deschise"""
        if not self.trade_history_file.exists():
            logger.warning("trade_history.json not found")
            return
        
        try:
            # Always reload from disk for perfect sync
            self.seen_open_tickets = self._load_seen_tickets('seen_open_tickets')
            self.seen_closed_tickets = self._load_seen_tickets('seen_closed_tickets')
            
            with open(self.trade_history_file, 'r') as f:
                data = json.load(f)

            # Separate open and closed trades
            open_positions = data.get('open_positions', [])
            closed_trades = data.get('closed_trades', [])

            # Check for NEW OPEN positions (avoid duplicate notifications)
            new_open = []
            unique_tickets = set()
            for trade in open_positions:
                ticket = trade.get('ticket')
                if not ticket:
                    continue
                # Avoid duplicate notifications for same ticket
                if ticket in self.seen_open_tickets or ticket in unique_tickets:
                    continue
                new_open.append(trade)
                unique_tickets.add(ticket)
                self.seen_open_tickets.add(ticket)
                logger.info(f"🆕 NEW POSITION OPENED: {trade.get('symbol')} #{ticket}")

            # Check for NEW CLOSED trades (TP/SL hit) - SEPARATE tracking from opens!
            new_closed = []
            for trade in closed_trades:
                ticket = trade.get('ticket')
                # NEW LOGIC: Check if ticket is in seen_closed (not seen_open!)
                if ticket and ticket not in self.seen_closed_tickets:
                    new_closed.append(trade)
                    self.seen_closed_tickets.add(ticket)
                    profit = trade.get('profit', 0)
                    emoji = "✅" if profit > 0 else "❌"
                    logger.info(f"{emoji} TRADE CLOSED: {trade.get('symbol')} #{ticket} (Profit: ${profit:.2f})")

            # Send notifications
            for trade in new_open:
                self._send_armageddon_notification(trade)

            for trade in new_closed:
                self._send_closed_trade_notification(trade)
                
                # 🧠 AUTO-LEARNING: Trigger ML update after every closed trade
                logger.info("🧠 Triggering AUTO-LEARNING system...")
                try:
                    subprocess.Popen(
                        [sys.executable, "trigger_ml_update.py"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        start_new_session=True
                    )
                    logger.success("✅ ML update triggered in background")
                except Exception as e:
                    logger.warning(f"⚠️  Could not trigger ML update: {e}")

            if new_open or new_closed:
                self._save_seen_tickets()
                logger.success(f"✅ Processed {len(new_open)} new opens, {len(new_closed)} new closes!")

        except Exception as e:
            logger.error(f"Error checking positions: {e}")
    
    def monitor_loop(self, interval=10):
        """Loop continuu de monitorizare (check la fiecare 10s)"""
        logger.info(f"🔄 Starting position monitor (check every {interval}s)")
        logger.info("🎯 Will send ARMAGEDDON notification for every new position!")
        
        try:
            while True:
                self.check_for_new_positions()
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("⏹️  Monitor stopped by user")
        except Exception as e:
            logger.error(f"Monitor loop error: {e}")


if __name__ == "__main__":
    import sys
    
    monitor = PositionMonitor()
    
    # Check for --loop or --test
    if '--loop' in sys.argv:
        monitor.monitor_loop(interval=10)
    elif '--test' in sys.argv:
        # Test mode - check once
        print("\n🧪 Testing position detection...\n")
        monitor.check_for_new_positions()
        print("\n✅ Test complete!")
    else:
        # Default: run loop
        print("🚀 Starting Position Monitor...")
        print("💡 This will send ARMAGEDDON notification for EVERY new trade opened!")
        print("⏹️  Press Ctrl+C to stop\n")
        monitor.monitor_loop(interval=10)
