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
from pip_utils import (
    format_telegram_price,
    format_telegram_fvg_range,
    format_swap_line,
    format_poi_price_relation,
)
from radar_gates import ltf_choch_confirmed_for_card, ltf_choch_price_for_card

from telegram_command_format import SLIM_FOOTER_SEP, format_slim_footer

load_dotenv()

# W→D→4H: raportul așteaptă CHoCH 4H aliniat cu D1 (nu BOS ca mesaj user-facing).
_WAIT_4H_CHOCH_HINT = "Waiting 4H CHoCH"
_WAIT_4H_CHOCH_HINT_RO = "Așteptăm CHoCH aliniat D1"

# V60 MARKET_REPORT — phase keys (grouped vertical layout)
PHASE_WD_SYNC = "wd_sync"
PHASE_W1_ZONE = "w1_zone"
PHASE_D1_PULLBACK = "d1_pullback"
PHASE_H4_CHOCH = "h4_choch"
PHASE_READY = "ready"

_PHASE_ORDER = (
    PHASE_WD_SYNC,
    PHASE_W1_ZONE,
    PHASE_D1_PULLBACK,
    PHASE_H4_CHOCH,
    PHASE_READY,
)

_PHASE_LABELS = {
    PHASE_WD_SYNC: "⏳ W+D nealiniat",
    PHASE_W1_ZONE: "⏳ Zonă W1",
    PHASE_D1_PULLBACK: "⏳ Pullback D1",
    PHASE_H4_CHOCH: "⏳ Confirmare 4H",
    PHASE_READY: "✅ Gata execuție",
}


def _normalize_sym_info(sym_info: dict) -> dict:
    """Normalize setup dict keys from JSON or legacy send_daily_summary."""
    out = dict(sym_info)
    if 'strategy' not in out and out.get('strategy_type'):
        out['strategy'] = out['strategy_type']
    return out


def _classify_setup_phase(sym_info: dict) -> str:
    """Classify setup into W→D→4H phase for grouped MARKET_REPORT."""
    info = _normalize_sym_info(sym_info)
    status = str(info.get('status') or '').upper()
    if status == 'READY':
        return PHASE_READY
    if info.get('h4_structure_locked') or info.get('h4_bias_locked'):
        return PHASE_READY
    if status == 'WAITING_W_D_SYNC' or info.get('w_d_aligned') is False:
        return PHASE_WD_SYNC
    if status == 'WAITING_W_ZONE':
        return PHASE_W1_ZONE
    if status == 'WAITING_D1_PULLBACK':
        return PHASE_D1_PULLBACK
    if status == 'WAITING_4H_CHOCH':
        return PHASE_H4_CHOCH
    if status == 'MONITORING':
        return PHASE_H4_CHOCH
    return PHASE_H4_CHOCH


def _format_strategy_short(raw_strat: str) -> str:
    s = str(raw_strat or 'UNKNOWN').upper().replace('_COUNTER_W1', '')
    if s in ('CONTINUITY', 'CONTINUATION'):
        return 'CONT'
    if s.startswith('REVERSAL'):
        return 'REV'
    return s[:4] if len(s) > 4 else s


def _format_compact_line(sym_info: dict) -> str:
    """One symbol per line: 🟢 GBPCAD · REV"""
    info = _normalize_sym_info(sym_info)
    symbol = info.get('symbol', '?')
    direction = str(info.get('direction', 'buy')).lower()
    strat = _format_strategy_short(info.get('strategy', 'UNKNOWN'))
    dot = "🔴" if direction == 'sell' else "🟢"
    return f"{dot} {symbol} · {strat}\n"


def _group_setups_by_phase(setup_symbols: list) -> dict:
    grouped = {k: [] for k in _PHASE_ORDER}
    for sym_info in setup_symbols or []:
        phase = _classify_setup_phase(sym_info)
        grouped[phase].append(sym_info)
    return grouped


