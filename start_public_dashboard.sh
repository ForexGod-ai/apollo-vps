#!/bin/bash

# ForexGod Dashboard - PUBLIC 24/7 with Auto-Restart
# Keeps both HTTP server and SSH tunnel running continuously

DASHBOARD_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
HTTP_PORT=8080
LOG_DIR="$DASHBOARD_DIR/logs"

mkdir -p "$LOG_DIR"

echo "🚀 ForexGod Dashboard - Starting PUBLIC Server"
echo "=============================================="

# Function to start HTTP server
start_http_server() {
    cd "$DASHBOARD_DIR"
    
    # Kill existing server on port 8080
    lsof -ti:$HTTP_PORT | xargs kill -9 2>/dev/null
    
    # Copy dashboard as index.html for auto-open
    cp dashboard_live.html index.html
    
    # Start HTTP server
    nohup python3 -m http.server $HTTP_PORT --bind 0.0.0.0 > "$LOG_DIR/http_server.log" 2>&1 &
    HTTP_PID=$!
    
    echo "✅ HTTP Server started (PID: $HTTP_PID) on port $HTTP_PORT"
    echo $HTTP_PID > "$DASHBOARD_DIR/.http_server.pid"
}

# Function to start SSH tunnel
start_tunnel() {
    echo "🌍 Creating PUBLIC tunnel..."
    
    while true; do
        echo "⏳ Connecting to localhost.run..."
        ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -R 80:localhost:$HTTP_PORT nokey@localhost.run
        
        echo "⚠️  Tunnel disconnected. Reconnecting in 5 seconds..."
        sleep 5
    done
}

# Start HTTP server
start_http_server

# Wait for server to start
sleep 2

# Test local access
if curl -s http://localhost:$HTTP_PORT/index.html | grep -q "ForexGod"; then
    echo "✅ Dashboard accessible locally: http://localhost:$HTTP_PORT"
    echo ""
    echo "🌍 Starting PUBLIC tunnel..."
    echo "📋 URL will appear below:"
    echo "=============================================="
    
    # Start tunnel (this will block and show the URL)
    start_tunnel
else
    echo "❌ Error: HTTP server not responding"
    exit 1
fi
