#!/usr/bin/env python3
"""
V5.0 ZERO-LATENCY: Signal Confirmation Monitor
Watches execution_report.json / trade_confirmations.json — logging + rejections only.
Fill Telegram disabled V37.16 (position_monitor → GLITCH ACTIVATED).

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
        self.execution_report_file = confirmation_file.replace(
            'trade_confirmations.json', 'execution_report.json'
        )
        
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
    
    def _read_fresh_confirmation(self) -> tuple:
        """V37.9: Citeste confirmarea din execution_report.json (nou) sau trade_confirmations (legacy)."""
        candidates = []
        for path in (self.execution_report_file, self.confirmation_file):
            if os.path.exists(path):
                candidates.append((os.path.getmtime(path), path))
        if not candidates:
            return None, None
        candidates.sort(reverse=True)
        _mtime, path = candidates[0]
        if _mtime <= self.last_check_time:
            return None, None
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f), path

    def check_confirmation(self) -> bool:
        """Check for new confirmations"""
        try:
            data, source_path = self._read_fresh_confirmation()
            if not data:
                return False

            self.last_check_time = os.path.getmtime(source_path)
            
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
                os.remove(source_path)
                logger.debug(f"🗑️  Deleted {os.path.basename(source_path)} (anti-spam)")
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
    
    @staticmethod
    def _volume_to_lots(data: dict) -> float:
        """
        V37.11: cBot V9.3 scrie Volume deja in LOTS + VolumeInUnits separat.
        Cod vechi presupunea Volume in units ( / 100000 ) → afisa 0.00 lots.
        """
        try:
            vol = float(data.get('Volume') or 0)
            vol_units = float(data.get('VolumeInUnits') or 0)
            if vol_units > 0 and vol > 0 and vol < 100:
                return vol  # V9.3: Volume = lots, VolumeInUnits = broker units
            if vol_units > 0:
                return vol_units / 100000.0
            if vol > 100:
                return vol / 100000.0  # legacy: Volume in units
            return vol
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _prices_plausible(symbol: str, direction: str, entry: float, sl: float, tp: float) -> bool:
        if entry <= 0:
            return False
        d = direction.lower()
        if sl > 0:
            if d in ('buy', 'long') and sl >= entry:
                return False
            if d in ('sell', 'short') and sl <= entry:
                return False
        if tp > 0:
            if d in ('buy', 'long') and tp <= entry:
                return False
            if d in ('sell', 'short') and tp >= entry:
                return False
            # TP nu poate fi >2x entry pe FX (ex. AUDJPY TP 223 la entry 112)
            ratio = tp / entry if entry else 0
            if 'JPY' in symbol.upper() and (ratio > 1.5 or ratio < 0.5):
                return False
            if ratio > 3.0 or ratio < 0.33:
                return False
        return True

    def _send_execution_notification(self, data: dict):
        """
        V37.16: Fără Telegram la fill — position_monitor trimite deja GLITCH ACTIVATED.
        Monitorul rămâne activ doar pentru logging + dedup + rejections.
        """
        symbol = data.get('Symbol', 'Unknown')
        direction = data.get('Direction', 'unknown')
        order_id = data.get('OrderId', 'N/A')
        entry = float(data.get('EntryPrice') or 0)
        sl = float(data.get('StopLoss') or 0)
        tp = float(data.get('TakeProfit') or 0)

        volume_lots = self._volume_to_lots(data)

        if volume_lots < 0.01:
            logger.warning(
                f"⚠️ Confirmare suspecta {symbol}: volume={volume_lots:.4f} lots — "
                f"ignorat (posibil ghost/stale)"
            )
            return

        if not self._prices_plausible(symbol, direction, entry, sl, tp):
            logger.warning(
                f"⚠️ Confirmare suspecta {symbol}: preturi invalide "
                f"entry={entry} sl={sl} tp={tp} — ignorat"
            )
            return

        logger.success(
            f"[V37.16] Fill confirmat (fără Telegram): {symbol} {direction.upper()} "
            f"#{order_id} | {volume_lots:.2f} lots @ {entry:.5f} — "
            f"Position Monitor → GLITCH ACTIVATED"
        )
    
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
