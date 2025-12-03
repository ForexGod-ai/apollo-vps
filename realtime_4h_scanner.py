"""
Real-Time 4H Market Scanner
Analizează toate paritatile la fiecare 4H candle close (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)
Folosește aceeași logică SMC ca morning scanner (Daily CHoCH + FVG)
"""

import time
import json
import os
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
from loguru import logger
from dotenv import load_dotenv

# Import your SMC detector
from smc_detector import SMCDetector
from telegram_notifier import TelegramNotifier
from tradingview_chart_generator import TradingViewChartGenerator
from ctrader_data_client import get_ctrader_client

load_dotenv()


class Realtime4HScanner:
    """Scanner 4H pentru toate paritatile - detectează setups SMC"""
    
    def __init__(self):
        # Load pairs from config
        with open('pairs_config.json', 'r') as f:
            config = json.load(f)
            self.pairs = [(p['symbol'], p['priority']) for p in config['pairs']]
        
        self.smc_detector = SMCDetector()
        self.telegram = TelegramNotifier()
        self.chart_generator = TradingViewChartGenerator(login=False)
        self.ctrader_client = get_ctrader_client()  # cTrader data source
        
        # Track last alerts to avoid spam
        self.last_alerts: Dict[str, datetime] = {}
        
        logger.info(f"🚀 Initialized 4H Scanner with {len(self.pairs)} pairs")
    
    def _wait_for_next_4h_close(self):
        """Așteaptă până la următoarea închidere de candelă 4H"""
        now = datetime.now()
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
        logger.info(f"💤 Waiting {int(wait_seconds/3600):.1f} hours ({int(wait_seconds/60)} minutes)...")
        
        time.sleep(wait_seconds + 10)  # +10 sec buffer
    
    def analyze_pair(self, symbol: str, priority: int) -> dict:
        """
        Analizează o pereche pe timeframe Daily (strategia principală)
        Returns: {'has_setup': bool, 'setup': Setup, 'signal': dict}
        """
        try:
            logger.info(f"📊 Analyzing {symbol} (Priority {priority}) on Daily timeframe...")
            
            # Download data from cTrader (IC Markets feed)
            df_daily = self.ctrader_client.get_historical_data(symbol, 'D1', 200)
            
            if df_daily is None or df_daily.empty or len(df_daily) < 50:
                logger.warning(f"   ⚠️ {symbol}: Insufficient data")
                return {'has_setup': False, 'symbol': symbol}
            
            # Analyze using SMC detector (same as morning scanner)
            setup = self.smc_detector.scan_for_setup(symbol, df_daily, df_daily, priority)
            
            if not setup:
                logger.info(f"   ⚪ {symbol}: No setup")
                return {'has_setup': False, 'symbol': symbol}
            
            strategy_emoji = "🔴" if setup.strategy_type == 'reversal' else "🟢"
            
            logger.success(f"   {strategy_emoji} {symbol}: {setup.strategy_type.upper()} setup!")
            logger.info(f"      Direction: {setup.daily_choch.direction}")
            logger.info(f"      R:R: 1:{setup.risk_reward:.2f}")
            
            # Check if already alerted recently (avoid spam)
            if symbol in self.last_alerts:
                time_since_alert = (datetime.now() - self.last_alerts[symbol]).total_seconds() / 3600
                if time_since_alert < 24:  # Don't alert same pair within 24h
                    logger.info(f"      ⏭️ Skipping alert (already sent {time_since_alert:.1f}h ago)")
                    return {'has_setup': True, 'symbol': symbol, 'already_alerted': True}
            
            return {
                'has_setup': True,
                'symbol': symbol,
                'setup': setup,
                'already_alerted': False
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing {symbol}: {e}")
            return {'has_setup': False, 'symbol': symbol, 'error': str(e)}
    
    def run_scan(self):
        """Rulează scan complet pe toate paritatile"""
        logger.info("\n" + "="*80)
        logger.info(f"🔍 4H SCAN STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)
        
        results = []
        for i, (symbol, priority) in enumerate(self.pairs, 1):
            logger.info(f"\n📍 Progress: {i}/{len(self.pairs)}")
            result = self.analyze_pair(symbol, priority)
            results.append(result)
        
        # Filter setups found
        new_setups = [r for r in results if r['has_setup'] and not r.get('already_alerted')]
        
        logger.info("\n" + "="*80)
        logger.info(f"📊 SCAN COMPLETE: Found {len(new_setups)} new setups")
        logger.info("="*80)
        
        # Log setups for learning (NO Telegram alerts - only morning scanner sends alerts)
        if new_setups:
            logger.info("\n📚 SETUPS DETECTED (Silent monitoring - no alerts):")
            for r in new_setups:
                symbol = r['symbol']
                setup = r['setup']
                logger.info(f"   • {symbol}: {setup.strategy_type.upper()} | R:R 1:{setup.risk_reward:.2f}")
        
        # DO NOT send Telegram alerts - only log for learning
        # Telegram alerts ONLY from:
        # 1. Morning Scanner (09:00) - Daily report
        # 2. Auto-execution - When cBot executes trade
        
        return results
    
    def _send_telegram_alerts(self, setups: List[dict]):
        """Trimite alerte pe Telegram pentru setups găsite"""
        logger.info(f"\n📤 Sending Telegram alerts for {len(setups)} setups...")
        
        for result in setups:
            symbol = result['symbol']
            setup = result['setup']
            
            # Get chart screenshot
            chart_path = f"charts/4h_scan/{symbol}_daily.png"
            os.makedirs(os.path.dirname(chart_path), exist_ok=True)
            
            screenshot = self.chart_generator.get_chart_screenshot(symbol, "D")
            if screenshot:
                with open(chart_path, 'wb') as f:
                    f.write(screenshot)
            
            # Format message
            strategy_emoji = "🔴" if setup.strategy_type == 'reversal' else "🟢"
            direction_emoji = "🟢" if setup.daily_choch.direction == 'bullish' else "🔴"
            
            message = f"""
{strategy_emoji} *{setup.strategy_type.upper()} SETUP DETECTED*

*Pair:* `{symbol}`
*Timeframe:* Daily (detected on 4H scan)

{direction_emoji} *Direction:* {setup.daily_choch.direction.upper()}
📊 *Entry:* {setup.entry_price:.5f}
🛑 *Stop Loss:* {setup.stop_loss:.5f}
🎯 *Take Profit:* {setup.take_profit:.5f}
⚡ *Risk:Reward:* 1:{setup.risk_reward:.2f}

🕐 *Detected:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            # Send to Telegram
            try:
                if screenshot:
                    self.telegram.send_photo(screenshot, caption=message)
                else:
                    self.telegram.send_message(message)
                
                # Mark as alerted
                self.last_alerts[symbol] = datetime.now()
                logger.success(f"   ✅ Alert sent for {symbol}")
                
            except Exception as e:
                logger.error(f"   ❌ Failed to send alert for {symbol}: {e}")
    
    def run_forever(self):
        """Loop infinit - scanează la fiecare 4H candle close"""
        logger.info("🚀 Starting 4H Real-Time Scanner...")
        logger.info(f"📊 Monitoring {len(self.pairs)} pairs:")
        for i, (symbol, priority) in enumerate(self.pairs, 1):
            logger.info(f"   {i}. {symbol} (Priority {priority})")
        logger.info("\n🕐 Will scan every 4H candle close (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                logger.info(f"\n\n{'#'*80}")
                logger.info(f"🔄 ITERATION #{iteration}")
                logger.info(f"{'#'*80}")
                
                # Run scan
                self.run_scan()
                
                # Wait for next 4H candle
                self._wait_for_next_4h_close()
                
        except KeyboardInterrupt:
            logger.info("\n\n⏸️ Scanner stopped by user")
        except Exception as e:
            logger.error(f"\n\n❌ Fatal error: {e}")
        finally:
            self.chart_generator.close()
            logger.info("👋 Scanner shut down")


def main():
    """Start the 4H scanner"""
    scanner = Realtime4HScanner()
    scanner.run_forever()


if __name__ == "__main__":
    main()
