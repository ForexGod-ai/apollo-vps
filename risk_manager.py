#!/usr/bin/env python3
"""
Risk Management Monitor - Daily Loss Limit & Exposure Tracking
Monitors daily P&L and sends alerts when approaching limits
"""
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

class RiskManager:
    def __init__(self):
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Risk limits (configurabile)
        self.daily_loss_limit = -500  # Max loss per day in $
        self.daily_loss_warning = -350  # Warning threshold
        self.max_open_trades = 5
        self.max_exposure_per_currency = 0.30  # 30% of account
        
        self.trade_history_file = Path('trade_history.json')
        
    def load_data(self):
        """Load trade history and account data"""
        if not self.trade_history_file.exists():
            print('❌ trade_history.json not found!')
            return None
        
        return json.loads(self.trade_history_file.read_text())
    
    def calculate_daily_pnl(self, data):
        """Calculate P&L for today"""
        today = datetime.now().date()
        
        # Closed trades today
        closed_today = [
            t for t in data.get('closed_trades', [])
            if 'close_time' in t and datetime.fromisoformat(t['close_time']).date() == today
        ]
        
        closed_pnl = sum(float(t.get('profit', 0)) for t in closed_today)
        
        # Open P&L
        open_pnl = float(data.get('account', {}).get('open_pl', 0))
        
        total_pnl = closed_pnl + open_pnl
        
        return {
            'closed_pnl': closed_pnl,
            'open_pnl': open_pnl,
            'total_pnl': total_pnl,
            'closed_trades': len(closed_today)
        }
    
    def calculate_exposure(self, data):
        """Calculate exposure per currency"""
        open_trades = data.get('open_trades', [])
        account_balance = float(data.get('account', {}).get('balance', 10000))
        
        exposure = {}
        
        for trade in open_trades:
            symbol = trade.get('symbol', '')
            lot_size = float(trade.get('lot_size', 0))
            
            # Extract currencies from symbol (e.g., EURUSD -> EUR, USD)
            if len(symbol) >= 6:
                base = symbol[:3]
                quote = symbol[3:6]
                
                # Calculate exposure value (simplified)
                exposure_value = lot_size * 100000  # Standard lot
                
                exposure[base] = exposure.get(base, 0) + exposure_value
                exposure[quote] = exposure.get(quote, 0) + exposure_value
        
        # Calculate percentage
        exposure_pct = {
            currency: (value / account_balance) 
            for currency, value in exposure.items()
        }
        
        return exposure_pct
    
    def check_risk_limits(self):
        """Check all risk limits and send alerts if needed"""
        data = self.load_data()
        if not data:
            return
        
        # Calculate daily P&L
        pnl = self.calculate_daily_pnl(data)
        
        # Calculate exposure
        exposure = self.calculate_exposure(data)
        
        # Check open trades count
        open_trades_count = len(data.get('open_trades', []))
        
        # Build alert message
        alerts = []
        alert_level = 'INFO'
        
        # Check daily loss limit
        if pnl['total_pnl'] <= self.daily_loss_limit:
            alerts.append(f"🚨 <b>DAILY LOSS LIMIT REACHED!</b>")
            alerts.append(f"   Current: ${pnl['total_pnl']:.2f}")
            alerts.append(f"   Limit: ${self.daily_loss_limit:.2f}")
            alerts.append(f"   ⚠️ <b>STOP TRADING FOR TODAY!</b>")
            alert_level = 'CRITICAL'
        elif pnl['total_pnl'] <= self.daily_loss_warning:
            alerts.append(f"⚠️ <b>APPROACHING DAILY LOSS LIMIT</b>")
            alerts.append(f"   Current: ${pnl['total_pnl']:.2f}")
            alerts.append(f"   Warning: ${self.daily_loss_warning:.2f}")
            alerts.append(f"   Limit: ${self.daily_loss_limit:.2f}")
            alert_level = 'WARNING'
        
        # Check exposure per currency
        high_exposure = {curr: pct for curr, pct in exposure.items() if pct > self.max_exposure_per_currency}
        if high_exposure:
            alerts.append(f"\n⚠️ <b>HIGH CURRENCY EXPOSURE:</b>")
            for curr, pct in high_exposure.items():
                alerts.append(f"   {curr}: {pct*100:.1f}% (max: {self.max_exposure_per_currency*100:.0f}%)")
            if alert_level == 'INFO':
                alert_level = 'WARNING'
        
        # Check open trades count
        if open_trades_count >= self.max_open_trades:
            alerts.append(f"\n⚠️ <b>MAX OPEN TRADES REACHED</b>")
            alerts.append(f"   Current: {open_trades_count}/{self.max_open_trades}")
            if alert_level == 'INFO':
                alert_level = 'WARNING'
        
        # Send alert if needed
        if alerts:
            self.send_alert(alert_level, alerts, pnl, exposure, open_trades_count)
        else:
            print("✅ All risk limits OK")
    
    def send_daily_risk_report(self):
        """Send daily risk management report"""
        data = self.load_data()
        if not data:
            return
        
        pnl = self.calculate_daily_pnl(data)
        exposure = self.calculate_exposure(data)
        open_trades_count = len(data.get('open_trades', []))
        account = data.get('account', {})
        
        # Status emoji
        if pnl['total_pnl'] >= 0:
            status_emoji = "🟢"
            status_text = "PROFIT"
        elif pnl['total_pnl'] > self.daily_loss_warning:
            status_emoji = "🟡"
            status_text = "MINOR LOSS"
        else:
            status_emoji = "🔴"
            status_text = "WARNING"
        
        message = f"""
{status_emoji} <b>DAILY RISK REPORT</b> {status_emoji}

📊 <b>P&L STATUS:</b>
━━━━━━━━━━━━━━━━━━━━━━━━
💰 <b>Closed P/L:</b> ${pnl['closed_pnl']:.2f}
📊 <b>Open P/L:</b> ${pnl['open_pnl']:.2f}
💎 <b>Total Daily P/L:</b> ${pnl['total_pnl']:.2f}
📈 <b>Status:</b> {status_text}

⚠️ <b>RISK LIMITS:</b>
━━━━━━━━━━━━━━━━━━━━━━━━
🛑 <b>Daily Loss Limit:</b> ${self.daily_loss_limit:.2f}
⚠️ <b>Warning Level:</b> ${self.daily_loss_warning:.2f}
📊 <b>Distance to Limit:</b> ${abs(pnl['total_pnl'] - self.daily_loss_limit):.2f}

📈 <b>EXPOSURE:</b>
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        if exposure:
            for curr, pct in sorted(exposure.items(), key=lambda x: x[1], reverse=True)[:5]:
                warning = " ⚠️" if pct > self.max_exposure_per_currency else ""
                message += f"{curr}: {pct*100:.1f}%{warning}\n"
        else:
            message += "No open positions\n"
        
        message += f"""
