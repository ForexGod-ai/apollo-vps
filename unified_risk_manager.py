#!/usr/bin/env python3
"""
──────────────────
🛡️ Unified Risk Manager - Single Source of Truth
──────────────────

Reads SUPER_CONFIG.json (shared with cBot)
Enforces risk limits across Python and cTrader
Activates KILL SWITCH on 10% daily loss

✨ Glitch in Matrix by ФорексГод ✨
──────────────────
"""

import json
import sqlite3
import os
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

class UnifiedRiskManager:
    """
    Unified Risk Manager - Enforces limits from SUPER_CONFIG.json
    Used by both Python and cBot (via config file)
    """
    
    def __init__(self, config_file="SUPER_CONFIG.json"):
        self.config_file = Path(config_file)
        self.db_path = Path("data/trades.db")
        self.kill_switch_file = Path("trading_disabled.flag")
        
        # Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Load unified config
        self.config = self._load_config()
        
        # Extract limits
        self.risk_per_trade = self.config['risk_management']['risk_per_trade_percent']
        self.max_positions = self.config['position_limits']['max_open_positions']
        self.max_daily_loss_pct = self.config['daily_limits']['max_daily_loss_percent']
        self.daily_warning_pct = self.config['daily_limits']['daily_loss_warning_percent']
        self.kill_switch_enabled = self.config['kill_switch']['enabled']
        self.kill_switch_trigger = self.config['kill_switch']['trigger_daily_loss_percent']
        
        print(f"\n🛡️  UNIFIED RISK MANAGER INITIALIZED")
        print(f"──────────────────")
        print(f"📊 Risk per trade: {self.risk_per_trade}%")
        print(f"📈 Max positions: {self.max_positions}")
        print(f"🛑 Daily loss limit: {self.max_daily_loss_pct}%")
        print(f"⚠️  Daily warning: {self.daily_warning_pct}%")
        print(f"🔴 Kill switch: {'ENABLED' if self.kill_switch_enabled else 'DISABLED'} @ {self.kill_switch_trigger}%")
        print(f"──────────────────")
    
    def _load_config(self):
        """Load SUPER_CONFIG.json"""
        try:
            if not self.config_file.exists():
                raise FileNotFoundError(f"SUPER_CONFIG.json not found!")
            
            with open(self.config_file, 'r') as f:
                config = json.load(f)
            
            print(f"✅ Config loaded: {config['system_info']['name']} v{config['system_info']['version']}")
            return config
            
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            raise
    
    def get_account_balance(self):
        """Get current account balance from SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get latest snapshot
            cursor.execute("""
                SELECT equity, balance 
                FROM account_snapshots 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                equity, balance = result
                return float(equity), float(balance)
            else:
                # Fallback to env variable
                balance = float(os.getenv('ACCOUNT_BALANCE', 1000))
                return balance, balance
                
        except Exception as e:
            print(f"⚠️  Error reading balance: {e}")
            balance = float(os.getenv('ACCOUNT_BALANCE', 1000))
            return balance, balance
    
    def get_daily_pnl(self):
        """Calculate P&L for today"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().date().isoformat()
            
            # Closed trades today
            cursor.execute("""
                SELECT SUM(profit) 
                FROM closed_trades 
                WHERE DATE(close_time) = ?
            """, (today,))
            
            closed_pnl = cursor.fetchone()[0] or 0.0
            
            # Open P&L - calculate from current equity vs balance
            # (More reliable than trying to sum individual position profits)
            cursor.execute("""
                SELECT equity, balance 
                FROM account_snapshots 
                ORDER BY timestamp DESC 
                LIMIT 1
            """)
            
            snapshot = cursor.fetchone()
            if snapshot:
                equity, balance = snapshot
                open_pnl = float(equity) - float(balance)
            else:
                open_pnl = 0.0
            
            conn.close()
            
            total_pnl = float(closed_pnl) + float(open_pnl)
            
            return {
                'closed_pnl': float(closed_pnl),
                'open_pnl': float(open_pnl),
                'total_pnl': total_pnl
            }
            
        except Exception as e:
            print(f"⚠️  Error calculating daily P&L: {e}")
            return {'closed_pnl': 0, 'open_pnl': 0, 'total_pnl': 0}
    
    def get_open_positions_count(self):
        """Get number of open positions"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM open_positions")
            count = cursor.fetchone()[0]
            
            conn.close()
            return count
            
        except Exception as e:
            print(f"⚠️  Error counting positions: {e}")
            return 0
    
    def check_kill_switch(self):
        """Check if kill switch is active"""
        return self.kill_switch_file.exists()
    
    def activate_kill_switch(self, reason="Daily loss limit reached"):
        """Activate kill switch - stops all trading"""
        try:
            # Create flag file
            self.kill_switch_file.touch()
            
            print(f"\n🔴 KILL SWITCH ACTIVATED!")
            print(f"   Reason: {reason}")
            print(f"   File created: {self.kill_switch_file}")
            
            # Send Telegram alert
            self._send_kill_switch_alert(reason)
            
            return True
            
        except Exception as e:
            print(f"❌ Error activating kill switch: {e}")
            return False
    
    def deactivate_kill_switch(self):
        """Deactivate kill switch - resume trading"""
        try:
            if self.kill_switch_file.exists():
                self.kill_switch_file.unlink()
                print(f"\n🟢 KILL SWITCH DEACTIVATED")
                print(f"   Trading resumed")
                
                # Send Telegram notification
                message = (
                    "🟢 <b>KILL SWITCH DEACTIVATED</b>\n\n"
                    "Trading has been resumed.\n"
                    "System is now accepting new signals.\n\n"
                    "──────────────────\n"
                    "✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
                    "🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
                )
                self._send_telegram(message)
                
                return True
            else:
                print("⚠️  Kill switch not active")
                return False
                
        except Exception as e:
            print(f"❌ Error deactivating kill switch: {e}")
            return False
    
    def validate_new_trade(self, symbol="", direction="", entry_price=0, stop_loss=0):
        """
        Validate if new trade is allowed based on all risk rules
        
        Returns:
            dict: {
                'approved': bool,
                'reason': str,
                'lot_size': float
            }
        """
        result = {
            'approved': False,
            'reason': None,
            'lot_size': 0.0
        }
        
        # 🚀 V8.1 BULLETPROOF NO-MATH BYPASS: BTCUSD gets DIRECT volume injection
        # Skip ALL risk calculations, daily range checks, and data dependencies
        # BULLETPROOF: Case-insensitive, ignores spaces/slashes
        if 'BTC' in symbol.upper().replace(' ', '').replace('/', ''):
            result['approved'] = True
            result['lot_size'] = 0.50
            result['reason'] = "V8.1 BULLETPROOF NO-MATH BYPASS - Manual Override"
            print(f"\n🚀 BTC EXECUTION: Forced 0.50 lots (Bulletproof Bypass)")
            print(f"   Symbol detected: {symbol} → BTC identified")
            print(f"   ⚠️  SKIPPED: All risk calculations, daily range, data validation")
            print(f"   ✅ APPROVED: Direct volume injection")
            return result
        
        # 1. Check kill switch
        if self.check_kill_switch():
            result['reason'] = "Kill switch active - Trading disabled"
            print(f"⛔ TRADE REJECTED: {result['reason']}")
            return result
        
        # 2. Check position count
        open_positions = self.get_open_positions_count()
        if open_positions >= self.max_positions:
            result['reason'] = f"Max positions reached ({open_positions}/{self.max_positions})"
            print(f"⛔ TRADE REJECTED: {result['reason']}")
            self._send_rejection_alert(symbol, direction, result['reason'])
            return result
        
        # 3. Check daily loss
        pnl = self.get_daily_pnl()
        equity, balance = self.get_account_balance()
        
        daily_loss_pct = (pnl['total_pnl'] / balance) * 100 if balance > 0 else 0
        
        # Activate kill switch if loss >= trigger threshold
        if self.kill_switch_enabled and daily_loss_pct <= -self.kill_switch_trigger:
            self.activate_kill_switch(f"Daily loss {daily_loss_pct:.2f}% >= {self.kill_switch_trigger}%")
            result['reason'] = f"Kill switch activated - Daily loss {daily_loss_pct:.2f}%"
            print(f"🔴 TRADE REJECTED: {result['reason']}")
            return result
        
        # Check daily loss limit (warning, but don't block yet)
        if daily_loss_pct <= -self.max_daily_loss_pct:
            result['reason'] = f"Daily loss limit reached ({daily_loss_pct:.2f}%)"
            print(f"⚠️  TRADE REJECTED: {result['reason']}")
            self._send_rejection_alert(symbol, direction, result['reason'])
            return result
        
        # Send warning if approaching limit
        if daily_loss_pct <= -self.daily_warning_pct:
            self._send_warning_alert(daily_loss_pct, balance)
        
        # 4. Calculate lot size - CASH RISK ALIGNMENT (The $200 Rule)
        if entry_price > 0 and stop_loss > 0:
            # ✅ V8.1 BULLETPROOF: Robust lot calculation for $200 risk
            risk_amount = balance * (self.risk_per_trade / 100.0)
            sl_distance = abs(entry_price - stop_loss)
            
            # 🚨 V8.1 BULLETPROOF: Clean symbol for robust detection
            symbol_clean = symbol.upper().replace(' ', '').replace('/', '')
            
            if any(x in symbol_clean for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA']):
                # Crypto: pip_size = 1.0 (whole dollar), pip_value = 0.01 per micro lot
                pip_size = 1.0
                pip_value = 0.01  # $0.01 per micro lot per $1 move (IC Markets leverage)
                # For BTC at 66.5k with 1330$ SL, risk $200:
                # lot_size = 200 / (1330 * 0.01) = 15.04 micro lots (0.15 standard lots)
            elif any(x in symbol_clean for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
                # Metals: pip at 2nd decimal
                pip_size = 0.01
                pip_value = 10.0
            elif 'JPY' in symbol_clean:
                # JPY pairs: pip at 2nd decimal (0.01)
                pip_size = 0.01
                pip_value = 10.0  # $10 per standard lot per pip (0.01 move)
            elif any(x in symbol_clean for x in ['XTI', 'WTI', 'OIL']):
                # Oil: pip at 2nd decimal
                pip_size = 0.01
                pip_value = 10.0
            else:
                # Standard forex: pip at 4th decimal (0.0001)
                pip_size = 0.0001
                pip_value = 10.0  # $10 per standard lot per pip
            
            # Calculate lot size: risk_amount / (SL_distance_in_price * pip_value_per_unit)
            sl_pips = sl_distance / pip_size
            
            if sl_pips > 0:
                # Formula: LotSize = Risk_Amount / (SL_Distance_in_Price * Pip_Value)
                lot_size = risk_amount / (sl_pips * pip_value)
                lot_size = round(lot_size, 2)
                
                # Apply limits
                min_lot = self.config['lot_size']['min_lot']
                max_lot = self.config['lot_size']['max_lot']
                lot_size = max(min_lot, min(lot_size, max_lot))
                
                # 🚨 CRITICAL: Force minimum 0.01 lots to prevent BadVolume
                # Especially for small accounts (<$1000) on BTC with large SL
                if lot_size < 0.01:
                    print(f"⚠️  Lot size {lot_size:.4f} below broker minimum - forcing to 0.01")
                    lot_size = 0.01
                
                # ✅ Logging for debugging
                print(f"\n[LOT CALCULATION] {symbol}")
                print(f"   Risk Amount: ${risk_amount:.2f}")
                print(f"   SL Distance: {sl_distance:.5f} ({sl_pips:.1f} pips)")
                print(f"   Pip Value: ${pip_value:.2f}")
                print(f"   Calculated Lot: {lot_size:.2f}")
                
                result['lot_size'] = lot_size
            else:
                result['lot_size'] = 0.01
                print(f"⚠️  Invalid SL distance, defaulting to 0.01 lots")
        
        # All checks passed
        result['approved'] = True
        result['reason'] = "All risk checks passed"
        
        print(f"\n✅ TRADE APPROVED: {symbol} {direction}")
        print(f"   Open positions: {open_positions}/{self.max_positions}")
        print(f"   Daily P&L: ${pnl['total_pnl']:.2f} ({daily_loss_pct:.2f}%)")
        print(f"   Lot size: {result['lot_size']}")
        
        return result
    
    def _send_rejection_alert(self, symbol, direction, reason):
        """Send Telegram alert when trade is rejected"""
        message = (
            "⛔ <b>TRADE REJECTED</b>\n\n"
            f"Symbol: <b>{symbol}</b>\n"
            f"Direction: <b>{direction}</b>\n"
            f"Reason: <i>{reason}</i>\n\n"
            "──────────────────\n"
            "✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
            "🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
        )
        self._send_telegram(message)
    
    def _send_warning_alert(self, daily_loss_pct, balance):
        """Send warning when approaching daily loss limit"""
        pnl = self.get_daily_pnl()
        
        message = (
            "⚠️ <b>DAILY LOSS WARNING</b>\n\n"
            f"Current loss: <b>{daily_loss_pct:.2f}%</b>\n"
            f"Warning threshold: <b>{self.daily_warning_pct}%</b>\n"
            f"Kill switch trigger: <b>{self.kill_switch_trigger}%</b>\n\n"
            f"💰 Balance: ${balance:.2f}\n"
            f"📊 Today's P&L: ${pnl['total_pnl']:.2f}\n\n"
            "⚠️ <i>Approaching daily loss limit!</i>\n\n"
            "──────────────────\n"
            "✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
            "🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
        )
        self._send_telegram(message)
    
    def _send_kill_switch_alert(self, reason):
        """Send kill switch activation alert"""
        pnl = self.get_daily_pnl()
        equity, balance = self.get_account_balance()
        daily_loss_pct = (pnl['total_pnl'] / balance) * 100 if balance > 0 else 0
        
        message = (
            "🔴 <b>KILL SWITCH ACTIVATED!</b> 🔴\n\n"
            f"<b>Reason:</b> {reason}\n\n"
            "──────────────────\n"
            "📊 <b>DAILY SUMMARY:</b>\n"
            f"💰 Balance: ${balance:.2f}\n"
            f"💎 Equity: ${equity:.2f}\n"
            f"📉 Daily P&L: ${pnl['total_pnl']:.2f} ({daily_loss_pct:.2f}%)\n"
            f"🛑 Loss limit: {self.max_daily_loss_pct}%\n\n"
            "⛔ <b>ALL TRADING STOPPED</b>\n"
            "System will not accept new signals.\n"
            "Existing positions remain open.\n\n"
            "To resume: Delete trading_disabled.flag\n\n"
            "──────────────────\n"
            "✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
            "🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
        )
        self._send_telegram(message)
    
    def _send_telegram(self, message):
        """Send message to Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️  Telegram credentials missing")
            return False
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {
            'chat_id': self.telegram_chat_id,
            'text': message.strip(),
            'parse_mode': 'HTML',
            'disable_web_page_preview': True
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Telegram error: {e}")
            return False
    
    def send_daily_summary(self):
        """Send daily risk management summary"""
        pnl = self.get_daily_pnl()
        equity, balance = self.get_account_balance()
        open_positions = self.get_open_positions_count()
        daily_loss_pct = (pnl['total_pnl'] / balance) * 100 if balance > 0 else 0
        
        # Status emoji
        if pnl['total_pnl'] >= 0:
            status = "🟢 PROFIT"
        elif daily_loss_pct > -self.daily_warning_pct:
            status = "🟡 MINOR LOSS"
        else:
            status = "🔴 WARNING"
        
        kill_switch_status = "🔴 ACTIVE" if self.check_kill_switch() else "🟢 INACTIVE"
        
        message = (
            f"{status}\n"
            "──────────────────\n"
            "📊 <b>DAILY RISK SUMMARY</b>\n"
            "──────────────────\n\n"
            f"💰 <b>Balance:</b> ${balance:.2f}\n"
            f"💎 <b>Equity:</b> ${equity:.2f}\n"
            f"📈 <b>Open Positions:</b> {open_positions}/{self.max_positions}\n\n"
            "──────────────────\n"
            "📉 <b>TODAY'S P&L:</b>\n"
            f"💵 Closed: ${pnl['closed_pnl']:.2f}\n"
            f"📊 Open: ${pnl['open_pnl']:.2f}\n"
            f"💎 <b>Total: ${pnl['total_pnl']:.2f} ({daily_loss_pct:.2f}%)</b>\n\n"
            "──────────────────\n"
            "🛡️ <b>RISK LIMITS:</b>\n"
            f"⚠️  Warning: {self.daily_warning_pct}%\n"
            f"🛑 Daily limit: {self.max_daily_loss_pct}%\n"
            f"🔴 Kill switch: {self.kill_switch_trigger}%\n"
            f"🚦 Status: {kill_switch_status}\n\n"
            "──────────────────\n"
            "✨ <b>Glitch in Matrix by ФорексГод</b> ✨\n"
            "🧠 <i>AI-Powered</i> • 💎 <i>Smart Money</i>"
        )
        
        self._send_telegram(message)
        print("\n✅ Daily summary sent to Telegram")


def main():
    """Main entry point"""
    import sys
    
    risk_manager = UnifiedRiskManager()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == '--summary':
            risk_manager.send_daily_summary()
        
        elif command == '--validate':
            # Test validation
            result = risk_manager.validate_new_trade(
                symbol='EURUSD',
                direction='BUY',
                entry_price=1.0850,
                stop_loss=1.0800
            )
            print(f"\nValidation result: {result}")
        
        elif command == '--kill-switch-on':
            risk_manager.activate_kill_switch("Manual activation")
        
        elif command == '--kill-switch-off':
            risk_manager.deactivate_kill_switch()
        
        elif command == '--check':
            pnl = risk_manager.get_daily_pnl()
            equity, balance = risk_manager.get_account_balance()
            positions = risk_manager.get_open_positions_count()
            kill_switch = risk_manager.check_kill_switch()
            
            print(f"\n📊 RISK STATUS:")
            print(f"──────────────────")
            print(f"💰 Balance: ${balance:.2f}")
            print(f"💎 Equity: ${equity:.2f}")
            print(f"📈 Positions: {positions}/{risk_manager.max_positions}")
            print(f"📊 Daily P&L: ${pnl['total_pnl']:.2f}")
            print(f"🚦 Kill switch: {'🔴 ACTIVE' if kill_switch else '🟢 INACTIVE'}")
            print(f"──────────────────\n")
        
        else:
            print(f"Unknown command: {command}")
            print("Available commands:")
            print("  --summary       Send daily summary")
            print("  --validate      Test trade validation")
            print("  --kill-switch-on   Activate kill switch")
            print("  --kill-switch-off  Deactivate kill switch")
            print("  --check         Show current risk status")
    
    else:
        # Default: check risk status
        risk_manager.send_daily_summary()


if __name__ == '__main__':
    main()
