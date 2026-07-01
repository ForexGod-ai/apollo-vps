#!/usr/bin/env python3
"""V47: simulare eligibilitate alerte CHoCH/BOS din monitoring_setups.json."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from multi_tf_radar import (
    _v47_break_post_poi_touch,
    _v47_live_alert_bars_ok,
)


def _load_setups(path: Path) -> list:
    data = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(data, dict):
        return data.get('setups', [])
    return data


def audit_setup(setup: dict) -> dict:
    sym = setup.get('symbol', '?')
    macro = 'bearish' if str(setup.get('direction', '')).upper() in ('SELL', 'SHORT') else 'bullish'
    panda = setup.get('radar_panda_active', False)
    h4_gate = setup.get('radar_4h_choch_detected') or setup.get('h4_structure_locked')
    sig = setup.get('radar_4h_signal_type', 'CHoCH')
    bars = setup.get('radar_4h_choch_bars_ago', 9999)
    choch_time = setup.get('radar_4h_choch_time')
    post_poi = _v47_break_post_poi_touch(setup, choch_time)
    live = _v47_live_alert_bars_ok('4H', int(bars) if bars is not None else 9999)
    dir_ok = setup.get('radar_4h_choch_direction') == macro

    h4_choch_ok = (
        panda and dir_ok and post_poi and live
        and sig == 'CHoCH' and not setup.get('h4_choch_alert_sent')
    )
    h4_bos_ok = (
        panda and dir_ok and post_poi and live
        and sig == 'BOS' and not setup.get('h4_bos_alert_sent')
    )
    h1_ok = (
        panda and h4_gate and setup.get('radar_1h_choch_detected')
        and setup.get('radar_1h_choch_direction') == macro
        and not setup.get('h1_choch_alert_sent')
        and setup.get('poi_first_touch_time')
    )

    return {
        'symbol': sym,
        'panda': panda,
        'h4_gate': h4_gate,
        'signal': sig,
        'post_poi': post_poi,
        'live_4h': live,
        'would_alert_4h_choch': h4_choch_ok,
        'would_alert_4h_bos': h4_bos_ok,
        'would_alert_1h': h1_ok,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='V47 CHoCH alert eligibility audit')
    parser.add_argument('--symbol', default=None)
    parser.add_argument(
        '--json',
        default=str(ROOT / 'monitoring_setups.json'),
        help='Path to monitoring_setups.json',
    )
    args = parser.parse_args()
    path = Path(args.json)
    if not path.exists():
        print(f"Missing {path}")
        sys.exit(1)
    setups = _load_setups(path)
    if args.symbol:
        setups = [s for s in setups if s.get('symbol') == args.symbol.upper()]
    for s in setups:
        r = audit_setup(s)
        print(
            f"{r['symbol']}: panda={r['panda']} h4_gate={r['h4_gate']} "
            f"sig={r['signal']} post_poi={r['post_poi']} live={r['live_4h']} | "
            f"alert CHoCH={r['would_alert_4h_choch']} BOS={r['would_alert_4h_bos']} "
            f"1H={r['would_alert_1h']}"
        )


if __name__ == '__main__':
    main()
