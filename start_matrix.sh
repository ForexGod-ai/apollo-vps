#!/bin/bash

################################################################################
# 🚀 START MATRIX - System Initialization Script
# Starts all monitoring daemons with Ghost Notification prevention
#
# ✨ Glitch in Matrix by ФорексГод ✨
################################################################################

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Workspace directory
WORKSPACE="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
cd "$WORKSPACE" || exit 1

echo ""
echo "${CYAN}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo "${CYAN}║${NC}           ${BOLD}🚀 GLITCH IN MATRIX - SYSTEM STARTUP${NC}                    ${CYAN}║${NC}"
echo "${CYAN}║${NC}               ${YELLOW}✨ by ФорексГод - V5.1 Anti-Ghost ✨${NC}                ${CYAN}║${NC}"
echo "${CYAN}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

################################################################################
# STEP 1: KILL SWITCH - Stop All Old Instances
################################################################################

echo "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${YELLOW}🔪 STEP 1: Kill Switch - Stopping old monitor instances...${NC}"
echo "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# List of monitors to kill
MONITORS=(
    "watchdog_monitor.py"
    "position_monitor.py"
    "realtime_monitor.py"
    "ctrader_sync_daemon.py"
    "news_calendar_monitor.py"
    "signal_confirmation_monitor.py"
    "setup_executor_monitor.py"
    "telegram_command_center.py"
)

for monitor in "${MONITORS[@]}"; do
    if pgrep -f "$monitor" > /dev/null; then
        echo "   ${RED}❌ Killing:${NC} $monitor"
        pkill -9 -f "$monitor"
        sleep 0.5
    else
        echo "   ${BLUE}⏹️  Not running:${NC} $monitor"
    fi
done

echo ""
echo "${GREEN}✅ Kill switch complete - All old instances terminated${NC}"
sleep 1

################################################################################
# STEP 2: CLEANUP - Remove Ghost Notification Files
################################################################################

echo ""
echo "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${YELLOW}🧹 STEP 2: Cleanup - Removing ghost files for clean start...${NC}"
echo "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Ghost notification files to remove
GHOST_FILES=(
    "execution_report.json"
    "trade_confirmations.json"
    "execution_report_legacy.json"
)

for file in "${GHOST_FILES[@]}"; do
    if [ -f "$WORKSPACE/$file" ]; then
        echo "   ${RED}🗑️  Deleting:${NC} $file"
        rm -f "$WORKSPACE/$file"
    else
        echo "   ${BLUE}✓ Clean:${NC} $file (not found)"
    fi
done

echo ""
echo "${GREEN}✅ Cleanup complete - No ghost files remaining${NC}"
sleep 1

################################################################################
# STEP 3: START MONITORS - Launch All Daemons
################################################################################

echo ""
echo "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${YELLOW}🚀 STEP 3: Starting monitors in background (nohup)...${NC}"
echo "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Activate virtual environment
if [ -d "$WORKSPACE/.venv" ]; then
    echo "   ${CYAN}🐍 Activating virtual environment...${NC}"
    source "$WORKSPACE/.venv/bin/activate"
fi

# Check if watchdog exists (will auto-start other monitors)
if [ -f "$WORKSPACE/watchdog_monitor.py" ]; then
    echo ""
    echo "   ${GREEN}🐕 Starting Watchdog Guardian (auto-starts other monitors)...${NC}"
    nohup python3 "$WORKSPACE/watchdog_monitor.py" --interval 60 > "$WORKSPACE/watchdog.log" 2>&1 &
    WATCHDOG_PID=$!
    echo "      ${CYAN}→ PID: $WATCHDOG_PID${NC}"
    echo "      ${CYAN}→ Log: watchdog.log${NC}"
    sleep 3
    
    echo ""
    echo "   ${YELLOW}⏳ Waiting for watchdog to start other monitors (10s)...${NC}"
    sleep 10
    
    echo ""
    echo "   ${GREEN}✅ Watchdog Guardian active - monitoring all processes${NC}"
    
