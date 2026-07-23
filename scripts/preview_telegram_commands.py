#!/usr/bin/env python3
"""
V63 — Preview Telegram Command Center layouts (no Telegram send).

Usage:
  python3 scripts/preview_telegram_commands.py
  python3 scripts/preview_telegram_commands.py --command stats
  python3 scripts/preview_telegram_commands.py --command status
  python3 scripts/preview_telegram_commands.py --command btcusd
  python3 scripts/preview_telegram_commands.py --command help
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault('TELEGRAM_BOT_TOKEN', 'preview-token')
os.environ.setdefault('TELEGRAM_CHAT_ID', 'preview-chat')
os.environ.setdefault('AUTHORIZED_USER_ID', '1')

from telegram_command_center import TelegramCommandCenter
from telegram_command_format import append_slim_footer

MOBILE_WIDTH = 40


def _strip_html(text: str) -> str:
    return re.sub(r'</?[^>]+>', '', text)


def _print_block(title: str, body: str) -> None:
    plain = _strip_html(body)
    print("=" * MOBILE_WIDTH)
    print(title)
    print("-" * MOBILE_WIDTH)
    for line in plain.splitlines():
        print(line[:MOBILE_WIDTH])
    print(f"[{len(plain)} chars]")


def main() -> int:
    parser = argparse.ArgumentParser(description="Preview V63 command layouts")
    parser.add_argument(
        '--command',
        choices=['stats', 'weekly', 'help', 'monitoring', 'status', 'btcusd', 'active', 'news', 'resume', 'all'],
        default='all',
    )
    args = parser.parse_args()

    cc = TelegramCommandCenter()
    handlers = {
        'stats': cc.handle_stats_command,
        'weekly': cc.handle_weekly_command,
        'help': lambda: cc.process_command.__doc__,  # placeholder
        'monitoring': cc.handle_monitoring_command,
        'status': cc.handle_status_command,
        'btcusd': cc.handle_btcusd_command,
        'active': cc.handle_active_command,
        'news': cc.handle_news_command,
        'resume': cc.handle_resume_command,
    }

    if args.command == 'help':
        with patch.object(cc, 'admin_id', cc.authorized_user_id):
            cc.admin_id = cc.authorized_user_id
        # Simulate help output directly
        sep_cmd = __import__('telegram_command_format', fromlist=['SLIM_FOOTER_SEP']).SLIM_FOOTER_SEP
        body = (
            f"<b>🎮 Command Center V63</b>\n{sep_cmd}\n\n"
            f"<code>/stats</code> · <code>/status</code> · <code>/monitoring</code>"
        )
        _print_block('/help (preview)', append_slim_footer(body))
        return 0

    targets = list(handlers.keys()) if args.command == 'all' else [args.command]
    for name in targets:
        if name == 'help':
            continue
        try:
            body = handlers[name]()
        except Exception as exc:
            body = f"❌ Preview error: {exc}"
        _print_block(f"/{name}", append_slim_footer(body))

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