def _render_grouped_setups(setup_symbols: list) -> str:
    """Vertical list grouped by phase — status shown once per group header."""
    if not setup_symbols:
        return ""
    grouped = _group_setups_by_phase(setup_symbols)
    parts = []
    for phase in _PHASE_ORDER:
        items = grouped.get(phase) or []
        if not items:
            continue
        label = _PHASE_LABELS[phase]
        parts.append(f"{label} · {len(items)}\n")
        for sym_info in items:
            parts.append(_format_compact_line(sym_info))
        parts.append("\n")
    return "".join(parts)


def _scan_report_wait_suffix(sym_info: dict) -> str:
    """Legacy suffix — prefer grouped MARKET_REPORT (V60). Kept for send_daily_summary fallback."""
    phase = _classify_setup_phase(sym_info)
    return f" ({_PHASE_LABELS.get(phase, '⏳ Confirmare 4H')})"

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
    'h4_choch_alert_sent', 'h4_bos_alert_sent',
    'radar_panda_active', 'radar_4h_choch_detected', 'radar_4h_choch_direction',
    'radar_4h_choch_price', 'radar_4h_choch_time', 'radar_4h_choch_bars_ago',
    'radar_4h_status', 'EXECUTE_NOW', 'execute_now_trigger_tf',
    'poi_first_touch_time', 'h4_fvg_first_touch_time',
)


def _setup_attr(setup: Any, key: str, default=None):
    if isinstance(setup, dict):
        return setup.get(key, default)
    return getattr(setup, key, default)


def _scan_card_wait_hint(setup: Any) -> str:
    """RO wait hint for V61 scan card Block 3."""
    status = str(_setup_attr(setup, 'status', '') or '')
    if status == 'WAITING_W_D_SYNC' or _setup_attr(setup, 'w_d_aligned', True) is False:
        return 'Așteptăm sync W+D'
    if status == 'WAITING_W_ZONE':
        return 'Așteptăm zonă W1'
    return _WAIT_4H_CHOCH_HINT_RO


def _is_w1_counter_trend(setup: Any, raw_dir: str) -> bool:
    confidence = _setup_attr(setup, 'confidence', 'NORMAL')
    w1_bias = _setup_attr(setup, 'w1_bias', None)
    if confidence == 'LOW_W1_COUNTER_TREND':
        return True
    if not w1_bias or w1_bias == 'NEUTRAL':
        return False
    return (
        (w1_bias == 'BEARISH' and raw_dir == 'bullish')
        or (w1_bias == 'BULLISH' and raw_dir == 'bearish')
    )


def _resolve_radar_snapshot(
    symbol: str,
    macro_dir: str,
    radar_snapshot: Optional[Dict],
) -> Dict:
    """Use in-memory snapshot when provided; else fall back to monitoring JSON."""
    if radar_snapshot is not None:
        if not radar_snapshot:
            return {}
        return {k: radar_snapshot[k] for k in _RADAR_LIVE_KEYS if k in radar_snapshot}
    return _load_monitoring_radar_snapshot(symbol, macro_dir)


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


def _merge_radar_state(setup: Any, snap: Dict) -> Dict:
    """Merge monitoring JSON snapshot with setup dict fields for V51 gate evaluation."""
    merged = dict(snap) if snap else {}
    if isinstance(setup, dict):
        source = setup
    else:
        source = {}
        for key in _RADAR_LIVE_KEYS:
            val = getattr(setup, key, None)
            if val not in (None, False, ''):
                source[key] = val
    for key in _RADAR_LIVE_KEYS:
        val = source.get(key)
        if val not in (None, False, '') and key not in merged:
            merged[key] = val
    return merged


def _ltf_choch_confirmed(
    setup: Any,
    snap: Dict,
    tf: str,
    macro_dir: str,
) -> bool:
    """V51/W→D→4H: live interconectat cu radar — fără artefacte scanner istorice."""
    merged = _merge_radar_state(setup, snap)
    return ltf_choch_confirmed_for_card(merged, tf, macro_dir)


