#!/usr/bin/env python3
"""
V5.0 ZERO-LATENCY: Signal Confirmation Monitor
Watches trade_confirmations.json and sends Telegram alerts

Glitch in Matrix by ФорексГод
"""

import json
import os
import time
from pathlib import Path
from datetime import datetime
from loguru import logger
from telegram_notifier import TelegramNotifier


class SignalConfirmationMonitor:
    """
    Monitors trade confirmations from cTrader
    Sends instant Telegram notifications
    
    V6.0 UPGRADE: Prevents duplicate alerts on restart
    """
    
    def __init__(self, confirmation_file: str = None):
        # V5.0: Absolute path enforcement
        if confirmation_file is None:
            script_dir = Path(__file__).parent.resolve()
            confirmation_file = str(script_dir / "trade_confirmations.json")
        elif not os.path.isabs(confirmation_file):
            script_dir = Path(__file__).parent.resolve()
            confirmation_file = str(script_dir / confirmation_file)
        
        self.confirmation_file = confirmation_file
        
        # V6.0: Seen confirmations tracking (prevents duplicate alerts on restart)
        self.seen_file = str(Path(__file__).parent.resolve() / ".seen_confirmations.json")
        self.seen_signal_ids = self._load_seen_confirmations()
        
        self.telegram = TelegramNotifier()
        self.last_processed_id = None
        self.last_check_time = 0
        
        logger.success(f"✅ Confirmation monitor initialized (V6.0 - Duplicate Prevention)")
        logger.info(f"📁 Watching: {self.confirmation_file}")
        logger.info(f"💾 Seen tracking: {len(self.seen_signal_ids)} confirmations in history")
    
    def _load_seen_confirmations(self) -> set:
        """
        V6.0: Load previously seen Signal IDs to prevent duplicate alerts
        
        This prevents the monitor from re-alerting old confirmations when restarted.
        Similar to Position Monitor's .seen_positions.json tracking.
        """
        try:
            if os.path.exists(self.seen_file):
                with open(self.seen_file, 'r') as f:
                    data = json.load(f)
                seen_ids = set(data.get('seen_signal_ids', []))
                logger.info(f"📥 Loaded {len(seen_ids)} seen confirmations")
                return seen_ids
            return set()
        except Exception as e:
            logger.warning(f"⚠️  Could not load seen confirmations: {e}")
            return set()
    
    def _save_seen_confirmations(self):
        """V6.0: Persist seen Signal IDs to disk"""
        try:
            data = {
                'seen_signal_ids': list(self.seen_signal_ids),
                'last_update': datetime.now().isoformat()
            }
            with open(self.seen_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"❌ Failed to save seen confirmations: {e}")
    
    def check_confirmation(self) -> bool:
        """Check for new confirmations"""
        try:
            if not os.path.exists(self.confirmation_file):
                return False
            
            # Check file modification time
            file_mtime = os.path.getmtime(self.confirmation_file)
            if file_mtime <= self.last_check_time:
                return False
            
            self.last_check_time = file_mtime
            
            # Read confirmation
            with open(self.confirmation_file, 'r') as f:
                data = json.load(f)
            
            signal_id = data.get('SignalId')
            
            # V6.0: Skip if already seen (prevents duplicate alerts on restart)
            if signal_id in self.seen_signal_ids:
                logger.debug(f"🔇 Skipping seen confirmation: {signal_id}")
                return False
            
            # Skip if already processed in this session
            if signal_id == self.last_processed_id:
                return False
            
            self.last_processed_id = signal_id
            
            # V6.0: Add to seen list
            self.seen_signal_ids.add(signal_id)
            self._save_seen_confirmations()
            
            # Process confirmation
            self._process_confirmation(data)
            
            # 🚨 V6.1 CRITICAL: Delete confirmation file to prevent Ghost Notifications
            try:
                os.remove(self.confirmation_file)
                logger.debug(f"🗑️  Deleted {os.path.basename(self.confirmation_file)} (anti-spam)")
            except Exception as e:
                logger.warning(f"⚠️  Could not delete confirmation file: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking confirmation: {e}")
            return False
    
    def _process_confirmation(self, data: dict):
        """Process and send Telegram notification"""
        signal_id = data.get('SignalId', 'Unknown')
        status = data.get('Status', 'UNKNOWN')
        symbol = data.get('Symbol', 'Unknown')
        direction = data.get('Direction', 'unknown')
        
        if status == 'EXECUTED':
            self._send_execution_notification(data)
        elif status == 'REJECTED':
            self._send_rejection_notification(data)
        else:
            logger.warning(f"⚠️  Unknown status: {status}")
    
    def _send_execution_notification(self, data: dict):
        """Send execution confirmation to Telegram"""
        symbol = data.get('Symbol', 'Unknown')
        direction = data.get('Direction', 'unknown')
        order_id = data.get('OrderId', 'N/A')
        volume = data.get('Volume', 0)
        entry = data.get('EntryPrice', 0)
        sl = data.get('StopLoss', 0)
        tp = data.get('TakeProfit', 0)
        
        # Format volume (cTrader returns units, convert to lots)
        volume_lots = volume / 100000 if volume > 0 else 0
        
        direction_emoji = "🟢 LONG" if direction.lower() == 'buy' else "🔴 SHORT"
        
        message = f"""
🎯 <b>EXECUTION CONFIRMED</b>

<b>{symbol}</b> {direction_emoji}

✅ Trade executed by cTrader
🎫 Order ID: <code>{order_id}</code>
📦 Volume: <code>{volume_lots:.2f}</code> lots

📍 Entry: <code>{entry:.5f}</code>
🛡️ Stop Loss: <code>{sl:.5f}</code>
🎯 Take Profit: <code>{tp:.5f}</code>

⚡ <b>ZERO-LATENCY V5.0</b>
"""
        
        try:
            self.telegram.send_message(message.strip(), parse_mode="HTML")
            logger.success(f"✅ Execution notification sent: {symbol}")
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}")
    
    def _send_rejection_notification(self, data: dict):
        """Send rejection notification to Telegram"""
        symbol = data.get('Symbol', 'Unknown')
        direction = data.get('Direction', 'unknown')
        reason = data.get('Reason', 'Unknown reason')
        
        direction_emoji = "🟢 LONG" if direction.lower() == 'buy' else "🔴 SHORT"
        
        message = f"""
⚠️ <b>TRADE REJECTED</b>

<b>{symbol}</b> {direction_emoji}

❌ Execution failed in cTrader
📝 Reason: <code>{reason}</code>

💡 <b>Possible causes:</b>
• Symbol not available
• Insufficient margin
• Market closed
• Risk limits exceeded

⚡ <b>ZERO-LATENCY V5.0</b>
"""
        
        try:
            self.telegram.send_message(message.strip(), parse_mode="HTML")
            logger.warning(f"⚠️  Rejection notification sent: {symbol}")
        except Exception as e:
            logger.error(f"❌ Failed to send notification: {e}")
    
    def run_loop(self, check_interval: int = 2):
        """Run continuous monitoring loop"""
        logger.info(f"🔄 Starting confirmation monitor (interval: {check_interval}s)")
        
        try:
            while True:
                self.check_confirmation()
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            logger.info("👋 Confirmation monitor stopped")
        except Exception as e:
            logger.error(f"❌ Monitor error: {e}")
            raise


if __name__ == "__main__":
    import sys
    
    # Setup logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # Start monitor
    monitor = SignalConfirmationMonitor()
    monitor.run_loop(check_interval=2)
