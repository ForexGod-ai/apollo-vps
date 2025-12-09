"""
Position Monitor - detectează NOUL TRADE OPEN și trimite ARMAGEDDON notification
Monitorizează trade_history.json pentru poziții noi deschise
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


class PositionMonitor:
    """Monitorizează noi poziții deschise și trimite ARMAGEDDON notifications"""
    
    def __init__(self):
        self.trade_history_file = Path("trade_history.json")
        self.seen_positions_file = Path(".seen_positions.json")
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.seen_tickets = self._load_seen_tickets()
        
        logger.info("👀 Position Monitor initialized")
    
    def _load_seen_tickets(self):
        """Încarcă ticket-urile deja procesate"""
        if self.seen_positions_file.exists():
            try:
                with open(self.seen_positions_file, 'r') as f:
                    data = json.load(f)
                    return set(data.get('seen_tickets', []))
            except Exception as e:
                logger.warning(f"Could not load seen tickets: {e}")
        return set()
    
    def _save_seen_tickets(self):
        """Salvează ticket-urile procesate"""
        try:
            with open(self.seen_positions_file, 'w') as f:
                json.dump({
                    'seen_tickets': list(self.seen_tickets),
                    'last_update': datetime.now().isoformat()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save seen tickets: {e}")
    
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
        
        direction_emoji = "📈" if direction == 'BUY' else "📉"
        
        # Epic ARMAGEDDON messages
        import random
        armageddon_messages = [
            "⚔️ <b>THE ARMAGEDDON BEGINS</b> ⚔️",
            "💥 <b>MARKET APOCALYPSE INITIATED</b> 💥",
            "🔥 <b>UNLEASHING THE BEAST</b> 🔥",
            "⚡ <b>GODMODE ACTIVATED</b> ⚡",
            "🎯 <b>SNIPER ELITE EXECUTION</b> 🎯",
            "💀 <b>NO MERCY PROTOCOL</b> 💀",
            "🚀 <b>MOONSHOT ENGAGED</b> 🚀",
            "👑 <b>KING'S GAMBIT</b> 👑"
        ]
        epic_title = random.choice(armageddon_messages)
        
        message = f"""
{epic_title}

🔥 <b>GLITCH IN MATRIX DETECTED</b> 🔥

{direction_emoji} <b>{direction}</b> {lot} {symbol}
💰 Entry: {entry:.5f}
🎫 Ticket: #{ticket}

🧠 <b>AI Validation</b>: CONFIRMED
⚡ <b>Risk Level</b>: CALCULATED
🤖 <b>Status</b>: POSITION OPENED

<i>🤖 Executed by FOREXGOD AI Bot</i>
<i>💎 "The Matrix cannot hold us"</i>
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
            with open(self.trade_history_file, 'r') as f:
                trades = json.load(f)
            
            # Găsește poziții noi (nu văzute anterior)
            new_positions = []
            for trade in trades:
                ticket = trade.get('ticket')
                
                if ticket and ticket not in self.seen_tickets:
                    # Poziție nouă!
                    new_positions.append(trade)
                    self.seen_tickets.add(ticket)
                    logger.info(f"🆕 NEW POSITION detected: {trade.get('symbol')} #{ticket}")
            
            # Trimite ARMAGEDDON notification pentru fiecare poziție nouă
            for trade in new_positions:
                self._send_armageddon_notification(trade)
            
            if new_positions:
                self._save_seen_tickets()
                logger.success(f"✅ Processed {len(new_positions)} new positions!")
            
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
