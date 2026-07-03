#!/usr/bin/env python3
"""V50: simulare eligibilitate alerte CHoCH/BOS + replay structural post-POI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar_gates import (
    parse_radar_dt as _parse_radar_dt,
    v47_break_post_poi_touch as _v47_break_post_poi_touch,
    v47_live_alert_bars_ok as _v47_live_alert_bars_ok,
)
from multi_tf_radar import (
    MultiTFRadar,
    _filter_structural_post_poi,
    _is_structural_break_valid,
    _retrace_is_alert_valid,
    _structural_event_dt,
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
    h4_gate_v50 = bool(setup.get('h4_choch_alert_sent') or setup.get('h4_bos_alert_sent'))
    sig = setup.get('radar_4h_signal_type', 'CHoCH')
    bars_4h = setup.get('radar_4h_choch_bars_ago', 9999)
    bars_1h = setup.get('radar_1h_choch_bars_ago', 9999)
    choch_time_4h = setup.get('radar_4h_choch_time')
    choch_time_1h = setup.get('radar_1h_choch_time')
    post_poi_4h = _v47_break_post_poi_touch(setup, choch_time_4h)
    post_poi_1h = _v47_break_post_poi_touch(setup, choch_time_1h)
    live_4h = _v47_live_alert_bars_ok('4H', int(bars_4h) if bars_4h is not None else 9999)
    live_1h = _v47_live_alert_bars_ok('1H', int(bars_1h) if bars_1h is not None else 9999)
    dir_4h_ok = setup.get('radar_4h_choch_direction') == macro
    dir_1h_ok = setup.get('radar_1h_choch_direction') == macro
    retrace_1h = setup.get('radar_1h_retrace_pct')
    retrace_ok = _retrace_is_alert_valid(retrace_1h)

    h4_choch_ok = (
        panda and dir_4h_ok and post_poi_4h and live_4h
        and sig == 'CHoCH' and not setup.get('h4_choch_alert_sent')
        and setup.get('radar_4h_choch_detected')
    )
    h4_bos_ok = (
        panda and dir_4h_ok and post_poi_4h and live_4h
        and sig == 'BOS' and not setup.get('h4_bos_alert_sent')
    )
    h1_ok = (
        panda and h4_gate_v50
        and setup.get('radar_1h_choch_detected')
        and dir_1h_ok
        and not setup.get('h1_choch_alert_sent')
        and setup.get('poi_first_touch_time')
        and post_poi_1h and live_1h and retrace_ok
        and not setup.get('radar_1h_choch_stale')
    )

    block_reasons = []
    if panda and setup.get('radar_1h_choch_detected') and not h1_ok:
        if not h4_gate_v50:
            block_reasons.append('no_h4_alert_this_poi')
        if not live_1h:
            block_reasons.append(f'1h_stale_{bars_1h}b')
        if not post_poi_1h:
            block_reasons.append('1h_pre_poi')
        if not retrace_ok:
            block_reasons.append('retrace_invalid')

    return {
        'symbol': sym,
        'panda': panda,
        'h4_gate_v50': h4_gate_v50,
        'signal': sig,
        'post_poi_4h': post_poi_4h,
        'post_poi_1h': post_poi_1h,
        'live_4h': live_4h,
        'live_1h': live_1h,
        'would_alert_4h_choch': h4_choch_ok,
        'would_alert_4h_bos': h4_bos_ok,
        'would_alert_1h': h1_ok,
        'block_reasons': block_reasons,
    }


def replay_symbol(symbol: str) -> None:
    """V50: listează CHoCH-uri H1/H4 aliniate vs post-POI din scan live."""
    radar = MultiTFRadar()
    setups = radar.load_monitoring_setups()
    setup = next((s for s in setups if s.get('symbol') == symbol.upper()), None)
    if not setup:
        print(f"No setup for {symbol} in monitoring_setups.json")
        return

    macro = 'bearish' if str(setup.get('direction', '')).upper() in ('SELL', 'SHORT') else 'bullish'
    anchor = _parse_radar_dt(setup.get('poi_first_touch_time'))
    print(f"\n=== V50 REPLAY {symbol} bias={macro} poi_touch={setup.get('poi_first_touch_time')} ===")

    for tf, bars in (('H1', 400), ('H4', 300)):
        df = radar.get_historical_data(symbol.upper(), tf, bars)
        if df is None or df.empty:
            print(f"  [{tf}] no data")
            continue
        det = radar.smc_1h if tf == 'H1' else radar.smc_4h
        chochs, bos = det.detect_choch_and_bos(df)
        aligned = [c for c in chochs if c.direction == macro]
        post_poi = _filter_structural_post_poi(aligned, anchor) if anchor else aligned
        print(f"  [{tf}] aligned={len(aligned)} post_poi={len(post_poi)} (anchor={anchor})")
        for c in aligned[-5:]:
            ba = len(df) - c.index
            edt = _structural_event_dt(c)
            post = edt is not None and anchor is not None and edt > anchor
            valid = _is_structural_break_valid(c, c.direction, df)
            live = _v47_live_alert_bars_ok('1H' if tf == 'H1' else '4H', ba)
            print(
                f"    {c.direction} @ {c.break_price:.5f} -{ba}b "
                f"post_poi={post} valid={valid} live={live}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description='V50 CHoCH alert eligibility audit')
    parser.add_argument('--symbol', default=None)
    parser.add_argument('--replay', action='store_true', help='Live structural replay for --symbol')
    parser.add_argument(
        '--json',
        default=str(ROOT / 'monitoring_setups.json'),
        help='Path to monitoring_setups.json',
    )
    args = parser.parse_args()
    if args.replay:
        if not args.symbol:
            print('--replay requires --symbol')
            sys.exit(1)
        replay_symbol(args.symbol.upper())
        return

    path = Path(args.json)
    if not path.exists():
        print(f"Missing {path}")
        sys.exit(1)
    setups = _load_setups(path)
    if args.symbol:
        setups = [s for s in setups if s.get('symbol') == args.symbol.upper()]
    for s in setups:
        r = audit_setup(s)
        blocks = ','.join(r['block_reasons']) if r['block_reasons'] else '-'
        print(
            f"{r['symbol']}: panda={r['panda']} h4_gate_v50={r['h4_gate_v50']} "
            f"post_poi_4h={r['post_poi_4h']} live_4h={r['live_4h']} "
            f"live_1h={r['live_1h']} | "
            f"alert CHoCH={r['would_alert_4h_choch']} BOS={r['would_alert_4h_bos']} "
            f"1H={r['would_alert_1h']} blocks=[{blocks}]"
        )


if __name__ == '__main__':
    main()
