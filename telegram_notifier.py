"""
Telegram Notifier for ForexGod - ETM Signals
Sends trade alerts with screenshots and interactive buttons
NOW USES ChartGenerator FOR PROFESSIONAL WHITE CHARTS
"""

import os
import requests
import io
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from smc_detector import TradeSetup, CHoCH, FVG
from chart_generator import ChartGenerator

load_dotenv()


class TelegramNotifier:
    """Sends trading alerts to Telegram group"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Use ChartGenerator for professional white background charts
        self.chart_generator = ChartGenerator()
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
    
    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """Send text message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            response = requests.post(url, json=data)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
            return False
    
    def send_photo(self, photo_bytes: bytes, caption: str = "") -> bool:
        """Send photo to Telegram (raw bytes)"""
        try:
            url = f"{self.base_url}/sendPhoto"
            files = {"photo": photo_bytes}
            data = {
                "chat_id": self.chat_id,
                "caption": caption,
                "parse_mode": "Markdown"
            }
            response = requests.post(url, files=files, data=data)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error sending Telegram photo: {e}")
            return False
    
    def send_photo_file(self, file_path: str, caption: str = "") -> bool:
        """Send photo from file path"""
        try:
            if not os.path.exists(file_path):
                print(f"❌ Photo file not found: {file_path}")
                return False
            
            url = f"{self.base_url}/sendPhoto"
            with open(file_path, 'rb') as photo_file:
                files = {"photo": photo_file}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown"
                }
                response = requests.post(url, files=files, data=data)
            
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error sending Telegram photo from file: {e}")
            return False
    
    def send_setup_alert(
        self, 
        setup: TradeSetup, 
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame
    ) -> bool:
        """
        Send complete trade setup alert with:
        - Formatted message
        - Daily chart screenshot
        - 4H chart screenshot
        - Interactive buttons
        """
        # 1. Send main alert message
        message = self._format_setup_message(setup)
        print(f"[DEBUG] Sending setup alert for {setup.symbol} | status: {getattr(setup, 'status', None)}")
        if not self.send_message(message):
            print(f"[ERROR] Failed to send main message for {setup.symbol}")
            return False
        # 2. Generate and send Daily chart
        try:
            daily_chart = self._create_daily_chart(setup, df_daily)
            if daily_chart:
                print(f"[DEBUG] Daily chart generated for {setup.symbol}")
                self.send_photo(daily_chart, caption=f"📊 {setup.symbol} - Daily Timeframe")
            else:
                print(f"[ERROR] Daily chart NOT generated for {setup.symbol}")
        except Exception as e:
            print(f"[EXCEPTION] Error generating Daily chart for {setup.symbol}: {e}")
        # 3. Generate and send 4H chart
        try:
            h4_chart = self._create_4h_chart(setup, df_4h)
            if h4_chart:
                print(f"[DEBUG] 4H chart generated for {setup.symbol}")
                self.send_photo(h4_chart, caption=f"🔍 {setup.symbol} - 4H Timeframe")
            else:
                print(f"[ERROR] 4H chart NOT generated for {setup.symbol}")
        except Exception as e:
            print(f"[EXCEPTION] Error generating 4H chart for {setup.symbol}: {e}")
        # 4. Send interactive buttons
        self._send_action_buttons(setup)
        return True
    
    def _format_setup_message(self, setup: TradeSetup) -> str:
        """Format trade setup for Telegram message"""
        # Direction from Daily CHoCH (h4_choch may be None for MONITORING)
        direction = "🟢 LONG" if setup.daily_choch.direction == 'bullish' else "🔴 SHORT"
        emoji = "📈" if setup.daily_choch.direction == 'bullish' else "📉"
        
        # Status indicator
        if setup.status == 'READY':
            status_text = "✅ *READY TO EXECUTE*"
        else:
            status_text = "👀 *MONITORING* (waiting for entry)"
        
        # Strategy type indicator
        strategy_emoji = "🔥🚨" if setup.strategy_type == 'reversal' else "🎯"
        strategy_text = "*REVERSAL - MAJOR TREND CHANGE!*" if setup.strategy_type == 'reversal' else "*CONTINUATION - Pullback Entry*"
        
        # 4H CHoCH info
        if setup.h4_choch:
            h4_info = f"🔄 4H CHoCH: {setup.h4_choch.direction.upper()} @ {setup.h4_choch.break_price:.5f}"
        else:
            h4_info = "⏳ *Waiting for 4H confirmation*"
        
        # Calculate lot size (example: $10k account, 2% risk)
        account_balance = float(os.getenv('ACCOUNT_BALANCE', '10000'))
        risk_percent = float(os.getenv('RISK_PER_TRADE', '0.02'))
        risk_amount = account_balance * risk_percent
        
        pip_value = 10  # Standard for 1 lot forex
        stop_distance = abs(setup.entry_price - setup.stop_loss)
        lot_size = risk_amount / (stop_distance * pip_value * 100000)  # Rough calculation
        
        message = f"""
{strategy_emoji} *SETUP - {setup.symbol}* {strategy_emoji}
{direction} {emoji}

{status_text}
{strategy_text}

━━━━━━━━━━━━━━━━━━━━
📊 *DAILY ANALYSIS:*
CHoCH Direction: `{setup.daily_choch.direction.upper()}`
FVG Zone: `{setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}`

🔍 *4H STATUS:*
{h4_info}

━━━━━━━━━━━━━━━━━━━━
💰 *TRADE DETAILS:*
Entry: `{setup.entry_price:.5f}`
Stop Loss: `{setup.stop_loss:.5f}`
Take Profit: `{setup.take_profit:.5f}`

📊 Risk:Reward: `1:{setup.risk_reward:.2f}`
📦 Suggested Lot Size: `{lot_size:.2f}`
💵 Risk Amount: `${risk_amount:.2f}`

⭐ Priority: `{setup.priority}`
⏰ Setup Time: `{setup.setup_time.strftime('%Y-%m-%d %H:%M UTC')}`

━━━━━━━━━━━━━━━━━━━━
📊 *VIEW CHARTS:*
[📈 Daily Chart](https://www.tradingview.com/chart/?symbol={self._get_tv_symbol(setup.symbol)}&interval=D)
[🔍 4H Chart](https://www.tradingview.com/chart/?symbol={self._get_tv_symbol(setup.symbol)}&interval=240)

━━━━━━━━━━━━━━━━━━━━
✨ *Strategy by ForexGod* ✨
🧠 _Glitch in Matrix Trading System_
💎 _+ AI Validation_
"""
        
        return message.strip()
    
    def _get_tv_symbol(self, symbol: str) -> str:
        """Convert MT5 symbol to TradingView symbol format"""
        # Map common symbols to TradingView format
        tv_symbols = {
            "EURUSD": "FX:EURUSD",
            "GBPUSD": "FX:GBPUSD",
            "USDJPY": "FX:USDJPY",
            "USDCHF": "FX:USDCHF",
            "AUDUSD": "FX:AUDUSD",
            "USDCAD": "FX:USDCAD",
            "NZDUSD": "FX:NZDUSD",
            "EURJPY": "FX:EURJPY",
            "GBPJPY": "FX:GBPJPY",
            "EURGBP": "FX:EURGBP",
            "EURCAD": "FX:EURCAD",
            "AUDCAD": "FX:AUDCAD",
            "AUDNZD": "FX:AUDNZD",
            "NZDCAD": "FX:NZDCAD",
            "GBPNZD": "FX:GBPNZD",
            "GBPCHF": "FX:GBPCHF",
            "CADCHF": "FX:CADCHF",
            "XAUUSD": "TVC:GOLD",
            "BTCUSD": "BITSTAMP:BTCUSD",
            "USOIL": "TVC:USOIL",
            "XTIUSD": "TVC:USOIL"
        }
        
        return tv_symbols.get(symbol, f"FX:{symbol}")
    
    def _create_daily_chart(self, setup: TradeSetup, df: pd.DataFrame) -> Optional[bytes]:
        """Create Daily timeframe chart using ChartGenerator (professional white background)"""
        try:
            # Use ChartGenerator to create professional chart
            chart_bytes = self.chart_generator.create_daily_chart(
                symbol=setup.symbol,
                df=df,
                setup=setup,
                save_path=None  # Return bytes instead of saving
            )
            return chart_bytes
        except Exception as e:
            print(f"❌ Error creating Daily chart: {e}")
            return None
    
    def _create_4h_chart(self, setup: TradeSetup, df: pd.DataFrame) -> Optional[bytes]:
        """Create 4H timeframe chart using ChartGenerator (professional white background)"""
        try:
            # Use ChartGenerator to create professional chart
            chart_bytes = self.chart_generator.create_4h_chart(
                symbol=setup.symbol,
                df=df,
                setup=setup,
                save_path=None  # Return bytes instead of saving
            )
            return chart_bytes
        except Exception as e:
            print(f"❌ Error creating 4H chart: {e}")
            return None
    
    def _send_action_buttons(self, setup: TradeSetup) -> bool:
        """Send interactive buttons for Execute/Skip actions"""
        try:
            # Only send buttons for READY setups (have h4_choch)
            if not setup.h4_choch:
                return True  # Skip buttons for MONITORING setups
            
            url = f"{self.base_url}/sendMessage"            
            # Determine direction and format callback data
            direction = 'buy' if setup.h4_choch.direction == 'bullish' else 'sell'
            callback_data = f"execute_{setup.symbol}_{direction}_{setup.entry_price:.5f}_{setup.stop_loss:.5f}_{setup.take_profit:.5f}"
            
            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "✅ Execute Trade",
                            "callback_data": callback_data
                        },
                        {
                            "text": "⏭️ Skip",
                            "callback_data": "skip"
                        }
                    ],
                    [
                        {
                            "text": "❌ Close Position",
                            "callback_data": f"close_{setup.symbol}"
                        }
                    ]
                ]
            }
            
            data = {
                "chat_id": self.chat_id,
                "text": "🎯 *What would you like to do?*",
                "parse_mode": "Markdown",
                "reply_markup": keyboard
            }
            
            response = requests.post(url, json=data)
            return response.status_code == 200
        
        except Exception as e:
            print(f"❌ Error sending action buttons: {e}")
            return False
    
    def send_daily_summary(self, scanned_pairs: int, setups_found: int, active_setups: list = None) -> bool:
        """Send daily scan summary with ACTIVE monitoring setups"""
        message = f"""
📊 *Daily Scan Complete*

🔍 Pairs Scanned: `{scanned_pairs}`
🎯 New Setups Found: `{setups_found}`
📋 Total Active Setups: `{len(active_setups) if active_setups else 0}`
⏰ Scan Time: `{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}`
"""
        
        # Add active setups list
        if active_setups:
            message += "\n━━━━━━━━━━━━━━━━━━━━\n"
            message += "🎯 *ACTIVE MONITORING SETUPS:*\n\n"
            for setup in active_setups:
                symbol = setup.get('symbol', 'Unknown')
                dir_raw = str(setup.get('direction', '')).strip().lower()
                direction = "🟢 LONG" if dir_raw == 'buy' else ("🔴 SHORT" if dir_raw == 'sell' else dir_raw.upper())
                entry = setup.get('entry_price', 0)
                rr = setup.get('risk_reward', 0)
                message += f"• *{symbol}* - {direction}\n"
                message += f"  Entry: `{entry:.5f}` | R:R `1:{rr:.1f}`\n"
        
        message += """
━━━━━━━━━━━━━━━━━━━━
✨ *Strategy by ForexGod* ✨
🧠 _Glitch in Matrix Trading System_
💎 _+ AI Validation_
"""
        return self.send_message(message.strip())
    
    def send_error_alert(self, error_msg: str) -> bool:
        """Send error notification"""
        message = f"""
⚠️ *Scanner Error*

`{error_msg}`

⏰ Time: `{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}`
"""
        return self.send_message(message.strip())
    
    def test_connection(self) -> bool:
        """Test Telegram bot connection"""
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url)
            
            if response.status_code == 200:
                bot_info = response.json()
                print(f"✅ Telegram bot connected: @{bot_info['result']['username']}")
                return True
            else:
                print(f"❌ Telegram bot connection failed: {response.text}")
                return False
        
        except Exception as e:
            print(f"❌ Error testing Telegram connection: {e}")
            return False


if __name__ == "__main__":
    """Test Telegram notifier"""
    print("🧪 Testing Telegram Notifier...")
    
    notifier = TelegramNotifier()
    
    if notifier.test_connection():
        notifier.send_message("🚀 *ForexGod - ETM Signals Bot*\n\nBot is online and ready!")
        print("✅ Test message sent successfully!")
    else:
        print("❌ Telegram connection test failed!")
