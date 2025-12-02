"""
Procesator de semnale - coordonează validarea AI și execuția pe broker
"""
from loguru import logger
from datetime import datetime
import os

from broker_manager import BrokerManager
from money_manager import MoneyManager


class SignalProcessor:
    """Procesează semnalele primite de la TradingView"""
    
    def __init__(self):
        self.broker_manager = BrokerManager()
        self.money_manager = MoneyManager()
        self.ai_validation_enabled = os.getenv('AI_VALIDATION_ENABLED', 'True').lower() == 'true'
        
    def process_signal(self, signal_data, ai_validator=None):
        """
        Procesează un semnal complet: validare AI -> money management -> execuție
        
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
            'execution': None,
            'executed': False
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
            
            # STEP 3: Execuție pe broker
            logger.info("🚀 STEP 3: Execuție pe broker...")
            
            # Pregătește ordinul
            order_data = {
                'symbol': signal_data['symbol'],
                'action': signal_data['action'],
                'volume': risk_assessment['position_size'],
                'price': signal_data.get('price'),
                'stop_loss': signal_data.get('stop_loss'),
                'take_profit': signal_data.get('take_profit'),
                'comment': f"TradingView-{signal_data.get('strategy', 'auto')}"
            }
            
            # Execută
            execution_result = self.broker_manager.execute_order(order_data)
            result['execution'] = execution_result
            
            if execution_result['success']:
                logger.info(f"✅ Ordin executat cu succes: Ticket={execution_result.get('ticket')}")
                result['executed'] = True
                
                # Update money manager
                self.money_manager.record_trade(order_data, execution_result)
            else:
                logger.error(f"❌ Eroare la execuție: {execution_result.get('error')}")
            
        except Exception as e:
            logger.error(f"❌ Eroare la procesarea semnalului: {e}")
            result['error'] = str(e)
        
        logger.info("=" * 60)
        return result
