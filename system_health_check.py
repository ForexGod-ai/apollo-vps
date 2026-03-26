#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║   🦅 GLITCH IN MATRIX — SYSTEM HEALTH CHECK V11.2 EAGLE EYE    ║
║   Autor: ФорексГод | Actualizat: 26 Martie 2026                 ║
╚══════════════════════════════════════════════════════════════════╝

Verifică integritatea completă a sistemului:
  1. 6 Daemoni activi
  2. Port 8767 (cTrader Bridge) + swap DB
  3. V11.2 Eagle Eye config (200 bare, Fractal 10, extrema abs)
  4. Spread guard / TF alignment check
  5. Fișiere critice + monitoring_setups.json freshness

Rulare: python3 system_health_check.py
"""

import os
import sys
import json
import re
import psutil
import requests
from pathlib import Path
from datetime import datetime, timezone

# ── Configuration ──────────────────────────────────────────────
BASE_DIR = Path(__file__).parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    pass

TELEGRAM_TOKEN   = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
CTRADER_PORT     = int(os.getenv('CTRADER_PORT', '8767'))

# ── Culori ANSI ────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):    return f"{GREEN}✅ {msg}{RESET}"
def fail(msg):  return f"{RED}❌ {msg}{RESET}"
def warn(msg):  return f"{YELLOW}⚠️  {msg}{RESET}"
def info(msg):  return f"{CYAN}ℹ️  {msg}{RESET}"


class HealthCheck:
    """🦅 V11.2 Eagle Eye — Health Check complet Glitch in Matrix"""

    # ── Cei 6 daemoni critici ──────────────────────────────────
    DAEMONS = {
        "ctrader_sync_daemon.py":       "🔗 cTrader Sync Daemon",
        "position_monitor.py":          "📊 Position Monitor",
        "setup_executor_monitor.py":    "🎯 Setup Executor Monitor",
        "watchdog_monitor.py":          "🐕 Watchdog Monitor",
        "telegram_command_center.py":   "📱 Telegram Command Center",
        "news_calendar_monitor.py":     "📰 News Calendar Monitor",
    }

    def __init__(self):
        self.passed  = 0
        self.failed  = 0
        self.warnings = 0
        self.issues  = []

    def _p(self, line=""):
        print(line)

    def _section(self, title):
        print(f"\n{BOLD}{'─'*66}{RESET}")
        print(f"{BOLD}{CYAN}  {title}{RESET}")
        print(f"{BOLD}{'─'*66}{RESET}")

    # ──────────────────────────────────────────────────────────
    # CHECK 1 — CEI 6 DAEMONI
    # ──────────────────────────────────────────────────────────
    def check_daemons(self):
        self._section("1/5  👻 DAEMONI ACTIVI")
        running_scripts = set()
        for proc in psutil.process_iter(['cmdline']):
            try:
                cmd = ' '.join(proc.info['cmdline'] or [])
                for script in self.DAEMONS:
                    if script in cmd:
                        running_scripts.add(script)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        all_ok = True
        for script, label in self.DAEMONS.items():
            if script in running_scripts:
                print(f"   {ok(f'{label:<40} RUNNING')}")
                self.passed += 1
            else:
                print(f"   {fail(f'{label:<40} NOT RUNNING')}")
                self.failed += 1
                self.issues.append(f"Daemon oprit: {label}")
                all_ok = False

        if all_ok:
            print(f"\n   {ok('Toți cei 6 daemoni sunt activi!')} 🚀")
        else:
            print(f"\n   {warn('Repornire: python3 <daemon>.py &')}")

    # ──────────────────────────────────────────────────────────
    # CHECK 2 — PORT 8767 + SWAP DB
    # ──────────────────────────────────────────────────────────
    def check_ctrader_bridge(self):
        self._section("2/5  🔌 cTRADER BRIDGE (port 8767) + SWAP DB")

        base_url = f"http://localhost:{CTRADER_PORT}"

        # 2a. /health
        try:
            r = requests.get(f"{base_url}/health", timeout=4)
            if r.status_code == 200:
                print(f"   {ok(f'Bridge online: {base_url}/health → HTTP 200')}")
                self.passed += 1
            else:
                print(f"   {warn(f'Bridge HTTP {r.status_code}')}")
                self.warnings += 1
        except Exception:
            print(f"   {fail(f'Bridge OFFLINE — localhost:{CTRADER_PORT} nu răspunde')}")
            self.failed += 1
            self.issues.append(f"cTrader Bridge offline (port {CTRADER_PORT})")

        # 2b. Price feed EURUSD D1
        try:
            r = requests.get(f"{base_url}/data?symbol=EURUSD&timeframe=D1&bars=1", timeout=4)
            if r.status_code == 200:
                data = r.json()
                bars = data.get('bars') or data.get('data', [])
                if bars:
                    close = bars[-1].get('close', 'N/A')
                    print(f"   {ok(f'Price feed activ — EURUSD D1 close: {close}')}")
                    self.passed += 1
                else:
                    print(f"   {warn('Price feed → 0 bare returnate')}")
                    self.warnings += 1
            else:
                print(f"   {warn(f'Price feed HTTP {r.status_code}')}")
                self.warnings += 1
        except Exception as e:
            print(f"   {warn(f'Price feed error: {e}')}")
            self.warnings += 1

        # 2c. Swap DB — verifică monitoring_setups.json pentru swap fields
        setups_file = BASE_DIR / "monitoring_setups.json"
        try:
            with open(setups_file) as f:
                data = json.load(f)
            setups = data.get('setups', data) if isinstance(data, dict) else data
            setups = setups if isinstance(setups, list) else []

            with_swap = [s for s in setups if s.get('swap_long') is not None]
            total     = len(setups)
            print(f"   {ok(f'monitoring_setups.json: {total} setups, {len(with_swap)}/{total} cu swap rates')}"
                  if with_swap or total == 0 else
                  f"   {warn(f'{total} setups FĂRĂ swap rates — rulează ctrader_sync_daemon')}")
            self.passed += 1 if (with_swap or total == 0) else 0
            if not with_swap and total > 0:
                self.warnings += 1

            # Freshness check — ultima modificare
            mtime = os.path.getmtime(setups_file)
            age_h = (datetime.now().timestamp() - mtime) / 3600
            if age_h < 25:
                print(f"   {ok(f'monitoring_setups.json proaspăt — modificat acum {age_h:.1f}h')}")
                self.passed += 1
            else:
                print(f"   {warn(f'monitoring_setups.json vechi — {age_h:.0f}h de la ultimul scan')}")
                self.warnings += 1

        except FileNotFoundError:
            print(f"   {warn('monitoring_setups.json LIPSĂ — nu s-a rulat niciun scan')}")
            self.warnings += 1
        except Exception as e:
            print(f"   {fail(f'monitoring_setups.json eroare: {e}')}")
            self.failed += 1

        # 2d. Swap live via /swap_info
        try:
            r = requests.get(f"{base_url}/swap_info?symbol=EURUSD", timeout=4)
            if r.status_code == 200:
                d = r.json()
                sl = d.get('swap_long', 'N/A')
                ss = d.get('swap_short', 'N/A')
                tri = d.get('swap_triple_day', 'N/A')
                print(f"   {ok(f'Swap live EURUSD: Long={sl} Short={ss} Triple={tri}')}")
                self.passed += 1
            else:
                print(f"   {warn(f'/swap_info HTTP {r.status_code}')}")
                self.warnings += 1
        except Exception:
            print(f"   {warn('/swap_info endpoint indisponibil (bridge offline?)')}")
            self.warnings += 1

    # ──────────────────────────────────────────────────────────
    # CHECK 3 — V11.2 EAGLE EYE CONFIG
    # ──────────────────────────────────────────────────────────
    def check_v112_config(self):
        self._section("3/5  🦅 V11.2 EAGLE EYE — CONFIG CHECKS")

        # 3a. pairs_config.json — D1=200, H4=200
        try:
            with open(BASE_DIR / "pairs_config.json") as f:
                cfg = json.load(f)
            lb = cfg['scanner_settings']['lookback_candles']
            d1, h4, h1 = lb.get('daily', 0), lb.get('h4', 0), lb.get('h1', 0)

            for label, val, req in [('D1 lookback', d1, 200), ('H4 lookback', h4, 200), ('H1 lookback', h1, 300)]:
                if val >= req:
                    print(f"   {ok(f'{label}: {val} bare (≥{req} ✅)')}")
                    self.passed += 1
                else:
                    print(f"   {fail(f'{label}: {val} bare (trebuie ≥{req})')}")
                    self.failed += 1
                    self.issues.append(f"pairs_config {label}={val} < {req}")
        except Exception as e:
            print(f"   {fail(f'pairs_config.json eroare: {e}')}")
            self.failed += 1

        # 3b. smc_detector.py — Fractal Window 10
        try:
            with open(BASE_DIR / "smc_detector.py") as f:
                smc = f.read()

            checks = [
                ('FRACTAL_WINDOW = 10',                    'Fractal Window 10 declarat'),
                ('body_lows_4h.iloc[sl_window_start:',     'SL LONG extrema absolută'),
                ('body_highs_4h.iloc[sl_window_start:',    'SL SHORT extrema absolută'),
                ('body_highs_d1.iloc[:-1].max()',           'TP LONG raw D1 max'),
                ('body_lows_d1.iloc[:-1].min()',            'TP SHORT raw D1 min'),
                ('V11.2 EXTREME VISION',                    'Label V11.2 prezent'),
            ]
            for pattern, label in checks:
                if pattern in smc:
                    print(f"   {ok(label)}")
                    self.passed += 1
                else:
                    print(f"   {fail(f'{label} — LIPSĂ în smc_detector.py')}")
                    self.failed += 1
                    self.issues.append(f"smc_detector: {label} lipsă")

            # Verificare că [-1] SL nu mai există
            old_sl = re.findall(r'structural_\w+\[-1\]\.price', smc)
            if old_sl:
                print(f"   {fail(f'SL [-1] REZIDUAL găsit: {old_sl}')}")
                self.failed += 1
                self.issues.append(f"smc_detector: SL [-1] rezidual")
            else:
                print(f"   {ok('Zero referințe SL [-1] rezidual')}")
                self.passed += 1

        except Exception as e:
            print(f"   {fail(f'smc_detector.py eroare: {e}')}")
            self.failed += 1

        # 3c. daily_scanner.py — scan_single_pair nu mai are 100 hardcodat
        try:
            with open(BASE_DIR / "daily_scanner.py") as f:
                ds = f.read()
            old100 = re.findall(r'get_historical_data\([^)]+,\s*100\s*\)', ds)
            if old100:
                print(f"   {fail(f'daily_scanner: 100-bara hardcodat găsit: {len(old100)} loc(uri)')}")
                self.failed += 1
                self.issues.append("daily_scanner: 100 bare hardcodat")
            else:
                print(f"   {ok('daily_scanner: zero 100-bara hardcodat')}")
                self.passed += 1
        except Exception as e:
            print(f"   {fail(f'daily_scanner.py eroare: {e}')}")
            self.failed += 1

    # ──────────────────────────────────────────────────────────
    # CHECK 4 — SPREAD GUARD + TF ALIGNMENT
    # ──────────────────────────────────────────────────────────
    def check_spread_and_tf_alignment(self):
        self._section("4/5  📐 SPREAD GUARD + TF ALIGNMENT")

        # 4a. Ora curentă UTC — risc spread la 00:00 UTC
        now_utc = datetime.now(timezone.utc)
        hour_utc = now_utc.hour
        is_rollover = (hour_utc == 0 and now_utc.minute < 15)
        is_weekend  = now_utc.weekday() >= 5  # Sâmbătă=5, Duminică=6

        time_str    = now_utc.strftime("%H:%M")
        weekday_str = now_utc.strftime("%A %H:%M")

        if is_rollover:
            print(f"   {warn('ORA CRITICA: ' + time_str + ' UTC — ROLLOVER! Spread x3-x10 posibil')}")
            print(f"   {warn('Executiile sunt blocate automat daca spread_guard e activ')}")
            self.warnings += 1
            self.issues.append("Rollover 00:00 UTC activ — spread periculos")
        elif is_weekend:
            print(f"   {warn('WEEKEND: ' + weekday_str + ' UTC — Spread largit, piete inchise')}")
            self.warnings += 1
        else:
            print(f"   {ok('Ora sigura: ' + time_str + ' UTC (non-rollover, non-weekend)')}")
            self.passed += 1

        # 4b. Verifică SUPER_CONFIG pentru spread guard
        try:
            with open(BASE_DIR / "SUPER_CONFIG.json") as f:
                sc = json.load(f)
            max_spread = sc.get('max_spread_pips') or sc.get('risk_management', {}).get('max_spread_pips')
            if max_spread:
                print(f"   {ok(f'Spread guard configurat: max {max_spread} pips')}")
                self.passed += 1
            else:
                print(f"   {warn('max_spread_pips NEGĂSIT în SUPER_CONFIG.json')}")
                self.warnings += 1
                self.issues.append("Spread guard neconfigurat în SUPER_CONFIG.json")
        except Exception as e:
            print(f"   {warn(f'SUPER_CONFIG.json eroare: {e}')}")
            self.warnings += 1

        # 4c. TF Alignment: verifică că D1 close se actualizează la 00:00 UTC
        print(f"\n   {info('TF Alignment — Logică V11.2:')}")
        print(f"        D1 bara nouă se deschide la 00:00 UTC (IC Markets)")
        print(f"        4H bare: 00:00 / 04:00 / 08:00 / 12:00 / 16:00 / 20:00 UTC")
        print(f"        Scanner recomandat: 06:00-08:00 UTC (după D1 close + 4H confirmare)")

        # 4d. Verifică dacă există spread check în smc_detector sau executor
        try:
            with open(BASE_DIR / "smc_detector.py") as f:
                smc_txt = f.read()
            with open(BASE_DIR / "setup_executor_monitor.py") as f:
                exec_txt = f.read()

            has_spread = ('spread' in smc_txt.lower() or 'spread' in exec_txt.lower())
            if has_spread:
                print(f"\n   {ok('Referință \"spread\" găsită în cod (guard parțial activ)')}")
                self.passed += 1
            else:
                print(f"\n   {warn('Zero referință la spread în detector/executor — recomandăm add spread_guard')}")
                self.warnings += 1
                self.issues.append("Spread guard lipsă în setup_executor_monitor.py")
        except Exception as e:
            print(f"   {warn(f'Spread check eroare: {e}')}")

    # ──────────────────────────────────────────────────────────
    # CHECK 5 — FIȘIERE CRITICE + LOG SIZE
    # ──────────────────────────────────────────────────────────
    def check_critical_files(self):
        self._section("5/5  📂 FIȘIERE CRITICE + LOGS")

        critical = [
            "smc_detector.py",
            "daily_scanner.py",
            "setup_executor_monitor.py",
            "position_monitor.py",
            "watchdog_monitor.py",
            "telegram_command_center.py",
            "news_calendar_monitor.py",
            "ctrader_cbot_client.py",
            "ctrader_executor.py",
            "pairs_config.json",
            "SUPER_CONFIG.json",
            "monitoring_setups.json",
            "economic_calendar.json",
        ]

        for fname in critical:
            fpath = BASE_DIR / fname
            if fpath.exists():
                size_kb = fpath.stat().st_size // 1024
                print(f"   {ok(f'{fname:<45} {size_kb:>5} KB')}")
                self.passed += 1
            else:
                print(f"   {fail(f'{fname:<45} LIPSĂ!')}")
                self.failed += 1
                self.issues.append(f"Fișier critic lipsă: {fname}")

        # Log sizes
        print()
        heavy_logs = []
        for logf in BASE_DIR.glob("*.log"):
            size_mb = logf.stat().st_size / (1024 * 1024)
            if size_mb > 50:
                heavy_logs.append((logf.name, size_mb))

        if heavy_logs:
            print(f"   {warn('Loguri mari (>50MB) — consideră rotație:')}")
            for name, mb in sorted(heavy_logs, key=lambda x: -x[1])[:5]:
                print(f"        {name}: {mb:.0f} MB")
            self.warnings += 1
        else:
            print(f"   {ok('Niciun log >50MB (dimensiuni OK)')}")
            self.passed += 1

    # ──────────────────────────────────────────────────────────
    # SUMMARY FINAL
    # ──────────────────────────────────────────────────────────
    def print_summary(self):
        total = self.passed + self.failed + self.warnings
        print(f"\n{'═'*66}")
        print(f"{BOLD}  🦅 V11.2 EAGLE EYE — REZULTAT FINAL{RESET}")
        print(f"{'═'*66}")
        print(f"  {GREEN}✅ Passed:   {self.passed}{RESET}")
        print(f"  {YELLOW}⚠️  Warnings: {self.warnings}{RESET}")
        print(f"  {RED}❌ Failed:   {self.failed}{RESET}")
        print(f"{'─'*66}")

        if self.failed == 0 and self.warnings == 0:
            print(f"\n  {GREEN}{BOLD}💚 SISTEM 100% OPERATIONAL — GLITCH IN MATRIX READY TO HUNT!{RESET}\n")
        elif self.failed == 0:
            print(f"\n  {YELLOW}{BOLD}💛 SISTEM FUNCTIONAL cu {self.warnings} avertisment(e) minore.{RESET}")
            print(f"  {YELLOW}   Verifică warnings dar poți opera.{RESET}\n")
        else:
            print(f"\n  {RED}{BOLD}🔴 ATENȚIE: {self.failed} PROBLEME CRITICE DETECTATE!{RESET}")
            print(f"\n  {BOLD}Probleme de rezolvat:{RESET}")
            for i, issue in enumerate(self.issues, 1):
                print(f"  {RED}  {i}. {issue}{RESET}")
            print()

        print(f"{'─'*66}")
        print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} local")
        print(f"  🔱 AUTHORED BY ФорексГод 🔱  |  Glitch in Matrix V11.2")
        print(f"{'═'*66}\n")

    # ──────────────────────────────────────────────────────────
    # MAIN RUN
    # ──────────────────────────────────────────────────────────
    def run(self):
        print(f"\n{'╔'+'═'*64+'╗'}")
        print(f"║{'  🦅 GLITCH IN MATRIX — SYSTEM HEALTH CHECK V11.2 EAGLE EYE  ':^64}║")
        print(f"{'╚'+'═'*64+'╝'}")
        print(f"  ⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  Rulat din: {BASE_DIR.name}")

        self.check_daemons()
        self.check_ctrader_bridge()
        self.check_v112_config()
        self.check_spread_and_tf_alignment()
        self.check_critical_files()
        self.print_summary()

        return 0 if self.failed == 0 else 1


if __name__ == "__main__":
    checker = HealthCheck()
    sys.exit(checker.run())
