#!/usr/bin/env python3
"""Audit monitoring_setups.json — compare total vs /monitoring 'pândă' filter."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

WATCHING = frozenset({
    'MONITORING', 'READY', 'WAITING_D1_PULLBACK',
    'WAITING_4H_CHOCH', 'WAITING_4H_PULLBACK',
    'WAITING_W_D_SYNC', 'WAITING_W_ZONE',
    'WAITING_POSITION_CLOSE',
})


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit monitoring_setups.json counts')
    parser.add_argument('--symbol', help='Show detail for one symbol (e.g. USDCAD)')
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    mon_file = root / 'monitoring_setups.json'
    if not mon_file.exists():
        print(f'❌ Missing: {mon_file}')
        return 1

    raw = mon_file.read_text(encoding='utf-8').strip()
    if not raw:
        print('⚠️  monitoring_setups.json is empty')
        return 1

    data = json.loads(raw)
    if isinstance(data, dict):
        setups = data.get('setups', [])
        last_updated = data.get('last_updated', '?')
    elif isinstance(data, list):
        setups = data
        last_updated = '?'
    else:
        print('❌ Unexpected JSON shape')
        return 1

    in_panda = [s for s in setups if s.get('status') in WATCHING]
    hidden = [s for s in setups if s.get('status') not in WATCHING]

    print(f'last_updated:      {last_updated}')
    print(f'TOTAL JSON:        {len(setups)}')
    print(f'IN PANDA (/mon):   {len(in_panda)}')
    print(f'HIDDEN from /mon:  {len(hidden)}')
    print()
    print('Status breakdown:', dict(Counter(s.get('status') for s in setups)))
    print()
    print('IN PANDA (/monitoring):')
    for s in sorted(in_panda, key=lambda x: x.get('symbol', '')):
        fvg = ' | In FVG' if s.get('radar_4h_in_fvg') else ''
        en = ' | EXECUTE_NOW' if s.get('EXECUTE_NOW') else ''
        wd = '' if s.get('w_d_aligned', True) else ' | W≠D'
        print(f"  {s.get('symbol', '?'):8} {s.get('status', '?')}{fvg}{en}{wd}")
    print()
    if hidden:
        print('HIDDEN from /monitoring (still in JSON):')
        for s in sorted(hidden, key=lambda x: x.get('symbol', '')):
            print(f"  {s.get('symbol', '?'):8} {s.get('status', '?')}")
    else:
        print('No hidden setups — all JSON entries are in _WATCHING.')

    if args.symbol:
        sym_u = args.symbol.upper()
        match = next((s for s in setups if s.get('symbol', '').upper() == sym_u), None)
        print()
        if not match:
            print(f'❌ {sym_u} NOT in monitoring_setups.json')
            print('   → rulează daily_scanner.py sau verifică [V59 PERSIST AUDIT] în log scan')
            return 1
        print(f'Detail {sym_u}:')
        for k in (
            'status', 'direction', 'w_d_aligned', 'w1_bias', 'EXECUTE_NOW',
            'radar_4h_in_fvg', 'radar_4h_choch_detected', 'h4_structure_locked',
            'structural_breach', 'last_rejection_reason',
        ):
            if k in match:
                print(f'  {k}: {match[k]}')
        if match.get('status') == 'WAITING_W_D_SYNC' and match.get('w_d_aligned'):
            print('  ⚠️  STICKY BUG: w_d_aligned=True but status still WAITING_W_D_SYNC')
            print('     → pull latest code (resolve_status_after_w_d_sync fix)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
