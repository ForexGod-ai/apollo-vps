#!/bin/bash
# Setup News Calendar Monitors - ForexGod Trading System
# Daily checks: 8am, 2pm, 8pm, 2am
# Weekly report: Sunday 21:00

echo "📰 Setting up News Calendar Monitors..."
echo ""

PROJECT_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Install Python dependencies
echo "📦 Installing dependencies..."
pip3 install beautifulsoup4 requests python-dotenv cloudscraper

echo ""
echo "🧪 Testing daily monitor..."
python3 "$PROJECT_DIR/news_calendar_monitor.py"

echo ""
echo "🧪 Testing weekly report..."
python3 "$PROJECT_DIR/weekly_news_report.py"

echo ""
echo "⚙️ Installing LaunchAgents..."

# Copy plist files
cp "$PROJECT_DIR/com.forexgod.newscalendar.plist" ~/Library/LaunchAgents/
cp "$PROJECT_DIR/com.forexgod.weeklynews.plist" ~/Library/LaunchAgents/

# Load LaunchAgents
launchctl load ~/Library/LaunchAgents/com.forexgod.newscalendar.plist
launchctl load ~/Library/LaunchAgents/com.forexgod.weeklynews.plist

echo ""
echo "✅ News monitors installed!"
echo ""
echo "📋 Configuration:"
echo "   Daily checks: 8am, 2pm, 8pm, 2am (next 48h)"
echo "   Weekly report: Sunday 21:00 (next 7 days)"
echo ""
echo "🔍 Verify installation:"
echo "   launchctl list | grep forexgod"
echo ""
echo "📝 View logs:"
echo "   tail -f logs/news_calendar.log"
echo "   tail -f logs/weekly_news.log"
echo ""
echo "✨ All set! News alerts will be sent to Telegram automatically."
