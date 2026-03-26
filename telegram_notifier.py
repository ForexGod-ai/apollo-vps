"""
Telegram Notifier for ForexGod - ETM Signals
Sends trade alerts with screenshots and interactive buttons
NOW USES ChartGenerator FOR PROFESSIONAL WHITE CHARTS
"""

import os
import time
import requests
import io
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv
from smc_detector import TradeSetup, CHoCH, FVG
from chart_generator import ChartGenerator

load_dotenv()

# ════════════════════════════════════════
# V10.4 SOVEREIGN SIGNATURE — ФорексГод EDITION
# ════════════════════════════════════════
# 16-line symmetrical footer on EVERY message, no exceptions.
# Branding = FOOTER ONLY. Never header. Clean & institutional.
# ════════════════════════════════════════
UNIVERSAL_SEPARATOR = "────────────────"  # EXACTLY 16 chars — COMPACT SYMMETRIC
SEPARATOR_LENGTH = 16  # Enforced rule: Name-aligned width
# ════════════════════════════════════════


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
        V10.4 SOVEREIGN SIGNATURE — 16-Line Symmetry by ФорексГод
        
        Every Telegram message ends with this institutional stamp.
        FOOTER ONLY. No header duplication. No exceptions.
        """
        sep = UNIVERSAL_SEPARATOR  # 16 chars
        if parse_mode == "HTML":
            footer = (
                f"\n\n"
                f"  {sep}\n"
                f"  🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
                f"  {sep}\n"
                f"  🏛️  <b>Глитч Ин Матрикс</b>  🏛️"
            )
        else:  # Markdown
            footer = (
                f"\n\n"
                f"  {sep}\n"
                f"  🔱 AUTHORED BY *ФорексГод* 🔱\n"
                f"  {sep}\n"
                f"  🏛️  *Глитч Ин Матрикс*  🏛️"
            )
        
        # FOOTER ONLY — message stays clean, stamp at the end
        return f"{message.rstrip()}{footer}"
    
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
        
        # V10.1: Anti-flood delay — Telegram rate-limits rapid media sends
        time.sleep(1.5)
        
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
        
        # V10.1: Anti-flood delay between charts
        time.sleep(1.5)
        
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
        
        # V10.1: Anti-flood delay before 1H chart
        time.sleep(1.5)
        
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
        """Format trade setup for Telegram message - COMPACT CARD v11.7"""
        SEP = "───────────"

        # Direction from Daily CHoCH
        raw_dir = setup.daily_choch.direction  # 'bullish' or 'bearish'
        direction = "🟢 LONG" if raw_dir == 'bullish' else "🔴 SHORT"
        emoji = "📈" if raw_dir == 'bullish' else "📉"

        # Load pair stats
        pair_stats = self._load_pair_statistics(setup.symbol)

        # Status
        status_emoji = "✅" if setup.status == 'READY' else "👀"
        status = "READY" if setup.status == 'READY' else "MONITORING"

        # Strategy type
        strategy_type = getattr(setup, 'strategy_type', 'reversal').upper()
        if strategy_type == 'REVERSAL':
            strategy_emoji = "🔄"
            strategy_label = "REVERSAL (CHoCH)"
        else:
            strategy_emoji = "➡️"
            strategy_label = "CONTINUITY (BOS)"

        # --- HEADER ---
        header = f"{strategy_emoji} <b>{setup.symbol}</b> {direction} {emoji}\n"
        header += f"{status_emoji} <b>{status}</b>\n"
        header += f"🎯 <b>Strategy: {strategy_label}</b>"

        # --- SWAP ROW (V11.7) ---
        swap_line = ""
        swap_val = getattr(setup, 'swap_long', None) if raw_dir == 'bullish' \
                   else getattr(setup, 'swap_short', None)
        swap_triple = getattr(setup, 'swap_triple_day', 'Wed')
        if swap_val is not None:
            swap_status = "✅ CREDIT" if swap_val >= 0 else "⚠️ DEBIT"
            swap_line = f"\n💱 SWAP: {swap_status} | {swap_val:+.2f} pips/day (3x {swap_triple})"

        # --- AI FUSION: Single compact line ---
        ai_fusion = ""
        if hasattr(setup, 'ml_score') and setup.ml_score is not None and \
           hasattr(setup, 'ai_probability_score') and setup.ai_probability_score is not None:

            ml_score = setup.ml_score
            ai_prob = setup.ai_probability_score * 10
            fused_score = int((ml_score * 0.6) + (ai_prob * 0.4))
            confidence = "HIGH" if fused_score >= 75 else "MED" if fused_score >= 60 else "LOW"

            rec = getattr(setup, 'ml_recommendation', 'REVIEW')
            rec_badge = "EXECUTE" if rec == 'TAKE' else "REVIEW" if rec == 'REVIEW' else "SKIP"

            ai_fusion = f"\n{SEP}\n🧠 <b>AI: {fused_score}% ({confidence})</b> | {rec_badge}"

        # --- QUALITY BADGE (compact inline) ---
        quality_line = ""
        if pair_stats:
            wr = pair_stats.get('win_rate', 0)
            trades = pair_stats.get('total_trades', 0)
            quality = "Exc" if wr >= 60 else "Good" if wr >= 45 else "Avg"
            quality_line = f"\n✨ {quality} | 📊 {trades} trades"

        # --- DAILY SECTION (compact) ---
        h1_choch = getattr(setup, 'h1_choch', None)
        choch_detected = getattr(setup, 'choch_1h_detected', False)

        if h1_choch or choch_detected:
            price = h1_choch.break_price if h1_choch else getattr(setup, 'choch_1h_price', 0)
            h1_line = f"⚡ 1H: <code>{price:.5f}</code>"
        else:
            h1_line = "⏳ 1H: Waiting"

        if setup.h4_choch:
            h4_line = f"🔄 4H: <code>{setup.h4_choch.break_price:.5f}</code>"
        else:
            h4_line = "⏳ 4H: Waiting"

        # Liquidity (compact)
        liquidity_line = ""
        if hasattr(setup, 'liquidity_sweep') and setup.liquidity_sweep:
            sweep = setup.liquidity_sweep
            sweep_type = sweep['sweep_type']
            conf_boost = getattr(setup, 'confidence_boost', 0)
            liquidity_line = f"\n💧 {sweep_type} +{conf_boost}"

        daily_section = (
            f"\n{SEP}\n"
            f"📊 <b>DAILY:</b> {setup.daily_choch.direction.upper()} CHoCH\n"
            f"🎯 FVG: <code>{setup.fvg.bottom:.5f}</code> – <code>{setup.fvg.top:.5f}</code>"
            f"{liquidity_line}\n"
            f"{h1_line} | {h4_line}"
        )

        # --- TRADE SECTION (compact) ---
        account_balance = float(os.getenv('ACCOUNT_BALANCE', '10000'))
        risk_percent = float(os.getenv('RISK_PER_TRADE', '0.02'))
        risk_amount = account_balance * risk_percent
        pip_value = 10

        # GUARD V11.2: dacă entry_price/stop_loss/take_profit sunt None
        if setup.entry_price is None or setup.stop_loss is None or setup.take_profit is None:
            trade_section = (
                f"\n{SEP}\n"
                f"💰 <b>TRADE</b>\n"
                f"⚠️ Entry/SL/TP în calcul (MONITORING)\n"
                f"⏳ Așteptăm confirmare 4H CHoCH + FVG"
            )
        else:
            stop_distance = abs(setup.entry_price - setup.stop_loss)
            lot_size = risk_amount / (stop_distance * pip_value * 100000) if stop_distance > 0 else 0.01
            if lot_size < 0.01:
                lot_size = 0.01

            rr_str = f"1:{setup.risk_reward:.2f}" if setup.risk_reward else "N/A"
            trade_section = (
                f"\n{SEP}\n"
                f"💰 <b>TRADE</b>\n"
                f"🔹 Entry  <code>{setup.entry_price:.5f}</code>\n"
                f"🔸 SL     <code>{setup.stop_loss:.5f}</code>\n"
                f"🎯 TP     <code>{setup.take_profit:.5f}</code>\n"
                f"💵 ${risk_amount:.2f} | 📦 {lot_size:.2f} lots | ⚖️ {rr_str}"
            )

        # --- ASSEMBLE: Compact Card V11.7 ---
        message = (
            f"{header}"
            f"{swap_line}"
            f"{ai_fusion}"
            f"{quality_line}"
            f"{daily_section}"
            f"{trade_section}"
        )

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
⏰ Scan Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M EET')}</code>
"""
        
        # Add monitoring setups with clean formatting
        if monitoring_setups:
            message += f"\n{UNIVERSAL_SEPARATOR}\n"
            message += "<b>📊 MONITORING SETUPS:</b>\n\n"
            for setup in monitoring_setups:
                symbol = setup.get('symbol', 'Unknown')
                dir_raw = str(setup.get('direction', '')).strip().lower()
                direction = "🟢 LONG" if dir_raw == 'buy' else ("🔴 SHORT" if dir_raw == 'sell' else dir_raw.upper())
                entry = setup.get('entry_price')
                rr = setup.get('risk_reward')
                
                # CRITICAL FIX by ФорексГод: Verifică None înainte de formatare
                if entry is None or rr is None:
                    # Skip acest setup dacă datele sunt incomplete
                    continue
                
                # Clean HTML formatting - no markdown
                message += f"• <b>{symbol}</b> - {direction}\n"
                message += f"  Entry: <code>{entry:.5f}</code> | RR: <code>1:{rr:.1f}</code>\n"
        
        # Add active positions with clean formatting
        if executed_positions:
            message += f"\n{UNIVERSAL_SEPARATOR}\n"
            message += "<b>🔥 ACTIVE TRADES:</b>\n\n"
            for pos in executed_positions:
                symbol = pos.get('symbol', 'Unknown')
                dir_raw = str(pos.get('direction', '')).strip().lower()
                direction = "🟢 LONG" if dir_raw == 'buy' else ("🔴 SHORT" if dir_raw == 'sell' else dir_raw.upper())
                entry = pos.get('entry_price')
                rr = pos.get('risk_reward')
                profit = pos.get('profit')
                
                # CRITICAL FIX by ФорексГод: Verifică None înainte de formatare
                if entry is None or rr is None or profit is None:
                    # Skip această poziție dacă datele sunt incomplete
                    continue
                
                profit_emoji = "💚" if profit > 0 else ("❤️" if profit < 0 else "💛")
                
                # Clean HTML formatting - no markdown
                message += f"• <b>{symbol}</b> - {direction} {profit_emoji}\n"
                message += f"  Entry: <code>{entry:.5f}</code> | RR: <code>1:{rr:.1f}</code> | P/L: <code>${profit:.2f}</code>\n"
        
        # Send with HTML parse mode
        return self.send_message(message.strip(), parse_mode="HTML")
    
    def send_scan_report(
        self,
        total_pairs: int,
        new_setups_found: int,
        truly_new: int,
        re_detected: int,
        monitoring_count: int,
        open_positions: int,
        deep_sleep_active: bool = False,
        deep_sleep_until: str = None,
        setup_symbols: list = None
    ) -> bool:
        """
        V10.1 SCAN REPORT — The Official Stamp by ФорексГод
        
        Sends a SINGLE final message after ALL charts are delivered.
        Mirrors the exact console output so the Telegram report matches
        what you see in the terminal. This is the 'ștampila de control'.
        
        Must be called with time.sleep(2) BEFORE to dodge Telegram flood-control.
        """
        sep = UNIVERSAL_SEPARATOR
        
        # Build the report — exact mirror of console output
        report = f"<b>✅ Scan Complete!</b>\n\n"
        report += f"📊 Total Pairs Scanned: <code>{total_pairs}</code>\n"
        report += f"🆕 New Setups Found: <code>{new_setups_found}</code>\n"
        report += f"    └─ Truly New (no position): <code>{truly_new}</code>\n"
        report += f"    └─ Re-detected (has position): <code>{re_detected}</code>\n"
        report += f"📋 Total Active Tracking:\n"
        report += f"    └─ Saved in Monitoring: <code>{monitoring_count}</code>\n"
        report += f"    └─ Open Positions: <code>{open_positions}</code>\n"
        report += f"\n⏰ <code>{datetime.now().strftime('%Y-%m-%d %H:%M EET')}</code>"
        
        # V10.1: List setup symbols if available
        if setup_symbols:
            report += f"\n\n{sep}\n"
            report += f"<b>🎯 DETECTED SETUPS:</b>\n"
            for sym_info in setup_symbols:
                symbol = sym_info.get('symbol', '?')
                direction = sym_info.get('direction', '?')
                dir_emoji = "🟢" if direction.lower() == 'buy' else "🔴"
                strategy = sym_info.get('strategy', 'UNKNOWN')
                strat_emoji = "🔄" if strategy == 'REVERSAL' else "➡️"
                report += f"  {dir_emoji} <b>{symbol}</b> {strat_emoji} {strategy}\n"
        
        # V9.3: Deep Sleep status line
        if deep_sleep_active and deep_sleep_until:
            report += f"\n\n😴 <b>Status: DEEP SLEEP ACTIVE</b>\n"
            report += f"    └─ Wake: <code>{deep_sleep_until}</code>"
        else:
            report += f"\n\n⚡ Status: <b>ACTIVE</b> — Monitoring live"
        
        # V10.1: Retry logic — if Telegram rejects (flood), wait and retry once
        success = self.send_message(report.strip(), parse_mode="HTML")
        if not success:
            print("[WARN] Scan report send failed — retrying in 5s...")
            time.sleep(5)
            success = self.send_message(report.strip(), parse_mode="HTML")
            if not success:
                print("[ERROR] Scan report FAILED after retry. Report lost.")
        
        return success
    
    def send_execution_confirmation(self, setup: TradeSetup, entry_type: str = 'pullback', 
                                    momentum_score: float = 0, hours_elapsed: float = 0) -> bool:
        """Send execution confirmation when trade is placed"""
        direction = "🟢 LONG" if setup.direction == 'buy' else "🔴 SHORT"
        direction_emoji = "📈" if setup.direction == 'buy' else "📉"
        
        # ✅ TELEGRAM UPDATES by ФорексГод: SL description with protection type
        # Detect asset class for SL description
        symbol_upper = setup.symbol.upper()
        if any(x in symbol_upper for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA']):
            # Crypto: Show percentage
            sl_pct = abs(setup.stop_loss - setup.entry_price) / setup.entry_price * 100
            sl_description = f"🛡️ SL: <code>{setup.stop_loss:.2f}</code> ({sl_pct:.1f}% Crypto Safety) ✅"
        else:
            # Forex: Show pips with Min Protected indicator
            pip_size = 0.01 if 'JPY' in symbol_upper else 0.0001
            sl_pips = abs(setup.stop_loss - setup.entry_price) / pip_size
            if sl_pips <= 35:  # Close to 30 pip minimum
                sl_description = f"🛡️ SL: <code>{setup.stop_loss:.5f}</code> ({sl_pips:.0f} pips - Min Protected) ✅"
            else:
                sl_description = f"🛡️ SL: <code>{setup.stop_loss:.5f}</code> ({sl_pips:.0f} pips)"
        
        if entry_type == 'pullback':
            message = f"""
🎯 <b>TRADE EXECUTED - PULLBACK ENTRY</b>

{setup.symbol} {direction} {direction_emoji}
──────────────────

✅ Pullback reached Fibo 50%
📍 Entry: <code>{setup.entry_price:.5f}</code>
{sl_description}
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
{sl_description}
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

⏰ Time: <code>{datetime.now().strftime('%Y-%m-%d %H:%M EET')}</code>
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
            message += f"\n\n{UNIVERSAL_SEPARATOR}"
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
                message += f"\n\n{UNIVERSAL_SEPARATOR}"
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
                    
                    message += f"\n\n{UNIVERSAL_SEPARATOR}"
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
                        message += f"\n\n{UNIVERSAL_SEPARATOR}"
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
