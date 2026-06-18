"""
Dashboard HTTP Server - Port 8000
Serves dashboard_live.html and dashboard_pro.html
V40.5: /api/dashboard + trade_history.json with Europe/Bucharest close times
Managed by Watchdog Monitor (auto-restart on crash)
"""
import http.server
import socketserver
import socket
import os
import sys
import time
import json
import logging
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from dashboard_time_utils import localize_dashboard_payload

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PORT = 8000
SCRIPT_DIR = Path(__file__).parent.resolve()
TRADE_HISTORY_FILE = SCRIPT_DIR / 'trade_history.json'

# Always serve from the script's own directory
os.chdir(SCRIPT_DIR)


def kill_port(port):
    """Kill any process occupying the port (cross-platform)."""
    try:
        if sys.platform == 'win32':
            result = subprocess.run(
                f'netstat -ano | findstr :{port}',
                shell=True, capture_output=True, text=True
            )
            pids = set()
            for line in result.stdout.splitlines():
                parts = line.split()
                if parts and ('LISTENING' in line or 'LISTEN' in line):
                    pids.add(parts[-1])
            for pid in pids:
                try:
                    subprocess.run(f'taskkill /F /PID {pid}', shell=True,
                                   capture_output=True)
                    logger.info(f"🔪 Killed PID {pid} on port {port}")
                except Exception:
                    pass
        else:
            result = subprocess.run(
                ['lsof', '-ti', f'tcp:{port}'],
                capture_output=True, text=True
            )
            for pid in result.stdout.strip().splitlines():
                try:
                    subprocess.run(['kill', '-9', pid], capture_output=True)
                    logger.info(f"🔪 Killed PID {pid} on port {port}")
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"kill_port: {e}")


def is_port_free(port, host='0.0.0.0'):
    """Return True if port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def load_localized_trade_history() -> dict:
    if not TRADE_HISTORY_FILE.exists():
        raise FileNotFoundError('trade_history.json not found')
    with open(TRADE_HISTORY_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return localize_dashboard_payload(data)


class DashboardHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Static files + V40.5 dashboard API with RO timezone on closed trades."""

    def log_message(self, format, *args):
        pass

    def log_error(self, format, *args):
        pass

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ('/api/dashboard', '/trade_history.json'):
            self._serve_trade_history_json()
            return
        return super().do_GET()

    def _serve_trade_history_json(self):
        try:
            payload = load_localized_trade_history()
            body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self.send_error(404, 'trade_history.json not found')
        except Exception as exc:
            logger.error(f"Dashboard API error: {exc}")
            self.send_error(500, str(exc))


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    """ThreadingTCPServer with address reuse and quick restart support."""
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


# ── Startup ──────────────────────────────────────────────────────────────────
logger.info(f"🌐 Dashboard Server starting on port {PORT}...")

if not is_port_free(PORT):
    logger.warning(f"⚠️  Port {PORT} busy — attempting to free it...")
    kill_port(PORT)
    time.sleep(2)

MAX_RETRIES = 5
for attempt in range(1, MAX_RETRIES + 1):
    try:
        httpd = ReusableTCPServer(("", PORT), DashboardHTTPHandler)
        logger.info(f"✅ Dashboard Server running on port {PORT}")
        logger.info(f"   http://localhost:{PORT}/dashboard_live.html")
        logger.info(f"   http://204.168.251.41:{PORT}/dashboard_pro.html")
        logger.info("   🕒 V40.5: trade_history.json served with Europe/Bucharest times")
        httpd.serve_forever()
        break
    except OSError as e:
        logger.error(f"❌ Attempt {attempt}/{MAX_RETRIES} failed: {e}")
        if attempt < MAX_RETRIES:
            kill_port(PORT)
            time.sleep(3)
        else:
            logger.critical("💀 Could not bind to port 8000 after all retries. Exiting.")
            sys.exit(1)
