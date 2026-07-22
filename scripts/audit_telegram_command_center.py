#!/usr/bin/env python3
"""
Audit Telegram Command Center — diagnostic inbound /status /monitoring.

Rulează pe VPS după deploy:
  python scripts/audit_telegram_command_center.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import psutil
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')
USER_ID = os.getenv('TELEGRAM_USER_ID', '')


def _sep(title: str) -> None:
    print(f"\n{'=' * 60}\n  {title}\n{'=' * 60}")


def check_env() -> bool:
    _sep('1. ENV')
    ok = True
    print(f"  TELEGRAM_BOT_TOKEN: {'OK' if TOKEN else 'MISSING'}")
    print(f"  TELEGRAM_CHAT_ID:   {CHAT_ID or 'MISSING'}")
    print(f"  TELEGRAM_USER_ID:   {USER_ID or 'MISSING'}")
    if not TOKEN:
        ok = False
    return ok


def check_processes() -> None:
    _sep('2. PROCESE telegram_command_center.py')
    found = []
    for proc in psutil.process_iter(['pid', 'cmdline', 'name']):
        try:
            cmd = ' '.join(proc.info.get('cmdline') or [])
            if 'telegram_command_center' in cmd:
                found.append((proc.info['pid'], cmd[:120]))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    if not found:
        print("  ❌ ZERO instanțe — command center NU rulează")
        print("     → python telegram_command_center.py")
    elif len(found) == 1:
        print(f"  ✅ O instanță (PID {found[0][0]})")
    else:
        print(f"  ❌ {len(found)} instanțe — CONFLICT getUpdates probabil:")
        for pid, cmd in found:
            print(f"     PID {pid}: {cmd}")


def check_lock() -> None:
    _sep('3. PID LOCK')
    lock = ROOT / 'process_telegram_command_center.lock'
    if not lock.exists():
        print("  ⚪ Lock file absent")
        return
    try:
        pid = int(lock.read_text().strip())
        alive = psutil.pid_exists(pid)
        print(f"  Lock PID: {pid} | alive={alive}")
        if alive and not any(
            'telegram_command_center' in ' '.join(p.info.get('cmdline') or [])
            for p in psutil.process_iter(['cmdline'])
            if p.pid == pid
        ):
            print("  ⚠️ PID alive dar cmdline nu conține scriptul (Windows hidden — normal)")
    except Exception as e:
        print(f"  ⚠️ Lock unreadable: {e}")


def check_webhook_and_updates() -> None:
    _sep('4. TELEGRAM API (polling)')
    if not TOKEN:
        print("  skip — no token")
        return
    wh = requests.get(f"https://api.telegram.org/bot{TOKEN}/getWebhookInfo", timeout=15).json()
    url = wh.get('result', {}).get('url') or ''
    print(f"  Webhook URL: {url or '(none — polling OK)'}")
    if url:
        print("  ❌ Webhook ACTIV — getUpdates nu primește comenzi. Rulează deleteWebhook.")
    offset_file = ROOT / 'data' / 'tg_last_update_id.json'
    offset = 0
    if offset_file.exists():
        offset = int(json.loads(offset_file.read_text()).get('last_update_id', 0))
    print(f"  last_update_id: {offset}")
    resp = requests.get(
        f"https://api.telegram.org/bot{TOKEN}/getUpdates",
        params={'offset': offset + 1, 'limit': 3, 'timeout': 0},
        timeout=15,
    )
    print(f"  getUpdates HTTP: {resp.status_code}")
    if resp.status_code == 409:
        print("  ❌ 409 CONFLICT — alt proces face polling pe același bot")
    elif resp.status_code == 200:
        data = resp.json()
        pending = len(data.get('result', []))
        print(f"  pending updates: {pending}")
        if pending:
            print("  ℹ️ Comenzi în coadă — command center nu le consumă (proces mort sau blocat)")


def check_send_test() -> None:
    _sep('5. sendMessage test (outbound)')
    if not TOKEN or not CHAT_ID:
        print("  skip")
        return
    text = "🔧 AUDIT: outbound Telegram OK — trimite /status acum"
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={'chat_id': CHAT_ID, 'text': text},
        timeout=15,
    )
    print(f"  HTTP {r.status_code}: {r.text[:150]}")


def main() -> int:
    print("TELEGRAM COMMAND CENTER AUDIT")
    if not check_env():
        return 1
    check_processes()
    check_lock()
    check_webhook_and_updates()
    check_send_test()
    _sep('REZUMAT')
    print("  Outbound (scan/alerts) ≠ Inbound (getUpdates polling).")
    print("  Dacă outbound OK dar comenzi nu merg:")
    print("    1) O singură instanță telegram_command_center.py")
    print("    2) Fără webhook (deleteWebhook)")
    print("    3) Fără getUpdates 409 (oprește duplicate)")
    print("    4) git pull + restart command center")
    return 0


if __name__ == '__main__':
    sys.exit(main())
