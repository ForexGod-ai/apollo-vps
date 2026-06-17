#!/usr/bin/env python3
"""
Daily central bank rates refresh for VPS cron.

Usage:
    python scripts/refresh_cb_rates.py
    python scripts/refresh_cb_rates.py --no-notify
    python scripts/refresh_cb_rates.py --print

Cron example (08:00 EET daily):
    0 8 * * * cd /path/to/apollo && python3 scripts/refresh_cb_rates.py >> logs/cb_rates_refresh.log 2>&1
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from macro_rates import refresh_rates_daily  # noqa: E402


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Refresh CB rates cache on VPS")
    parser.add_argument("--no-notify", action="store_true", help="Skip Telegram alerts")
    parser.add_argument("--print", action="store_true", dest="print_json", help="Print JSON summary")
    args = parser.parse_args()

    result = refresh_rates_daily(notify_telegram=not args.no_notify)
    if args.print_json:
        import json
        print(json.dumps(result, indent=2))
    else:
        n = len(result.get("changes", []))
        print(f"[refresh_cb_rates] source={result.get('source')} changes={n}")
    return 0 if result.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
