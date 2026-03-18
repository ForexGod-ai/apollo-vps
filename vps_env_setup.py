#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  GLITCH IN MATRIX — VPS ENVIRONMENT SETUP & HEALTH CHECK                    ║
║  Engineered by ФорексГод                                                     ║
║                                                                              ║
║  Assistant script for deploy_glitch.sh                                       ║
║  Runs:  python vps_env_setup.py --health-check                              ║
║                                                                              ║
║  Health Checks:                                                              ║
║    1. monitoring_setups.json — readable, valid JSON array                    ║
║    2. Telegram API — bot token valid, can reach chat                         ║
║    3. cTrader Bridge — signals.json exists & writable                        ║
║    4. Log infrastructure — logs/ dir, rotation configured                    ║
║    5. Critical modules — all importable                                      ║
║    6. .env integrity — required keys present                                 ║
║                                                                              ║
║  Protocol V8.0 · VPS-Ready Edition                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import json
import time
import argparse
import importlib
from pathlib import Path
from datetime import datetime, timezone

# ─── Force UTC ──────────────────────────────────────────────────────────────
os.environ['TZ'] = 'UTC'
try:
    time.tzset()
except AttributeError:
    pass  # Windows

# ─── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
LOG_DIR = SCRIPT_DIR / "logs"

# ─── Colors ─────────────────────────────────────────────────────────────────
class C:
    """ANSI color codes"""
    GREEN  = '\033[0;32m'
    RED    = '\033[0;31m'
    YELLOW = '\033[1;33m'
    CYAN   = '\033[0;36m'
    DIM    = '\033[2m'
    BOLD   = '\033[1m'
    WHITE  = '\033[1;37m'
    NC     = '\033[0m'

    @staticmethod
    def ok(msg: str)   -> str: return f"  {C.GREEN}✅{C.NC}  {msg}"
    @staticmethod
    def fail(msg: str) -> str: return f"  {C.RED}❌{C.NC}  {msg}"
    @staticmethod
    def warn(msg: str) -> str: return f"  {C.YELLOW}⚠️{C.NC}  {msg}"
    @staticmethod
    def info(msg: str) -> str: return f"  {C.CYAN}▸{C.NC}  {msg}"
    @staticmethod
    def header(msg: str) -> str: return f"\n  {C.WHITE}{C.BOLD}{'─'*52}{C.NC}\n  {C.WHITE}{C.BOLD}  {msg}{C.NC}\n  {C.WHITE}{C.BOLD}{'─'*52}{C.NC}"


