"""
Morning Strategy Scanner - ForexGod Trading AI
Runs at 09:00 daily to classify all pairs as REVERSAL or CONTINUITY
Generates Daily chart screenshots for each pair and sends grouped Telegram report
Auto-executes trades via cTrader when high-quality setups are found
"""

import os
import json
import sys
import time
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass
from dotenv import load_dotenv
from loguru import logger

# Import our modules
from smc_detector_fixed import (
    detect_body_swing_highs,
    detect_body_swing_lows,
    analyze_trend_structure
)
from smc_detector import SMCDetector, TradeSetup
from tradingview_chart_generator import TradingViewChartGenerator
from telegram_notifier import TelegramNotifier
from ctrader_data_client import get_ctrader_client

load_dotenv()

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="INFO")
logger.add("logs/morning_scan.log", rotation="1 week", retention="1 month")


@dataclass
class PairAnalysis:
    """Analysis result for a single pair"""
    symbol: str
    priority: int
    has_setup: bool
    setup: Optional[TradeSetup]
    chart_path: Optional[str]
    error: Optional[str] = None


class MorningStrategyScanner:
    """Morning scanner that analyzes all pairs and generates report with charts"""
    
    def __init__(self):
        self.smc_detector = SMCDetector()
        self.chart_generator = TradingViewChartGenerator(login=False)  # Use saved session
        self.telegram = TelegramNotifier()
        self.ctrader_client = get_ctrader_client()  # cTrader data source
        self.pairs_config = self._load_pairs_config()
        
    def _load_pairs_config(self) -> List[Dict]:
        """Load trading pairs from config file"""
        try:
            with open('pairs_config.json', 'r') as f:
                config = json.load(f)
                return config.get('pairs', [])
        except Exception as e:
            logger.error(f"❌ Error loading pairs_config.json: {e}")
            return []
    
    def _get_market_data(self, symbol: str, timeframe: str = "D1", bars: int = 100) -> Optional[dict]:
        """
        Get market data from cTrader (IC Markets feed) 
        Screenshots vin de pe TradingView separat!
        """
        try:
            logger.info(f"📊 Fetching data for {symbol} from cTrader...")
            
            # Use cTrader client instead of Yahoo Finance
            df = self.ctrader_client.get_historical_data(symbol, timeframe, bars)
            
            if df is None or df.empty:
                logger.warning(f"⚠️  No data for {symbol}")
                return None
            
            logger.success(f"✅ Got {len(df)} candles for {symbol} from cTrader")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error getting market data for {symbol}: {e}")
            return None
    
    def analyze_pair(self, pair: Dict) -> PairAnalysis:
        """Analyze a single pair and generate chart"""
        symbol = pair['symbol']
        priority = pair.get('priority', 2)
        
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"🔍 Analyzing {symbol} (Priority {priority})...")
            
            # Get Daily data
            df_daily = self._get_market_data(symbol, "D1", 100)
            if df_daily is None:
                return PairAnalysis(
                    symbol=symbol,
                    priority=priority,
                    has_setup=False,
                    setup=None,
                    chart_path=None,
                    error="Failed to get market data"
                )
            
            # FIXED: Analyze trend structure first (Glitch in Matrix)
            highs = detect_body_swing_highs(df_daily)
            lows = detect_body_swing_lows(df_daily)
            trend = analyze_trend_structure(highs, lows)
            
            logger.info(f"📊 Trend: {trend.direction.upper()} ({trend.structure}, {trend.confidence:.0%})")
            
            # Detect setup using SMC algorithm (cu trend corect)
            setup = self.smc_detector.scan_for_setup(symbol, df_daily, df_daily, priority)
            
            # NOTE: Do NOT override CHoCH direction with trend!
            # CHoCH direction = NEW trend after break
            # Previous trend = what analyze_trend_structure shows
            # For REVERSAL: Previous BEARISH + CHoCH BULLISH = REVERSAL BULLISH (BUY)
            
            if setup is None:
                logger.info(f"⚪ {symbol}: No valid setup detected")
                
                # Get TradingView screenshot (ca dimineața!)
                chart_path = f"charts/morning_scan/{symbol}_daily.png"
                os.makedirs(os.path.dirname(chart_path), exist_ok=True)
                
                screenshot = self.chart_generator.get_chart_screenshot(symbol, "D")
                if screenshot:
                    with open(chart_path, 'wb') as f:
                        f.write(screenshot)
                else:
                    chart_path = None
                
                return PairAnalysis(
                    symbol=symbol,
                    priority=priority,
                    has_setup=False,
                    setup=None,
                    chart_path=chart_path
                )
            
            # Setup found!
            strategy_emoji = "🔴" if setup.strategy_type == 'reversal' else "🟢"
            logger.success(f"{strategy_emoji} {symbol}: {setup.strategy_type.upper()} setup found!")
            logger.info(f"   Direction: {setup.daily_choch.direction}")
            logger.info(f"   Entry: {setup.entry_price:.5f}")
            logger.info(f"   SL: {setup.stop_loss:.5f}")
            logger.info(f"   TP: {setup.take_profit:.5f}")
            logger.info(f"   R:R: 1:{setup.risk_reward:.2f}")
            
            # Get TradingView screenshot (EXACT ca dimineața!)
            chart_path = f"charts/morning_scan/{symbol}_daily.png"
            os.makedirs(os.path.dirname(chart_path), exist_ok=True)
            
            screenshot = self.chart_generator.get_chart_screenshot(symbol, "D")
            if screenshot:
                with open(chart_path, 'wb') as f:
                    f.write(screenshot)
            else:
                chart_path = None
            
            return PairAnalysis(
                symbol=symbol,
                priority=priority,
                has_setup=True,
                setup=setup,
                chart_path=chart_path
            )
            
        except Exception as e:
            logger.error(f"❌ Error analyzing {symbol}: {e}")
            return PairAnalysis(
                symbol=symbol,
                priority=priority,
                has_setup=False,
                setup=None,
                chart_path=None,
                error=str(e)
            )
    
    def run_scan(self) -> Dict:
        """Run full morning scan on all pairs"""
        logger.info("🚀 Starting Morning Strategy Scan...")
        logger.info(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"📊 Pairs to analyze: {len(self.pairs_config)}")
        
        # Create charts directory
        os.makedirs("charts/morning_scan", exist_ok=True)
        
        # Analyze all pairs
        results: List[PairAnalysis] = []
        for i, pair in enumerate(self.pairs_config, 1):
            logger.info(f"\n📍 Progress: {i}/{len(self.pairs_config)}")
            analysis = self.analyze_pair(pair)
            results.append(analysis)
        
        # Group results
        reversal_setups = [r for r in results if r.has_setup and r.setup.strategy_type == 'reversal']
        continuity_setups = [r for r in results if r.has_setup and r.setup.strategy_type == 'continuation']
        no_setup_pairs = [r for r in results if not r.has_setup]
        
        # Sort by priority and R:R
        reversal_setups.sort(key=lambda x: (x.priority, -x.setup.risk_reward))
        continuity_setups.sort(key=lambda x: (x.priority, -x.setup.risk_reward))
        no_setup_pairs.sort(key=lambda x: x.priority)
        
        summary = {
            'total_pairs': len(results),
            'reversal_count': len(reversal_setups),
            'continuity_count': len(continuity_setups),
            'no_setup_count': len(no_setup_pairs),
            'reversal_setups': reversal_setups,
            'continuity_setups': continuity_setups,
            'no_setup_pairs': no_setup_pairs,
            'scan_time': datetime.now()
        }
        
        logger.info("\n" + "="*60)
        logger.success("✅ Morning Scan Complete!")
        logger.info(f"🔴 REVERSAL setups: {len(reversal_setups)}")
        logger.info(f"🟢 CONTINUITY setups: {len(continuity_setups)}")
        logger.info(f"⚪ No setup: {len(no_setup_pairs)}")
        
        # Auto-execute best setup via cTrader
        self._auto_execute_best_setup(reversal_setups, continuity_setups)
        
        return summary
    
    def _auto_execute_best_setup(self, reversal_setups: List[PairAnalysis], continuity_setups: List[PairAnalysis]):
        """
        Automatically send best setup to cTrader for execution
        Prioritizes: Priority 1 pairs with R:R >= 5.0 (1:5 minimum, targeting 1:10)
        """
        try:
            # Combine all setups and filter by quality (MINIMUM 1:5 R:R)
            all_setups = reversal_setups + continuity_setups
            high_quality = [s for s in all_setups if s.priority == 1 and s.setup.risk_reward >= 5.0]
            
            if not high_quality:
                logger.info("⚠️  No high-quality setups found (Priority 1 + R:R >= 1:5). No auto-execution.")
                return
            
            # Get best setup (highest R:R)
            best = max(high_quality, key=lambda x: x.setup.risk_reward)
            setup = best.setup
            
            logger.info(f"\n🎯 BEST SETUP FOUND: {best.symbol}")
            logger.info(f"   Strategy: {setup.strategy_type.upper()}")
            logger.info(f"   Direction: {setup.daily_choch.direction.upper()}")
            logger.info(f"   R:R: 1:{setup.risk_reward:.2f}")
            
            # Generate signal for cTrader
            signal = {
                "SignalId": f"MORNING_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                "Symbol": best.symbol.replace('USD', '/USD').replace('EUR', 'EUR/').replace('GBP', 'GBP/').replace('JPY', '/JPY').replace('CHF', '/CHF').replace('AUD', 'AUD/').replace('NZD', 'NZD/').replace('CAD', '/CAD'),
                "Direction": "buy" if setup.daily_choch.direction == 'bullish' else "sell",
                "StrategyType": f"Morning Glitch - {setup.strategy_type.capitalize()}",
                "EntryPrice": setup.entry_price,
                "StopLoss": setup.stop_loss,
                "TakeProfit": setup.take_profit,
                "StopLossPips": abs(setup.entry_price - setup.stop_loss) * 10000,  # Convert to pips
                "TakeProfitPips": abs(setup.take_profit - setup.entry_price) * 10000,
                "RiskReward": setup.risk_reward,
                "Timestamp": datetime.now().isoformat()
            }
            
            # Write signal file for cBot
            signal_path = "signals.json"
            with open(signal_path, 'w') as f:
                json.dump(signal, f, indent=2)
            
            logger.success(f"✅ Signal file created: {signal_path}")
            logger.info("🤖 cTrader cBot will execute this trade automatically!")
            
            # EPIC MESSAGE for super trades (R:R >= 1:5)
            direction_emoji = "🟢" if signal["Direction"] == "buy" else "🔴"
            armageddon_messages = [
                "⚔️ **THE ARMAGEDDON BEGINS** ⚔️",
                "💥 **MARKET APOCALYPSE INITIATED** 💥",
                "🔥 **UNLEASHING THE BEAST** 🔥",
                "⚡ **GODMODE ACTIVATED** ⚡",
                "🎯 **SNIPER ELITE EXECUTION** 🎯",
                "💀 **NO MERCY PROTOCOL** 💀",
                "🚀 **MOONSHOT ENGAGED** 🚀",
                "👑 **KING'S GAMBIT** 👑"
            ]
            import random
            epic_title = random.choice(armageddon_messages)
            
            telegram_msg = f"""
{epic_title}

{direction_emoji} *{best.symbol}* - {signal['Direction'].upper()}
Strategy: `{setup.strategy_type.upper()}`
💎 R:R: `1:{setup.risk_reward:.2f}` (LEGENDARY SETUP)

📍 Entry: `{setup.entry_price:.5f}`
🛑 SL: `{setup.stop_loss:.5f}` ({signal['StopLossPips']:.1f} pips)
🎯 TP: `{setup.take_profit:.5f}` ({signal['TakeProfitPips']:.1f} pips)

⏰ cBot executing in 10 seconds...
💰 Risk: 2% | Expected: {setup.risk_reward*2:.1f}%
"""
            self.telegram.send_message(telegram_msg.strip())
            
        except Exception as e:
            logger.error(f"❌ Error in auto-execution: {e}")

    
    def send_telegram_report(self, summary: Dict):
        """Send grouped Telegram report with charts"""
        logger.info("\n📱 Sending Telegram report...")
        
        try:
            # Header message
            header = f"""
🌅 *MORNING STRATEGY SCAN*
⏰ {summary['scan_time'].strftime('%Y-%m-%d %H:%M UTC')}

📊 *SUMMARY:*
• Total Pairs: `{summary['total_pairs']}`
• 🔴 REVERSAL: `{summary['reversal_count']}`
• 🟢 CONTINUITY: `{summary['continuity_count']}`
• ⚪ No Setup: `{summary['no_setup_count']}`

{'='*30}
"""
            self.telegram.send_message(header.strip())
            
            # REVERSAL SETUPS
            if summary['reversal_setups']:
                self.telegram.send_message("\n🔴 *REVERSAL SETUPS* 🔴\n_Major trend change detected!_")
                
                for analysis in summary['reversal_setups']:
                    setup = analysis.setup
                    direction = "🟢 LONG" if setup.daily_choch.direction == 'bullish' else "🔴 SHORT"
                    
                    message = f"""
━━━━━━━━━━━━━━━━━━━━
*{analysis.symbol}* {direction}
Priority: `{analysis.priority}` | R:R: `1:{setup.risk_reward:.2f}`

📍 Entry: `{setup.entry_price:.5f}`
🛑 Stop Loss: `{setup.stop_loss:.5f}`
🎯 Take Profit: `{setup.take_profit:.5f}`

📊 CHoCH: `{setup.daily_choch.direction.upper()} @ {setup.daily_choch.break_price:.5f}`
📦 FVG Zone: `{setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}`
"""
                    self.telegram.send_message(message.strip())
                    
                    # Send chart
                    if analysis.chart_path and os.path.exists(analysis.chart_path):
                        with open(analysis.chart_path, 'rb') as photo:
                            self.telegram.send_photo(
                                photo.read(),
                                caption=f"📊 {analysis.symbol} - Daily Chart (REVERSAL)"
                            )
            
            # CONTINUITY SETUPS
            if summary['continuity_setups']:
                self.telegram.send_message("\n🟢 *CONTINUITY SETUPS* 🟢\n_Existing trend continuation_")
                
                for analysis in summary['continuity_setups']:
                    setup = analysis.setup
                    direction = "🟢 LONG" if setup.daily_choch.direction == 'bullish' else "🔴 SHORT"
                    
                    message = f"""
━━━━━━━━━━━━━━━━━━━━
*{analysis.symbol}* {direction}
Priority: `{analysis.priority}` | R:R: `1:{setup.risk_reward:.2f}`

📍 Entry: `{setup.entry_price:.5f}`
🛑 Stop Loss: `{setup.stop_loss:.5f}`
🎯 Take Profit: `{setup.take_profit:.5f}`

📊 CHoCH: `{setup.daily_choch.direction.upper()} @ {setup.daily_choch.break_price:.5f}`
📦 FVG Zone: `{setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}`
"""
                    self.telegram.send_message(message.strip())
                    
                    # Send chart
                    if analysis.chart_path and os.path.exists(analysis.chart_path):
                        with open(analysis.chart_path, 'rb') as photo:
                            self.telegram.send_photo(
                                photo.read(),
                                caption=f"📊 {analysis.symbol} - Daily Chart (CONTINUITY)"
                            )
            
            # NO SETUP PAIRS (brief summary)
            if summary['no_setup_pairs']:
                no_setup_list = ", ".join([f"`{a.symbol}`" for a in summary['no_setup_pairs']])
                message = f"""
⚪ *NO SETUP DETECTED*
_Waiting for structure to develop_

Pairs: {no_setup_list}
"""
                self.telegram.send_message(message.strip())
            
            # Footer
            footer = f"""
━━━━━━━━━━━━━━━━━━━━
🔥 *ForexGod - Glitch Strategy*
_Next scan in 24 hours_
"""
            self.telegram.send_message(footer.strip())
            
            logger.success("✅ Telegram report sent successfully!")
            
        except Exception as e:
            logger.error(f"❌ Error sending Telegram report: {e}")
            self.telegram.send_error_alert(f"Morning scan report failed: {str(e)}")


def main():
    """Main execution"""
    try:
        scanner = MorningStrategyScanner()
        
        # Test Telegram connection
        if not scanner.telegram.test_connection():
            logger.error("❌ Telegram connection failed! Check your .env file.")
            sys.exit(1)
        
        # Run scan
        summary = scanner.run_scan()
        
        # Send report
        scanner.send_telegram_report(summary)
        
        # Save summary to JSON
        summary_data = {
            'scan_time': summary['scan_time'].isoformat(),
            'total_pairs': summary['total_pairs'],
            'reversal_count': summary['reversal_count'],
            'continuity_count': summary['continuity_count'],
            'no_setup_count': summary['no_setup_count'],
            'reversal_symbols': [a.symbol for a in summary['reversal_setups']],
            'continuity_symbols': [a.symbol for a in summary['continuity_setups']]
        }
        
        with open('logs/morning_scan_summary.json', 'w') as f:
            json.dump(summary_data, f, indent=2)
        
        logger.success("🎉 Morning scan completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Fatal error in morning scan: {e}")
        try:
            notifier = TelegramNotifier()
            notifier.send_error_alert(f"Morning scan crashed: {str(e)}")
        except:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