def _ltf_choch_price(setup: Any, snap: Dict, tf: str, macro_dir: str):
    merged = _merge_radar_state(setup, snap)
    confirmed = ltf_choch_confirmed_for_card(merged, tf, macro_dir)
    return ltf_choch_price_for_card(merged, tf, confirmed)


def _format_radar_exec_lines(
    setup: Any,
    symbol: str,
    macro_dir: str,
    wait_hint: str,
    radar_snapshot: Optional[Dict] = None,
) -> str:
    snap = _resolve_radar_snapshot(symbol, macro_dir, radar_snapshot)

    if _ltf_choch_confirmed(setup, snap, '4H', macro_dir):
        price_4h = _ltf_choch_price(setup, snap, '4H', macro_dir)
        if price_4h is not None:
            return (
                f"📡 ✅ 4H CHoCH confirmat — "
                f"<code>{format_telegram_price(symbol, price_4h)}</code>"
            )
        return "📡 ✅ 4H CHoCH confirmat"
    return f"📡 4H: ⏳ {wait_hint}"


def _trade_levels_valid(entry, sl) -> bool:
    """True dacă entry și SL sunt non-zero și floatabile."""
    try:
        ef = float(entry)
        sf = float(sl)
        return abs(ef) > 1e-12 and abs(sf) > 1e-12
    except (TypeError, ValueError):
        return False


def _choch_monitoring_levels_line() -> str:
    """V62: disclaimer scurt — Entry/SL/TP doar la EXECUTE_NOW."""
    return "📐 <i>Entry/SL/TP live la semnal · fără nivele fantomă D1</i>"


def _strategy_chip_4h(strategy: str, d1_sig: str, signal_type: str) -> str:
    """REV (CHoCH) / CONT (BOS) for 4H structural alert caption."""
    strat_u = str(strategy or '').upper().replace('_COUNTER_W1', '')
    if strat_u.startswith('REVERSAL'):
        return 'REV (CHoCH)'
    if strat_u.startswith('CONTINUATION') or strat_u.startswith('CONTINUITY'):
        return 'CONT (BOS)'
    sig = (signal_type or 'CHoCH').upper()
    if sig == 'BOS' or str(d1_sig or '').upper() == 'BOS':
        return 'CONT (BOS)'
    return 'REV (CHoCH)'


def _normalize_alert_direction(raw: str) -> tuple:
    """Return (BUY|SELL, display label 🟢 LONG|🔴 SHORT)."""
    d = str(raw or 'buy').upper()
    if d in ('LONG', 'BUY', 'BULLISH'):
        return 'BUY', '🟢 LONG'
    return 'SELL', '🔴 SHORT'


def _live_price_from_df(df_4h) -> Optional[float]:
    if df_4h is None or getattr(df_4h, 'empty', True):
        return None
    try:
        if len(df_4h) < 1:
            return None
        return float(df_4h['close'].iloc[-1])
    except (TypeError, ValueError, KeyError, IndexError):
        return None


