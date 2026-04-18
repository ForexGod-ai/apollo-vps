"""
Dashboard HTTP Server - Port 8000
Serves dashboard_live.html and dashboard_pro.html
Managed by Watchdog Monitor (auto-restart on crash)
"""
import http.server
import socketserver
import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

PORT = 8000

# Always serve from the script's own directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class QuietHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """Suppress per-request log spam in production."""
    def log_message(self, format, *args):
        pass  # silent — watchdog logs are enough

socketserver.TCPServer.allow_reuse_address = True

logger.info(f"🌐 Dashboard Server starting on port {PORT}...")
logger.info(f"   http://localhost:{PORT}/dashboard_live.html")
logger.info(f"   http://204.168.251.41:{PORT}/dashboard_pro.html")

with socketserver.TCPServer(("", PORT), QuietHTTPHandler) as httpd:
    logger.info(f"✅ Dashboard Server running on port {PORT}")
    httpd.serve_forever()
