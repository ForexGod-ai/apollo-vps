#!/bin/bash

# ====================================================================
# Install LaunchD Auto-Start for Glitch in Matrix
# ====================================================================

echo "🚀 Installing LaunchD auto-start for Glitch in Matrix..."
echo ""

PLIST_FILE="com.forexgod.glitch.plist"
LAUNCHD_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$LAUNCHD_DIR/$PLIST_FILE"

# Create LaunchAgents directory if it doesn't exist
mkdir -p "$LAUNCHD_DIR"

# Copy plist file
cp "$PLIST_FILE" "$PLIST_PATH"
echo "✅ Copied $PLIST_FILE to $LAUNCHD_DIR"

# Load the job
launchctl unload "$PLIST_PATH" 2>/dev/null
launchctl load "$PLIST_PATH"

if [ $? -eq 0 ]; then
    echo "✅ LaunchD job loaded successfully!"
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "📋 LAUNCHD CONFIGURATION"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "Label: com.forexgod.glitch"
    echo "Script: start_system.sh"
    echo "RunAtLoad: YES (runs at login/boot)"
    echo ""
    echo "Logs:"
    echo "  • stdout: logs/launchd_stdout.log"
    echo "  • stderr: logs/launchd_stderr.log"
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "🎯 COMMANDS"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "Check status:"
    echo "  launchctl list | grep forexgod"
    echo ""
    echo "Unload (disable auto-start):"
    echo "  launchctl unload ~/Library/LaunchAgents/com.forexgod.glitch.plist"
    echo ""
    echo "Reload (after editing plist):"
    echo "  launchctl unload ~/Library/LaunchAgents/com.forexgod.glitch.plist"
    echo "  launchctl load ~/Library/LaunchAgents/com.forexgod.glitch.plist"
    echo ""
    echo "Remove completely:"
    echo "  launchctl unload ~/Library/LaunchAgents/com.forexgod.glitch.plist"
    echo "  rm ~/Library/LaunchAgents/com.forexgod.glitch.plist"
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "✅ System will auto-start at next login/reboot!"
    echo "════════════════════════════════════════════════════════════════"
else
    echo "❌ Failed to load LaunchD job"
    echo "Check logs for errors"
fi
