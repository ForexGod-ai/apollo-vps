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
        """Send photo to Telegram"""
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
        
        if not self.send_message(message):
            return False
        
        # 2. Generate and send Daily chart
        daily_chart = self._create_daily_chart(setup, df_daily)
        if daily_chart:
            self.send_photo(daily_chart, caption=f"📊 {setup.symbol} - Daily Timeframe")
        
        # 3. Generate and send 4H chart
        h4_chart = self._create_4h_chart(setup, df_4h)
        if h4_chart:
            self.send_photo(h4_chart, caption=f"🔍 {setup.symbol} - 4H Timeframe")
        
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
🎯 *ForexGod - Glitch Strategy*
_Glitch in Matrix_ 🔥
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
            "USOIL": "TVC:USOIL"
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
    
    def send_daily_summary(self, scanned_pairs: int, setups_found: int) -> bool:
        """Send daily scan summary"""
        message = f"""
📊 *Daily Scan Complete*

🔍 Pairs Scanned: `{scanned_pairs}`
🎯 Setups Found: `{setups_found}`
⏰ Scan Time: `{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}`

━━━━━━━━━━━━━━━━━━━━
🔥 *ForexGod - Glitch Signals*
_Next scan in 24 hours_
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
