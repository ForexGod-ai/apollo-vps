"""
Telegram Notifier for ForexGod - ETM Signals
Sends trade alerts with screenshots and interactive buttons
NOW USES ChartGenerator FOR PROFESSIONAL WHITE CHARTS
"""

import os
import requests
import io
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from smc_detector import TradeSetup, CHoCH, FVG
from chart_generator import ChartGenerator

load_dotenv()


class TelegramNotifier:
    """Sends trading alerts to Telegram group"""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        # Use ChartGenerator for professional white background charts
        self.chart_generator = ChartGenerator()
        
        if not self.bot_token or not self.chat_id:
            raise ValueError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env")
    
    def _add_branding_signature(self, message: str, parse_mode: str = "Markdown") -> str:
        """
        Add professional branding signature to any message
        This ensures consistent branding across all Telegram notifications
        Adapts formatting based on parse_mode (Markdown vs HTML)
        """
        if parse_mode == "HTML":
            signature = """
━━━━━━━━━━━━━━━━━━━━
✨ <b>Glitch in Matrix by ФорексГод</b> ✨
🧠 AI-Powered • 💎 Smart Money"""
        else:  # Markdown
            signature = """
━━━━━━━━━━━━━━━━━━━━
✨ *Glitch in Matrix by ФорексГод* ✨
🧠 AI-Powered • 💎 Smart Money"""
        
        # Add signature at the end of message
        return f"{message.rstrip()}\n{signature}"
    
    def send_message(self, text: str, parse_mode: str = "HTML", add_signature: bool = True) -> bool:
        """Send text message to Telegram with automatic branding signature"""
        try:
            # Add branding signature automatically (unless explicitly disabled)
            if add_signature:
                text = self._add_branding_signature(text, parse_mode)
            
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
        """Send photo to Telegram (raw bytes)"""
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
    
    def send_photo_file(self, file_path: str, caption: str = "") -> bool:
        """Send photo from file path"""
        try:
            if not os.path.exists(file_path):
                print(f"❌ Photo file not found: {file_path}")
                return False
            
            url = f"{self.base_url}/sendPhoto"
            with open(file_path, 'rb') as photo_file:
                files = {"photo": photo_file}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                    "parse_mode": "Markdown"
                }
                response = requests.post(url, files=files, data=data)
            
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Error sending Telegram photo from file: {e}")
            return False
    
    def send_setup_alert(
        self, 
        setup: TradeSetup, 
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame,
        df_1h: pd.DataFrame = None
    ) -> bool:
        """
        Send complete trade setup alert with:
        - Formatted message
        - Daily chart screenshot
        - 4H chart screenshot
        - 1H chart screenshot (for SCALE_IN strategy)
        - Interactive buttons
        """
        # 1. Send main alert message
        message = self.format_setup_alert(setup)
        print(f"[DEBUG] Sending setup alert for {setup.symbol} | status: {getattr(setup, 'status', None)}")
        if not self.send_message(message):
            print(f"[ERROR] Failed to send main message for {setup.symbol}")
            return False
        
        # 2. Generate and send Daily chart
        try:
            print(f"[INFO] Generating Daily chart for {setup.symbol}...")
            daily_chart = self._create_daily_chart(setup, df_daily)
            if daily_chart:
                print(f"[SUCCESS] Daily chart generated ({len(daily_chart)} bytes)")
                self.send_photo(daily_chart, caption=f"📊 {setup.symbol} - Daily Timeframe")
            else:
                print(f"[WARNING] Daily chart returned None for {setup.symbol}")
        except Exception as e:
            print(f"[ERROR] Error generating Daily chart for {setup.symbol}: {e}")
            import traceback
            traceback.print_exc()
        
        # 3. Generate and send 4H chart
        try:
            print(f"[INFO] Generating 4H chart for {setup.symbol}...")
            h4_chart = self._create_4h_chart(setup, df_4h)
            if h4_chart:
                print(f"[SUCCESS] 4H chart generated ({len(h4_chart)} bytes)")
                self.send_photo(h4_chart, caption=f"🔍 {setup.symbol} - 4H Timeframe")
            else:
                print(f"[WARNING] 4H chart returned None for {setup.symbol}")
        except Exception as e:
            print(f"[ERROR] Error generating 4H chart for {setup.symbol}: {e}")
            import traceback
            traceback.print_exc()
        
        # 4. Generate and send 1H chart (for SCALE_IN strategy)
        if df_1h is not None:
            try:
                print(f"[INFO] Generating 1H chart for {setup.symbol}...")
                h1_chart = self._create_1h_chart(setup, df_1h)
                if h1_chart:
                    print(f"[SUCCESS] 1H chart generated ({len(h1_chart)} bytes)")
                    self.send_photo(h1_chart, caption=f"⏰ {setup.symbol} - 1H Timeframe (Entry 1)")
                else:
                    print(f"[WARNING] 1H chart returned None for {setup.symbol}")
            except Exception as e:
                print(f"[ERROR] Error generating 1H chart for {setup.symbol}: {e}")
                import traceback
                traceback.print_exc()
        
        # 5. Send interactive buttons
        self._send_action_buttons(setup)
        return True
    
    def format_setup_alert(self, setup) -> str:
        """Format trade setup for Telegram message"""
        # Direction from Daily CHoCH (h4_choch may be None for MONITORING)
        direction = "🟢 LONG" if setup.daily_choch.direction == 'bullish' else "🔴 SHORT"
        emoji = "📈" if setup.daily_choch.direction == 'bullish' else "📉"
        
        # Get current price for Live Price Distance calculation
        current_price = getattr(setup, 'current_price', setup.entry_price)
        
        # Load Pair Statistics from trade_history.json
        pair_stats = self._load_pair_statistics(setup.symbol)
        
        # V3.3: Get entry type and momentum data
        entry_type = getattr(setup, 'entry_type', None)
        momentum_score = getattr(setup, 'momentum_score', 0)
        hours_elapsed = getattr(setup, 'hours_waited', 0)
        
        # Status indicator
        if setup.status == 'READY':
            status_text = "✅ <b>READY TO EXECUTE</b>"
        else:
            status_text = "👀 <b>MONITORING</b> (waiting for entry)"
        
        # Strategy type indicator
        strategy_emoji = "🔥🚨" if setup.strategy_type == 'reversal' else "🎯"
        strategy_text = "<b>REVERSAL - MAJOR TREND CHANGE!</b>" if setup.strategy_type == 'reversal' else "<b>CONTINUATION - Pullback Entry</b>"
        
        # V3.3 ENTRY TYPE BADGE
        entry_method_text = ""
        if entry_type == 'pullback':
            entry_method_text = "\n🎯 <b>ENTRY METHOD:</b> Pullback @ Fibo 50% (Classic)"
        elif entry_type == 'continuation':
            entry_method_text = f"\n🚀 <b>ENTRY METHOD:</b> Momentum Entry (Score: {momentum_score:.0f}/100) 🔥"
        else:
            entry_method_text = "\n⏳ <b>ENTRY METHOD:</b> Waiting for signal..."
        
        # CHoCH AGE TRACKING with progress bar
        age_tracking_text = ""
        if hours_elapsed > 0:
            progress = min(hours_elapsed / 12.0, 1.0)
            bar_filled = int(progress * 10)
            progress_bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
            
            age_tracking_text = f"\n⏰ <b>Time Elapsed:</b> {hours_elapsed:.1f}h / 12h timeout"
            age_tracking_text += f"\n{progress_bar} {progress*100:.0f}%"
            
            if hours_elapsed >= 10:
                age_tracking_text += "\n⚠️ Setup aging - Entry may timeout soon!"
        
        # #5: MOMENTUM SCORE VISUAL (Only for continuation entries)
        momentum_visual = ""
        if entry_type == 'continuation' and momentum_score > 0:
            bar_filled = int(momentum_score / 10)  # 0-100 score to 0-10 bars
            bar_empty = 10 - bar_filled
            momentum_bar = "🔥" * bar_filled + "⬜" * bar_empty
            momentum_visual = f"\n\n🔥 <b>MOMENTUM STRENGTH:</b>\n{momentum_bar} {momentum_score:.0f}/100"
            
            if momentum_score >= 80:
                momentum_visual += "\n🚀 EXPLOSIVE - High probability!"
            elif momentum_score >= 60:
                momentum_visual += "\n✅ STRONG - Good entry!"
            else:
                momentum_visual += "\n⚠️ MODERATE - Wait for confirmation"
        
        # 1H CHoCH info (for SCALE_IN Entry 1)
        # Check if CHoCH detected (from monitoring_setups.json flag or TradeSetup object)
        h1_choch_obj = getattr(setup, 'h1_choch', None)
        choch_detected = getattr(setup, 'choch_1h_detected', False)
        choch_price = getattr(setup, 'choch_1h_price', 0)
        
        if h1_choch_obj or choch_detected:
            # CHoCH detected - show price from object or stored value
            price = h1_choch_obj.break_price if h1_choch_obj else choch_price
            direction_text = h1_choch_obj.direction.upper() if h1_choch_obj else (setup.direction.upper() if hasattr(setup, 'direction') else 'BEARISH')
            h1_info = f"⚡ 1H CHoCH: {direction_text} @ {price:.5f} ✅"
            h1_status = "⏰ <b>Waiting for pullback to Fibo 50%</b>"
        else:
            h1_info = "⏳ <b>Waiting for 1H CHoCH</b>"
            h1_status = "⏰ Monitoring for Entry 1..."
        
        # 4H CHoCH info (for SCALE_IN Entry 2)
        if setup.h4_choch:
            h4_info = f"🔄 4H CHoCH: {setup.h4_choch.direction.upper()} @ {setup.h4_choch.break_price:.5f} ✅"
            h4_status = "✅ <b>Entry 2 Ready</b> (50% position)"
        else:
            h4_info = "⏳ <b>Waiting for 4H confirmation</b>"
            h4_status = "⏰ Monitoring for Entry 2..."
        
        # Calculate lot size (example: $10k account, 2% risk)
        account_balance = float(os.getenv('ACCOUNT_BALANCE', '10000'))
        risk_percent = float(os.getenv('RISK_PER_TRADE', '0.02'))
        risk_amount = account_balance * risk_percent
        
        pip_value = 10  # Standard for 1 lot forex
        stop_distance = abs(setup.entry_price - setup.stop_loss)
        lot_size = risk_amount / (stop_distance * pip_value * 100000)  # Rough calculation
        
        # #4: PAIR STATISTICS
        pair_stats_text = ""
        if pair_stats:
            win_rate = pair_stats.get('win_rate', 0)
            total_trades = pair_stats.get('total_trades', 0)
            avg_rr = pair_stats.get('avg_rr', 0)
            best_trade = pair_stats.get('best_trade', 0)
            
            confidence_emoji = "🟢" if win_rate >= 60 else "🟡" if win_rate >= 45 else "🔴"
            
            pair_stats_text = f"""\n\n━━━━━━━━━━━━━━━━━━━━
📈 <b>{setup.symbol} STATISTICS:</b>
━━━━━━━━━━━━━━━━━━━━
{confidence_emoji} Win Rate: {win_rate:.1f}% ({pair_stats.get('wins', 0)}W/{pair_stats.get('losses', 0)}L)
💰 Avg R:R: 1:{avg_rr:.1f}
🏆 Best Trade: ${best_trade:.2f}
📊 Total Trades: {total_trades}"""
        
        # NEW: ML SCORE SECTION
        ml_score_text = ""
        if hasattr(setup, 'ml_score') and setup.ml_score is not None:
            score = setup.ml_score
            confidence = getattr(setup, 'ml_confidence', 'UNKNOWN')
            recommendation = getattr(setup, 'ml_recommendation', 'REVIEW')
            factors = getattr(setup, 'ml_factors', {})
            
            # Score visualization
            score_emoji = "🟢" if score >= 75 else "🟡" if score >= 60 else "🔴"
            bar_filled = int(score / 10)
            score_bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
            
            # Recommendation badge
            rec_badge = "✅ TAKE" if recommendation == 'TAKE' else "⚠️ REVIEW" if recommendation == 'REVIEW' else "🚫 SKIP"
            
            ml_score_text = f"""\n\n━━━━━━━━━━━━━━━━━━━━
🧠 <b>AI CONFIDENCE SCORE:</b>
━━━━━━━━━━━━━━━━━━━━
{score_emoji} Score: {score}/100 ({confidence})
{score_bar}
🤖 AI Says: {rec_badge}

📊 Analysis:"""
            
            for factor, desc in factors.items():
                # Clean up factor name
                factor_clean = factor.replace('_', ' ').title()
                ml_score_text += f"\n  • {factor_clean}: {desc}"
            
            ml_score_text += "\n\n<i>Based on {trades} historical trades</i>".format(
                trades=getattr(setup, 'ml_trades_analyzed', 116)
            )
        
        # NEW: AI PROBABILITY ANALYSIS (1-10 scale)
        ai_prob_text = ""
        if hasattr(setup, 'ai_probability_score') and setup.ai_probability_score is not None:
            from ai_probability_analyzer import get_analyzer
            analyzer = get_analyzer()
            
            analysis = {
                'score': setup.ai_probability_score,
                'confidence': setup.ai_probability_confidence,
                'factors': setup.ai_probability_factors,
                'warning': setup.ai_probability_warning
            }
            
            ai_prob_text = "\n" + analyzer.format_telegram_analysis(analysis, setup.symbol)
        
        message = f"""
{strategy_emoji} <b>SETUP - {setup.symbol}</b> {strategy_emoji}
{direction} {emoji}

{status_text}
{strategy_text}{entry_method_text}{momentum_visual}{age_tracking_text}{pair_stats_text}{ml_score_text}{ai_prob_text}

━━━━━━━━━━━━━━━━━━━━
📊 <b>DAILY ANALYSIS:</b>
📍 CHoCH: <code>{setup.daily_choch.direction.upper()}</code>
🎯 FVG Zone: <code>{setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}</code>

⚡ <b>1H STATUS (Entry 1):</b>
{h1_info}
{h1_status}

🔍 <b>4H STATUS (Entry 2):</b>
{h4_info}
{h4_status}

━━━━━━━━━━━━━━━━━━━━
💰 <b>TRADE SETUP:</b>
💎 Entry: <code>{setup.entry_price:.5f}</code>
🛑 Stop Loss: <code>{setup.stop_loss:.5f}</code>
🎯 Take Profit: <code>{setup.take_profit:.5f}</code>

📊 R:R Ratio: <code>1:{setup.risk_reward:.2f}</code>
📦 Lot Size: <code>{lot_size:.2f}</code>
💵 Risk: <code>${risk_amount:.2f}</code>

⭐ Priority: <code>{setup.priority}</code>
⏰ Setup: <code>{setup.setup_time if isinstance(setup.setup_time, str) else (datetime.fromtimestamp(setup.setup_time).strftime('%Y-%m-%d %H:%M UTC') if isinstance(setup.setup_time, int) else setup.setup_time.strftime('%Y-%m-%d %H:%M UTC'))}</code>

━━━━━━━━━━━━━━━━━━━━
📈 <b>VIEW CHARTS:</b>
<a href='https://www.tradingview.com/chart/?symbol={self._get_tv_symbol(setup.symbol)}&interval=D'>📊 Daily</a> • <a href='https://www.tradingview.com/chart/?symbol={self._get_tv_symbol(setup.symbol)}&interval=60'>⚡ 1H</a> • <a href='https://www.tradingview.com/chart/?symbol={self._get_tv_symbol(setup.symbol)}&interval=240'>🔍 4H</a>
"""
        
        return message.strip()
    
    def _load_pair_statistics(self, symbol: str) -> dict:
        """Load pair statistics from trade_history.json"""
        try:
            import json
            from pathlib import Path
            
            history_file = Path('trade_history.json')
            if not history_file.exists():
                return None
            
            with open(history_file, 'r') as f:
                data = json.load(f)
            
            # Filter closed trades for this symbol
            symbol_trades = [
                t for t in data.get('closed_trades', [])
                if t.get('symbol') == symbol
            ]
            
            if not symbol_trades:
                return None
            
            # Calculate statistics
            total_trades = len(symbol_trades)
            winners = [t for t in symbol_trades if float(t.get('profit', 0)) > 0]
            losers = [t for t in symbol_trades if float(t.get('profit', 0)) <= 0]
            
            win_rate = (len(winners) / total_trades * 100) if total_trades > 0 else 0
            
            # Calculate average R:R (simplified - using profit/loss ratio)
            avg_win = sum(float(t.get('profit', 0)) for t in winners) / len(winners) if winners else 0
            avg_loss = abs(sum(float(t.get('profit', 0)) for t in losers) / len(losers)) if losers else 1
            avg_rr = (avg_win / avg_loss) if avg_loss > 0 else 0
            
            best_trade = max(float(t.get('profit', 0)) for t in symbol_trades) if symbol_trades else 0
            
            return {
                'win_rate': win_rate,
                'total_trades': total_trades,
                'wins': len(winners),
                'losses': len(losers),
                'avg_rr': avg_rr,
                'best_trade': best_trade
            }
        except Exception as e:
            print(f"⚠️ Could not load pair statistics: {e}")
            return None
    
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
            "USOIL": "TVC:USOIL",
            "XTIUSD": "TVC:USOIL"
        }
        
        return tv_symbols.get(symbol, f"FX:{symbol}")
    
    def _create_daily_chart(self, setup: TradeSetup, df: pd.DataFrame) -> Optional[bytes]:
        """Create Daily timeframe chart using ChartGenerator (professional white background)"""
        try:
            # Use ChartGenerator to create professional chart
            chart_bytes = self.chart_generator.create_daily_chart(
                symbol=setup.symbol,
                df=df,
                setup=setup,
                save_path=None  # Return bytes instead of saving
            )
            return chart_bytes
        except Exception as e:
            print(f"❌ Error creating Daily chart: {e}")
            return None
    
    def _create_4h_chart(self, setup: TradeSetup, df: pd.DataFrame) -> Optional[bytes]:
        """Create 4H timeframe chart using ChartGenerator (professional white background)"""
        try:
            # Use ChartGenerator to create professional chart
            chart_bytes = self.chart_generator.create_4h_chart(
                symbol=setup.symbol,
                df=df,
                setup=setup,
                save_path=None  # Return bytes instead of saving
            )
            return chart_bytes
        except Exception as e:
            print(f"❌ Error creating 4H chart: {e}")
            return None
    
    def _create_1h_chart(self, setup: TradeSetup, df: pd.DataFrame) -> Optional[bytes]:
        """Create 1H timeframe chart using ChartGenerator (for SCALE_IN Entry 1)"""
        try:
            # Use ChartGenerator to create professional chart
            chart_bytes = self.chart_generator.create_1h_chart(
                symbol=setup.symbol,
                df=df,
                setup=setup,
                save_path=None  # Return bytes instead of saving
            )
            return chart_bytes
        except Exception as e:
            print(f"❌ Error creating 1H chart: {e}")
            return None
    
    def _send_action_buttons(self, setup: TradeSetup) -> bool:
        """Send interactive buttons for Execute/Skip actions"""
        try:
            # Only send buttons for READY setups (have h4_choch)
            if not setup.h4_choch:
                return True  # Skip buttons for MONITORING setups
            
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
    
    def send_daily_summary(self, scanned_pairs: int, setups_found: int, active_setups: list = None) -> bool:
        """Send daily scan summary with ACTIVE monitoring setups"""
        # Separate monitoring setups from executed positions
        monitoring_setups = [s for s in (active_setups or []) if s.get('status') != 'EXECUTED']
        executed_positions = [s for s in (active_setups or []) if s.get('status') == 'EXECUTED']
        
        message = f"""
📊 *Daily Scan Complete*

🔍 Pairs Scanned: `{scanned_pairs}`
🎯 New Setups Found: `{setups_found}`
📋 Monitoring: `{len(monitoring_setups)}` | Active Trades: `{len(executed_positions)}`
⏰ Scan Time: `{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}`
"""
        
        # Add monitoring setups
        if monitoring_setups:
            message += "\n━━━━━━━━━━━━━━━━━━━━\n"
            message += "📊 *MONITORING SETUPS:*\n\n"
            for setup in monitoring_setups:
                symbol = setup.get('symbol', 'Unknown')
                dir_raw = str(setup.get('direction', '')).strip().lower()
                direction = "🟢 LONG" if dir_raw == 'buy' else ("🔴 SHORT" if dir_raw == 'sell' else dir_raw.upper())
                entry = setup.get('entry_price', 0)
                rr = setup.get('risk_reward', 0)
                message += f"• *{symbol}* - {direction}\n"
                message += f"  Entry: `{entry:.5f}` | R:R `1:{rr:.1f}`\n"
        
        # Add active positions
        if executed_positions:
            message += "\n━━━━━━━━━━━━━━━━━━━━\n"
            message += "🔥 *ACTIVE TRADES:*\n\n"
            for pos in executed_positions:
                symbol = pos.get('symbol', 'Unknown')
                dir_raw = str(pos.get('direction', '')).strip().lower()
                direction = "🟢 LONG" if dir_raw == 'buy' else ("🔴 SHORT" if dir_raw == 'sell' else dir_raw.upper())
                entry = pos.get('entry_price', 0)
                rr = pos.get('risk_reward', 0)
                profit = pos.get('profit', 0)
                profit_emoji = "💚" if profit > 0 else ("❤️" if profit < 0 else "💛")
                message += f"• *{symbol}* - {direction} {profit_emoji}\n"
                message += f"  Entry: `{entry:.5f}` | R:R `1:{rr:.1f}` | P/L: `${profit:.2f}`\n"
        
        return self.send_message(message.strip())
    
    def send_execution_confirmation(self, setup: TradeSetup, entry_type: str = 'pullback', 
                                    momentum_score: float = 0, hours_elapsed: float = 0) -> bool:
        """Send execution confirmation when trade is placed"""
        direction = "🟢 LONG" if setup.direction == 'buy' else "🔴 SHORT"
        direction_emoji = "📈" if setup.direction == 'buy' else "📉"
        
        if entry_type == 'pullback':
            message = f"""
🎯 *TRADE EXECUTED - PULLBACK ENTRY*

{setup.symbol} {direction} {direction_emoji}
━━━━━━━━━━━━━━━━━━━━

✅ Pullback reached Fibo 50%
📍 Entry: `{setup.entry_price:.5f}`
🛡️ Stop Loss: `{setup.stop_loss:.5f}`
🎯 Take Profit: `{setup.take_profit:.5f}`
📊 Risk:Reward: `1:{setup.risk_reward:.1f}`

⏰ Time to entry: {hours_elapsed:.1f}h
🎯 Classic pullback strategy ✅

━━━━━━━━━━━━━━━━━━━━
✨ *Glitch in Matrix* - by ForexGod
"""
        else:  # continuation momentum
            message = f"""
🚀 *TRADE EXECUTED - MOMENTUM ENTRY*

{setup.symbol} {direction} {direction_emoji}
━━━━━━━━━━━━━━━━━━━━

✅ Strong continuation detected!
📊 Momentum Score: {momentum_score:.0f}/100 🔥
📍 Entry: `{setup.entry_price:.5f}` (market)
🛡️ Stop Loss: `{setup.stop_loss:.5f}`
🎯 Take Profit: `{setup.take_profit:.5f}`
📊 Risk:Reward: `1:{setup.risk_reward:.1f}`

⏰ Time to entry: {hours_elapsed:.1f}h (after 6h wait)
💨 Riding the momentum! 🚀

━━━━━━━━━━━━━━━━━━━━
✨ *Glitch in Matrix* - by ForexGod
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
    
    def send_daily_performance_report(self, include_news: bool = True) -> bool:
        """
        Send comprehensive daily performance report
        
        Args:
            include_news: If True, include high-impact news section
        
        Returns:
            True if sent successfully
        """
        try:
            import json
            import sqlite3
            from datetime import timedelta
            
            print("📊 Generating daily performance report...")
            
            # ============ LOAD ACCOUNT DATA ============
            with open('trade_history.json', 'r') as f:
                data = json.load(f)
            
            account = data.get('account', {})
            positions = data.get('open_positions', [])
            
            balance = account.get('balance', 0)
            equity = account.get('equity', 0)
            margin_used = account.get('margin_used', 0)
            free_margin = account.get('free_margin', 0)
            
            total_pnl = equity - balance
            pnl_percent = (total_pnl / balance * 100) if balance > 0 else 0
            pnl_emoji = "🟢" if total_pnl > 0 else ("🔴" if total_pnl < 0 else "⚪")
            
            # ============ TODAY'S PERFORMANCE FROM SQLITE ============
            db_path = 'data/trades.db'
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
                    SUM(profit) as total_profit,
                    AVG(profit) as avg_profit,
                    MAX(profit) as best_trade,
                    MIN(profit) as worst_trade
                FROM closed_trades
                WHERE DATE(close_time) = ?
            """, (today,))
            
            today_stats = cursor.fetchone()
            today_trades, today_wins, today_losses, today_profit, today_avg, today_best, today_worst = today_stats
            
            # Get today's trades details
            cursor.execute("""
                SELECT symbol, profit, close_time
                FROM closed_trades
                WHERE DATE(close_time) = ?
                ORDER BY profit DESC
            """, (today,))
            
            today_trades_list = cursor.fetchall()
            
            # ============ WEEKLY PROGRESS ============
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT 
                    DATE(close_time) as date,
                    SUM(profit) as profit
                FROM closed_trades
                WHERE DATE(close_time) >= ?
                GROUP BY DATE(close_time)
                ORDER BY date DESC
                LIMIT 7
            """, (seven_days_ago,))
            
            weekly_breakdown = cursor.fetchall()
            conn.close()
            
            # ============ BUILD MESSAGE ============
            message = f"""
