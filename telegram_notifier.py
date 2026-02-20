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
──────────────────
✨ <b>Glitch in Matrix by ФорексГод</b> ✨
🧠 AI-Powered • 💎 Smart Money"""
        else:  # Markdown
            signature = """
──────────────────
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
        """Format trade setup for Telegram message - ELITE STACK v32.0 (Elegant & Scannable)"""
        # Direction from Daily CHoCH
        direction = "🟢 LONG" if setup.daily_choch.direction == 'bullish' else "🔴 SHORT"
        emoji = "📈" if setup.daily_choch.direction == 'bullish' else "📉"
        
        # Load pair stats
        pair_stats = self._load_pair_statistics(setup.symbol)
        
        # Entry type and momentum
        entry_type = getattr(setup, 'entry_type', None)
        momentum_score = getattr(setup, 'momentum_score', 0)
        hours_elapsed = getattr(setup, 'hours_waited', 0)
        
        # Status
        status_emoji = "✅" if setup.status == 'READY' else "👀"
        status = "READY" if setup.status == 'READY' else "MONITORING"
        
        # Strategy type
        strategy_emoji = "🔥" if setup.strategy_type == 'reversal' else "🎯"
        strategy = "REVERSAL" if setup.strategy_type == 'reversal' else "CONTINUATION"
        
        # --- HEADER SECTION ---
        header = f"{strategy_emoji} <b>SETUP: {setup.symbol}</b> {direction} {emoji}\n"
        header += f"{status_emoji} <b>{status}</b> • {strategy}"
        
        # --- PAIR STATS: Inline ---
        stats_line = ""
        if pair_stats:
            wr = pair_stats.get('win_rate', 0)
            trades = pair_stats.get('total_trades', 0)
            rr = pair_stats.get('avg_rr', 0)
            conf_emoji = "🟢" if wr >= 60 else "🟡" if wr >= 45 else "🔴"
            stats_line = f"\n{conf_emoji} <b>Stats:</b> {wr:.0f}% WR • 1:{rr:.1f} R:R • {trades} trades"
        
        # --- AI RADIOGRAPHY SECTION ---
        ai_section = ""
        if hasattr(setup, 'ml_score') and setup.ml_score is not None:
            score = setup.ml_score
            confidence = getattr(setup, 'ml_confidence', 'UNKNOWN')
            rec = getattr(setup, 'ml_recommendation', 'REVIEW')
            
            # Visual bar on separate line
            bar = "🟩" * int(score / 10) + "⬜" * (10 - int(score / 10))
            rec_badge = "✅ TAKE" if rec == 'TAKE' else "⚠️ REVIEW" if rec == 'REVIEW' else "🚫 SKIP"
            
            ai_section = f"\n\n╼╼╼╼╼\n🧠 <b>AI Score:</b> {score}/100 ({confidence})\n[{bar}] {rec_badge}"
        
        # --- ENTRY METHOD ---
        entry_line = ""
        if entry_type == 'pullback':
            entry_line = "\n🎯 <b>Entry:</b> Pullback @ Fibo 50%"
        elif entry_type == 'continuation':
            entry_line = f"\n🚀 <b>Entry:</b> Momentum (Score: {momentum_score:.0f}/100)"
        else:
            entry_line = "\n⏳ <b>Entry:</b> Waiting..."
        
        # --- MOMENTUM BAR (only if continuation) ---
        momentum_line = ""
        if entry_type == 'continuation' and momentum_score > 0:
            mom_bar = "🔥" * int(momentum_score / 10) + "⬜" * (10 - int(momentum_score / 10))
            momentum_line = f"\n[{mom_bar}] {momentum_score:.0f}/100"
            if momentum_score >= 80:
                momentum_line += " 🚀"
            elif momentum_score >= 60:
                momentum_line += " ✅"
        
        # --- AGE TRACKING ---
        age_line = ""
        if hours_elapsed > 0:
            progress = min(hours_elapsed / 12.0, 1.0)
            bar = "🟩" * int(progress * 10) + "⬜" * (10 - int(progress * 10))
            age_line = f"\n⏰ <b>Elapsed:</b> {hours_elapsed:.1f}h/12h\n[{bar}] {progress*100:.0f}%"
            if hours_elapsed >= 10:
                age_line += " ⚠️"
        
        # --- DAILY ANALYSIS SECTION ---
        h1_choch = getattr(setup, 'h1_choch', None)
        choch_detected = getattr(setup, 'choch_1h_detected', False)
        
        if h1_choch or choch_detected:
            price = h1_choch.break_price if h1_choch else getattr(setup, 'choch_1h_price', 0)
            h1_line = f"⚡ 1H CHoCH @ {price:.5f} ✅"
        else:
            h1_line = "⏳ Waiting 1H CHoCH"
        
        if setup.h4_choch:
            h4_line = f"🔄 4H CHoCH @ {setup.h4_choch.break_price:.5f} ✅"
        else:
            h4_line = "⏳ Waiting 4H confirm"
        
        # 💧 V4.0: Liquidity Sweep Info
        liquidity_line = ""
        if hasattr(setup, 'liquidity_sweep') and setup.liquidity_sweep:
            sweep = setup.liquidity_sweep
            sweep_type = sweep['sweep_type']
            conf_boost = getattr(setup, 'confidence_boost', 0)
            liquidity_line = f"\n💧 <b>Liquidity Sweep:</b> YES ({sweep_type}) <b>+{conf_boost} Conf</b>"
        
        daily_section = f"""\n\n╼╼╼╼╼
📊 <b>DAILY:</b> CHoCH {setup.daily_choch.direction.upper()}
🎯 FVG: <code>{setup.fvg.bottom:.5f} - {setup.fvg.top:.5f}</code>{liquidity_line}
{h1_line}
{h4_line}"""
        
        # --- TRADE SETUP SECTION (Claritate) ---
        account_balance = float(os.getenv('ACCOUNT_BALANCE', '10000'))
        risk_percent = float(os.getenv('RISK_PER_TRADE', '0.02'))
        risk_amount = account_balance * risk_percent
        
        pip_value = 10
        stop_distance = abs(setup.entry_price - setup.stop_loss)
        lot_size = risk_amount / (stop_distance * pip_value * 100000)
        
        trade_section = f"""\n\n╼╼╼╼╼
💰 <b>TRADE:</b>
📥 In: <code>{setup.entry_price:.5f}</code> | 🛑 SL: <code>{setup.stop_loss:.5f}</code>
🎯 TP: <code>{setup.take_profit:.5f}</code> | 💵 Risk: <code>${risk_amount:.2f}</code>
📦 Size: <code>{lot_size:.2f}</code> lots | ⚖️ RR: <code>1:{setup.risk_reward:.2f}</code>"""
        
        # --- AI PROBABILITY (if exists) ---
        ai_prob_section = ""
        if hasattr(setup, 'ai_probability_score') and setup.ai_probability_score is not None:
            from ai_probability_analyzer import get_analyzer
            analyzer = get_analyzer()
            
            analysis = {
                'score': setup.ai_probability_score,
                'confidence': setup.ai_probability_confidence,
                'factors': setup.ai_probability_factors,
                'warning': setup.ai_probability_warning
            }
            
            ai_prob_section = "\n\n╼╼╼╼╼\n" + analyzer.format_telegram_analysis(analysis, setup.symbol)
        
        # ⚠️ NO MANUAL FOOTER - send_message() adds signature automatically!
        # Removed duplicate signature to avoid double branding
        
        # --- ASSEMBLE MESSAGE ---
        message = f"{header}{stats_line}{ai_section}{entry_line}{momentum_line}{age_line}{daily_section}{trade_section}{ai_prob_section}"
        
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
        """Send daily scan summary with ACTIVE monitoring setups - CLEAN HTML FORMAT"""
        # Separate monitoring setups from executed positions
        monitoring_setups = [s for s in (active_setups or []) if s.get('status') != 'EXECUTED']
        executed_positions = [s for s in (active_setups or []) if s.get('status') == 'EXECUTED']
        
        # Header with clean HTML
        message = f"""<b>📊 Daily Scan Complete</b>

🔍 Pairs Scanned: <code>{scanned_pairs}</code>
🎯 New Setups Found: <code>{setups_found}</code>
📋 Monitoring: <code>{len(monitoring_setups)}</code> | Active Trades: <code>{len(executed_positions)}</code>
⏰ Scan Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</code>
"""
        
        # Add monitoring setups with clean formatting
        if monitoring_setups:
            message += "\n──────────────────\n"
            message += "<b>📊 MONITORING SETUPS:</b>\n\n"
            for setup in monitoring_setups:
                symbol = setup.get('symbol', 'Unknown')
                dir_raw = str(setup.get('direction', '')).strip().lower()
                direction = "🟢 LONG" if dir_raw == 'buy' else ("🔴 SHORT" if dir_raw == 'sell' else dir_raw.upper())
                entry = setup.get('entry_price', 0)
                rr = setup.get('risk_reward', 0)
                
                # Clean HTML formatting - no markdown
                message += f"• <b>{symbol}</b> - {direction}\n"
                message += f"  Entry: <code>{entry:.5f}</code> | RR: <code>1:{rr:.1f}</code>\n"
        
        # Add active positions with clean formatting
        if executed_positions:
            message += "\n──────────────────\n"
            message += "<b>🔥 ACTIVE TRADES:</b>\n\n"
            for pos in executed_positions:
                symbol = pos.get('symbol', 'Unknown')
                dir_raw = str(pos.get('direction', '')).strip().lower()
                direction = "🟢 LONG" if dir_raw == 'buy' else ("🔴 SHORT" if dir_raw == 'sell' else dir_raw.upper())
                entry = pos.get('entry_price', 0)
                rr = pos.get('risk_reward', 0)
                profit = pos.get('profit', 0)
                profit_emoji = "💚" if profit > 0 else ("❤️" if profit < 0 else "💛")
                
                # Clean HTML formatting - no markdown
                message += f"• <b>{symbol}</b> - {direction} {profit_emoji}\n"
                message += f"  Entry: <code>{entry:.5f}</code> | RR: <code>1:{rr:.1f}</code> | P/L: <code>${profit:.2f}</code>\n"
        
        # Send with HTML parse mode
        return self.send_message(message.strip(), parse_mode="HTML")
    
    def send_execution_confirmation(self, setup: TradeSetup, entry_type: str = 'pullback', 
                                    momentum_score: float = 0, hours_elapsed: float = 0) -> bool:
        """Send execution confirmation when trade is placed"""
        direction = "🟢 LONG" if setup.direction == 'buy' else "🔴 SHORT"
        direction_emoji = "📈" if setup.direction == 'buy' else "📉"
        
        if entry_type == 'pullback':
            message = f"""
🎯 <b>TRADE EXECUTED - PULLBACK ENTRY</b>

{setup.symbol} {direction} {direction_emoji}
──────────────────

✅ Pullback reached Fibo 50%
📍 Entry: <code>{setup.entry_price:.5f}</code>
🛡️ Stop Loss: <code>{setup.stop_loss:.5f}</code>
🎯 Take Profit: <code>{setup.take_profit:.5f}</code>
📊 RR: <code>1:{setup.risk_reward:.1f}</code>

⏰ Time to entry: <code>{hours_elapsed:.1f}h</code>
🎯 Classic pullback strategy ✅
"""
        else:  # continuation momentum
            message = f"""
🚀 <b>TRADE EXECUTED - MOMENTUM ENTRY</b>

{setup.symbol} {direction} {direction_emoji}
──────────────────

✅ Strong continuation detected!
📊 Momentum Score: <code>{momentum_score:.0f}/100</code> 🔥
📍 Entry: <code>{setup.entry_price:.5f}</code> (market)
🛡️ Stop Loss: <code>{setup.stop_loss:.5f}</code>
🎯 Take Profit: <code>{setup.take_profit:.5f}</code>
📊 RR: <code>1:{setup.risk_reward:.1f}</code>

⏰ Time to entry: <code>{hours_elapsed:.1f}h</code> (after 6h wait)
💨 Riding the momentum! 🚀
"""
        
        return self.send_message(message.strip(), parse_mode="HTML")
    
    def send_error_alert(self, error_msg: str) -> bool:
        """Send error notification"""
        message = f"""
⚠️ <b>Scanner Error</b>

<code>{error_msg}</code>

⏰ Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M UTC')}</code>
"""
        return self.send_message(message.strip(), parse_mode="HTML")
    
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

──────────────────
📊 *ACCOUNT SUMMARY:*

💵 Balance: `${balance:,.2f}`
💎 Equity: `${equity:,.2f}`
📈 P&L: `${total_pnl:+,.2f}` ({pnl_percent:+.2f}%) {pnl_emoji}

📊 Margin: `${margin_used:,.2f}` used ({margin_used/balance*100:.1f}%)
🔓 Free: `${free_margin:,.2f}`

──────────────────
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
            message += f"\n\n──────────────────"
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
                message += f"\n\n──────────────────"
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
                    
                    message += f"\n\n──────────────────"
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
                        message += f"\n\n──────────────────"
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
