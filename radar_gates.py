"""
V47/V50 shared gates — radar structural alerts + Telegram scan card LTF lines.
Single source of truth for post-POI, live bars, and card confirmation logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

V47_ALERT_MAX_BARS_4H = 3
V47_ALERT_MAX_BARS_1H = 3


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
    return break_dt > anchor


def v47_live_alert_bars_ok(timeframe_display: str, bars_ago: int) -> bool:
    """V47: confirmare live doar pe break proaspăt (≤3 bare TF)."""
    cap = V47_ALERT_MAX_BARS_1H if timeframe_display == '1H' else V47_ALERT_MAX_BARS_4H
    try:
        return int(bars_ago) <= cap
    except (TypeError, ValueError):
        return False


def _h4_structural_alert_sent(merged: Dict) -> bool:
    return bool(merged.get('h4_choch_alert_sent') or merged.get('h4_bos_alert_sent'))


def _poi_monitoring_active(merged: Dict) -> bool:
    return bool(merged.get('poi_first_touch_time') or merged.get('radar_panda_active'))


def ltf_choch_confirmed_for_card(merged: Dict, tf: str, macro_dir: str) -> bool:
    """
    V51: Card Telegram scan — aceleași porți ca alertele structurale V47/V50.
    Nu folosește h4_choch/h1_choch din TradeSetup (artefact scanner istoric).
    """
    if tf == '4H':
        if _h4_structural_alert_sent(merged):
            return True
        if merged.get('EXECUTE_NOW') and str(merged.get('execute_now_trigger_tf', '')).upper() == '4H':
            return True
        if not _poi_monitoring_active(merged):
            return False
        if not merged.get('radar_4h_choch_detected'):
            return False
        if merged.get('radar_4h_choch_direction') != macro_dir:
            return False
        if not v47_break_post_poi_touch(merged, merged.get('radar_4h_choch_time')):
            return False
        return True

    if bool(merged.get('radar_1h_choch_stale')):
        return False
    if merged.get('h1_choch_alert_sent'):
        return True
    if merged.get('EXECUTE_NOW') and str(merged.get('execute_now_trigger_tf', '')).upper() == '1H':
        return True
    if not _h4_structural_alert_sent(merged):
        return False
    if not _poi_monitoring_active(merged):
        return False
    if not merged.get('radar_1h_choch_detected'):
        return False
    if merged.get('radar_1h_choch_direction') != macro_dir:
        return False
    if not v47_break_post_poi_touch(merged, merged.get('radar_1h_choch_time')):
        return False
    return True


def ltf_choch_price_for_card(merged: Dict, tf: str, confirmed: bool):
    """Preț CHoCH doar când confirmarea live e validă — fără fallback scanner."""
    if not confirmed:
        return None
    if tf == '4H':
        return merged.get('radar_4h_choch_price')
    return merged.get('choch_1h_price') or merged.get('radar_1h_choch_price')