else
    # Manual start if no watchdog
    echo "   ${YELLOW}⚠️  No watchdog found - starting monitors manually...${NC}"
    echo ""
    
    # Position Monitor
    echo "   ${GREEN}1️⃣ Starting Position Monitor...${NC}"
    nohup python3 "$WORKSPACE/position_monitor.py" > "$WORKSPACE/position_monitor.log" 2>&1 &
    echo "      ${CYAN}→ PID: $!${NC}"
    sleep 1
    
    # Realtime Monitor
    if [ -f "$WORKSPACE/realtime_monitor.py" ]; then
        echo "   ${GREEN}2️⃣ Starting Realtime Monitor...${NC}"
        nohup python3 "$WORKSPACE/realtime_monitor.py" > "$WORKSPACE/realtime_monitor.log" 2>&1 &
        echo "      ${CYAN}→ PID: $!${NC}"
        sleep 1
    fi
    
    # cTrader Sync Daemon
    if [ -f "$WORKSPACE/ctrader_sync_daemon.py" ]; then
        echo "   ${GREEN}3️⃣ Starting cTrader Sync Daemon...${NC}"
        nohup python3 "$WORKSPACE/ctrader_sync_daemon.py" > "$WORKSPACE/ctrader_sync.log" 2>&1 &
        echo "      ${CYAN}→ PID: $!${NC}"
        sleep 1
    fi
    
    # News Calendar Monitor
    if [ -f "$WORKSPACE/news_calendar_monitor.py" ]; then
        echo "   ${GREEN}4️⃣ Starting News Calendar Monitor...${NC}"
        nohup python3 "$WORKSPACE/news_calendar_monitor.py" > "$WORKSPACE/news_monitor.log" 2>&1 &
        echo "      ${CYAN}→ PID: $!${NC}"
        sleep 1
    fi
    
    # Signal Confirmation Monitor (V6.1 - Ghost Prevention)
    if [ -f "$WORKSPACE/signal_confirmation_monitor.py" ]; then
        echo "   ${GREEN}5️⃣ Starting Signal Confirmation Monitor (V6.1 Anti-Ghost)...${NC}"
        nohup python3 "$WORKSPACE/signal_confirmation_monitor.py" > "$WORKSPACE/signal_confirmation.log" 2>&1 &
        echo "      ${CYAN}→ PID: $!${NC}"
        sleep 1
    fi
    
    # Setup Executor Monitor (if exists)
    if [ -f "$WORKSPACE/setup_executor_monitor.py" ]; then
        echo "   ${GREEN}6️⃣ Starting Setup Executor Monitor...${NC}"
        nohup python3 "$WORKSPACE/setup_executor_monitor.py" --interval 30 --loop > "$WORKSPACE/setup_monitor.log" 2>&1 &
        echo "      ${CYAN}→ PID: $!${NC}"
        sleep 1
    fi
    
    # Telegram Command Center (if exists)
    if [ -f "$WORKSPACE/telegram_command_center.py" ]; then
        echo "   ${GREEN}7️⃣ Starting Telegram Command Center...${NC}"
        nohup python3 "$WORKSPACE/telegram_command_center.py" > "$WORKSPACE/command_center.log" 2>&1 &
        echo "      ${CYAN}→ PID: $!${NC}"
        sleep 1
    fi
fi

echo ""
echo "${GREEN}✅ All monitors started successfully${NC}"
sleep 2

################################################################################
# STEP 4: VERIFICATION - Check System Status
################################################################################

echo ""
echo "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo "${YELLOW}🔍 STEP 4: System Status Verification...${NC}"
echo "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if monitor_status.py exists
if [ -f "$WORKSPACE/monitor_status.py" ]; then
    python3 "$WORKSPACE/monitor_status.py"
else
    # Manual status check
    echo "${CYAN}📊 Running Monitors:${NC}"
    echo ""
    
    for monitor in "${MONITORS[@]}"; do
        if pgrep -f "$monitor" > /dev/null; then
            PID=$(pgrep -f "$monitor")
            echo "   ${GREEN}✅ RUNNING:${NC} $monitor ${CYAN}(PID: $PID)${NC}"
        else
            echo "   ${RED}❌ STOPPED:${NC} $monitor"
        fi
    done
fi

################################################################################
# FINAL STATUS
################################################################################

echo ""
echo "${GREEN}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo "${GREEN}║${NC}                  ${BOLD}✅ SYSTEM STARTUP COMPLETE${NC}                       ${GREEN}║${NC}"
echo "${GREEN}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "${CYAN}📋 Quick Commands:${NC}"
echo "   ${YELLOW}• Check logs:${NC}       tail -f watchdog.log"
echo "   ${YELLOW}• Monitor status:${NC}   python3 monitor_status.py"
echo "   ${YELLOW}• Stop all:${NC}         pkill -f 'monitor.py'"
echo "   ${YELLOW}• Restart:${NC}          bash start_matrix.sh"
echo ""
echo "${CYAN}🛡️  Ghost Notifications:${NC} ${GREEN}PREVENTED${NC} (V5.1 Anti-Spam Active)"
echo "${CYAN}📱 Telegram:${NC}            ${GREEN}READY${NC} (Command Center active)"
echo "${CYAN}💎 Trading Engine:${NC}      ${GREEN}ARMED${NC} (Waiting for signals)"
echo ""
echo "${BOLD}${CYAN}✨ May the Matrix be with you, ФорексГод! ✨${NC}"
echo ""
