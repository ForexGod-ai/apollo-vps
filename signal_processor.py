"""
Procesator de semnale - coordonează validarea AI și notificările pentru setup-uri bune
"""
from loguru import logger
from datetime import datetime
import os

from notification_manager import NotificationManager
from money_manager import MoneyManager


class SignalProcessor:
    """Procesează semnalele primite de la TradingView"""
    
    def __init__(self):
        self.notification_manager = NotificationManager()
        self.money_manager = MoneyManager()
        self.ai_validation_enabled = os.getenv('AI_VALIDATION_ENABLED', 'True').lower() == 'true'
        self.auto_trade_enabled = os.getenv('AUTO_TRADE_ENABLED', 'False').lower() == 'true'
        
    def process_signal(self, signal_data, ai_validator=None):
        """
        Procesează un semnal complet: validare AI -> money management -> notificare
        
        Args:
            signal_data: Dict cu datele semnalului
            ai_validator: Instanță AISignalValidator
            
        Returns:
            Dict cu rezultatul procesării
        """
        logger.info("=" * 60)
        logger.info(f"📊 Procesare semnal: {signal_data.get('action', '').upper()} {signal_data.get('symbol', '')}")
        
        result = {
            'signal': signal_data,
            'timestamp': datetime.now().isoformat(),
            'ai_validation': None,
            'risk_assessment': None,
            'notification_sent': False,
            'alert_sent': False
        }
        
        try:
            # STEP 1: Validare AI
            if self.ai_validation_enabled and ai_validator:
                logger.info("🤖 STEP 1: Validare AI...")
                ai_result = ai_validator.validate_signal(signal_data)
                result['ai_validation'] = ai_result
                
                if not ai_result['approved']:
                    logger.warning(f"❌ Semnal respins de AI: Confidence={ai_result['confidence']:.2%}")
                    result['rejection_reason'] = 'AI validation failed'
                    return result
                
                logger.info(f"✅ Semnal validat de AI: Confidence={ai_result['confidence']:.2%}")
            else:
                logger.info("⏭️ Validare AI dezactivată")
            
            # STEP 2: Money Management
            logger.info("💰 STEP 2: Money Management...")
            risk_assessment = self.money_manager.calculate_position_size(signal_data)
            result['risk_assessment'] = risk_assessment
            
            if not risk_assessment['approved']:
                logger.warning(f"❌ Semnal respins de Money Manager: {risk_assessment.get('reason')}")
                result['rejection_reason'] = 'Risk management rejection'
                return result
            
            logger.info(f"✅ Poziție aprobată: {risk_assessment['position_size']} lots")
            
            # STEP 3: Trimite notificare (NU mai executăm automat!)
            logger.info("📢 STEP 3: Trimit alertă pentru setup bun...")
            
            notification_sent = self.notification_manager.send_trade_alert(
                signal_data=signal_data,
                ai_validation=result.get('ai_validation'),
                risk_assessment=risk_assessment
            )
            
            result['notification_sent'] = notification_sent
            result['alert_sent'] = notification_sent
            
            if notification_sent:
                logger.info("✅ Alertă trimisă cu succes! Execută trade manual.")
            else:
                logger.warning("⚠️ Alertă nu a putut fi trimisă!")
            
        except Exception as e:
            logger.error(f"❌ Eroare la procesarea semnalului: {e}")
            result['error'] = str(e)
        
        logger.info("=" * 60)
        return result
