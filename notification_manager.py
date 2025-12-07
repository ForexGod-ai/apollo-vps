"""
Notification Manager - Trimite alerte pentru setup-uri bune de trading
"""
from loguru import logger
from datetime import datetime
import os
import requests
import subprocess
import platform
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class NotificationManager:
    """Gestionează notificările pentru alertele de trading"""
    
    def __init__(self):
        self.telegram_enabled = os.getenv('TELEGRAM_ENABLED', 'False').lower() == 'true'
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID', '')
        self.desktop_notifications = os.getenv('DESKTOP_NOTIFICATIONS', 'True').lower() == 'true'
        
        logger.info("📢 Notification Manager inițializat")
        if self.telegram_enabled:
            logger.info(f"✅ Telegram notifications: ENABLED")
        if self.desktop_notifications:
            logger.info(f"✅ Desktop notifications: ENABLED")
    
    def send_trade_alert(self, signal_data, ai_validation=None, risk_assessment=None, execution_result=None):
        """
        Trimite alertă pentru un setup de trading bun
        
        Args:
            signal_data: Date semnal original
            ai_validation: Rezultat validare AI
            risk_assessment: Rezultat money management
            execution_result: Rezultat executare trade (optional)
        """
        logger.info("📢 Trimit alertă pentru setup de trading...")
        
        # Construiește mesajul
        message = self._build_alert_message(signal_data, ai_validation, risk_assessment, execution_result)
        
        # Trimite pe toate canalele activate
        success = False
        
        if self.telegram_enabled:
            success = self._send_telegram(message) or success
        
        if self.desktop_notifications:
            success = self._send_desktop_notification(signal_data, message) or success
        
        if not success:
            logger.warning("⚠️ Nici un canal de notificare nu a funcționat!")
        
        return success
    
    def _build_alert_message(self, signal_data, ai_validation, risk_assessment, execution_result=None):
        """Construiește mesaj frumos pentru alertă"""
        
        action = signal_data.get('action', '').upper()
        symbol = signal_data.get('symbol', 'N/A')
        price = signal_data.get('price', 0)
        stop_loss = signal_data.get('stop_loss', 0)
        take_profit = signal_data.get('take_profit', 0)
        
        # Emoji pentru acțiune
        emoji = "🟢" if action == "BUY" else "🔴" if action == "SELL" else "⚪"
        
        # Header
        message = f"{emoji} *SETUP DE TRADING GĂSIT!* {emoji}\n\n"
        
        # Detalii trade
        message += f"📊 *Simbol:* {symbol}\n"
        message += f"🎯 *Acțiune:* {action}\n"
        message += f"💰 *Preț Entry:* {price}\n"
        
        if stop_loss:
            message += f"🛑 *Stop Loss:* {stop_loss}\n"
        if take_profit:
            message += f"🎯 *Take Profit:* {take_profit}\n"
        
        # Risk/Reward
        if stop_loss and take_profit and price:
            if action == "BUY":
                risk = abs(price - stop_loss)
                reward = abs(take_profit - price)
            else:
                risk = abs(stop_loss - price)
                reward = abs(price - take_profit)
            
            if risk > 0:
                rr_ratio = reward / risk
                message += f"⚖️ *Risk/Reward:* 1:{rr_ratio:.2f}\n"
        
        message += "\n"
        
        # Validare AI
        if ai_validation:
            confidence = ai_validation.get('confidence', 0)
            message += f"🤖 *AI Confidence:* {confidence:.1%}\n"
            
            if ai_validation.get('score'):
                message += f"📈 *AI Score:* {ai_validation['score']:.2f}/10\n"
        
        # Money Management
        if risk_assessment:
            position_size = risk_assessment.get('position_size', 0)
            risk_amount = risk_assessment.get('risk_amount', 0)
            risk_percent = risk_assessment.get('risk_percent', 0)
            
            message += f"\n💼 *Position Size:* {position_size} lots\n"
            message += f"📉 *Risk Amount:* ${risk_amount:.2f}\n"
            message += f"📊 *Risk Percent:* {risk_percent:.1%}\n"
        
        # Metadata
        if 'metadata' in signal_data:
            metadata = signal_data['metadata']
            message += f"\n📊 *Indicatori:*\n"
            if 'rsi' in metadata:
                message += f"   RSI: {metadata['rsi']:.1f}\n"
            if 'macd' in metadata:
                message += f"   MACD: {metadata['macd']:.4f}\n"
            if 'volume' in metadata:
                message += f"   Volume: {metadata['volume']}\n"
        
        # Timestamp
        message += f"\n🕐 *Timp:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # Execution status
        if execution_result:
            if execution_result.get('success'):
                message += f"\n✅ *EXECUTAT AUTOMAT în cTrader*\n"
                message += f"🎫 *Ticket:* {execution_result.get('ticket')}\n"
            else:
                message += f"\n⚠️ *Execuție eșuată:* {execution_result.get('error')}\n"
                message += f"✅ *Execută manual!*"
        else:
            # Call to action
            message += f"\n✅ *Verifică chart-ul și execută manual!*"
        
        return message
    
    def _send_telegram(self, message):
        """Trimite mesaj pe Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.warning("⚠️ Telegram credentials lipsă!")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            payload = {
                'chat_id': self.telegram_chat_id,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                logger.info("✅ Telegram notification trimisă!")
                return True
            else:
                logger.error(f"❌ Telegram error: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Eroare Telegram: {e}")
            return False
    
    def _send_desktop_notification(self, signal_data, message):
        """Trimite notificare desktop (macOS/Windows/Linux)"""
        try:
            action = signal_data.get('action', '').upper()
            symbol = signal_data.get('symbol', 'N/A')
            title = f"🎯 Setup {action} - {symbol}"
            
            # Mesaj scurt pentru desktop
            price = signal_data.get('price', 0)
            body = f"Preț: {price}"
            
            if platform.system() == 'Darwin':  # macOS
                self._send_macos_notification(title, body)
            elif platform.system() == 'Windows':
                self._send_windows_notification(title, body)
            else:  # Linux
                self._send_linux_notification(title, body)
            
            logger.info("✅ Desktop notification trimisă!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Eroare desktop notification: {e}")
            return False
    
    def _send_macos_notification(self, title, message):
        """Notificare macOS"""
        script = f'''
        display notification "{message}" with title "{title}" sound name "Glass"
        '''
        subprocess.run(['osascript', '-e', script], check=True)
    
    def _send_windows_notification(self, title, message):
        """Notificare Windows"""
        try:
            from win10toast import ToastNotifier
            toaster = ToastNotifier()
            toaster.show_toast(title, message, duration=10, threaded=True)
        except ImportError:
            logger.warning("win10toast nu este instalat!")
    
    def _send_linux_notification(self, title, message):
        """Notificare Linux"""
        subprocess.run(['notify-send', title, message], check=True)
    
    def send_summary_alert(self, stats):
        """Trimite rezumat periodic cu statistici"""
        message = f"📊 *REZUMAT TRADING*\n\n"
        message += f"📥 Semnale primite: {stats.get('total_received', 0)}\n"
        message += f"✅ Aprobate de AI: {stats.get('approved', 0)}\n"
        message += f"❌ Respinse: {stats.get('rejected', 0)}\n"
        message += f"📈 Success rate: {stats.get('success_rate', 0):.1f}%\n"
        
        if self.telegram_enabled:
            self._send_telegram(message)
        
        logger.info("📊 Summary alert trimis!")