def format_4h_structural_alert(
    setup_data: dict,
    tf_data=None,
    signal_type: str = 'CHoCH',
    live_price: Optional[float] = None,
) -> str:
    """V62 — caption hibrid RO pentru alertă 4H CHoCH/BOS (+ chart PNG)."""
    symbol = setup_data.get('symbol', 'UNKNOWN')
    sig = (signal_type or 'CHoCH').upper()
    direction, dir_label = _normalize_alert_direction(setup_data.get('direction', 'buy'))
    strategy = str(setup_data.get('strategy_type', 'reversal'))
    d1_sig = str(setup_data.get('d1_signal_type', '') or '').upper()
    w1_bias = setup_data.get('w1_bias', 'NEUTRAL') or 'NEUTRAL'
    sep = UNIVERSAL_SEPARATOR

    struct_dir = (
        getattr(tf_data, 'choch_direction', None)
        or setup_data.get('radar_4h_choch_direction')
        or ('bearish' if direction == 'SELL' else 'bullish')
    )
    if sig == 'BOS' and getattr(tf_data, 'bos_direction', None):
        struct_dir = tf_data.bos_direction

    break_px = (
        getattr(tf_data, 'choch_price', None)
        or setup_data.get('radar_4h_choch_price')
        or setup_data.get('entry_price')
        or 0
    )
    bars_ago = getattr(tf_data, 'choch_bars_ago', None) or setup_data.get('radar_4h_choch_bars_ago')
    if sig == 'BOS':
        bars_ago = getattr(tf_data, 'bos_bars_ago', None) or bars_ago

    strategy_chip = _strategy_chip_4h(strategy, d1_sig, sig)
    is_cont = strategy_chip.startswith('CONT')
    line_emoji = '➡️' if is_cont or sig == 'BOS' else '🔄'
    sig_label = 'BOS 4H confirmat' if sig == 'BOS' else 'CHoCH 4H confirmat'

    block1 = (
        f"{line_emoji} <b>{symbol}</b> · {dir_label}\n"
        f"⚡ <b>{sig_label}</b> · {strategy_chip}"
    )
    if w1_bias and w1_bias != 'NEUTRAL':
        aligned = (w1_bias == 'BULLISH' and direction == 'BUY') or \
                  (w1_bias == 'BEARISH' and direction == 'SELL')
        w1_suffix = '✅' if aligned else '⚠️ nealiniat'
        block1 += f"\n📅 W1: <b>{w1_bias}</b> {w1_suffix}"

    block2_parts = []
    if live_price is not None:
        block2_parts.append(
            f"💹 Preț cTrader: <code>{format_telegram_price(symbol, live_price)}</code>"
        )

    break_line = f"📍 Break 4H: <code>{format_telegram_price(symbol, break_px)}</code>"
    if bars_ago is not None and bars_ago != 9999:
        break_line += f" · {bars_ago} bare post-POI"
    block2_parts.append(break_line)

    macro_dir = 'BULLISH' if direction == 'BUY' else 'BEARISH'
    d1_label = d1_sig or ('BOS' if is_cont else 'CHoCH')
    block2_parts.append(f"📊 D1: <b>{macro_dir} {d1_label}</b>")

    if w1_bias == 'NEUTRAL':
        block2_parts.append('📅 W1: NEUTRAL')

    retrace = getattr(tf_data, 'retrace_pct', None) if tf_data is not None else None
    if retrace is not None:
        try:
            rp = float(retrace)
            pct_display = rp * 100.0 if abs(rp) <= 1.5 else rp
            block2_parts.append(
                f"📉 Retrace impuls: {pct_display:.0f}% · așteptăm 60–80%"
            )
        except (TypeError, ValueError):
            pass

    impulse_label = 'BOS' if sig == 'BOS' else '4H'
    block3 = (
        f"\n{sep}\n"
        f"⏳ <b>Următorul pas:</b> retrace 60–80% pe impuls {impulse_label} → <b>EXECUTE NOW</b>\n"
        f"{_choch_monitoring_levels_line()}"
    )

    return f"{block1}\n{sep}\n" + "\n".join(block2_parts) + block3


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
        charts_mode: str = 'full',  # V15.0: 'full' | 'daily_only'
        radar_snapshot: Optional[Dict] = None,
    ) -> bool:
        """
        Send complete trade setup alert with:
        - Formatted message
        - Daily chart screenshot
        - 4H chart screenshot (ONLY when charts_mode='full')
        V15.0 Silent Scan: charts_mode='daily_only' → trimite doar Daily chart la scanare.
        V43.9: fără butoane manuale — execuția rămâne autonomă (radar + executor).
        Alertele structurale 4H se trimit separat (send_4h_structural_alert).
        """
        # 1. Send main alert message
        message = self.format_setup_alert(setup, radar_snapshot=radar_snapshot)
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
        
        # V15.0 SILENT SCAN: la charts_mode='daily_only' oprim aici — 4H vine la confirmare CHoCH
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
        V62: Alertă 4H — CHoCH/BOS, photo+caption hibrid RO, fallback text.
        """
        symbol = setup_data.get('symbol', 'UNKNOWN')
        sig = (signal_type or 'CHoCH').upper()
        try:
            direction, _ = _normalize_alert_direction(setup_data.get('direction', 'buy'))
            strategy = str(setup_data.get('strategy_type', 'reversal')).upper()

            live_price = _live_price_from_df(df_4h)
            caption = format_4h_structural_alert(
                setup_data, tf_data=tf_data, signal_type=sig, live_price=live_price,
            )

            break_px = (
                getattr(tf_data, 'choch_price', None)
                or setup_data.get('radar_4h_choch_price')
                or setup_data.get('entry_price')
                or 0
            )
            struct_dir = (
                getattr(tf_data, 'choch_direction', None)
                or setup_data.get('radar_4h_choch_direction')
                or ('bearish' if direction == 'SELL' else 'bullish')
            )

            chart_4h = None
            if df_4h is not None and not df_4h.empty and len(df_4h) >= 50:
                try:
                    from types import SimpleNamespace
                    struct_dir_l = str(struct_dir).lower()
                    h4_choch_ns = SimpleNamespace(
                        direction=struct_dir_l,
                        break_price=break_px,
                        index=getattr(tf_data, 'choch_bars_ago', None),
                    )
                    setup_ns = SimpleNamespace(
                        symbol=symbol,
                        entry_price=break_px,
                        stop_loss=None,
                        take_profit=None,
                        risk_reward=0,
                        status='MONITORING',
                        strategy_type=strategy.lower(),
                        daily_choch=SimpleNamespace(
                            direction='bullish' if direction == 'BUY' else 'bearish'
                        ),
                        h4_choch=h4_choch_ns,
                        fvg=None,
                        choch_break_price=break_px,
                    )
                    chart_4h = self.chart_generator.create_4h_chart(
                        symbol=symbol,
                        df=df_4h,
                        setup=setup_ns,
                        save_path=None,
                    )
                    if chart_4h is None:
                        print(f"[WARNING] 4H chart render returned None for {symbol} — retry once")
                        chart_4h = self.chart_generator.create_4h_chart(
                            symbol=symbol,
                            df=df_4h,
                            setup=setup_ns,
                            save_path=None,
                        )
                except Exception as chart_err:
                    print(f"[WARNING] 4H chart render failed for {symbol}: {chart_err}")
            else:
                df_len = len(df_4h) if df_4h is not None else 0
                print(f"[WARNING] 4H chart skipped for {symbol}: df len={df_len} (need >=50)")

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

    def format_setup_alert(self, setup, radar_snapshot: Optional[Dict] = None) -> str:
        """V61 scan card — hibrid RO, preț live cTrader, Block 3 compact."""
        sep = UNIVERSAL_SEPARATOR
        symbol = setup.symbol

        raw_dir = getattr(setup, 'd1_bias_direction', None) or setup.daily_choch.direction
        if raw_dir in ('buy', 'long'):
            raw_dir = 'bullish'
        elif raw_dir in ('sell', 'short'):
            raw_dir = 'bearish'
        direction = "🟢 LONG" if raw_dir == 'bullish' else "🔴 SHORT"

        pair_stats = self._load_pair_statistics(symbol)

        status_emoji = "✅" if setup.status == 'READY' else "📋"
        status_label = "Gata execuție" if setup.status == 'READY' else "Scan OK"

        strategy_type = getattr(setup, 'strategy_type', 'reversal').upper()
        if strategy_type.startswith('REVERSAL'):
            strategy_emoji = "🔄"
            strategy_chip = "REV (CHoCH)"
        else:
            strategy_emoji = "➡️"
            strategy_chip = "CONT (BOS)"

        wait_hint = _scan_card_wait_hint(setup)
        w1_counter = _is_w1_counter_trend(setup, raw_dir)

        # ── BLOC 1: Identitate ──
        block1 = (
            f"{strategy_emoji} <b>{symbol}</b> · {direction}\n"
            f"{status_emoji} <b>{status_label}</b> · {strategy_chip}"
        )
        if w1_counter:
            block1 += "\n⚠️ <b>W1 nealiniat</b>"

        swap_val = getattr(setup, 'swap_long', None) if raw_dir == 'bullish' \
                   else getattr(setup, 'swap_short', None)
        swap_triple = getattr(setup, 'swap_triple_day', 'Wed')
        block1 += format_swap_line(swap_val, triple_day=swap_triple, ro=True)

        # ── BLOC 2: Context live cTrader ──
        block2_parts = []

        live_price = getattr(setup, 'live_price', None)
        if live_price is not None:
            block2_parts.append(
                f"💹 Preț cTrader: <code>{format_telegram_price(symbol, live_price)}</code>"
            )

        poi_range = format_telegram_fvg_range(symbol, setup.fvg.bottom, setup.fvg.top)
        poi_relation = format_poi_price_relation(live_price, setup.fvg.bottom, setup.fvg.top)
        poi_line = f"🎯 POI Daily: <code>{poi_range}</code>"
        if poi_relation:
            poi_line += f" · {poi_relation}"
        block2_parts.append(poi_line)

        daily_structure_label = getattr(setup, 'd1_signal_type', None) or (
            "CHoCH" if strategy_type.startswith('REVERSAL') else "BOS"
        )
        block2_parts.append(
            f"📊 D1: <b>{raw_dir.upper()} {daily_structure_label}</b>"
        )

        w1_bias_val = getattr(setup, 'w1_bias', None)
        if w1_bias_val and w1_bias_val != 'NEUTRAL':
            is_aligned = (w1_bias_val == 'BULLISH' and raw_dir == 'bullish') or \
                         (w1_bias_val == 'BEARISH' and raw_dir == 'bearish')
            w1_suffix = "✅" if is_aligned else "⚠️ nealiniat"
            block2_parts.append(f"📅 W1: <b>{w1_bias_val}</b> {w1_suffix}")
        else:
            block2_parts.append("📅 W1: NEUTRAL")

        if hasattr(setup, 'ml_score') and setup.ml_score is not None and \
           hasattr(setup, 'ai_probability_score') and setup.ai_probability_score is not None:
            ml_score = setup.ml_score
            ai_prob = setup.ai_probability_score * 10
            fused_score = int((ml_score * 0.6) + (ai_prob * 0.4))
            confidence = "HIGH" if fused_score >= 75 else "MED" if fused_score >= 60 else "LOW"
            rec = getattr(setup, 'ml_recommendation', 'REVIEW')
            rec_badge = "EXECUTE" if rec == 'TAKE' else "REVIEW" if rec == 'REVIEW' else "SKIP"
            block2_parts.append(
                f"🧠 <b>AI: {fused_score}% ({confidence})</b> · {rec_badge} · <i>informativ</i>"
            )

        if pair_stats:
            wr = pair_stats.get('win_rate', 0)
            trades = pair_stats.get('total_trades', 0)
            quality = "Exc" if wr >= 60 else "Good" if wr >= 45 else "Avg"
            block2_parts.append(f"✨ Istoric bot: {quality} · {trades} trades")

        if hasattr(setup, 'liquidity_sweep') and setup.liquidity_sweep:
            sweep = setup.liquidity_sweep
            conf_boost = getattr(setup, 'confidence_boost', 0)
            block2_parts.append(f"💧 {sweep['sweep_type']} +{conf_boost}")

        block2 = f"\n{sep}\n" + "\n".join(block2_parts)

        # ── BLOC 3: Radar & Execuție ──
        h4_line = _format_radar_exec_lines(
            setup, symbol, raw_dir, wait_hint, radar_snapshot=radar_snapshot,
        )

        block3 = (
            f"\n{sep}\n"
            f"{h4_line}\n"
            f"⏳ <b>Entry/SL/TP</b> la <b>EXECUTE NOW</b> · radar 4H live"
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

        # Setup list — monitoring (V60 grouped vertical)
        if monitoring_setups:
            message += f"{sep}\n"
            sym_list = [
                {
                    'symbol': s.get('symbol', 'Unknown'),
                    'direction': s.get('direction', 'buy'),
                    'strategy': s.get('strategy_type', 'UNKNOWN'),
                    'status': s.get('status', 'MONITORING'),
                    'h4_structure_locked': s.get('h4_structure_locked', s.get('h4_bias_locked', False)),
                    'w_d_aligned': s.get('w_d_aligned', True),
                }
                for s in monitoring_setups
            ]
            message += f"🎯 SETUP-URI ({len(sym_list)})\n\n"
            message += _render_grouped_setups(sym_list)

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
        setup_symbols: list = None,
        watching_count: int = None,
        persist_missing: list = None,
    ) -> bool:
        """
        V60 MARKET_REPORT — grouped vertical layout, compact header/footer.

        Sends a SINGLE final message after ALL charts are delivered.
        Must be called with time.sleep(2) BEFORE to dodge Telegram flood-control.
        """
        sep = UNIVERSAL_SEPARATOR
        _watching = watching_count if watching_count is not None else monitoring_count

        # ── HEADER (compact) ──
        report = (
            f"<b>ФорексГод.АИ</b>\n"
            f"🏛 <b>MARKET_REPORT</b> 🏛\n"
            f"{sep}\n"
            f"✅ <b>Scan complet</b> · {total_pairs} perechi\n"
            f"📊 {new_setups_found} setup · {_watching} monitorizare · {open_positions} deschise\n"
        )
        if truly_new > 0 or re_detected > 0:
            report += (
                f"<i>Detectate azi: {new_setups_found} "
                f"({truly_new} noi · {re_detected} re-scan)</i>\n"
            )
        if monitoring_count != _watching:
            report += f"<i>Total JSON: {monitoring_count}</i>\n"
        report += f"{sep}\n"

        # ── SETUP-URI (grouped vertical) ──
        if setup_symbols:
            _full_setups = [s for s in setup_symbols if not s.get('bias_fallback')]
            _bias_only = [s for s in setup_symbols if s.get('bias_fallback')]
            if _full_setups:
                report += f"🎯 <b>Setup-uri cu POI ({len(_full_setups)})</b>\n\n"
                report += _render_grouped_setups(_full_setups)
            if _bias_only:
                report += (
                    f"📡 <b>Bias D1 fără FVG ({len(_bias_only)})</b>\n"
                    f"   <i>structură OK — lipsește zona POI Daily</i>\n\n"
                )
                report += _render_grouped_setups(_bias_only)

        if persist_missing:
            report += "⚠️ <b>Detectate dar nesalvate în JSON</b>\n"
            for row in persist_missing[:10]:
                sym = row.get('symbol', '?')
                reason = row.get('reason', '?')
                report += f"• <code>{sym}</code> — <i>{reason}</i>\n"
            report += "\n"

        # ── STATUS ──
        if deep_sleep_active and deep_sleep_until:
            report += f"{sep}\n😴 <b>Deep sleep</b> · wake {deep_sleep_until}\n"
        else:
            report += f"{sep}\n⚡ Activ — radar live\n"

        footer = format_slim_footer()
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
