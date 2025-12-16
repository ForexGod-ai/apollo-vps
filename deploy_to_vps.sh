#!/bin/zsh

# ============================================
# Deploy Trading Bot to VPS
# Run this on your MacBook
# ============================================

set -e  # Exit on error

# Check arguments
if [ -z "$1" ]; then
    echo "❌ Usage: ./deploy_to_vps.sh <VPS_IP>"
    echo "Example: ./deploy_to_vps.sh 134.209.123.45"
    exit 1
fi

VPS_IP="$1"
VPS_USER="root"  # Change to 'forexgod' if using non-root
PROJECT_DIR="/home/forexgod/trading-ai-agent"
LOCAL_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

echo "🚀 Deploying Trading Bot to VPS..."
echo "📍 VPS IP: $VPS_IP"
echo "📁 Remote dir: $PROJECT_DIR"
echo ""

# Test SSH connection
echo "🔐 Testing SSH connection..."
if ! ssh -o ConnectTimeout=10 "$VPS_USER@$VPS_IP" "echo 'SSH connection OK'"; then
    echo "❌ Cannot connect to VPS. Check:"
    echo "   - VPS IP is correct"
    echo "   - SSH port 22 is open"
    echo "   - SSH key is configured"
    exit 1
fi

# Upload setup script
echo "📤 Uploading setup script..."
scp "$LOCAL_DIR/vps_setup.sh" "$VPS_USER@$VPS_IP:/tmp/vps_setup.sh"

# Run setup on VPS
echo "⚙️  Running VPS setup (this may take 5-10 minutes)..."
ssh "$VPS_USER@$VPS_IP" "bash /tmp/vps_setup.sh"

# Create list of files to upload (exclude logs, cache, etc.)
echo "📦 Preparing files for upload..."
cd "$LOCAL_DIR"

# Upload bot files
echo "📤 Uploading bot files..."
rsync -avz --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='venv' \
    --exclude='logs/*.log' \
    --exclude='.DS_Store' \
    --exclude='*.bat' \
    --exclude='*.ps1' \
    --exclude='setup_daily_scan.*' \
    --exclude='nohup.out' \
    --exclude='.position_monitor.pid' \
    --exclude='.trade_monitor.pid' \
    ./ "$VPS_USER@$VPS_IP:$PROJECT_DIR/"

# Upload .env if exists (IMPORTANT!)
if [ -f ".env" ]; then
    echo "🔐 Uploading .env file..."
    scp .env "$VPS_USER@$VPS_IP:$PROJECT_DIR/.env"
else
    echo "⚠️  No .env file found locally. You'll need to create it on VPS."
fi

# Set correct permissions
echo "🔒 Setting permissions..."
ssh "$VPS_USER@$VPS_IP" << 'EOF'
cd /home/forexgod/trading-ai-agent
chmod +x *.sh *.py
chmod 600 .env 2>/dev/null || true
chown -R forexgod:forexgod . 2>/dev/null || true
EOF

# Start services
echo "▶️  Starting services..."
ssh "$VPS_USER@$VPS_IP" << 'EOF'
systemctl daemon-reload
systemctl enable trading-monitor
systemctl start trading-monitor
systemctl enable trade-monitor
systemctl start trade-monitor
systemctl enable trading-dashboard
systemctl start trading-dashboard

# Wait for services to start
sleep 3

# Check status
echo ""
echo "============================================"
echo "📊 SERVICE STATUS"
echo "============================================"
systemctl status trading-monitor --no-pager -l | head -15
echo ""
systemctl status trade-monitor --no-pager -l | head -15
echo ""
systemctl status trading-dashboard --no-pager -l | head -15
EOF

# Get VPS IP for dashboard
echo ""
echo "============================================"
echo "✅ DEPLOYMENT COMPLETE!"
echo "============================================"
echo ""
echo "🎯 Your bot is now running 24/7 on VPS!"
echo ""
echo "📊 Dashboard: http://$VPS_IP:8080/dashboard_live.html"
echo "🔐 SSH Access: ssh $VPS_USER@$VPS_IP"
echo ""
echo "📝 Useful commands (run on VPS):"
echo "   systemctl status trading-monitor"
echo "   systemctl restart trading-monitor"
echo "   tail -f $PROJECT_DIR/logs/trade_monitor.log"
echo "   journalctl -u trading-monitor -f"
echo ""
echo "🚀 Monitors are active and will send Telegram notifications!"
echo ""
