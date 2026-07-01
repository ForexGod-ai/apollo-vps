"""
Telegram Notifier for ForexGod - ETM Signals
Sends trade alerts with chart screenshots (info-only scan cards)
NOW USES ChartGenerator FOR PROFESSIONAL WHITE CHARTS
"""

import os
import json
import time
import requests
import io
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, Any, Dict
from datetime import datetime, timezone
from dotenv import load_dotenv
from smc_detector import TradeSetup, CHoCH, FVG
from chart_generator import ChartGenerator
from pip_utils import format_telegram_price, format_telegram_fvg_range, format_swap_line

load_dotenv()

# ════════════════════════════════════════
# V10.4 SOVEREIGN SIGNATURE — ФорексГод EDITION
# ════════════════════════════════════════
# 16-line symmetrical footer on EVERY message, no exceptions.
# Branding = FOOTER ONLY. Never header. Clean & institutional.
# ════════════════════════════════════════
UNIVERSAL_SEPARATOR = "────────────────"  # 16 chars — matches signature width

_MONITORING_JSON = Path(__file__).resolve().parent / 'monitoring_setups.json'

_RADAR_LIVE_KEYS = (
    'h4_structure_locked', 'h4_locked', 'h4_structure_locked_at',
    'radar_4h_choch_detected', 'radar_4h_choch_direction', 'radar_4h_choch_price',
    'radar_4h_status', 'radar_1h_choch_detected', 'radar_1h_choch_direction',
    'radar_1h_choch_price', 'radar_1h_status', 'radar_1h_choch_stale', 'EXECUTE_NOW',
    'poi_first_touch_time', 'h4_fvg_first_touch_time',
)


def _setup_attr(setup: Any, key: str, default=None):
    if isinstance(setup, dict):
        return setup.get(key, default)
    return getattr(setup, key, default)


def _radar_direction_matches(stored_dir: str, macro_dir: str) -> bool:
    d = str(stored_dir or '').lower()
    if macro_dir == 'bullish':
        return d in ('buy', 'long', 'bullish')
    return d in ('sell', 'short', 'bearish')


