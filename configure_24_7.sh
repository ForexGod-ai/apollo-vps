#!/bin/zsh

# ============================================
# Configure macOS for 24/7 Trading Bot
# ============================================

echo "⚙️  Configuring macOS for 24/7 operation..."
echo ""

# Prevent system sleep when plugged in (AC power)
echo "🔌 Setting AC Power settings..."
sudo pmset -c sleep 0          # Never sleep when plugged in
sudo pmset -c disksleep 0      # Never sleep disk when plugged in
sudo pmset -c displaysleep 30  # Turn off display after 30 min (save energy)

# Enable wake for network access (important for remote monitoring)
sudo pmset -c womp 1           # Wake on network/magic packet

# Prevent sleep when display is off
sudo pmset -c ttyskeepawake 1  # Prevent sleep when remote terminal active

# Disable standby and hibernation (for true 24/7)
sudo pmset -c standby 0
sudo pmset -c autopoweroff 0

# Battery settings (more conservative)
echo "🔋 Setting Battery Power settings..."
sudo pmset -b sleep 15         # Sleep after 15 min on battery
sudo pmset -b disksleep 10
sudo pmset -b displaysleep 10

echo ""
echo "============================================"
echo "📊 CURRENT POWER SETTINGS"
echo "============================================"
pmset -g custom | grep -A 10 "AC Power"

echo ""
echo "============================================"
echo "✅ CONFIGURATION COMPLETE"
echo "============================================"
echo ""
echo "🔌 With laptop PLUGGED IN:"
echo "   ✅ System will NEVER sleep"
echo "   ✅ Monitors run 24/7"
echo "   ✅ Telegram notifications work always"
echo "   ⚠️  Display turns off after 30 min (saves energy)"
echo ""
echo "🔋 On BATTERY:"
echo "   ⚠️  System sleeps after 15 min (saves battery)"
echo "   ❌ Monitors will pause during sleep"
echo ""
echo "💡 RECOMMENDATION: Keep laptop plugged in for 24/7 trading!"
echo ""