💰 *DAILY PERFORMANCE REPORT*
{datetime.now().strftime('%Y-%m-%d')} • {datetime.now().strftime('%A')}

━━━━━━━━━━━━━━━━━━━━━━━━
📊 *ACCOUNT SUMMARY:*

💵 Balance: `${balance:,.2f}`
💎 Equity: `${equity:,.2f}`
📈 P&L: `${total_pnl:+,.2f}` ({pnl_percent:+.2f}%) {pnl_emoji}

📊 Margin: `${margin_used:,.2f}` used ({margin_used/balance*100:.1f}%)
🔓 Free: `${free_margin:,.2f}`

━━━━━━━━━━━━━━━━━━━━━━━━
🎯 *TODAY'S PERFORMANCE:*
"""
            
            if today_trades > 0:
                today_win_rate = (today_wins / today_trades * 100) if today_trades > 0 else 0
                today_emoji = "🟢" if today_profit > 0 else ("🔴" if today_profit < 0 else "⚪")
                
                message += f"""
Closed Trades: `{today_trades}`
✅ Wins: `{today_wins}` | ❌ Losses: `{today_losses}`
Win Rate: `{today_win_rate:.1f}%`

Total Profit: `${today_profit:+,.2f}` {today_emoji}
Average: `${today_avg:.2f}`
Best: `${today_best:.2f}` 💎
Worst: `${today_worst:.2f}`