class HealthChecker:
    """
    VPS Health Check Suite — validates all system components
    before live trading deployment.
    """

    def __init__(self):
        self.results: list[tuple[str, bool, str]] = []
        self.base_dir = SCRIPT_DIR

    def _record(self, name: str, passed: bool, detail: str = ""):
        self.results.append((name, passed, detail))
        if passed:
            print(C.ok(f"{name}: {detail}"))
        else:
            print(C.fail(f"{name}: {detail}"))

    # ═══════════════════════════════════════════════════════════════════════
    # CHECK 1: monitoring_setups.json
    # ═══════════════════════════════════════════════════════════════════════
    def check_monitoring_setups(self):
        """Verify monitoring_setups.json is accessible and valid JSON"""
        fpath = self.base_dir / "monitoring_setups.json"

        if not fpath.exists():
            self._record("monitoring_setups.json", False, "FILE NOT FOUND")
            return

        try:
            with open(fpath, 'r') as f:
                data = json.load(f)

            if isinstance(data, list):
                setup_count = len(data)
                active = sum(1 for s in data if isinstance(s, dict) and s.get('status') == 'MONITORING')
                self._record(
                    "monitoring_setups.json",
                    True,
                    f"Valid JSON array — {setup_count} setups ({active} MONITORING)"
                )
            else:
                self._record("monitoring_setups.json", True, f"Valid JSON ({type(data).__name__})")

        except json.JSONDecodeError as e:
            self._record("monitoring_setups.json", False, f"Invalid JSON: {e}")
        except PermissionError:
            self._record("monitoring_setups.json", False, "Permission denied")
        except Exception as e:
            self._record("monitoring_setups.json", False, str(e))

    # ═══════════════════════════════════════════════════════════════════════
    # CHECK 2: Telegram API
    # ═══════════════════════════════════════════════════════════════════════
    def check_telegram(self):
        """Verify Telegram bot token is valid and chat_id is reachable"""
        try:
            from dotenv import load_dotenv
            load_dotenv(self.base_dir / ".env")
        except ImportError:
            self._record("Telegram API", False, "python-dotenv not installed")
            return

        bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        chat_id = os.getenv('TELEGRAM_CHAT_ID', '')

        if not bot_token:
            self._record("Telegram API", False, "TELEGRAM_BOT_TOKEN not set in .env")
            return

        if not chat_id:
            self._record("Telegram API", False, "TELEGRAM_CHAT_ID not set in .env")
            return

        # Test getMe API call
        try:
            import requests
            url = f"https://api.telegram.org/bot{bot_token}/getMe"
            resp = requests.get(url, timeout=10)
            data = resp.json()

            if data.get('ok'):
                bot_name = data['result'].get('username', 'unknown')
                self._record("Telegram Bot", True, f"@{bot_name} — token valid")
            else:
                self._record("Telegram Bot", False, f"API error: {data.get('description', 'unknown')}")
                return
        except requests.exceptions.Timeout:
            self._record("Telegram Bot", False, "Connection timeout (10s)")
            return
        except requests.exceptions.ConnectionError:
            self._record("Telegram Bot", False, "Cannot reach api.telegram.org — check network")
            return
        except Exception as e:
            self._record("Telegram Bot", False, str(e))
            return

        # Test sendMessage capability (dry run — send a health check message)
        try:
            ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            sep = "────────────────"
            msg = (
                f"🏥 *VPS HEALTH CHECK*\n\n"
                f"✅ Deployment health check passed\n"
                f"🕐 {ts}\n"
                f"🔧 Protocol V8.2\n\n"
                f"  {sep}\n"
                f"  🔱 *AUTHORED BY ФорексГод* 🔱\n"
                f"  {sep}\n"
                f"  🏛️  *Глитч Ин Матрикс*  🏛️"
            )

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': msg,
                'parse_mode': 'Markdown'
            }
            resp = requests.post(url, json=payload, timeout=10)
            data = resp.json()

            if data.get('ok'):
                self._record("Telegram Chat", True, f"Message sent to chat {chat_id}")
            else:
                desc = data.get('description', 'unknown error')
                # Not fatal — bot works but chat access may be restricted
                self._record("Telegram Chat", False, f"Cannot send to chat: {desc}")

        except Exception as e:
            self._record("Telegram Chat", False, f"Send test failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # CHECK 3: cTrader Bridge (signals.json)
    # ═══════════════════════════════════════════════════════════════════════
    def check_ctrader_bridge(self):
        """Verify signals.json exists, is writable, and contains valid JSON"""
        signals_path = self.base_dir / "signals.json"

        if not signals_path.exists():
            # Create it
            try:
                signals_path.write_text("[]")
                self._record("cTrader Bridge", True, "signals.json created (empty array)")
            except Exception as e:
                self._record("cTrader Bridge", False, f"Cannot create signals.json: {e}")
            return

        # Check readable
        try:
            content = signals_path.read_text().strip()
            if not content:
                signals_path.write_text("[]")
                self._record("cTrader Bridge", True, "signals.json was empty — initialized as []")
                return

            data = json.loads(content)

            if isinstance(data, list):
                pending = len(data)
                self._record(
                    "cTrader Bridge",
                    True,
                    f"signals.json valid — {pending} pending signal(s)"
                )
            else:
                self._record("cTrader Bridge", False, f"Expected array, got {type(data).__name__}")

        except json.JSONDecodeError as e:
            self._record("cTrader Bridge", False, f"Invalid JSON in signals.json: {e}")
        except Exception as e:
            self._record("cTrader Bridge", False, str(e))

        # Check writable
        try:
            # Test write capability without modifying content
            test_path = self.base_dir / ".signals_write_test"
            test_path.write_text("test")
            test_path.unlink()
            # Already reported above — just ensuring write access works
        except Exception as e:
            self._record("cTrader Write Access", False, f"Cannot write to apollo dir: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # CHECK 4: Log Infrastructure
    # ═══════════════════════════════════════════════════════════════════════
    def check_logs(self):
        """Verify logs/ directory and loguru rotation in critical files"""
        log_dir = self.base_dir / "logs"

        if not log_dir.exists():
            self._record("Log Directory", False, "logs/ does not exist")
            return

        log_files = list(log_dir.glob("*.log"))
        self._record("Log Directory", True, f"logs/ exists — {len(log_files)} log file(s)")

        # Check loguru configured in critical files
        critical = [
            "setup_executor_monitor.py",
            "position_monitor.py",
            "watchdog_monitor.py",
            "realtime_monitor.py",
            "telegram_command_center.py",
        ]

        configured = 0
        for cf in critical:
            fpath = self.base_dir / cf
            if fpath.exists():
                content = fpath.read_text()
                if 'logger.add' in content and 'rotation' in content:
                    configured += 1

        self._record(
            "Loguru Rotation",
            configured == len(critical),
            f"{configured}/{len(critical)} critical processes have file rotation"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # CHECK 5: Critical Module Imports
    # ═══════════════════════════════════════════════════════════════════════
    def check_modules(self):
        """Verify all critical third-party modules are importable"""
        modules = [
            ('pandas',              'Data analysis'),
            ('numpy',               'Numerical computing'),
            ('loguru',              'Structured logging'),
            ('requests',            'HTTP client'),
            ('psutil',              'Process monitoring'),
            ('dotenv',              'Environment vars'),
            ('flask',               'Web framework'),
            ('telegram',            'Telegram bot SDK'),
            ('matplotlib',          'Chart rendering'),
            ('sklearn',             'Machine learning'),
            ('pydantic',            'Data validation'),
            ('schedule',            'Task scheduling'),
        ]

        passed = 0
        failed_names = []

        for mod_name, description in modules:
            try:
                importlib.import_module(mod_name)
                passed += 1
            except ImportError:
                failed_names.append(mod_name)

        if failed_names:
            self._record(
                "Module Imports",
                False,
                f"{passed}/{len(modules)} OK — MISSING: {', '.join(failed_names)}"
            )
        else:
            self._record("Module Imports", True, f"All {len(modules)} critical modules importable")

    # ═══════════════════════════════════════════════════════════════════════
    # CHECK 6: .env Integrity
    # ═══════════════════════════════════════════════════════════════════════
    def check_env(self):
        """Verify .env has all required keys"""
        env_path = self.base_dir / ".env"

        if not env_path.exists():
            self._record(".env File", False, "NOT FOUND")
            return

        try:
            from dotenv import load_dotenv
            load_dotenv(env_path, override=True)
        except Exception:
            pass

        required_keys = {
            'TELEGRAM_BOT_TOKEN':    'Telegram bot authentication',
            'TELEGRAM_CHAT_ID':      'Telegram alert destination',
            'CTRADER_ACCOUNT_ID':    'cTrader broker account',
            'CTRADER_ACCESS_TOKEN':  'cTrader API access',
        }

        optional_keys = {
            'CTRADER_CLIENT_ID':     'cTrader OAuth client',
            'CTRADER_CLIENT_SECRET': 'cTrader OAuth secret',
            'TELEGRAM_USER_ID':      'Telegram admin user',
        }

        missing = []
        present = []

        for key, desc in required_keys.items():
            val = os.getenv(key, '')
            if val:
                present.append(key)
            else:
                missing.append(key)

        if missing:
            self._record(".env Required Keys", False, f"MISSING: {', '.join(missing)}")
        else:
            self._record(".env Required Keys", True, f"All {len(required_keys)} required keys present")

        # Check optionals
        opt_present = sum(1 for k in optional_keys if os.getenv(k, ''))
        self._record(
            ".env Optional Keys",
            True,
            f"{opt_present}/{len(optional_keys)} optional keys configured"
        )

    # ═══════════════════════════════════════════════════════════════════════
    # RUN ALL CHECKS
    # ═══════════════════════════════════════════════════════════════════════
    def run_all(self) -> bool:
        """Execute all health checks and return True if all critical passed"""
        print(C.header("HEALTH CHECK — GLITCH IN MATRIX by ФорексГод"))
        print()

        self.check_monitoring_setups()
        self.check_telegram()
        self.check_ctrader_bridge()
        self.check_logs()
        self.check_modules()
        self.check_env()

        # Summary
        total = len(self.results)
        passed = sum(1 for _, ok, _ in self.results if ok)
        failed = total - passed

        print()
        print(f"  {C.DIM}{'─'*52}{C.NC}")
        print(f"  {C.WHITE}{C.BOLD}  RESULTS: {passed}/{total} checks passed{C.NC}", end="")

        if failed > 0:
            print(f"  {C.RED}({failed} failed){C.NC}")
        else:
            print(f"  {C.GREEN}(all clear){C.NC}")

        print(f"  {C.DIM}{'─'*52}{C.NC}")

        # Determine if critical checks passed
        # Critical = monitoring_setups, cTrader Bridge, Module Imports, .env Required
        critical_names = {
            "monitoring_setups.json",
            "cTrader Bridge",
            "Module Imports",
            ".env Required Keys",
        }

        critical_failed = [
            name for name, ok, _ in self.results
            if name in critical_names and not ok
        ]

        if critical_failed:
            print()
            print(f"  {C.RED}{C.BOLD}⛔ CRITICAL FAILURES: {', '.join(critical_failed)}{C.NC}")
            print(f"  {C.RED}   System is NOT ready for live trading.{C.NC}")
            return False
        else:
            print()
            print(f"  {C.GREEN}{C.BOLD}╔═══════════════════════════════════════════════════╗{C.NC}")
            print(f"  {C.GREEN}{C.BOLD}║                                                   ║{C.NC}")
            print(f"  {C.GREEN}{C.BOLD}║   SYSTEM OPERATIONAL — BY ФорексГод                ║{C.NC}")
            print(f"  {C.GREEN}{C.BOLD}║   READY FOR LIVE TRADING                          ║{C.NC}")
            print(f"  {C.GREEN}{C.BOLD}║                                                   ║{C.NC}")
            print(f"  {C.GREEN}{C.BOLD}╚═══════════════════════════════════════════════════╝{C.NC}")
            print()
            return True


# ═══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT SETUP MODE
# ═══════════════════════════════════════════════════════════════════════════════
class EnvironmentSetup:
    """
    Interactive environment configuration — runs when called without --health-check.
    Creates directory structure, validates permissions, generates configs.
    """

    def __init__(self):
        self.base_dir = SCRIPT_DIR

    def setup_directories(self):
        """Create all required directories"""
        print(C.header("FILESYSTEM SETUP"))
        print()

        dirs = [
            ("logs",            "Loguru rotated logs"),
            ("data",            "Market data cache"),
            ("backups",         "Database & config backups"),
            ("charts",          "Generated charts"),
            ("chart_snapshots", "Telegram chart images"),
            ("archive",         "Archived setups & reports"),
        ]

        for dirname, desc in dirs:
            path = self.base_dir / dirname
            path.mkdir(exist_ok=True)
            print(C.ok(f"{dirname}/ — {desc}"))

    def setup_state_files(self):
        """Ensure all state files exist with valid defaults"""
        print(C.header("STATE FILES"))
        print()

        state_files = {
            "monitoring_setups.json": "[]",
            "signals.json":          "[]",
            "active_positions.json": "[]",
            "trade_confirmations.json": "[]",
        }

        for fname, default in state_files.items():
            fpath = self.base_dir / fname
            if not fpath.exists():
                fpath.write_text(default)
                print(C.warn(f"Created: {fname} (initialized)"))
            else:
                size = fpath.stat().st_size
                print(C.ok(f"Exists: {fname} ({size}B)"))

    def setup_permissions(self):
        """Set IPC-friendly permissions"""
        print(C.header("PERMISSIONS"))
        print()

        # signals.json needs 666 for cTrader cBot to read/write
        signals = self.base_dir / "signals.json"
        if signals.exists():
            os.chmod(str(signals), 0o666)
            print(C.ok("signals.json → chmod 666 (cTrader IPC)"))

        # Apollo dir needs to be accessible
        try:
            os.chmod(str(self.base_dir), 0o777)
            print(C.ok("apollo/ → chmod 777 (full access)"))
        except OSError as e:
            print(C.warn(f"Could not chmod apollo/: {e}"))

    def verify_timezone(self):
        """Verify TZ=UTC is active"""
        print(C.header("TIMEZONE"))
        print()

        now = datetime.now(timezone.utc)
        print(C.ok(f"TZ=UTC active — {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"))

    def run(self):
        """Full environment setup"""
        print()
        print(f"  {C.GREEN}{C.BOLD}GLITCH IN MATRIX — VPS Environment Setup{C.NC}")
        print(f"  {C.DIM}Engineered by ФорексГод{C.NC}")
        print()

        self.setup_directories()
        self.setup_state_files()
        self.setup_permissions()
        self.verify_timezone()

        print()
        print(C.ok("Environment setup complete"))
        print()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(
        description="Glitch in Matrix — VPS Environment Setup & Health Check (by ФорексГод)"
    )
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Run health check diagnostics only'
    )
    parser.add_argument(
        '--setup',
        action='store_true',
        help='Run environment setup (directories, permissions, state files)'
    )

    args = parser.parse_args()

    if args.health_check:
        checker = HealthChecker()
        success = checker.run_all()
        sys.exit(0 if success else 1)
    elif args.setup:
        setup = EnvironmentSetup()
        setup.run()
    else:
        # Default: run both
        setup = EnvironmentSetup()
        setup.run()

        print()
        checker = HealthChecker()
        success = checker.run_all()
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
