"""
Dashboard HTTP Server - Port 8000
Serves dashboard_live.html and dashboard_pro.html
Managed by Watchdog Monitor (auto-restart on crash)
"""
import http.server
import socketserver
import socket
import os
import sys
import time
import logging
import subprocess

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PORT = 8000

# Always serve from the script's own directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))


def kill_port(port):
    """Kill any process occupying the port (cross-platform)."""
    try:
        if sys.platform == 'win32':
            # Windows: find PID via netstat then kill it
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
            # Linux/macOS: lsof
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


class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Suppress per-request log spam in production."""
    def log_message(self, format, *args):
        pass  # silent — watchdog logs are enough

    def log_error(self, format, *args):
        pass  # suppress broken-pipe noise


class ReusableTCPServer(socketserver.ThreadingTCPServer):
    """ThreadingTCPServer with address reuse and quick restart support."""
    allow_reuse_address = True
    daemon_threads = True

    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        super().server_bind()


# ── Startup ──────────────────────────────────────────────────────────────────
logger.info(f"🌐 Dashboard Server starting on port {PORT}...")

# If port is busy, kill the squatter and retry
if not is_port_free(PORT):
    logger.warning(f"⚠️  Port {PORT} busy — attempting to free it...")
    kill_port(PORT)
    time.sleep(2)

MAX_RETRIES = 5
for attempt in range(1, MAX_RETRIES + 1):
    try:
        httpd = ReusableTCPServer(("", PORT), QuietHTTPHandler)
        logger.info(f"✅ Dashboard Server running on port {PORT}")
        logger.info(f"   http://localhost:{PORT}/dashboard_live.html")
        logger.info(f"   http://204.168.251.41:{PORT}/dashboard_pro.html")
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
