"""Test simple HTTP server"""
import http.server
import socketserver

PORT = 8888

Handler = http.server.SimpleHTTPRequestHandler

print(f"🚀 Starting server on http://127.0.0.1:{PORT}")
print("Press CTRL+C to stop...")

with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
    print(f"✅ Server is listening on port {PORT}")
    httpd.serve_forever()
