#!/usr/bin/env python3
"""
Setup Monitor - Verifică setup-urile în MONITORING și execută când 4H confirmă
Rulează continuu, verifică la fiecare 15 minute
"""

import json
import time
import requests
from datetime import datetime, timedelta
from pathlib import Path
from loguru import logger
from smc_detector import SMCDetector
from notification_manager import NotificationManager
import pandas as pd

class SetupMonitor:
    def __init__(self):
        self.monitoring_file = Path("monitoring_setups.json")
        self.smc_detector = SMCDetector()
        self.notif_manager = NotificationManager()
        self.market_data_url = "http://localhost:8767"
        
    def load_monitoring_setups(self):
        """Încarcă setup-urile din fișier"""
        try:
            if self.monitoring_file.exists():
                with open(self.monitoring_file, 'r') as f:
                    data = json.load(f)
                    return data.get('setups', [])
            return []
        except Exception as e:
            logger.error(f"❌ Error loading monitoring setups: {e}")
            return []
    
    def save_monitoring_setups(self, setups):
        """Salvează setup-urile în fișier"""
        try:
            data = {
                "setups": setups,
                "last_updated": datetime.now().isoformat()
            }
            with open(self.monitoring_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"✅ Saved {len(setups)} monitoring setups")
        except Exception as e:
            logger.error(f"❌ Error saving monitoring setups: {e}")
    
    def get_market_data(self, symbol, timeframe, bars=100):
        """Preia date de la MarketDataProvider"""
        try:
            url = f"{self.market_data_url}/historical/{symbol}/{timeframe}/{bars}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'bars' in data:
                    df = pd.DataFrame(data['bars'])
                    df['time'] = pd.to_datetime(df['time'])
                    return df
            return None
        except Exception as e:
            logger.error(f"❌ Error getting data for {symbol}: {e}")
            return None
    
    def check_4h_confirmation(self, setup):
        """Verifică dacă setup e ready pentru execuție
        
        CONDIȚII pentru execuție:
        1. PRICE REACHED ENTRY ZONE (FVG bottom pentru LONG, FVG top pentru SHORT)
        2. SAU 4H CHoCH confirmare (pentru setups fără price entry încă)
        """
        try:
            symbol = setup['symbol']
            direction = setup['direction']  # 'buy' or 'sell'
            entry_price = setup.get('entry_price', 0)
            fvg_bottom = setup.get('fvg_zone_bottom', 0)
            fvg_top = setup.get('fvg_zone_top', 0)
            
            # Preia date 4H pentru current price
            df_4h = self.get_market_data(symbol, 'H4', 50)
            if df_4h is None or len(df_4h) < 20:
                return False
            
            current_price = df_4h['close'].iloc[-1]
            current_high = df_4h['high'].iloc[-1]
            current_low = df_4h['low'].iloc[-1]
            
            # CHECK 1: PRICE ENTRY CONDITION (PRIORITATE!)
            # ✅ LOGIC NOU: Verifică dacă CANDLE-ul 4H a TOUCHAT FVG zone
            # Pentru LONG: verifică dacă high/low a atins FVG bottom-top zone
            # Pentru SHORT: verifică dacă high/low a atins FVG top-bottom zone
            
            if direction.lower() == 'buy':
                # LONG: Execută când candle TOUCHEAZĂ FVG zone (pullback la CHoCH!)
                # Verifică dacă HIGH a intrat în FVG zone SAU LOW e aproape de FVG bottom
                fvg_touched = (current_high >= fvg_bottom) or (current_low >= fvg_bottom * 0.999)
                
                if fvg_touched:
                    logger.success(f"✅ {symbol}: PULLBACK LA FVG! High: {current_high:.5f}, FVG: {fvg_bottom:.5f}-{fvg_top:.5f}")
                    logger.success(f"   Current price: {current_price:.5f} - EXECUTE ACUM!")
                    return True
                else:
                    distance = fvg_bottom - current_high
                    logger.info(f"📊 {symbol}: Waiting for pullback. High: {current_high:.5f}, FVG bottom: {fvg_bottom:.5f}, Distance: {distance:.5f}")
                    
            elif direction.lower() == 'sell':
                # SHORT: Execută când candle TOUCHEAZĂ FVG zone
                fvg_touched = (current_low <= fvg_top) or (current_high <= fvg_top * 1.001)
                
                if fvg_touched:
                    logger.success(f"✅ {symbol}: PULLBACK LA FVG! Low: {current_low:.5f}, FVG: {fvg_bottom:.5f}-{fvg_top:.5f}")
                    logger.success(f"   Current price: {current_price:.5f} - EXECUTE ACUM!")
                    return True
                else:
                    distance = current_low - fvg_top
                    logger.info(f"📊 {symbol}: Waiting for pullback. Low: {current_low:.5f}, FVG top: {fvg_top:.5f}, Distance: {distance:.5f}")
            
            # CHECK 2: 4H CHoCH CONFIRMATION (backup method, less critical now)
            # Detectează swing points
            highs = self.smc_detector.detect_swing_highs(df_4h)
            lows = self.smc_detector.detect_swing_lows(df_4h)
            
            if len(highs) < 2 or len(lows) < 2:
                return False
            
            # Detectează CHoCH
            choch_list = self.smc_detector.detect_choch(highs, lows, df_4h)
            
            if not choch_list:
                return False
            
            # Verifică ultimul CHoCH
            latest_choch = choch_list[-1]
            
            # Pentru BUY: așteptăm CHoCH bullish
            # Pentru SELL: așteptăm CHoCH bearish
            if direction.lower() == 'buy' and latest_choch.direction == 'bullish':
                # Verifică dacă CHoCH este recent (ultimele 3 bare)
                if latest_choch.index >= len(df_4h) - 3:
                    logger.success(f"✅ {symbol}: 4H CHoCH BULLISH confirmed!")
                    return True
            
            elif direction.lower() == 'sell' and latest_choch.direction == 'bearish':
                if latest_choch.index >= len(df_4h) - 3:
                    logger.success(f"✅ {symbol}: 4H CHoCH BEARISH confirmed!")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking confirmation for {setup['symbol']}: {e}")
            return False
    
    def execute_setup(self, setup):
        """Execută setup-ul (scrie în signals.json pentru PythonSignalExecutor)"""
        try:
            # Calculate pips pentru cBot (cBot așteaptă PIPS, nu prețuri!)
            entry = setup['entry_price']
            sl = setup['stop_loss']
            tp = setup['take_profit']
            
            # JPY pairs: 1 pip = 0.01, altele: 1 pip = 0.0001
            pip_value = 0.01 if 'JPY' in setup['symbol'] else 0.0001
            
            sl_pips = abs(entry - sl) / pip_value
            tp_pips = abs(tp - entry) / pip_value
            
            signal = {
                "SignalId": f"SIGNAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "Symbol": setup['symbol'],
                "Direction": setup['direction'],
                "EntryPrice": setup['entry_price'],
                "StopLoss": setup['stop_loss'],
                "TakeProfit": setup['take_profit'],
                "StopLossPips": sl_pips,  # ✅ PascalCase pentru C#!
                "TakeProfitPips": tp_pips,  # ✅ PascalCase pentru C#!
                "Volume": setup.get('lot_size', 0.01),
                "RiskReward": setup['risk_reward'],
                "StrategyType": f"{setup['strategy_type']} - MONITORING_CONFIRMED",
                "Timestamp": datetime.now().isoformat()
            }
            
            # Scrie în signals.json
            with open('signals.json', 'w') as f:
                json.dump(signal, f, indent=2)
            
            logger.success(f"🎯 EXECUTED: {setup['symbol']} {setup['direction'].upper()} @ {setup['entry_price']}")
            
            # Trimite notificare ARMAGEDDON BEGINS pe Telegram
            setup_data = {
                'symbol': setup['symbol'],
                'direction': setup['direction'],
                'entry': setup['entry_price'],
                'sl': setup['stop_loss'],
                'tp': setup['take_profit'],
                'risk_reward': setup['risk_reward']
            }
            
            self.notif_manager.send_execution_alert(setup_data)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error executing setup: {e}")
            return False
    
    def check_setup_expiry(self, setup):
        """Verifică dacă setup-ul a expirat (>48h)"""
        try:
            setup_time = datetime.fromisoformat(setup['setup_time'])
            now = datetime.now()
            hours_passed = (now - setup_time).total_seconds() / 3600
            
            if hours_passed > 48:
                logger.warning(f"⚠️ Setup expired: {setup['symbol']} ({hours_passed:.1f}h old)")
                return True
            return False
        except:
            return False
    
    def monitor_loop(self):
        """Loop principal de monitorizare"""
        logger.info("🚀 Setup Monitor Started!")
        logger.info("⏰ Checking every 15 minutes for 4H confirmations...")
        
        while True:
            try:
                setups = self.load_monitoring_setups()
                
                if not setups:
                    logger.info("📭 No setups in MONITORING")
                else:
                    logger.info(f"📊 Monitoring {len(setups)} setup(s)...")
                    
                    updated_setups = []
                    
                    for setup in setups:
                        # Verifică expirare
                        if self.check_setup_expiry(setup):
                            logger.warning(f"🗑️ Removing expired setup: {setup['symbol']}")
                            continue
                        
                        # Verifică confirmare 4H
                        if self.check_4h_confirmation(setup):
                            # EXECUTĂ!
                            if self.execute_setup(setup):
                                logger.success(f"✅ Setup {setup['symbol']} executed and removed from monitoring")
                                # Nu îl mai adăugăm înapoi în listă
                                continue
                        
                        # Dacă nu a fost executat sau expirat, îl păstrăm
                        updated_setups.append(setup)
                    
                    # Salvează lista actualizată
                    self.save_monitoring_setups(updated_setups)
                
                # Așteaptă 15 minute
                logger.info("⏳ Next check in 15 minutes...")
                time.sleep(15 * 60)  # 15 minutes
                
            except KeyboardInterrupt:
                logger.info("🛑 Monitor stopped by user")
                break
            except Exception as e:
                logger.error(f"❌ Error in monitor loop: {e}")
                time.sleep(60)  # Wait 1 minute before retry

if __name__ == "__main__":
    monitor = SetupMonitor()
    monitor.monitor_loop()
