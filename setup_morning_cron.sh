#!/bin/bash
# Setup cron job for Morning Strategy Scanner
# Runs at 09:00 daily (London market open)

echo "🚀 Setting up Morning Strategy Scanner cron job..."

# Get the absolute path to the project directory
PROJECT_DIR="/Users/forexgod/Desktop/trading-ai-agent"
PYTHON_PATH="/usr/bin/python3"

# Create logs directory if it doesn't exist
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/charts/morning_scan"

# Create the cron job entry
CRON_JOB="0 9 * * * cd $PROJECT_DIR && $PYTHON_PATH morning_strategy_scan.py >> logs/morning_scan.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "morning_strategy_scan.py"; then
    echo "⚠️  Cron job already exists. Removing old one..."
    crontab -l | grep -v "morning_strategy_scan.py" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job installed successfully!"
echo ""
echo "📋 Schedule: Every day at 09:00"
echo "📂 Project: $PROJECT_DIR"
echo "📝 Logs: $PROJECT_DIR/logs/morning_scan.log"
echo "📊 Charts: $PROJECT_DIR/charts/morning_scan/"
echo ""
echo "🔍 To view current cron jobs, run: crontab -l"
echo "🗑️  To remove this job, run: crontab -l | grep -v morning_strategy_scan.py | crontab -"
echo ""
echo "✨ Morning scanner will run automatically at 09:00 every day!"
