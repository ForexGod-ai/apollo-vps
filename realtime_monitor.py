"""
Real-Time Market Monitor cu Spatiotemporal Analysis

Rulează continuu, monitorizează piața în timp real,
actualizează narrativul și alertează când setups become READY
"""

import time
from datetime import datetime, timedelta
from typing import Dict, List
import MetaTrader5 as mt5
from loguru import logger
import requests
import os
from dotenv import load_dotenv

from spatiotemporal_analyzer import SpatioTemporalAnalyzer, MarketNarrative

load_dotenv()

# Telegram config
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


class RealtimeMonitor:
    """
    Monitor în timp real pentru toate perechile
    """
    
    def __init__(self, symbols: List[str], check_interval_hours: int = 4):
        self.symbols = symbols
        self.check_interval_hours = check_interval_hours
        
        # Tracking pentru fiecare simbol
        self.analyzers: Dict[str, SpatioTemporalAnalyzer] = {}
        self.last_narratives: Dict[str, MarketNarrative] = {}
        self.last_recommendations: Dict[str, str] = {}
        
        # Initialize analyzers
        for symbol in symbols:
            self.analyzers[symbol] = SpatioTemporalAnalyzer(symbol)
            self.last_recommendations[symbol] = 'unknown'
    
    def _wait_for_next_candle_close(self):
        """Wait until next 4H candle closes (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)"""
        now = datetime.now()
        # Calculate next 4H candle close
        current_hour = now.hour
        next_4h_hours = [0, 4, 8, 12, 16, 20]
        
        # Find next 4H boundary
        next_close_hour = None
        for h in next_4h_hours:
            if h > current_hour:
                next_close_hour = h
                break
        
        if next_close_hour is None:
            # Next day 00:00
            next_close = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_close = now.replace(hour=next_close_hour, minute=0, second=0, microsecond=0)
        
        wait_seconds = (next_close - now).total_seconds()
        
        logger.info(f"\n⏰ Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"🕐 Next 4H candle closes at: {next_close.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"💤 Waiting {int(wait_seconds)} seconds ({int(wait_seconds/3600):.1f} hours)...")
        
        time.sleep(wait_seconds + 10)  # Wait + 10 seconds buffer for candle to fully close
    
    def run(self):
        """
        Main loop - rulează continuu, analizează la fiecare închidere de candelă 4H
        """
        logger.info("🚀 Starting Real-Time Market Monitor (4H Timeframe)...")
        logger.info(f"📊 Monitoring {len(self.symbols)} symbols (ALL PAIRS)")
        logger.info(f"🕐 Analysis trigger: Every 4H candle close (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)")
        logger.info(f"🔔 Telegram alerts enabled\n")
        
        iteration = 0
        
        while True:
            iteration += 1
            logger.info(f"\n{'='*80}")
            logger.info(f"🕐 4H CANDLE CLOSE #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*80}\n")
            
            for symbol in self.symbols:
                try:
                    self._check_symbol(symbol)
                except Exception as e:
                    logger.error(f"❌ Error checking {symbol}: {e}")
            
            # Summary
            ready_count = sum(1 for rec in self.last_recommendations.values() if rec == 'ready_to_trade')
            monitor_count = sum(1 for rec in self.last_recommendations.values() if rec == 'monitor_closely')
            
            logger.info(f"\n📊 4H CANDLE CLOSE SUMMARY:")
            logger.info(f"   ✅ Ready to trade: {ready_count}")
            logger.info(f"   👀 Monitor closely: {monitor_count}")
            logger.info(f"   ⏳ Waiting: {len(self.symbols) - ready_count - monitor_count}")
            
            # Wait for next 4H candle close
            self._wait_for_next_candle_close()
    
    def _check_symbol(self, symbol: str):
        """
        Check un simbol și detectează schimbări în narrativ
        """
        logger.info(f"🔍 Analyzing {symbol}...")
        
        # Get analyzer
        analyzer = self.analyzers[symbol]
        
        # Analyze current state
        narrative = analyzer.analyze_market()
        
        # Store narrative
        self.last_narratives[symbol] = narrative
        
        # Check for state changes
        previous_rec = self.last_recommendations[symbol]
        current_rec = narrative.recommendation
        
        if current_rec != previous_rec:
            # CHANGE DETECTED!
            self._handle_state_change(symbol, previous_rec, current_rec, narrative)
        else:
            # Same state, just log summary
            logger.info(f"   Status: {current_rec.upper()}")
            if narrative.waiting_for:
                logger.info(f"   Waiting: {', '.join(narrative.waiting_for[:2])}")
        
        # Update last recommendation
        self.last_recommendations[symbol] = current_rec
    
    def _handle_state_change(
        self, 
        symbol: str, 
        old_state: str, 
        new_state: str, 
        narrative: MarketNarrative
    ):
        """
        Handle state change (unknown → waiting → monitoring → ready)
        """
        logger.info(f"\n🔔 {symbol} STATE CHANGE: {old_state} → {new_state}")
        
        if new_state == 'ready_to_trade':
            # 🚨 READY TO TRADE - Send immediate alert!
            self._send_ready_alert(symbol, narrative)
            
        elif new_state == 'monitor_closely':
            # 👀 MONITOR CLOSELY - Send tracking alert
            self._send_monitoring_alert(symbol, narrative)
            
        elif new_state == 'wait_for_confirmation' and old_state in ['monitor_closely', 'ready_to_trade']:
            # ⚠️ Downgrade - setup degraded
            self._send_downgrade_alert(symbol, old_state, new_state, narrative)
        
        elif new_state == 'avoid' and old_state != 'unknown':
            # ❌ INVALIDATED - setup invalidated
            self._send_invalidation_alert(symbol, narrative)
    
    def _send_ready_alert(self, symbol: str, narrative: MarketNarrative):
        """
        🚨 READY TO TRADE - toate confirmările prezente!
        """
        best_scenario = narrative.expected_scenarios[0] if narrative.expected_scenarios else None
        
        if not best_scenario:
            return
        
        # Extract targets
        entry = next((t['level'] for t in best_scenario.get('targets', []) if t['type'] == 'entry_zone'), narrative.current_price)
        sl = next((t['level'] for t in best_scenario.get('targets', []) if t['type'] == 'stop_loss'), None)
        tp = next((t['level'] for t in best_scenario.get('targets', []) if t['type'] == 'take_profit'), None)
        
        # Calculate R:R
        if sl and tp and entry:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr = reward / risk if risk > 0 else 0
        else:
            rr = 0
        
        message = f"""
🚨🔥 <b>{symbol} - READY TO TRADE!</b> 🔥🚨

<b>📊 SETUP:</b> {best_scenario['name']}
<b>🎯 Probability:</b> {best_scenario['probability']}%
<b>💪 Confidence:</b> {narrative.confidence}%

<b>📍 LEVELS:</b>
• Entry Zone: ${entry:.5f}
• Stop Loss: ${sl:.5f}
• Take Profit: ${tp:.5f}
• Risk/Reward: 1:{rr:.2f}

<b>📖 STORY:</b>
{best_scenario['description']}

<b>⏰ TIMING:</b> {best_scenario.get('expected_timing', 'Now')}

<b>✅ ALL CONFIRMATIONS PRESENT - EXECUTE NOW!</b>

<b>🔍 MARKET STATE:</b>
• Structure: {narrative.current_state}
• Position: {narrative.price_position}
• Momentum: {narrative.momentum}

---
<i>Spatiotemporal Analysis v1.0</i>
        """
        
        self._send_telegram(message)
        logger.success(f"✅ READY alert sent for {symbol}")
    
    def _send_monitoring_alert(self, symbol: str, narrative: MarketNarrative):
        """
        👀 MONITOR CLOSELY - setup forming
        """
        best_scenario = narrative.expected_scenarios[0] if narrative.expected_scenarios else None
        
        if not best_scenario:
            return
        
        message = f"""
👀 <b>{symbol} - MONITOR CLOSELY</b>

<b>📊 SETUP FORMING:</b> {best_scenario['name']}
<b>🎯 Probability:</b> {best_scenario['probability']}%

<b>⏳ WAITING FOR:</b>
"""
        
        for conf in narrative.waiting_for[:5]:
            message += f"• {conf.replace('_', ' ').title()}\n"
        
        message += f"""
<b>⏰ EXPECTED:</b> {best_scenario.get('expected_timing', 'TBD')}

<b>📍 CURRENT PRICE:</b> ${narrative.current_price:.5f}

<b>🔍 STATUS:</b>
• Structure: {narrative.current_state}
• Position: {narrative.price_position}

🔔 <i>Will alert when READY!</i>
        """
        
        self._send_telegram(message)
        logger.info(f"👀 Monitoring alert sent for {symbol}")
    
    def _send_downgrade_alert(self, symbol: str, old_state: str, new_state: str, narrative: MarketNarrative):
        """
        ⚠️ Setup degraded
        """
        message = f"""
⚠️ <b>{symbol} - SETUP DOWNGRADED</b>

<b>Status:</b> {old_state.replace('_', ' ').title()} → {new_state.replace('_', ' ').title()}

<b>📍 Current Price:</b> ${narrative.current_price:.5f}

<b>⚠️ REASON:</b>
Setup conditions no longer fully met. Some confirmations lost.

<b>🔍 NEW WAITING LIST:</b>
"""
        
        for conf in narrative.waiting_for[:5]:
            message += f"• {conf.replace('_', ' ').title()}\n"
        
        message += "\n⏳ <i>Continue monitoring...</i>"
        
        self._send_telegram(message)
        logger.warning(f"⚠️ Downgrade alert sent for {symbol}")
    
    def _send_invalidation_alert(self, symbol: str, narrative: MarketNarrative):
        """
        ❌ Setup invalidated
        """
        message = f"""
❌ <b>{symbol} - SETUP INVALIDATED</b>

<b>📍 Current Price:</b> ${narrative.current_price:.5f}

<b>❌ INVALIDATION:</b>
"""
        
        if narrative.invalidation_levels:
            for level in narrative.invalidation_levels:
                message += f"• Price broke ${level:.5f}\n"
        else:
            message += "Setup conditions no longer valid.\n"
        
        message += f"""
<b>🔍 CURRENT STATE:</b>
• Structure: {narrative.current_state}
• Momentum: {narrative.momentum}

⏸️ <i>Waiting for new setup...</i>
        """
        
        self._send_telegram(message)
        logger.warning(f"❌ Invalidation alert sent for {symbol}")
    
    def _send_telegram(self, message: str):
        """
        Send Telegram message
        """
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram not configured")
            return
        
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'HTML'
            }
            response = requests.post(url, data=data, timeout=10)
            
            if response.status_code == 200:
                logger.debug("✅ Telegram message sent")
            else:
                logger.error(f"❌ Telegram error: {response.text}")
                
        except Exception as e:
            logger.error(f"❌ Telegram exception: {e}")


def main():
    """
    Start real-time monitor pentru TOATE perechile din config (4H timeframe)
    """
    # Initialize MT5
    if not mt5.initialize():
        logger.error("❌ MT5 initialization failed")
        return
    
    try:
        # Load ALL symbols from pairs_config.json
        import json
        with open('pairs_config.json', 'r') as f:
            config = json.load(f)
            symbols = [pair['symbol'] for pair in config['pairs']]
        
        logger.info(f"📋 Loaded {len(symbols)} pairs from config:")
        for i, sym in enumerate(symbols, 1):
            logger.info(f"   {i}. {sym}")
        
        # Create monitor (checks every 4H candle close)
        monitor = RealtimeMonitor(symbols, check_interval_hours=4)
        
        # Run forever
        monitor.run()
        
    except KeyboardInterrupt:
        logger.info("\n\n⏸️  Monitor stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
    finally:
        mt5.shutdown()
        logger.info("👋 MT5 disconnected")


if __name__ == "__main__":
    main()
