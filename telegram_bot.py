"""
Telegram Bot with command handlers and button callbacks
"""
import os
import time
from dotenv import load_dotenv
from loguru import logger
import requests
import json
from mt5_executor import MT5Executor
from smc_detector import TradeSetup

load_dotenv()


class TelegramBot:
    """Telegram bot that listens for commands and button presses"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.last_update_id = 0
        self.mt5_executor = None
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
    
    def send_message(self, text: str, reply_markup=None) -> bool:
        """Send message to Telegram"""
        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            if reply_markup:
                data["reply_markup"] = json.dumps(reply_markup)
            
            response = requests.post(url, json=data)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False
    
    def get_updates(self, timeout=30):
        """Get updates from Telegram (long polling)"""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {
                "offset": self.last_update_id + 1,
                "timeout": timeout
            }
            response = requests.get(url, params=params, timeout=timeout + 5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok') and data.get('result'):
                    return data['result']
            return []
        except Exception as e:
            logger.error(f"Error getting updates: {e}")
            return []
    
    def handle_callback(self, callback_query):
        """Handle button press callbacks"""
        try:
            callback_id = callback_query['id']
            data = callback_query.get('data', '')
            user = callback_query['from']
            
            logger.info(f"📲 Callback from {user.get('first_name')}: {data}")
            
            # Answer callback to remove loading state
            self._answer_callback(callback_id)
            
            if data.startswith('execute_'):
                # Parse: execute_EURUSD_buy_1.0850_1.0820_1.0920
                parts = data.split('_')
                if len(parts) >= 6:
                    symbol = parts[1]
                    direction = parts[2]  # 'buy' or 'sell'
                    entry = float(parts[3])
                    sl = float(parts[4])
                    tp = float(parts[5])
                    
                    # Execute trade on MT5
                    result = self._execute_trade(symbol, direction, entry, sl, tp)
                    
                    if result['success']:
                        self.send_message(
                            f"✅ *Trade Executed!*\n\n"
                            f"Symbol: {symbol}\n"
                            f"Order: #{result['order']}\n"
                            f"Direction: {direction.upper()}\n"
                            f"Entry: {entry}\n"
                            f"SL: {sl}\n"
                            f"TP: {tp}\n"
                            f"Volume: {result['volume']} lots"
                        )
                    else:
                        self.send_message(f"❌ Trade failed: {result['error']}")
            
            elif data == 'skip':
                self.send_message("⏭️ Setup skipped. Waiting for next opportunity...")
            
            elif data.startswith('close_'):
                # Parse: close_EURUSD
                symbol = data.replace('close_', '')
                result = self._close_position(symbol)
                
                if result['success']:
                    self.send_message(
                        f"✅ *Position Closed!*\n\n"
                        f"Symbol: {symbol}\n"
                        f"P&L: {result['profit']:.2f} USD"
                    )
                else:
                    self.send_message(f"❌ Close failed: {result['error']}")
        
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            self.send_message(f"❌ Error: {str(e)}")
    
    def _answer_callback(self, callback_id):
        """Answer callback query to remove loading state"""
        try:
            url = f"{self.base_url}/answerCallbackQuery"
            requests.post(url, json={"callback_query_id": callback_id})
        except:
            pass
    
    def _execute_trade(self, symbol: str, direction: str, entry: float, sl: float, tp: float):
        """Execute trade on MT5"""
        try:
            if not self.mt5_executor:
                self.mt5_executor = MT5Executor()
                if not self.mt5_executor.connect():
                    return {"success": False, "error": "MT5 connection failed"}
            
            # Calculate volume (1% risk)
            volume = 0.01  # Default minimal
            
            # Execute order
            if direction == 'buy':
                result = self.mt5_executor.execute_buy(symbol, volume, sl, tp)
            else:
                result = self.mt5_executor.execute_sell(symbol, volume, sl, tp)
            
            if result and result.retcode == 10009:  # TRADE_RETCODE_DONE
                return {
                    "success": True,
                    "order": result.order,
                    "volume": volume
                }
            else:
                error_msg = f"MT5 error code {result.retcode if result else 'unknown'}"
                return {"success": False, "error": error_msg}
        
        except Exception as e:
            logger.error(f"Execute trade error: {e}")
            return {"success": False, "error": str(e)}
    
    def _close_position(self, symbol: str):
        """Close open position"""
        try:
            if not self.mt5_executor:
                self.mt5_executor = MT5Executor()
                if not self.mt5_executor.connect():
                    return {"success": False, "error": "MT5 connection failed"}
            
            result = self.mt5_executor.close_position(symbol)
            
            if result['success']:
                return {
                    "success": True,
                    "profit": result.get('profit', 0.0)
                }
            else:
                return {"success": False, "error": result.get('error', 'Unknown error')}
        
        except Exception as e:
            logger.error(f"Close position error: {e}")
            return {"success": False, "error": str(e)}
    
    def handle_command(self, message):
        """Handle text commands"""
        try:
            text = message.get('text', '')
            chat_id = message['chat']['id']
            
            # Only respond in configured group
            if str(chat_id) != str(self.chat_id):
                return
            
            if text.startswith('/start'):
                self.send_message(
                    "🤖 *ForexGod - Glitch in Matrix Bot*\n\n"
                    "Bot is active and monitoring markets.\n"
                    "You'll receive alerts when setups are detected.\n\n"
                    "Commands:\n"
                    "/status - Check bot status\n"
                    "/help - Show this message"
                )
            
            elif text.startswith('/status'):
                # Check MT5 connection
                if not self.mt5_executor:
                    self.mt5_executor = MT5Executor()
                
                mt5_status = "✅ Connected" if self.mt5_executor.connect() else "❌ Disconnected"
                
                self.send_message(
                    f"📊 *Bot Status*\n\n"
                    f"Telegram: ✅ Active\n"
                    f"MT5: {mt5_status}\n"
                    f"Scanner: ✅ Running\n"
                    f"Dashboard: http://127.0.0.1:5001"
                )
            
            elif text.startswith('/help'):
                self.send_message(
                    "📖 *Help*\n\n"
                    "This bot automatically scans for Glitch in Matrix setups.\n\n"
                    "When a setup is detected:\n"
                    "1. You'll receive an alert with charts\n"
                    "2. Click [Execute] to open trade on MT5\n"
                    "3. Click [Skip] to ignore\n"
                    "4. Click [Close Position] to close manually\n\n"
                    "Scans run daily at 08:00 AM."
                )
        
        except Exception as e:
            logger.error(f"Error handling command: {e}")
    
    def start(self):
        """Start bot (blocking)"""
        logger.info(f"🤖 Telegram bot started. Listening for updates...")
        logger.info(f"Chat ID: {self.chat_id}")
        
        while True:
            try:
                updates = self.get_updates()
                
                for update in updates:
                    self.last_update_id = update['update_id']
                    
                    # Handle callback queries (button presses)
                    if 'callback_query' in update:
                        self.handle_callback(update['callback_query'])
                    
                    # Handle text messages (commands)
                    elif 'message' in update:
                        self.handle_command(update['message'])
                
                time.sleep(0.1)  # Small delay to prevent hammering API
            
            except KeyboardInterrupt:
                logger.info("Bot stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in bot loop: {e}")
                time.sleep(5)  # Wait before retry


if __name__ == "__main__":
    bot = TelegramBot()
    bot.start()
