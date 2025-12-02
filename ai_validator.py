"""
Validator AI pentru semnale de trading folosind machine learning
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
import pickle
import os
from loguru import logger
from datetime import datetime


class AISignalValidator:
    """
    Validează semnalele de trading folosind AI/ML
    Folosește multiple modele pentru a determina probabilitatea de succes
    """
    
    def __init__(self, model_path=None):
        self.model_path = model_path or os.getenv('AI_MODEL_PATH', 'models/signal_validator.pkl')
        self.min_confidence = float(os.getenv('AI_MIN_CONFIDENCE', 0.7))
        
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Încarcă modelul dacă există
        self.load_model()
        
        # Dacă nu există model, creează unul simplu
        if not self.is_trained:
            self._initialize_default_model()
    
    def _initialize_default_model(self):
        """Inițializează un model de bază"""
        logger.info("🤖 Inițializare model AI de bază")
        self.model = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        # Model neantrenant - va folosi reguli heuristice
        self.is_trained = False
    
    def extract_features(self, signal_data):
        """
        Extrage features din semnalul primit pentru validare AI
        
        Args:
            signal_data: Dict cu datele semnalului
            
        Returns:
            numpy array cu features
        """
        features = []
        
        # 1. Tip acțiune (encoded)
        action_map = {'buy': 1, 'sell': -1, 'close': 0}
        features.append(action_map.get(signal_data.get('action', '').lower(), 0))
        
        # 2. Risk/Reward ratio
        price = signal_data.get('price', 0)
        sl = signal_data.get('stop_loss', 0)
        tp = signal_data.get('take_profit', 0)
        
        if price and sl and tp and price != sl:
            risk = abs(price - sl)
            reward = abs(tp - price)
            rr_ratio = reward / risk if risk > 0 else 0
            features.append(rr_ratio)
        else:
            features.append(0)
        
        # 3. Timeframe (encoded)
        timeframe_map = {
            '1m': 1, '5m': 5, '15m': 15, '30m': 30,
            '1h': 60, '4h': 240, '1d': 1440
        }
        tf = signal_data.get('timeframe', '1h')
        features.append(timeframe_map.get(tf, 60))
        
        # 4. Metadata indicators (dacă există)
        metadata = signal_data.get('metadata', {})
        
        # RSI
        rsi = metadata.get('rsi', 50)
        features.append(rsi)
        
        # MACD
        macd = metadata.get('macd', 0)
        features.append(macd * 10000)  # Scale pentru MACD
        
        # Volume (normalized)
        volume = metadata.get('volume', 0)
        features.append(volume / 1000000 if volume > 0 else 0)
        
        # 5. Ora zilei (poate influența volatilitatea)
        try:
            timestamp = datetime.fromisoformat(signal_data.get('timestamp', datetime.now().isoformat()))
            features.append(timestamp.hour)
            features.append(timestamp.weekday())
        except:
            features.append(12)  # Default noon
            features.append(2)   # Default Wednesday
        
        # 6. Strategie (encoded)
        strategy_map = {
            'trend_following': 1,
            'mean_reversion': 2,
            'breakout': 3,
            'scalping': 4
        }
        strategy = signal_data.get('strategy', 'unknown')
        features.append(strategy_map.get(strategy, 0))
        
        return np.array(features).reshape(1, -1)
    
    def validate_signal_heuristic(self, signal_data):
        """
        Validare bazată pe reguli heuristice când modelul nu e antrenat
        """
        score = 0.5  # Scor de bază
        reasons = []
        
        # 1. Verifică Risk/Reward
        price = signal_data.get('price', 0)
        sl = signal_data.get('stop_loss', 0)
        tp = signal_data.get('take_profit', 0)
        
        if price and sl and tp and price != sl:
            risk = abs(price - sl)
            reward = abs(tp - price)
            rr_ratio = reward / risk if risk > 0 else 0
            
            if rr_ratio >= 2:
                score += 0.2
                reasons.append("Excellent R:R ratio (>=2:1)")
            elif rr_ratio >= 1.5:
                score += 0.1
                reasons.append("Good R:R ratio (>=1.5:1)")
            elif rr_ratio < 1:
                score -= 0.2
                reasons.append("Poor R:R ratio (<1:1)")
        
        # 2. Verifică indicatori tehnici
        metadata = signal_data.get('metadata', {})
        
        # RSI
        rsi = metadata.get('rsi')
        if rsi:
            action = signal_data.get('action', '').lower()
            if action == 'buy' and rsi < 40:
                score += 0.15
                reasons.append("RSI oversold for BUY")
            elif action == 'sell' and rsi > 60:
                score += 0.15
                reasons.append("RSI overbought for SELL")
            elif (action == 'buy' and rsi > 70) or (action == 'sell' and rsi < 30):
                score -= 0.15
                reasons.append("RSI contradicts signal")
        
        # MACD
        macd = metadata.get('macd')
        if macd:
            action = signal_data.get('action', '').lower()
            if (action == 'buy' and macd > 0) or (action == 'sell' and macd < 0):
                score += 0.1
                reasons.append("MACD confirms signal")
        
        # 3. Verifică timeframe
        timeframe = signal_data.get('timeframe', '')
        if timeframe in ['1h', '4h', '1d']:
            score += 0.05
            reasons.append("Reliable timeframe")
        
        # Normalizare scor
        confidence = max(0, min(1, score))
        
        return {
            'confidence': confidence,
            'approved': confidence >= self.min_confidence,
            'method': 'heuristic',
            'reasons': reasons
        }
    
    def validate_signal(self, signal_data):
        """
        Validează un semnal de trading folosind AI
        
        Args:
            signal_data: Dict cu datele semnalului
            
        Returns:
            Dict cu rezultatul validării
        """
        try:
            # Extrage features
            features = self.extract_features(signal_data)
            
            # Dacă modelul nu e antrenat, folosește reguli heuristice
            if not self.is_trained:
                return self.validate_signal_heuristic(signal_data)
            
            # Normalizare features
            features_scaled = self.scaler.transform(features)
            
            # Predicție
            prediction = self.model.predict(features_scaled)[0]
            confidence = self.model.predict_proba(features_scaled)[0][1]
            
            # Decizie
            approved = confidence >= self.min_confidence
            
            logger.info(f"🤖 AI Validation: Confidence={confidence:.2%}, Approved={approved}")
            
            return {
                'confidence': float(confidence),
                'approved': approved,
                'prediction': int(prediction),
                'method': 'ml_model',
                'min_confidence': self.min_confidence
            }
            
        except Exception as e:
            logger.error(f"❌ Eroare la validare AI: {e}")
            # Fallback la validare heuristică
            return self.validate_signal_heuristic(signal_data)
    
    def train_model(self, historical_data, labels):
        """
        Antrenează modelul pe date istorice
        
        Args:
            historical_data: Lista de semnale istorice
            labels: Lista de rezultate (1=succes, 0=eșec)
        """
        try:
            logger.info("🎓 Antrenare model AI...")
            
            # Extrage features pentru toate semnalele
            features_list = []
            for signal in historical_data:
                features = self.extract_features(signal)
                features_list.append(features[0])
            
            X = np.array(features_list)
            y = np.array(labels)
            
            # Normalizare
            X_scaled = self.scaler.fit_transform(X)
            
            # Antrenare model
            self.model.fit(X_scaled, y)
            self.is_trained = True
            
            # Salvare model
            self.save_model()
            
            # Scor de antrenare
            score = self.model.score(X_scaled, y)
            logger.info(f"✅ Model antrenat cu succes! Acuratețe: {score:.2%}")
            
            return score
            
        except Exception as e:
            logger.error(f"❌ Eroare la antrenarea modelului: {e}")
            return None
    
    def save_model(self):
        """Salvează modelul antrenat"""
        try:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            
            model_data = {
                'model': self.model,
                'scaler': self.scaler,
                'is_trained': self.is_trained,
                'min_confidence': self.min_confidence
            }
            
            with open(self.model_path, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"💾 Model salvat în {self.model_path}")
            
        except Exception as e:
            logger.error(f"❌ Eroare la salvarea modelului: {e}")
    
    def load_model(self):
        """Încarcă un model antrenat"""
        try:
            if os.path.exists(self.model_path):
                with open(self.model_path, 'rb') as f:
                    model_data = pickle.load(f)
                
                self.model = model_data['model']
                self.scaler = model_data['scaler']
                self.is_trained = model_data['is_trained']
                self.min_confidence = model_data.get('min_confidence', self.min_confidence)
                
                logger.info(f"✅ Model încărcat din {self.model_path}")
                return True
                
        except Exception as e:
            logger.warning(f"⚠️ Nu s-a putut încărca modelul: {e}")
        
        return False