━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>ACCOUNT:</b>
💰 Balance: ${account.get('balance', 0):.2f}
💎 Equity: ${account.get('equity', 0):.2f}
📈 Open Trades: {open_trades_count}/{self.max_open_trades}

━━━━━━━━━━━━━━━━━━━━━━━━
✨ <b>Risk Manager</b> by ФорексГод ✨
🛡️ Protecting Your Capital
━━━━━━━━━━━━━━━━━━━━━━━━
"""
        
        self._send_telegram(message)
        print("✅ Daily risk report sent")
    
    def send_alert(self, level, alerts, pnl, exposure, open_trades):
        """Send risk alert to Telegram"""
        emoji_map = {
            'INFO': '🔵',
            'WARNING': '🟡',
            'CRITICAL': '🔴'
        }
        
        emoji = emoji_map.get(level, '🔵')
        
        message = f"""
{emoji} <b>RISK ALERT - {level}</b> {emoji}

"""
        message += '\n'.join(alerts)
        
        message += f"""

━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>CURRENT STATUS:</b>
💰 Closed P/L: ${pnl['closed_pnl']:.2f}
📊 Open P/L: ${pnl['open_pnl']:.2f}
💎 Total: ${pnl['total_pnl']:.2f}
📈 Open Trades: {open_trades}

━━━━━━━━━━━━━━━━━━━━━━━━
✨ <b>Risk Manager</b> by ФорексГод ✨
"""
        
        self._send_telegram(message)
        print(f"⚠️ {level} alert sent!")
    
    def _send_telegram(self, message):
        """Send message to Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("⚠️ Telegram credentials missing")
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


def main():
    """Main entry point"""
    import sys
    
    risk_manager = RiskManager()
    
    if len(sys.argv) > 1 and sys.argv[1] == '--report':
        risk_manager.send_daily_risk_report()
    else:
        risk_manager.check_risk_limits()


if __name__ == '__main__':
    main()
