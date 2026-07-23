"""
V63 — Shared format helpers for Telegram Command Center + slim footer.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

SLIM_FOOTER_BRAND = "🔱 ФорексГод · Глитч Ин Матрикс"

# Telegram mobile: U+2500 (─) renders wider than Cyrillic/Latin in HTML bubbles.
# Calibrated on device: 16 chars flush with brand line (29 chars @ ~0.55).
_TELEGRAM_BOX_CHAR_RATIO = 0.55


def brand_separator(brand: str = SLIM_FOOTER_BRAND) -> str:
    """Horizontal rule flush with brand signature on Telegram mobile."""
    n = max(14, round(len(brand) * _TELEGRAM_BOX_CHAR_RATIO))
    return "─" * n


SLIM_FOOTER_SEP = brand_separator(SLIM_FOOTER_BRAND)


def format_slim_footer() -> str:
    """Single-line brand footer with separator matched to brand width."""
    return f"{SLIM_FOOTER_SEP}\n{SLIM_FOOTER_BRAND}"


def append_slim_footer(text: str) -> str:
    """Append slim footer to message body."""
    return f"{text.rstrip()}\n\n{format_slim_footer()}"


def section_header(title: str) -> str:
    """Section title with full-width separator."""
    return f"{SLIM_FOOTER_SEP}\n<b>{title}</b>"


def format_stat_block(label: str, value: str, emoji: str = "") -> str:
    """Compact stat line: emoji Label + monospace value."""
    prefix = f"{emoji} " if emoji else ""
    return f"{prefix}<b>{label}</b>\n<code>{value}</code>"


def format_two_column_grid(cells: List[str], cols: int = 2) -> str:
    """Render items in a simple multi-column grid (HTML)."""
    if not cells:
        return ""
    rows = []
    for i in range(0, len(cells), cols):
        chunk = cells[i:i + cols]
        rows.append("  " + "    ".join(chunk))
    return "\n".join(rows)


def load_monitoring_json(path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Load monitoring_setups.json resiliently.
    Handles empty files, list root, and concatenated/corrupt JSON (Extra data).
    """
    if not path.exists():
        return {}, []
    try:
        raw = path.read_text(encoding='utf-8').strip()
    except OSError as exc:
        logger.error(f"Cannot read {path}: {exc}")
        return {}, []
    if not raw:
        return {}, []

    data: Any = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            decoder = json.JSONDecoder()
            data, end = decoder.raw_decode(raw)
            if end < len(raw.strip()):
                logger.warning(
                    f"monitoring_setups.json truncated parse at char {end} "
                    f"(extra data ignored — run atomic save to repair)"
                )
        except json.JSONDecodeError as exc:
            logger.error(f"monitoring_setups.json unreadable: {exc}")
            return {}, []

    if isinstance(data, list):
        return {'setups': data}, data
    if isinstance(data, dict):
        setups = data.get('setups', [])
        if not isinstance(setups, list):
            setups = []
        return data, setups
    return {}, []


def save_monitoring_json(path: Path, data: Dict[str, Any]) -> None:
    """Atomic write — .tmp + os.replace() prevents partial/corrupt JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    with open(tmp_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_path, path)


def setup_radar_hint(setup: dict) -> str:
    """Short radar hint for command listings (hibrid RO)."""
    if setup.get('EXECUTE_NOW'):
        return '🔥 EXECUTE_NOW'
    if setup.get('radar_4h_in_fvg'):
        return '🎯 în FVG'
    if setup.get('radar_4h_choch_detected'):
        return '⏳ CHoCH → aștept FVG'
    verdict = (setup.get('radar_verdict') or '')[:40]
    return verdict or str(setup.get('status', '?'))


def format_btcusd_card(setup: dict) -> str:
    """V61-style BTCUSD quick view from monitoring JSON dict."""
    from pip_utils import format_telegram_price, format_swap_line

    symbol = setup.get('symbol', 'BTCUSD')
    direction_raw = str(setup.get('direction', 'buy')).lower()
    is_buy = direction_raw in ('buy', 'long', 'bullish')
    direction = 'LONG' if is_buy else 'SHORT'
    dir_emoji = '🟢' if is_buy else '🔴'
    status = str(setup.get('status', '?'))
    strategy = str(setup.get('strategy_type', '—')).upper()
    if strategy.startswith('CONTINUATION') or strategy.startswith('CONTINUITY'):
        strat_chip = 'CONT (BOS)'
        strat_emoji = '➡️'
    elif strategy.startswith('REVERSAL'):
        strat_chip = 'REV (CHoCH)'
        strat_emoji = '🔄'
    else:
        strat_chip = strategy[:4] if strategy else '—'
        strat_emoji = '📋'

    status_label = 'Gata execuție' if status.upper() == 'READY' else status
    block1 = (
        f"{strat_emoji} <b>{symbol}</b> · {dir_emoji} {direction}\n"
        f"📋 <b>{status_label}</b> · {strat_chip}"
    )

    block2_parts: List[str] = []
    live_price = setup.get('live_price') or setup.get('radar_live_price')
    if live_price is not None:
        try:
            block2_parts.append(
                f"💹 Preț cTrader: <code>{format_telegram_price(symbol, float(live_price))}</code>"
            )
        except (TypeError, ValueError):
            pass

    fvg_bot = setup.get('fvg_bottom') or setup.get('poi_bottom')
    fvg_top = setup.get('fvg_top') or setup.get('poi_top')
    if fvg_bot and fvg_top:
        try:
            block2_parts.append(
                f"🎯 POI Daily: <code>{format_telegram_price(symbol, float(fvg_bot))}"
                f" — {format_telegram_price(symbol, float(fvg_top))}</code>"
            )
        except (TypeError, ValueError):
            pass

    hint = setup_radar_hint(setup)
    block2_parts.append(f"📡 Radar: {hint}")

    entry = setup.get('entry_price') or setup.get('radar_4h_fvg_entry')
    sl = setup.get('stop_loss') or setup.get('h4_sl_price')
    tp = setup.get('take_profit') or setup.get('daily_tp_price')
    rr = setup.get('risk_reward')
    if entry and sl:
        try:
            block2_parts.append(
                f"🔹 Entry <code>{format_telegram_price(symbol, float(entry))}</code> · "
                f"SL <code>{format_telegram_price(symbol, float(sl))}</code>"
            )
            if tp:
                block2_parts.append(
                    f"🎯 TP <code>{format_telegram_price(symbol, float(tp))}</code>"
                )
            if rr and float(rr) > 0:
                block2_parts.append(f"⚖️ RR <code>1:{float(rr):.1f}</code>")
        except (TypeError, ValueError):
            pass
    elif setup.get('EXECUTE_NOW'):
        block2_parts.append("⏳ <i>Entry/SL/TP live la EXECUTE NOW</i>")

    swap_val = setup.get('swap_long') if is_buy else setup.get('swap_short')
    swap_line = format_swap_line(swap_val, triple_day=setup.get('swap_triple_day', 'Wed'), ro=True)
    if swap_line:
        block1 += swap_line

    setup_time = setup.get('setup_time', '')
    if setup_time:
        block2_parts.append(f"📅 Setup: <code>{setup_time[:10]}</code>")

    ml_score = setup.get('ml_score')
    if ml_score not in (None, '—', ''):
        block2_parts.append(f"🧠 ML: <code>{ml_score}/100</code> · <i>informativ</i>")

    body = block1
    if block2_parts:
        body += f"\n{SLIM_FOOTER_SEP}\n" + "\n".join(block2_parts)
    return body
