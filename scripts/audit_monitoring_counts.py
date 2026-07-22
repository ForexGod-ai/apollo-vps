#!/usr/bin/env python3
"""Audit monitoring_setups.json — compare total vs /monitoring 'pândă' filter."""
from __future__ import annotations

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
    elif isinstance(data, list):
        setups = data
    else:
        print('❌ Unexpected JSON shape')
        return 1

    in_panda = [s for s in setups if s.get('status') in WATCHING]
    hidden = [s for s in setups if s.get('status') not in WATCHING]

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
        print(f"  {s.get('symbol', '?'):8} {s.get('status', '?')}{fvg}{en}")
    print()
    if hidden:
        print('HIDDEN from /monitoring (still in JSON, counted in scan "11"):')
        for s in sorted(hidden, key=lambda x: x.get('symbol', '')):
            print(f"  {s.get('symbol', '?'):8} {s.get('status', '?')}")
    else:
        print('No hidden setups — all JSON entries are in _WATCHING.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
