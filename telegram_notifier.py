"""
Telegram Notifier for ForexGod - ETM Signals
Sends trade alerts with screenshots and interactive buttons
"""

import os
import requests
import io
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
import pandas as pd
from smc_detector import TradeSetup, CHoCH, FVG

load_dotenv()


class TelegramNotifier:
    """Sends trading alerts to Telegram group"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
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
        """Create Daily timeframe chart with CHoCH and FVG marked"""
        try:
            # Set style
            plt.style.use('dark_background')
            
            fig, ax = plt.subplots(figsize=(14, 7))
            fig.patch.set_facecolor('#0B0E11')
            ax.set_facecolor('#131722')
            
            # Plot candlesticks with better colors
            for i in range(len(df)):
                is_bullish = df['close'].iloc[i] >= df['open'].iloc[i]
                body_color = '#26a69a' if is_bullish else '#ef5350'
                wick_color = '#26a69a' if is_bullish else '#ef5350'
                
                # Candle body (thicker)
                body_height = abs(df['close'].iloc[i] - df['open'].iloc[i])
                body_bottom = min(df['open'].iloc[i], df['close'].iloc[i])
                
                ax.add_patch(plt.Rectangle((i - 0.3, body_bottom), 0.6, body_height,
                                          facecolor=body_color, edgecolor=body_color, linewidth=0))
                
                # Candle wick (thinner)
                ax.plot([i, i], [df['low'].iloc[i], df['high'].iloc[i]], 
                       color=wick_color, linewidth=1, alpha=0.8)
            
            # Mark CHoCH with emphasis
            choch_idx = setup.daily_choch.index
            ax.axhline(y=setup.daily_choch.break_price, color='#FF9800', 
                      linestyle='--', linewidth=2.5, label='CHoCH Level', alpha=0.9, zorder=5)
            ax.scatter(choch_idx, df['close'].iloc[choch_idx], 
                      color='#FF9800', s=300, marker='*', zorder=10, 
                      edgecolors='white', linewidths=1.5, label='CHoCH Break')
            
            # Mark FVG zone with gradient effect
            from matplotlib.patches import Rectangle
            fvg_width = len(df) - setup.fvg.index + 5
            fvg_rect = Rectangle((setup.fvg.index - 5, setup.fvg.bottom),
                                width=fvg_width,
                                height=setup.fvg.top - setup.fvg.bottom,
                                facecolor='#2196F3', alpha=0.25, 
                                edgecolor='#2196F3', linewidth=2.5, 
                                linestyle='--', label='FVG Zone', zorder=4)
            ax.add_patch(fvg_rect)
            
            # Add FVG middle line
            ax.axhline(y=setup.fvg.middle, color='#2196F3', 
                      linestyle=':', linewidth=1.5, alpha=0.6, zorder=5)
            
            # Labels and styling
            ax.set_title(f'{setup.symbol} - Daily Timeframe - Glitch in Matrix', 
                        color='#E0E3EB', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Candles', color='#787B86', fontsize=12, labelpad=10)
            ax.set_ylabel('Price', color='#787B86', fontsize=12, labelpad=10)
            ax.tick_params(colors='#787B86', labelsize=10)
            
            # Legend with better styling
            legend = ax.legend(loc='upper left', facecolor='#1E222D', edgecolor='#2962FF', 
                             labelcolor='#D1D4DC', fontsize=10, framealpha=0.95)
            legend.get_frame().set_linewidth(1.5)
            
            # Grid
            ax.grid(True, alpha=0.15, color='#363A45', linestyle='-', linewidth=0.5)
            ax.set_axisbelow(True)
            
            # Add price annotations
            bbox_props = dict(boxstyle='round,pad=0.5', facecolor='#2962FF', edgecolor='none', alpha=0.8)
            ax.annotate(f'CHoCH: {setup.daily_choch.break_price:.5f}', 
                       xy=(choch_idx, setup.daily_choch.break_price),
                       xytext=(10, 20), textcoords='offset points',
                       fontsize=9, color='white', weight='bold',
                       bbox=bbox_props, arrowprops=dict(arrowstyle='->', color='#FF9800', lw=1.5))
            
            # Save to bytes
            buf = io.BytesIO()
            plt.tight_layout()
            plt.savefig(buf, format='png', facecolor='#0B0E11', dpi=200, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            return buf.getvalue()
        
        except Exception as e:
            print(f"❌ Error creating Daily chart: {e}")
            return None
    
    def _create_4h_chart(self, setup: TradeSetup, df: pd.DataFrame) -> Optional[bytes]:
        """Create 4H timeframe chart with microtrend and CHoCH"""
        try:
            # Set style
            plt.style.use('dark_background')
            
            fig, ax = plt.subplots(figsize=(14, 7))
            fig.patch.set_facecolor('#0B0E11')
            ax.set_facecolor('#131722')
            
            # Plot candlesticks with better colors
            for i in range(len(df)):
                is_bullish = df['close'].iloc[i] >= df['open'].iloc[i]
                body_color = '#26a69a' if is_bullish else '#ef5350'
                wick_color = '#26a69a' if is_bullish else '#ef5350'
                
                # Candle body
                body_height = abs(df['close'].iloc[i] - df['open'].iloc[i])
                body_bottom = min(df['open'].iloc[i], df['close'].iloc[i])
                
                ax.add_patch(plt.Rectangle((i - 0.3, body_bottom), 0.6, body_height,
                                          facecolor=body_color, edgecolor=body_color, linewidth=0))
                
                # Candle wick
                ax.plot([i, i], [df['low'].iloc[i], df['high'].iloc[i]], 
                       color=wick_color, linewidth=1, alpha=0.8)
            
            # Mark FVG zone from Daily (translucent)
            fvg_start = max(0, setup.h4_choch.index - 50)
            fvg_rect = Rectangle((fvg_start, setup.fvg.bottom),
                                width=len(df) - fvg_start,
                                height=setup.fvg.top - setup.fvg.bottom,
                                facecolor='#2196F3', alpha=0.15, 
                                edgecolor='#2196F3', linewidth=2, 
                                linestyle='--', label='Daily FVG Zone', zorder=3)
            ax.add_patch(fvg_rect)
            
            # Mark 4H CHoCH with star
            choch_idx = setup.h4_choch.index
            ax.scatter(choch_idx, df['close'].iloc[choch_idx], 
                      color='#9C27B0', s=300, marker='*', zorder=10, 
                      edgecolors='white', linewidths=1.5, label='4H CHoCH (Reversal)')
            
            # Mark entry, SL, TP with clear lines
            ax.axhline(y=setup.entry_price, color='#4CAF50', 
                      linestyle='-', linewidth=2.5, label='Entry', alpha=0.9, zorder=5)
            ax.axhline(y=setup.stop_loss, color='#F44336', 
                      linestyle='--', linewidth=2, label='Stop Loss', alpha=0.9, zorder=5)
            ax.axhline(y=setup.take_profit, color='#FFC107', 
                      linestyle='--', linewidth=2, label='Take Profit', alpha=0.9, zorder=5)
            
            # Labels and styling
            ax.set_title(f'{setup.symbol} - 4H Timeframe - Entry Confirmation', 
                        color='#E0E3EB', fontsize=16, fontweight='bold', pad=20)
            ax.set_xlabel('Candles', color='#787B86', fontsize=12, labelpad=10)
            ax.set_ylabel('Price', color='#787B86', fontsize=12, labelpad=10)
            ax.tick_params(colors='#787B86', labelsize=10)
            
            # Legend
            legend = ax.legend(loc='upper left', facecolor='#1E222D', edgecolor='#2962FF', 
                             labelcolor='#D1D4DC', fontsize=9, framealpha=0.95)
            legend.get_frame().set_linewidth(1.5)
            
            # Grid
            ax.grid(True, alpha=0.15, color='#363A45', linestyle='-', linewidth=0.5)
            ax.set_axisbelow(True)
            
            # Add annotations for Entry/SL/TP
            bbox_props_entry = dict(boxstyle='round,pad=0.5', facecolor='#4CAF50', edgecolor='none', alpha=0.8)
            bbox_props_sl = dict(boxstyle='round,pad=0.5', facecolor='#F44336', edgecolor='none', alpha=0.8)
            bbox_props_tp = dict(boxstyle='round,pad=0.5', facecolor='#FFC107', edgecolor='none', alpha=0.8)
            
            # Position annotations on the right side
            ax.text(len(df) - 1, setup.entry_price, f' Entry: {setup.entry_price:.5f}', 
                   verticalalignment='center', fontsize=9, color='white', weight='bold',
                   bbox=bbox_props_entry)
            ax.text(len(df) - 1, setup.stop_loss, f' SL: {setup.stop_loss:.5f}', 
                   verticalalignment='center', fontsize=9, color='white', weight='bold',
                   bbox=bbox_props_sl)
            ax.text(len(df) - 1, setup.take_profit, f' TP: {setup.take_profit:.5f}', 
                   verticalalignment='center', fontsize=9, color='white', weight='bold',
                   bbox=bbox_props_tp)
            
            # Save to bytes
            buf = io.BytesIO()
            plt.tight_layout()
            plt.savefig(buf, format='png', facecolor='#0B0E11', dpi=200, bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            return buf.getvalue()
        
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
