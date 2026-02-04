#!/bin/zsh

# ============================================
# macOS LaunchAgent Setup for Trading Monitor
# ============================================

echo "🚀 Setting up Trading Monitor as macOS LaunchAgent..."

# Variables
PLIST_NAME="com.forexgod.trading-monitor.plist"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_NAME"
WORKSPACE="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Create LaunchAgents directory if doesn't exist
mkdir -p "$LAUNCH_AGENTS_DIR"
mkdir -p "$WORKSPACE/logs"

# Unload existing service if running
echo "📤 Unloading existing service (if any)..."
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl remove com.forexgod.trading-monitor 2>/dev/null || true

# Copy plist to LaunchAgents
echo "📋 Installing plist..."
cp "$PLIST_NAME" "$PLIST_PATH"

# Set correct permissions
chmod 644 "$PLIST_PATH"

# Make start_monitoring.sh executable
chmod +x "$WORKSPACE/start_monitoring.sh"

# Load the service
echo "🔄 Loading LaunchAgent..."
launchctl load "$PLIST_PATH"

# Start the service now
echo "▶️  Starting service..."
launchctl start com.forexgod.trading-monitor

# Wait a moment for startup
sleep 3

# Check status
echo ""
echo "============================================"
echo "📊 SERVICE STATUS"
echo "============================================"

if launchctl list | grep -q "com.forexgod.trading-monitor"; then
    echo "✅ Service LOADED and RUNNING"
    launchctl list | grep com.forexgod.trading-monitor
else
    echo "❌ Service NOT loaded"
fi

echo ""
echo "🔍 Checking processes..."
ps aux | grep -E "position_monitor|trade_monitor" | grep -v grep | head -5

echo ""
echo "============================================"
echo "📝 USEFUL COMMANDS"
echo "============================================"
echo "Check status:    launchctl list | grep forexgod"
echo "View logs:       tail -f logs/launchd.out.log"
echo "View errors:     tail -f logs/launchd.err.log"
echo "Stop service:    launchctl stop com.forexgod.trading-monitor"
echo "Start service:   launchctl start com.forexgod.trading-monitor"
echo "Unload service:  launchctl unload $PLIST_PATH"
echo "Reload service:  launchctl unload $PLIST_PATH && launchctl load $PLIST_PATH"
echo ""
echo "✅ Setup complete! Monitors will auto-start at boot."
