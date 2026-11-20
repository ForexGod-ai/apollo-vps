"""
V47/V50 shared gates — radar structural alerts + Telegram scan card LTF lines.
Single source of truth for post-POI, live bars, and card confirmation logic.
W→D→4H: LTF confirmare exclusiv pe 4H.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

V47_ALERT_MAX_BARS_4H = 3


def normalize_structural_direction(raw) -> Optional[str]:
    """Normalize LONG/SHORT/buy/sell/bullish/bearish → bullish/bearish."""
    if raw is None:
        return None
    d = str(raw).strip().lower()
    if d in ('bullish', 'long', 'buy'):
        return 'bullish'
    if d in ('bearish', 'short', 'sell'):
        return 'bearish'
    return None


def h4_structural_direction_ok(macro_dir, tf_4h) -> bool:
    """True when 4H CHoCH/BOS direction matches D1 macro bias (normalized)."""
    macro = normalize_structural_direction(macro_dir)
    if macro is None:
        return False
    sig = (getattr(tf_4h, 'signal_type', None) or 'CHoCH').upper()
    if sig == 'BOS':
        actual = normalize_structural_direction(getattr(tf_4h, 'bos_direction', None))
    else:
        actual = normalize_structural_direction(getattr(tf_4h, 'choch_direction', None))
    return actual == macro


def parse_radar_dt(ts) -> Optional[datetime]:
    """Parse ISO choch_time from TimeframeAnalysis or JSON."""
    if ts is None:
        return None
    try:
        s = str(ts).replace('Z', '+00:00')
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def resolve_mitigation_touch_anchor(setup_data: dict) -> Optional[datetime]:
    """V43.8: Ancoră cronologie = primul touch POI/FVG din pullback curent."""
    candidates = []
    for key in ('poi_first_touch_time', 'h4_fvg_first_touch_time'):
        dt = parse_radar_dt(setup_data.get(key))
        if dt is not None:
            candidates.append(dt)
    return max(candidates) if candidates else None


def v47_break_post_poi_touch(setup_data: dict, break_time_str: Optional[str]) -> bool:
    """V47: break structural trebuie să fie DUPĂ primul touch POI (anti-zombi)."""
    anchor = resolve_mitigation_touch_anchor(setup_data)
    if anchor is None:
        return False
    break_dt = parse_radar_dt(break_time_str)
    if break_dt is None:
        return True
    return break_dt >= anchor


def v47_live_alert_bars_ok(timeframe_display: str, bars_ago: int) -> bool:
    """V47: confirmare live doar pe break proaspăt (≤3 bare 4H)."""
    if timeframe_display != '4H':
        return False
    try:
        return int(bars_ago) <= V47_ALERT_MAX_BARS_4H
    except (TypeError, ValueError):
        return False


def _h4_structural_alert_sent(merged: Dict) -> bool:
    return bool(merged.get('h4_choch_alert_sent') or merged.get('h4_bos_alert_sent'))


def _poi_monitoring_active(merged: Dict) -> bool:
    return bool(merged.get('poi_first_touch_time') or merged.get('radar_panda_active'))


def ltf_choch_confirmed_for_card(merged: Dict, tf: str, macro_dir: str) -> bool:
    """
    V51/W→D→4H: Card Telegram scan — aceleași porți ca alertele structurale V47/V50.
    Confirmare LTF exclusiv pe 4H.
    """
    if tf != '4H':
        return False
    if _h4_structural_alert_sent(merged):
        return True
    if merged.get('EXECUTE_NOW') and str(merged.get('execute_now_trigger_tf', '')).upper() == '4H':
        return True
    if not _poi_monitoring_active(merged):
        return False
    if not merged.get('radar_4h_choch_detected'):
        return False
    if normalize_structural_direction(merged.get('radar_4h_choch_direction')) != normalize_structural_direction(macro_dir):
        return False
    if not v47_break_post_poi_touch(merged, merged.get('radar_4h_choch_time')):
        return False
    return True


def h4_move_exhausted_vs_d1_tp(
    setup_data: dict,
    break_price: Optional[float],
    threshold: float = 0.55,
) -> tuple[bool, str]:
    """
    V93: block 4H structural alert when break is >threshold along POI-mid → D1 TP leg.
    Returns (exhausted, reason).
    """
    if break_price is None:
        return False, ''
    poi_top = setup_data.get('poi_top') or setup_data.get('fvg_top')
    poi_bottom = setup_data.get('poi_bottom') or setup_data.get('fvg_bottom')
    d1_tp = setup_data.get('take_profit') or setup_data.get('daily_target_price')
    try:
        if poi_top is None or poi_bottom is None or d1_tp is None:
            return False, ''
        poi_mid = (float(poi_top) + float(poi_bottom)) / 2.0
        total_leg = abs(float(d1_tp) - poi_mid)
        if total_leg <= 0:
            return False, ''
        traveled = abs(float(break_price) - poi_mid)
        if traveled / total_leg > threshold:
            return True, 'move_exhausted_far_from_poi'
    except (TypeError, ValueError):
        return False, ''
    return False, ''


def fib_entry_zone_60_80(
    break_price: float,
    swing_broken_price: float,
    direction: str,
) -> tuple[Optional[float], Optional[float]]:
    """V93: 60–80% retrace band on 4H impulse (entry zone)."""
    try:
        bp = float(break_price)
        sb = float(swing_broken_price)
    except (TypeError, ValueError):
        return None, None
    impulse = abs(bp - sb)
    if impulse <= 0:
        return None, None
    d = str(direction or '').lower()
    if d == 'bullish':
        fib_60 = bp - impulse * 0.60
        fib_80 = bp - impulse * 0.80
        return min(fib_60, fib_80), max(fib_60, fib_80)
    fib_60 = bp + impulse * 0.60
    fib_80 = bp + impulse * 0.80
    return min(fib_60, fib_80), max(fib_60, fib_80)


def ltf_choch_price_for_card(merged: Dict, tf: str, confirmed: bool):
    """Preț CHoCH 4H doar când confirmarea live e validă — fără fallback scanner."""
    if not confirmed or tf != '4H':
        return None
    return merged.get('radar_4h_choch_price')