*Trade Breakdown:*"""
                
                for symbol, profit, close_time in today_trades_list[:5]:  # Show max 5 trades
                    emoji = "💚" if profit > 0 else ("❤️" if profit < 0 else "💛")
                    time_str = close_time.split(' ')[1][:5] if ' ' in close_time else ''
                    message += f"\n• `{symbol}`: `${profit:+.2f}` {emoji} @ {time_str}"
            else:
                message += "\n_No trades closed today_\n🕒 Market is waiting for perfect setups!"
            
            # ============ OPEN POSITIONS (cTrader Style) ============
            message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
            message += f"\n🔥 *OPEN POSITIONS:* {len(positions)}\n"
            
            if positions:
                # Sort by profit (highest first, like in cTrader)
                sorted_positions = sorted(positions, key=lambda p: p.get('profit', 0), reverse=True)
                
                winners = [p for p in positions if p.get('profit', 0) > 0]
                losers = [p for p in positions if p.get('profit', 0) < 0]
                
                message += f"\n💚 Winning: `{len(winners)}` | ❤️ Losing: `{len(losers)}`\n"
                
                # cTrader-style position display (clean and professional)
                for i, pos in enumerate(sorted_positions[:10], 1):  # Show max 10 positions
                    symbol = pos.get('symbol', 'Unknown')
                    direction = pos.get('direction', 'buy').upper()
                    profit = pos.get('profit', 0)
                    volume = pos.get('volume', pos.get('lot_size', 0))
                    
                    # Direction indicator
                    direction_emoji = "↗️" if direction == 'BUY' else "↘️"
                    
                    # Profit emoji and protection status
                    if profit > 20:
                        emoji = "💚 🛡️"  # Protected (break-even moved)
                    elif profit > 0:
                        emoji = "💚"
                    elif profit < 0:
                        emoji = "❤️"
                    else:
                        emoji = "💛"
                    
                    # Format like cTrader: Symbol | Direction | Volume | Profit
                    message += f"\n{i}. *{symbol}* {direction_emoji} `{volume:.2f}` → `${profit:+.2f}` {emoji}"
            else:
                message += "\n_No open positions_"
            
            # ============ WEEKLY PROGRESS ============
            if weekly_breakdown:
                message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
                message += f"\n📈 *WEEKLY PROGRESS:*\n"
                
                for date, profit in weekly_breakdown:
                    day_emoji = "🟢" if profit > 0 else ("🔴" if profit < 0 else "⚪")
                    # Get day name
                    date_obj = datetime.strptime(date, '%Y-%m-%d')
                    day_name = date_obj.strftime('%a')
                    message += f"\n`{day_name}`: `${profit:+.2f}` {day_emoji}"
                
                # Weekly total
                weekly_total = sum(p for _, p in weekly_breakdown)
                weekly_emoji = "🟢" if weekly_total > 0 else ("🔴" if weekly_total < 0 else "⚪")
                message += f"\n\n🔥 *Weekly Total:* `${weekly_total:+,.2f}` {weekly_emoji}"
            
            # ============ MONITORING SETUPS ============
            try:
                with open('monitoring_setups.json', 'r') as f:
                    setups_data = json.load(f)
                setups = setups_data.get('setups', [])
                
                if setups:
                    ready_setups = [s for s in setups if s.get('status') == 'READY']
                    monitoring_setups = [s for s in setups if s.get('status') == 'MONITORING']
                    
                    message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
                    message += f"\n📋 *MONITORING SETUPS:* {len(setups)}\n"
                    
                    if ready_setups:
                        message += f"\n🟢 Ready: `{len(ready_setups)}`"
                        for setup in ready_setups[:3]:
                            symbol = setup.get('symbol', 'N/A')
                            direction = setup.get('direction', 'buy').upper()
                            message += f"\n   • `{symbol}` {direction}"
                    
                    if monitoring_setups:
                        message += f"\n⏳ Monitoring: `{len(monitoring_setups)}`"
            except:
                pass
            
            # ============ HIGH-IMPACT NEWS ============
            if include_news:
                try:
                    news_alert = self._get_news_alert()
                    if news_alert:
                        message += f"\n\n━━━━━━━━━━━━━━━━━━━━━━━━"
                        message += f"\n{news_alert}"
                except Exception as e:
                    print(f"⚠️ Could not load news: {e}")
            
            # ============ FOOTER ============
            message += f"\n\n⏰ Generated: {datetime.now().strftime('%H:%M:%S')}"
            
            # Send message (branding signature added automatically)
            success = self.send_message(message.strip())
            
            if success:
                print("✅ Daily performance report sent!")
            else:
                print("❌ Failed to send report")
            
            return success
        
        except Exception as e:
            print(f"❌ Error generating daily report: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _get_news_alert(self) -> Optional[str]:
        """Get high-impact news alert for report"""
        try:
            import json
            from datetime import timedelta
            
            # Try to load economic_calendar.json
            with open('economic_calendar.json', 'r') as f:
                calendar = json.load(f)
            
            events = calendar.get('events', [])
            
            # Filter high-impact events in next 24 hours
            now = datetime.now()
            tomorrow = now + timedelta(hours=24)
            
            high_impact = []
            for event in events:
                try:
                    event_time = datetime.fromisoformat(event.get('time', ''))
                    
                    if now <= event_time <= tomorrow:
                        impact = event.get('impact', 'LOW')
                        if impact == 'HIGH':
                            high_impact.append({
                                'time': event_time,
                                'currency': event.get('currency', 'N/A'),
                                'event': event.get('event', 'Unknown')
                            })
                except:
                    continue
            
            if not high_impact:
                return "✅ *No High-Impact News* in next 24h\n🎯 Safe to trade all pairs!"
            
            # Build alert
            alert = f"⚠️ *HIGH-IMPACT NEWS* (Next 24h):\n"
            
            for event in high_impact[:5]:  # Show max 5 events
                time_str = event['time'].strftime('%H:%M')
                currency = event['currency']
                title = event['event']
                alert += f"\n🔴 `{currency}` @ {time_str}: {title}"
            
            # Add warning
            affected = set(e['currency'] for e in high_impact)
            alert += f"\n\n💡 Affected: {', '.join(affected)}"
            alert += f"\n⚠️ Avoid trading 30min before news!"
            
            return alert
        
        except Exception as e:
            return None


if __name__ == "__main__":
    """Test Telegram notifier"""
    print("🧪 Testing Telegram Notifier...")
    
    notifier = TelegramNotifier()
    
    if notifier.test_connection():
        notifier.send_message("🚀 *ForexGod - ETM Signals Bot*\n\nBot is online and ready!")
        print("✅ Test message sent successfully!")
    else:
        print("❌ Telegram connection test failed!")