def _load_monitoring_radar_snapshot(symbol: str, macro_dir: str) -> Dict:
    """Live radar flags from monitoring_setups.json — fills gap when TradeSetup is scan-only."""
    try:
        if not _MONITORING_JSON.exists():
            return {}
        with open(_MONITORING_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
        setups = data.get('setups', data) if isinstance(data, dict) else data
        if not isinstance(setups, list):
            return {}
        matched = None
        for s in setups:
            if not isinstance(s, dict) or s.get('symbol') != symbol:
                continue
            if _radar_direction_matches(s.get('direction', ''), macro_dir):
                matched = s
                break
        if matched is None:
            for s in setups:
                if isinstance(s, dict) and s.get('symbol') == symbol:
                    matched = s
                    break
        if not matched:
            return {}
        return {k: matched[k] for k in _RADAR_LIVE_KEYS if k in matched}
    except Exception:
        return {}


def _radar_field(setup: Any, snap: Dict, key: str, default=None):
    setup_val = _setup_attr(setup, key, None)
    if setup_val not in (None, False, ''):
        return setup_val
    if snap and key in snap and snap[key] not in (None, ''):
        return snap[key]
    return default


def _ltf_choch_confirmed(
    setup: Any,
    snap: Dict,
    tf: str,
    macro_dir: str,
) -> bool:
    prefix = 'radar_4h' if tf == '4H' else 'radar_1h'
    detected = bool(_radar_field(setup, snap, f'{prefix}_choch_detected', False))
    direction = _radar_field(setup, snap, f'{prefix}_choch_direction')
    status = str(_radar_field(setup, snap, f'{prefix}_status', '') or '').upper()
    aligned = direction is None or direction == macro_dir

    if tf == '4H':
        h4_locked = bool(
            _radar_field(setup, snap, 'h4_structure_locked', False)
            or _radar_field(setup, snap, 'h4_locked', False)
        )
        h4_choch = _setup_attr(setup, 'h4_choch', None)
        return bool(
            h4_locked
            or (detected and aligned)
            or h4_choch is not None
            or 'EXECUTE_NOW_4H' in status
            or 'WAITING_4H_PULLBACK' in status
            or ('PULLBACK' in status and detected)
        )

    h1_choch = _setup_attr(setup, 'h1_choch', None)
    choch_1h_flag = bool(_setup_attr(setup, 'choch_1h_detected', False))
    if bool(_radar_field(setup, snap, 'radar_1h_choch_stale', False)):
        return False
    return bool(
        (detected and aligned)
        or h1_choch is not None
        or choch_1h_flag
        or 'EXECUTE_NOW_1H' in status
        or 'WAITING_1H_PULLBACK' in status
        or ('PULLBACK' in status and detected)
    )


def _ltf_choch_price(setup: Any, snap: Dict, tf: str):
    prefix = 'radar_4h' if tf == '4H' else 'radar_1h'
    price = _radar_field(setup, snap, f'{prefix}_choch_price')
    if price is not None:
        return price
    obj = _setup_attr(setup, 'h4_choch' if tf == '4H' else 'h1_choch', None)
    if obj is not None and hasattr(obj, 'break_price'):
        return obj.break_price
    if tf == '1H':
        return _setup_attr(setup, 'choch_1h_price', None)
    return None


def _format_radar_exec_lines(
    setup: Any,
    symbol: str,
    macro_dir: str,
    wait_hint: str,
) -> tuple:
    snap = _load_monitoring_radar_snapshot(symbol, macro_dir)

    if _ltf_choch_confirmed(setup, snap, '4H', macro_dir):
        price_4h = _ltf_choch_price(setup, snap, '4H')
        if price_4h is not None:
            h4_line = (
                f"📡 ✅ 4H CHoCH Confirmat — "
                f"<code>{format_telegram_price(symbol, price_4h)}</code>"
            )
        else:
            h4_line = "📡 ✅ 4H CHoCH Confirmat"
    else:
        h4_line = f"📡 4H: ⏳ {wait_hint}"

    if _ltf_choch_confirmed(setup, snap, '1H', macro_dir):
        price_1h = _ltf_choch_price(setup, snap, '1H')
        if price_1h is not None:
            h1_line = (
                f"🔭 ✅ 1H CHoCH Confirmat — "
                f"<code>{format_telegram_price(symbol, price_1h)}</code>"
            )
        else:
            h1_line = "🔭 ✅ 1H CHoCH Confirmat"
    else:
        h1_line = "🔭 1H: ⏳ Waiting pullback + FVG"

    return h4_line, h1_line


def _trade_levels_valid(entry, sl) -> bool:
    """True dacă entry și SL sunt non-zero și floatabile."""
    try:
        ef = float(entry)
        sf = float(sl)
        return abs(ef) > 1e-12 and abs(sf) > 1e-12
    except (TypeError, ValueError):
        return False


def _choch_trade_block(symbol: str, entry, sl, tp, rr) -> str:
    """Bloc Entry/SL/TP pentru alerte CHoCH — omit dacă prețuri lipsă (MONITORING)."""
    if not _trade_levels_valid(entry, sl):
        return ""
    sep = UNIVERSAL_SEPARATOR
    try:
        rr_f = float(rr) if rr else 0.0
    except (TypeError, ValueError):
        rr_f = 0.0
    return (
        f"{sep}\n"
        f"🔹 Entry  <code>{format_telegram_price(symbol, entry)}</code>\n"
        f"🔸 SL     <code>{format_telegram_price(symbol, sl)}</code>\n"
        f"🎯 TP     <code>{format_telegram_price(symbol, tp)}</code>\n"
        f"⚖️ RR     1:{rr_f:.2f}\n"
    )
SEPARATOR_LENGTH = 24  # Enforced rule: Name-aligned width
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
    
    def _add_branding_signature(self, message: str, parse_mode: str = "HTML") -> str:
        """
        V14.3 SOVEREIGN SIGNATURE — 24-char Separator by ФорексГод

        Every Telegram message ends with this institutional stamp.
        FOOTER ONLY. No header duplication. No exceptions.
        """
        sep = UNIVERSAL_SEPARATOR  # 24 chars
        footer = (
            f"\n\n"
            f"{sep}\n"
            f"🔱 AUTHORED BY ФорексГод 🔱\n"
            f"{sep}\n"
            f"🏛 Глитч Ин Матрикс 🏛"
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
            # V11.9: Retry once on 429 (rate limit) using retry-after header
            for attempt in range(2):
                response = requests.post(url, json=data)
                if response.status_code == 200:
                    return True
                if response.status_code == 429:
                    try:
                        retry_after = response.json().get('parameters', {}).get('retry_after', 30)
                    except Exception:
                        retry_after = 30
                    print(f"[TELEGRAM 429] Rate limited — waiting {retry_after}s before retry...")
                    time.sleep(retry_after + 1)
                    continue  # retry
                # Other error — log and fail
                try:
                    err_json = response.json()
                    print(f"[TELEGRAM ERROR] status={response.status_code} | {err_json.get('description', response.text[:200])}")
                except Exception:
                    print(f"[TELEGRAM ERROR] status={response.status_code} | {response.text[:200]}")
                return False
            return False
        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
            return False
    
    def send_photo(self, photo_bytes: bytes, caption: str = "") -> bool:
        """Send photo to Telegram (raw bytes)"""
        try:
            url = f"{self.base_url}/sendPhoto"
            data = {
                "chat_id": self.chat_id,
                "caption": caption,
                "parse_mode": "HTML"
            }
            # V11.9: Retry once on 429 using retry-after
            for attempt in range(2):
                files = {"photo": photo_bytes}
                response = requests.post(url, files=files, data=data)
                if response.status_code == 200:
                    return True
                if response.status_code == 429:
                    try:
                        retry_after = response.json().get('parameters', {}).get('retry_after', 30)
                    except Exception:
                        retry_after = 30
                    print(f"[TELEGRAM 429] Photo rate limited — waiting {retry_after}s...")
                    time.sleep(retry_after + 1)
                    continue
                return False
            return False
        except Exception as e:
            print(f"❌ Error sending Telegram photo: {e}")
            return False
    
    def send_setup_alert(
        self, 
        setup: TradeSetup, 
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame,
        df_1h: pd.DataFrame = None,
        charts_mode: str = 'full'  # V15.0: 'full' | 'daily_only'
    ) -> bool:
        """
        Send complete trade setup alert with:
        - Formatted message
        - Daily chart screenshot
        - 4H chart screenshot (ONLY when charts_mode='full')
        - 1H chart screenshot  (ONLY when charts_mode='full')
        V15.0 Silent Scan: charts_mode='daily_only' → trimite doar Daily chart la scanare.
        V43.9: fără butoane manuale — execuția rămâne autonomă (radar + executor).
        4H+1H se trimit separat la confirmare CHoCH (send_4h_choch_alert: photo+caption 4H / send_1h_choch_alert).
        """
        # 1. Send main alert message
        message = self.format_setup_alert(setup)
        print(f"[DEBUG] Sending setup alert for {setup.symbol} | status: {getattr(setup, 'status', None)} | mode: {charts_mode}")
        if not self.send_message(message):
            print(f"[ERROR] Failed to send main message for {setup.symbol}")
            return False
        
        # V11.9: Anti-flood delay — mărit la 3s (10 perechi × 3 chart-uri = 30+ req/scan)
        time.sleep(3)
        
        # 2. Generate and send Daily chart (ALWAYS)
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
        
        # V15.0 SILENT SCAN: la charts_mode='daily_only' oprim aici — 4H+1H vin la confirmare CHoCH
        if charts_mode == 'daily_only':
            print(f"[INFO] {setup.symbol}: daily_only mode — scan card complete (no manual buttons)")
            return True

        time.sleep(3)
        
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
        
        # V11.9: Anti-flood delay înainte de 1H chart
        time.sleep(3)
        
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
        
        return True

    def send_setup_expired_alert(self, symbol: str, direction: str, reason: str) -> bool:
        """
        V24.5 GRAVEYARD ALERT: Trimis când un setup este anulat/expirat de Sentinel.
        Mesaj scurt — nu face spam, informat Colonelul că botul și-a făcut treaba.
        """
        try:
            dir_emoji = "🟢" if direction.upper() == 'BUY' else "🔴"
            sep = "────────────────"
            msg = (
                f"🗑️ <b>SETUP ANULAT</b> — {symbol} {direction.upper()}\n"
                f"{sep}\n"
                f"{dir_emoji} <b>{symbol}</b> | Sentinel a eliminat setup-ul\n"
                f"{sep}\n"
                f"⚠️ <b>Motiv:</b> <code>{reason}</code>\n"
                f"{sep}\n"
                f"🛡️ Garda de Risc și-a făcut datoria. Slot eliberat."
            )
            return self.send_message(msg)
        except Exception as e:
            print(f"❌ [GRAVEYARD ALERT] Eroare trimitere alert expired {symbol}: {e}")
            return False

    def send_4h_structural_alert(
        self,
        setup_data: dict,
        df_4h: pd.DataFrame,
        signal_type: str = 'CHoCH',
        tf_data=None,
    ) -> bool:
        """
        V47: Alertă 4H — CHoCH (inversare) sau BOS (continuare), photo+caption, fallback text.
        """
        symbol = setup_data.get('symbol', 'UNKNOWN')
        sig = (signal_type or 'CHoCH').upper()
        try:
            direction = setup_data.get('direction', 'buy').upper()
            entry = setup_data.get('entry_price', 0)
            sl = setup_data.get('stop_loss', 0)
            tp = setup_data.get('take_profit', 0)
            rr = setup_data.get('risk_reward', 0)
            strategy = str(setup_data.get('strategy_type', 'reversal')).upper()
            d1_sig = setup_data.get('d1_signal_type', '')
            w1_bias = setup_data.get('w1_bias', 'NEUTRAL')
            dir_emoji = "🟢" if direction == 'BUY' else "🔴"
            w1_emoji = (
                "✅" if w1_bias == 'BULLISH' and direction == 'BUY'
                else "✅" if w1_bias == 'BEARISH' and direction == 'SELL'
                else "⚠️ COUNTER" if w1_bias != 'NEUTRAL' else "⏳ NEUTRAL"
            )
            sep = UNIVERSAL_SEPARATOR
            trade_block = _choch_trade_block(symbol, entry, sl, tp, rr)

            break_px = (
                getattr(tf_data, 'choch_price', None)
                or setup_data.get('radar_4h_choch_price')
                or entry
            )
            bars_ago = getattr(tf_data, 'choch_bars_ago', None) or setup_data.get('radar_4h_choch_bars_ago')
            bars_str = f"-{bars_ago}b" if bars_ago is not None else "?b"
            d1_line = f"\n📊 D1 signal: <code>{d1_sig}</code>" if d1_sig else ""

            if sig == 'BOS':
                header = "⚡ <b>4H STRUCTURĂ CONFIRMATĂ (BOS)</b> — Continuare"
                wait_line = (
                    "⏳ Așteptăm pullback Premium/Discount 60–80% pe impuls BOS "
                    "în POI Daily pentru entry final..."
                )
            else:
                header = "🔄 <b>4H INVERSARE STRUCTURĂ (CHoCH)</b> — Pregătire Entry"
                wait_line = (
                    "⏳ Așteptăm pullback Premium/Discount 60–80% în POI Daily "
                    "pentru entry final..."
                )

            caption = (
                f"{header}\n"
                f"{sep}\n"
                f"{dir_emoji} <b>{symbol}</b> {direction}\n"
                f"🎯 Strategy: <code>{strategy}</code>{d1_line}\n"
                f"📅 W1 Bias: <b>{w1_bias}</b> {w1_emoji}\n"
                f"📍 Break @ <code>{format_telegram_price(symbol, break_px)}</code> | "
                f"{sig} {bars_str} post-POI touch\n"
                f"{trade_block}"
                f"{sep}\n"
                f"{wait_line}"
            )

            chart_4h = None
            if df_4h is not None and not df_4h.empty and len(df_4h) >= 50:
                try:
                    from types import SimpleNamespace
                    setup_ns = SimpleNamespace(
                        symbol=symbol,
                        entry_price=entry,
                        stop_loss=sl,
                        take_profit=tp,
                        risk_reward=rr,
                        status='MONITORING',
                        strategy_type=strategy.lower(),
                        daily_choch=SimpleNamespace(
                            direction='bullish' if direction == 'BUY' else 'bearish'
                        ),
                        h4_choch=None,
                        fvg=SimpleNamespace(bottom=sl, top=tp),
                    )
                    chart_4h = self.chart_generator.create_4h_chart(
                        symbol=symbol,
                        df=df_4h,
                        setup=setup_ns,
                        save_path=None,
                    )
                except Exception as chart_err:
                    print(f"[WARNING] 4H chart render failed for {symbol}: {chart_err}")
            else:
                print(f"[WARNING] 4H chart skipped for {symbol}: df gol sau prea scurt")

            if chart_4h:
                if not self.send_photo(chart_4h, caption=caption):
                    print(f"[WARNING] send_photo failed for {symbol} — fallback to text")
                    self.send_message(caption)
            else:
                print(f"[WARNING] No 4H chart bytes for {symbol} — fallback to text alert")
                self.send_message(caption)

            print(f"[✅] 4H {sig} Alert sent: {symbol}")
            return True
        except Exception as e:
            print(f"[ERROR] send_4h_structural_alert failed for {symbol}: {e}")
            return False

    def send_4h_choch_alert(self, setup_data: dict, df_4h: pd.DataFrame) -> bool:
        """Backward compat — delegă la V47 send_4h_structural_alert."""
        return self.send_4h_structural_alert(setup_data, df_4h, signal_type='CHoCH')

    def send_1h_choch_alert(
        self,
        setup_data: dict,
        df_1h: pd.DataFrame,
        tf_data=None,
    ) -> bool:
        """
        V47: Photo + caption HTML (paritate 4H), fallback text. Gate 4H confirmat în radar.
        """
        try:
            symbol = setup_data.get('symbol', 'UNKNOWN')
            if setup_data.get('radar_1h_choch_stale'):
                print(f"[BLOCK] 1H CHoCH STALE — skip Telegram for {symbol}")
                return False

            direction = setup_data.get('direction', 'buy').upper()
            entry = setup_data.get('entry_price', 0)
            sl = setup_data.get('stop_loss', 0)
            tp = setup_data.get('take_profit', 0)
            rr = setup_data.get('risk_reward', 0)
            strategy = str(setup_data.get('strategy_type', 'reversal')).upper()
            sig = (getattr(tf_data, 'signal_type', None) or 'CHoCH').upper()
            choch_1h_price = (
                setup_data.get('choch_1h_price')
                or setup_data.get('radar_1h_choch_price')
                or getattr(tf_data, 'choch_price', None)
                or entry
            )
            bars_ago = getattr(tf_data, 'choch_bars_ago', None)
            bars_str = f"-{bars_ago}b" if bars_ago is not None else ""
            dir_emoji = "🟢" if direction == 'BUY' else "🔴"
            sep = UNIVERSAL_SEPARATOR
            trade_block = _choch_trade_block(symbol, entry, sl, tp, rr)

            caption = (
                f"🎯 <b>SNIPER 1H READY</b> — structură 4H confirmată\n"
                f"{sep}\n"
                f"{dir_emoji} <b>{symbol}</b> {direction}\n"
                f"🎯 Strategy: <code>{strategy}</code>\n"
                f"📍 1H {sig} @ <code>{format_telegram_price(symbol, choch_1h_price)}</code>"
                f"{f' | {bars_str} post-POI' if bars_str else ''}\n"
                f"{trade_block}"
                f"{sep}\n"
                f"⏳ Așteptăm pullback Premium/Discount 60–80% în POI Daily "
                f"(confirmare 1H sniper)..."
            )

            chart_1h = None
            if df_1h is not None and not df_1h.empty and len(df_1h) >= 50:
                from types import SimpleNamespace
                setup_ns = SimpleNamespace(
                    symbol=symbol,
                    entry_price=entry,
                    stop_loss=sl,
                    take_profit=tp,
                    risk_reward=rr,
                    status='MONITORING',
                    daily_choch=SimpleNamespace(
                        direction='bullish' if direction == 'BUY' else 'bearish'
                    ),
                    h4_choch=None,
                    fvg=SimpleNamespace(bottom=sl, top=tp),
                )
                chart_1h = self._create_1h_chart(setup_ns, df_1h)

            if chart_1h:
                if not self.send_photo(chart_1h, caption=caption):
                    print(f"[WARNING] send_photo 1H failed for {symbol} — fallback to text")
                    self.send_message(caption)
            else:
                print(f"[WARNING] No 1H chart bytes for {symbol} — fallback to text alert")
                self.send_message(caption)

            print(f"[✅] 1H Alert sent: {symbol}")
            return True
        except Exception as e:
            print(f"[ERROR] send_1h_choch_alert failed for {setup_data.get('symbol', '?')}: {e}")
            return False

    def format_setup_alert(self, setup) -> str:
        """Format scan card — V43.6: 3-block premium layout + asset-class price precision."""
        sep = UNIVERSAL_SEPARATOR
        symbol = setup.symbol

        raw_dir = setup.daily_choch.direction
        direction = "🟢 LONG" if raw_dir == 'bullish' else "🔴 SHORT"
        emoji = "📈" if raw_dir == 'bullish' else "📉"

        pair_stats = self._load_pair_statistics(symbol)

        status_emoji = "✅" if setup.status == 'READY' else "📋"
        status = "READY" if setup.status == 'READY' else "SCAN OK"

        strategy_type = getattr(setup, 'strategy_type', 'reversal').upper()
        if strategy_type.startswith('REVERSAL'):
            strategy_emoji = "🔄"
            strategy_label = "REVERSAL (CHoCH)"
            wait_hint = "Waiting 4H CHoCH"
        else:
            strategy_emoji = "➡️"
            strategy_label = "CONTINUITY (BOS)"
            wait_hint = "Waiting 4H BOS / Pullback"

        # ── BLOC 1: Identitate & Strategie ──
        block1 = (
            f"{strategy_emoji} <b>{symbol}</b> {direction} {emoji}\n"
            f"{status_emoji} <b>{status}</b>\n"
            f"🎯 <b>Strategy: {strategy_label}</b>"
        )

        _confidence = getattr(setup, 'confidence', 'NORMAL')
        w1_bias_val_hdr = getattr(setup, 'w1_bias', None)
        _w1_counter = (
            _confidence == 'LOW_W1_COUNTER_TREND'
            or (
                w1_bias_val_hdr and w1_bias_val_hdr != 'NEUTRAL'
                and (
                    (w1_bias_val_hdr == 'BEARISH' and raw_dir == 'bullish')
                    or (w1_bias_val_hdr == 'BULLISH' and raw_dir == 'bearish')
                )
            )
        )
        if _w1_counter:
            block1 += f"\n⚠️ <b>[COUNTER-TREND W1]</b> — D1 vs W1 macro nealiniat"

        swap_val = getattr(setup, 'swap_long', None) if raw_dir == 'bullish' \
                   else getattr(setup, 'swap_short', None)
        swap_triple = getattr(setup, 'swap_triple_day', 'Wed')
        block1 += format_swap_line(swap_val, triple_day=swap_triple)

        # ── BLOC 2: Context macro live ──
        block2_parts = []

        if hasattr(setup, 'ml_score') and setup.ml_score is not None and \
           hasattr(setup, 'ai_probability_score') and setup.ai_probability_score is not None:
            ml_score = setup.ml_score
            ai_prob = setup.ai_probability_score * 10
            fused_score = int((ml_score * 0.6) + (ai_prob * 0.4))
            confidence = "HIGH" if fused_score >= 75 else "MED" if fused_score >= 60 else "LOW"
            rec = getattr(setup, 'ml_recommendation', 'REVIEW')
            rec_badge = "EXECUTE" if rec == 'TAKE' else "REVIEW" if rec == 'REVIEW' else "SKIP"
            block2_parts.append(
                f"🧠 <b>AI: {fused_score}% ({confidence})</b> | {rec_badge} "
                f"<i>— informativ, nu blochează execuția</i>"
            )

        if pair_stats:
            wr = pair_stats.get('win_rate', 0)
            trades = pair_stats.get('total_trades', 0)
            quality = "Exc" if wr >= 60 else "Good" if wr >= 45 else "Avg"
            block2_parts.append(f"✨ {quality} | 📊 {trades} trades")

        daily_structure_label = "CHoCH" if strategy_type.startswith('REVERSAL') else "BOS"
        block2_parts.append(
            f"📊 <b>DAILY:</b> {setup.daily_choch.direction.upper()} {daily_structure_label}"
        )
        block2_parts.append(
            f"🎯 FVG: <code>{format_telegram_fvg_range(symbol, setup.fvg.bottom, setup.fvg.top)}</code>"
        )

        if hasattr(setup, 'liquidity_sweep') and setup.liquidity_sweep:
            sweep = setup.liquidity_sweep
            conf_boost = getattr(setup, 'confidence_boost', 0)
            block2_parts.append(f"💧 {sweep['sweep_type']} +{conf_boost}")

        w1_bias_val = getattr(setup, 'w1_bias', None)
        if w1_bias_val and w1_bias_val != 'NEUTRAL':
            is_aligned = (w1_bias_val == 'BULLISH' and raw_dir == 'bullish') or \
                         (w1_bias_val == 'BEARISH' and raw_dir == 'bearish')
            w1_align_emoji = "✅" if is_aligned else "⚠️ [COUNTER-TREND W1]"
            block2_parts.append(f"📅 W1: <b>{w1_bias_val}</b> {w1_align_emoji}")
        else:
            block2_parts.append("📅 W1: NEUTRAL ⏳")

        block2 = f"\n{sep}\n" + "\n".join(block2_parts)

        # ── BLOC 3: Radar & Execuție (stare live din JSON radar + setup) ──
        h4_line, h1_line = _format_radar_exec_lines(setup, symbol, raw_dir, wait_hint)

        block3 = (
            f"\n{sep}\n"
            f"{h4_line}\n"
            f"{h1_line}\n"
            f"⏳ <b>Entry / SL / TP</b> — la semnal <b>EXECUTE NOW</b>\n"
            f"⚡ Radar monitorizează 4H + 1H live"
        )

        return f"{block1}{block2}{block3}".strip()

    def send_execute_now_alert(self, setup_data: dict, exec_tf: str = '?') -> bool:
        """
        V37.3: Trimis când radar setează EXECUTE_NOW=True.
        Conține Entry / SL / TP structural (4H SL + D1 TP) — singura sursă de prețuri de trade.
        """
        try:
            from pip_utils import (
                get_pip_size, sl_pips_between, MIN_SL_PIPS,
                prices_direction_valid, sl_entry_magnitude_sane,
            )

            symbol = setup_data.get('symbol', 'UNKNOWN')
            direction_raw = str(setup_data.get('direction', 'buy')).lower()
            direction = 'BUY' if direction_raw in ('buy', 'long') else 'SELL'
            dir_emoji = "🟢" if direction == 'BUY' else "🔴"
            sep = UNIVERSAL_SEPARATOR

            entry = (
                setup_data.get('radar_4h_fvg_entry')
                or setup_data.get('radar_1h_fvg_entry')
                or setup_data.get('entry_price')
            )
            sl = setup_data.get('h4_sl_price') or setup_data.get('stop_loss')
            tp = setup_data.get('daily_tp_price') or setup_data.get('daily_target_price') or setup_data.get('take_profit')

            if not _trade_levels_valid(entry, sl):
                print(
                    f"[BLOCK EXECUTE NOW] {symbol}: entry/sl invalid "
                    f"(entry={entry!r}, sl={sl!r}) — skip Telegram"
                )
                return False

            strategy = str(setup_data.get('strategy_type', 'unknown')).upper()
            if strategy.startswith('CONTINUATION'):
                strategy = 'CONTINUITY'
            strategy = strategy.replace('_COUNTER_W1', '')

            fvg_bot = setup_data.get('radar_4h_fvg_bottom') or setup_data.get('fvg_bottom') or setup_data.get('poi_bottom')
            fvg_top = setup_data.get('radar_4h_fvg_top') or setup_data.get('fvg_top') or setup_data.get('poi_top')

            swap_val = setup_data.get('swap_long') if direction == 'BUY' else setup_data.get('swap_short')
            swap_line = format_swap_line(swap_val, triple_day=None)

            w1_bias = setup_data.get('w1_bias', setup_data.get('daily_bias', ''))
            w1_line = f"\n📅 W1: <b>{w1_bias}</b>" if w1_bias else ""

            trade_block = ""
            if entry and sl and tp:
                try:
                    entry_f = float(entry)
                    sl_f = float(sl)
                    tp_f = float(tp)
                    _prices_ok = (
                        prices_direction_valid(direction_raw, entry_f, sl_f, tp_f)
                        and sl_entry_magnitude_sane(symbol, entry_f, sl_f)
                    )
                    if not _prices_ok:
                        trade_block = (
                            f"\n⏳ SL/TP — prețuri JSON invalide; "
                            f"executor recalculează live 4H + D1"
                        )
                    else:
                        sl_p = sl_pips_between(symbol, entry_f, sl_f)
                        tp_p = sl_pips_between(symbol, entry_f, tp_f)
                        rr = (tp_p / sl_p) if sl_p > 0 else 0
                        rr_str = f"1:{rr:.2f}" if rr > 0 else "N/A"

                        balance = float(os.getenv('ACCOUNT_BALANCE', '10000'))
                        try:
                            import json as _json
                            from pathlib import Path
                            th = Path(__file__).parent / 'trade_history.json'
                            if th.exists():
                                with open(th, encoding='utf-8') as _tf:
                                    bal = float(_json.load(_tf).get('account', {}).get('balance', 0))
                                if bal > 0:
                                    balance = bal
                        except Exception:
                            pass
                        pip_val = 8.33 if 'JPY' in symbol.upper() else 10.0
                        risk_usd = balance * 0.05
                        lots_est = round(risk_usd / (sl_p * pip_val), 2) if sl_p > 0 else 0.01
                        lots_est = max(0.01, min(lots_est, 10.0))

                        trade_block = (
                            f"{sep}\n"
                            f"🔹 Entry  <code>{format_telegram_price(symbol, entry_f)}</code>\n"
                            f"🔸 SL     <code>{format_telegram_price(symbol, sl_f)}</code>  <i>({sl_p:.0f}p)</i>\n"
                            f"🎯 TP     <code>{format_telegram_price(symbol, tp_f)}</code>  <i>({tp_p:.0f}p)</i>\n"
                            f"⚖️ R:R    {rr_str}\n"
                            f"💵 ~${risk_usd:.0f} risk (5%) | 📦 ~{lots_est:.2f} lots"
                        )
                        if sl_p < MIN_SL_PIPS:
                            trade_block += (
                                f"\n⚠️ SL {sl_p:.0f}p — executor recalculează live 4H "
                                f"(min {MIN_SL_PIPS}p)"
                            )
                except (TypeError, ValueError) as _fmt_err:
                    trade_block = f"\n⚠️ Prețuri incomplete — executor calculează live ({_fmt_err})"
            else:
                trade_block = f"\n⏳ SL/TP — executor calculează structural live (4H + D1)"

            fvg_line = ""
            if fvg_bot is not None and fvg_top is not None:
                retrace_pct = setup_data.get('radar_4h_retrace_pct')
                retrace_suffix = (
                    f" | retrace {float(retrace_pct) * 100:.1f}%"
                    if retrace_pct is not None else ""
                )
                fvg_line = (
                    f"\n🎯 Premium/Discount 60–80% {exec_tf}: <code>"
                    f"{format_telegram_fvg_range(symbol, fvg_bot, fvg_top)}</code>"
                    f"{retrace_suffix}"
                )

            msg = (
                f"🔥 <b>EXECUTE NOW</b> — semnal activ\n"
                f"{sep}\n"
                f"{dir_emoji} <b>{symbol}</b> {direction}\n"
                f"📡 Trigger: <b>{exec_tf}</b> | 🎯 {strategy}"
                f"{swap_line}"
                f"{w1_line}"
                f"{fvg_line}"
                f"{trade_block}\n"
                f"{sep}\n"
                f"📡 Radar confirmat — <b>executor procesează</b> (5–15s)\n"
                f"🔔 La fill: <b>GLITCH ACTIVATED</b> (Position Monitor)"
            )
            return self.send_message(msg.strip(), parse_mode="HTML")
        except Exception as e:
            print(f"[ERROR] send_execute_now_alert failed for {setup_data.get('symbol', '?')}: {e}")
            return False

    def send_execute_now_blocked_alert(self, symbol: str, direction: str, reason: str) -> bool:
        """V40.6/V41.1: o singura alerta BLOCAT per simbol — dedup atomic pe disc."""
        try:
            from telegram_alert_dedup import claim_execute_now_blocked_alert

            if not claim_execute_now_blocked_alert(symbol, direction):
                print(
                    f"[V41.1 DEDUP] skip EXECUTE NOW BLOCAT {symbol} {direction} "
                    f"(alerta deja trimisa in ultima ora)"
                )
                return False

            dir_u = str(direction).upper()
            dir_emoji = "🟢" if dir_u in ('BUY', 'LONG') else "🔴"
            msg = (
                f"⛔ <b>EXECUTE NOW BLOCAT</b>\n"
                f"{UNIVERSAL_SEPARATOR}\n"
                f"{dir_emoji} <b>{symbol}</b> {dir_u}\n"
                f"📡 Radar: confirmat ✅\n"
                f"🛑 Executor: <code>{reason[:200]}</code>\n"
                f"{UNIVERSAL_SEPARATOR}\n"
                f"<i>Ordinul NU a ajuns la cTrader.</i>"
            )
            return self.send_message(msg.strip(), parse_mode="HTML")
        except Exception as e:
            print(f"[ERROR] send_execute_now_blocked_alert failed for {symbol}: {e}")
            return False

    def _load_pair_statistics(self, symbol: str) -> dict:
        """Load pair statistics from trade_history.json"""
        try:
            import json
            from pathlib import Path
            
            history_file = Path('trade_history.json')
            if not history_file.exists():
                return None
            
            with open(history_file, 'r', encoding='utf-8') as f:
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
    
    def _create_1h_chart(self, setup, df: pd.DataFrame) -> Optional[bytes]:
        """V47: Create 1H chart — log explicit on failure."""
        symbol = getattr(setup, 'symbol', '?')
        if df is None or df.empty:
            print(f"[1H CHART FAIL] {symbol}: dataframe gol")
            return None
        if len(df) < 50:
            print(f"[1H CHART FAIL] {symbol}: doar {len(df)} bare (min 50)")
            return None
        try:
            chart_bytes = self.chart_generator.create_1h_chart(
                symbol=symbol,
                df=df,
                setup=setup,
                save_path=None,
            )
            if not chart_bytes:
                print(f"[1H CHART FAIL] {symbol}: create_1h_chart returnat None")
            return chart_bytes
        except Exception as e:
            print(f"[1H CHART FAIL] {symbol}: {e}")
            return None
    
    def send_system_start(self) -> bool:
        """V15.1 SYSTEM_START message — rich institutional System Boot-up design"""
        sep = UNIVERSAL_SEPARATOR
        now = datetime.now(timezone.utc)
        current_date = now.strftime('%A, %d %B %Y')
        current_time = now.strftime('%H:%M UTC')
        message = (
            f"<b>ФорексГод.АИ</b>\n"
            f"🛰 <b>ГЛИТЧ ИН МАТРИКС | SYSTEM_START</b>\n"
            f"{sep}\n"
            f"📅 {current_date}\n"
            f"🕒 Ora: {current_time}\n"
            f"{sep}\n"
            f"🔄 Scanare structurală activă (16 perechi)\n"
            f"🛡 Risk Sentinel: <b>ACTIV</b> — Risc 5% per trade\n"
            f"📊 Auto-restart: enabled\n"
            f"📈 State tracking: active"
        )
        return self.send_message(message.strip(), parse_mode="HTML")

    def send_daily_summary(self, scanned_pairs: int, setups_found: int, active_setups: list = None) -> bool:
        """V14.3 MARKET_REPORT — CLEAN INSTITUTIONAL FORMAT by ФорексГод"""
        sep = UNIVERSAL_SEPARATOR
        now = datetime.now(timezone.utc)

        # Separate monitoring setups from executed positions
        monitoring_setups = [s for s in (active_setups or []) if s.get('status') != 'EXECUTED']
        executed_positions = [s for s in (active_setups or []) if s.get('status') == 'EXECUTED']
        active_count = len(monitoring_setups)

        # Header
        message = (
            f"🏛 MARKET_REPORT 🏛\n"
            f"{sep}\n"
            f"✅ SCANARE COMPLETĂ\n"
            f"📈 CONTEXT PORTOFOLIU\n"
            f"• Perechi analizate: {scanned_pairs}\n"
            f"• Monitorizare activă: {active_count}\n"
        )

        # Setup list — monitoring
        if monitoring_setups:
            message += f"{sep}\n"
            message += "🎯 SETUP-URI DETECTATE (Daily Bias)\n"
            for setup in monitoring_setups:
                symbol = setup.get('symbol', 'Unknown')
                dir_raw = str(setup.get('direction', '')).strip().lower()
                h4_locked = setup.get('h4_structure_locked', setup.get('h4_bias_locked', False))
                # Normalize strategy type
                raw_strat = str(setup.get('strategy_type', 'UNKNOWN')).upper()
                if raw_strat in ('CONTINUATION',):
                    raw_strat = 'CONTINUITY'
                # V37.2: bulina = directie (🟢 buy / 🔴 sell), nu albastru uniform
                dot = "🔴" if dir_raw == 'sell' else "🟢"
                if not h4_locked:
                    if raw_strat in ('CONTINUATION', 'CONTINUITY'):
                        status_suffix = " (Waiting 4H BOS / Pullback)"
                    else:
                        status_suffix = " (Waiting 4H CHoCH)"
                elif dir_raw == 'sell':
                    status_suffix = "   (confirmed SELL)"
                else:
                    status_suffix = "   (confirmed BUY)"
                message += f"{dot} {symbol} ➔ {raw_strat}{status_suffix}\n"

        # Active trades section
        if executed_positions:
            message += f"{sep}\n"
            message += "🔥 POZIȚII ACTIVE\n"
            for pos in executed_positions:
                symbol = pos.get('symbol', 'Unknown')
                dir_raw = str(pos.get('direction', '')).strip().lower()
                entry = pos.get('entry_price')
                rr = pos.get('risk_reward')
                profit = pos.get('profit')
                if entry is None or rr is None or profit is None:
                    continue
                profit_emoji = "💚" if profit > 0 else ("❤️" if profit < 0 else "💛")
                dot = "🔴" if dir_raw == 'sell' else "🟢"
                entry_fmt = format_telegram_price(symbol, entry)
                message += f"{dot} {symbol} {profit_emoji} Entry: {entry_fmt} | RR: 1:{rr:.1f} | P/L: ${profit:.2f}\n"

        return self.send_message(message.strip(), parse_mode="HTML")
    
    def _format_scan_report_line(self, sym_info: dict, bias_fallback: bool = False) -> str:
        """V37.17 — formatare linie setup / bias fallback pentru MARKET_REPORT."""
        symbol = sym_info.get('symbol', '?')
        direction = str(sym_info.get('direction', '?')).lower()
        raw_strat = str(sym_info.get('strategy', 'UNKNOWN')).upper()
        if raw_strat == 'CONTINUITY':
            raw_strat = 'CONTINUATION'
        raw_strat = raw_strat.replace('_COUNTER_W1', '')
        h4_locked = sym_info.get('h4_structure_locked', sym_info.get('h4_bias_locked', True))
        dot = "🔴" if direction == 'sell' else "🟢"
        if bias_fallback:
            status_suffix = " (Daily Bias — WAITING_D1_PULLBACK)"
        elif not h4_locked:
            if raw_strat in ('CONTINUATION', 'CONTINUITY'):
                status_suffix = " (Waiting 4H BOS / Pullback)"
            else:
                status_suffix = " (Waiting 4H CHoCH)"
        elif direction == 'sell':
            status_suffix = " (confirmed SELL)"
        else:
            status_suffix = " (confirmed BUY)"
        return f"{dot} {symbol} ➔ {raw_strat}{status_suffix}\n"

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
        V14.4 MARKET_REPORT — Professional institutional format by ФорексГод

        Sends a SINGLE final message after ALL charts are delivered.
        Must be called with time.sleep(2) BEFORE to dodge Telegram flood-control.
        """
        sep = UNIVERSAL_SEPARATOR

        # ── HEADER ──
        report = (
            f"<b>ФорексГод.АИ</b>\n"
            f"🏛 <b>MARKET_REPORT</b> 🏛\n"
            f"{sep}\n"
            f"✅ <b>SCANARE COMPLETĂ</b>\n\n"
            f"📈 <b>CONTEXT PORTOFOLIU</b>\n"
            f"• Perechi analizate: {total_pairs}\n"
            f"• Monitorizare activă: {monitoring_count}\n"
            f"• Poziții deschise: {open_positions}\n"
            f"• Setup-uri noi: {new_setups_found} (noi: {truly_new} | re-detectate: {re_detected})\n"
            f"{sep}\n"
        )

        # ── SETUP-URI ──
        if setup_symbols:
            _full_setups = [s for s in setup_symbols if not s.get('bias_fallback')]
            _bias_only = [s for s in setup_symbols if s.get('bias_fallback')]
            if _full_setups:
                report += "🎯 <b>SETUP-URI DETECTATE (Daily Bias)</b>\n"
                for sym_info in _full_setups:
                    report += self._format_scan_report_line(sym_info)
                report += "\n"
            if _bias_only:
                report += "📡 <b>DAILY BIAS FALLBACK</b> <i>(structură D1 confirmată, FVG degradat)</i>\n"
                for sym_info in _bias_only:
                    report += self._format_scan_report_line(sym_info, bias_fallback=True)
                report += "\n"

        # ── STATUS ──
        if deep_sleep_active and deep_sleep_until:
            report += f"{sep}\n😴 <b>Status: DEEP SLEEP ACTIVE</b>\n• Wake: {deep_sleep_until}\n"
        else:
            report += f"{sep}\n⚡ Status: ACTIV — Monitoring live\n"

        # Semnătura ALL CAPS oficială
        footer = (
            f"{sep}\n"
            f"🔱 AUTHORED BY <b>ФорексГод</b> 🔱\n"
            f"{sep}\n"
            f"🏛 <b>ГЛИТЧ ИН МАТРИКС</b> 🏛"
        )
        full_report = report.rstrip() + "\n" + footer

        success = self.send_message(full_report.strip(), parse_mode="HTML", add_signature=False)
        if not success:
            print("[WARN] Scan report send failed — retrying in 5s...")
            time.sleep(5)
            success = self.send_message(full_report.strip(), parse_mode="HTML", add_signature=False)
            if not success:
                print("[ERROR] Scan report FAILED after retry. Report lost.")

        return success
    
    def send_execution_confirmation(self, setup: TradeSetup, entry_type: str = 'pullback',
                                    momentum_score: float = 0, hours_elapsed: float = 0,
                                    swap_info: dict = None) -> bool:
        """Send execution confirmation when trade is placed"""
        from pip_utils import get_pip_size, get_asset_class

        direction = "🟢 LONG" if setup.direction == 'buy' else "🔴 SHORT"
        direction_emoji = "📈" if setup.direction == 'buy' else "📉"
        symbol = setup.symbol

        symbol_upper = symbol.upper()
        if get_asset_class(symbol) == 'crypto':
            sl_pct = abs(setup.stop_loss - setup.entry_price) / setup.entry_price * 100
            sl_description = (
                f"🛡️ SL: <code>{format_telegram_price(symbol, setup.stop_loss)}</code> "
                f"({sl_pct:.1f}% Crypto Safety) ✅"
            )
        else:
            pip_size = get_pip_size(symbol)
            sl_pips = abs(setup.stop_loss - setup.entry_price) / pip_size
            sl_fmt = format_telegram_price(symbol, setup.stop_loss)
            if sl_pips <= 35:
                sl_description = f"🛡️ SL: <code>{sl_fmt}</code> ({sl_pips:.0f} pips - Min Protected) ✅"
            else:
                sl_description = f"🛡️ SL: <code>{sl_fmt}</code> ({sl_pips:.0f} pips)"

        sep = "────────────────"
        swap_line = ""
        if swap_info and swap_info.get('value') is not None:
            _sv = float(swap_info['value'])
            if abs(_sv) < 1e-9:
                _sl = '⚪ NEUTRAL'
            else:
                _sl = swap_info.get('label') or ('✅ CREDIT' if _sv > 0 else '⚠️ DEBIT')
            swap_line = f"\n{sep}\n💱 EXECUTION SWAP: {_sl} | <code>{_sv:+.2f}</code> pips/zi"

        if entry_type == 'pullback':
            message = f"""
🎯 <b>TRADE EXECUTED - PULLBACK ENTRY</b>

{setup.symbol} {direction} {direction_emoji}
{sep}

✅ Pullback reached Fibo 50%
📍 Entry: <code>{format_telegram_price(symbol, setup.entry_price)}</code>
{sl_description}
🎯 Take Profit: <code>{format_telegram_price(symbol, setup.take_profit)}</code>
📊 RR: <code>1:{setup.risk_reward:.1f}</code>

⏰ Time to entry: <code>{hours_elapsed:.1f}h</code>
🎯 Classic pullback strategy ✅{swap_line}
"""
        else:  # continuation momentum
            message = f"""
🚀 <b>TRADE EXECUTED - MOMENTUM ENTRY</b>

{setup.symbol} {direction} {direction_emoji}
{sep}

✅ Strong continuation detected!
📊 Momentum Score: <code>{momentum_score:.0f}/100</code> 🔥
📍 Entry: <code>{format_telegram_price(symbol, setup.entry_price)}</code> (market)
{sl_description}
🎯 Take Profit: <code>{format_telegram_price(symbol, setup.take_profit)}</code>
📊 RR: <code>1:{setup.risk_reward:.1f}</code>

⏰ Time to entry: <code>{hours_elapsed:.1f}h</code> (after 6h wait)
💨 Riding the momentum! 🚀{swap_line}
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
            with open('trade_history.json', 'r', encoding='utf-8') as f:
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

────────────────
📊 *ACCOUNT SUMMARY:*

💵 Balance: `${balance:,.2f}`
💎 Equity: `${equity:,.2f}`
📈 P&L: `${total_pnl:+,.2f}` ({pnl_percent:+.2f}%) {pnl_emoji}

📊 Margin: `${margin_used:,.2f}` used ({margin_used/balance*100:.1f}%)
🔓 Free: `${free_margin:,.2f}`

────────────────
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
                with open('monitoring_setups.json', 'r', encoding='utf-8') as f:
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
            with open('economic_calendar.json', 'r', encoding='utf-8') as f:
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
