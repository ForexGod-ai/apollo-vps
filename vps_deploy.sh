#!/bin/bash
# ═══════════════════════════════════════════════════════════
# 🔱 GLITCH IN MATRIX — VPS DEPLOY SCRIPT
# 🏛️ ФорексГод • Ubuntu 22.04 LTS
# Rulează LOCAL pe Mac: bash vps_deploy.sh <VPS_IP>
# ═══════════════════════════════════════════════════════════

VPS_IP="${1:-YOUR_VPS_IP}"
VPS_USER="root"
REMOTE_DIR="/home/matrix/trading-ai-agent-apollo"
LOCAL_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

if [ "$VPS_IP" = "YOUR_VPS_IP" ]; then
    echo "❌ Usage: bash vps_deploy.sh <VPS_IP>"
    echo "   Example: bash vps_deploy.sh 65.21.100.200"
    exit 1
fi

echo "🚀 Deploying Glitch in Matrix to VPS $VPS_IP..."

# ── Step 1: Setup server
echo ""
echo "📦 Step 1/4: Setting up server..."
ssh $VPS_USER@$VPS_IP bash << 'REMOTE_SETUP'
apt-get update -qq
apt-get install -y python3.11 python3.11-venv python3-pip git screen htop curl ufw -qq
ufw allow 22/tcp && ufw --force enable
useradd -m -s /bin/bash matrix 2>/dev/null || true
mkdir -p /home/matrix/trading-ai-agent-apollo
chown -R matrix:matrix /home/matrix/
echo "✅ Server ready"
REMOTE_SETUP

# ── Step 2: Sync project files (exclude venv, logs, cache, git)
echo ""
echo "📤 Step 2/4: Syncing project files..."
rsync -avz --progress \
    --exclude='.venv/' \
    --exclude='.git/' \
    --exclude='logs/' \
    --exclude='*.log' \
    --exclude='__pycache__/' \
    --exclude='*.pyc' \
    --exclude='data/backups/' \
    --exclude='screenshots/' \
    --exclude='charts/' \
    "$LOCAL_DIR/" \
    "$VPS_USER@$VPS_IP:$REMOTE_DIR/"

echo "✅ Files synced"

# ── Step 3: Install dependencies on VPS
echo ""
echo "🔧 Step 3/4: Installing Python dependencies..."
ssh $VPS_USER@$VPS_IP bash << REMOTE_INSTALL
cd $REMOTE_DIR
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements_vps_clean.txt -q
echo "✅ Dependencies installed"
REMOTE_INSTALL

# ── Step 4: Setup systemd services
echo ""
echo "⚙️  Step 4/4: Installing systemd services..."
ssh $VPS_USER@$VPS_IP bash << REMOTE_SERVICES
# Create all 6 systemd service files
for SERVICE in setup_executor_monitor position_monitor telegram_command_center watchdog_monitor news_calendar_monitor ctrader_sync_daemon; do
    cat > /etc/systemd/system/matrix-${SERVICE}.service << EOF
[Unit]
Description=Glitch in Matrix - ${SERVICE}
After=network.target
Restart=always
RestartSec=10

[Service]
User=matrix
WorkingDirectory=$REMOTE_DIR
ExecStart=$REMOTE_DIR/.venv/bin/python ${SERVICE}.py
StandardOutput=append:$REMOTE_DIR/logs/${SERVICE}.log
StandardError=append:$REMOTE_DIR/logs/${SERVICE}_error.log
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF
done

# Special args for setup_executor
sed -i 's/ExecStart=.*setup_executor_monitor.py/& --interval 30 --loop/' /etc/systemd/system/matrix-setup_executor_monitor.service

mkdir -p $REMOTE_DIR/logs
chown -R matrix:matrix $REMOTE_DIR/logs

systemctl daemon-reload
for SERVICE in setup_executor_monitor position_monitor telegram_command_center watchdog_monitor news_calendar_monitor ctrader_sync_daemon; do
    systemctl enable matrix-${SERVICE}
    systemctl start matrix-${SERVICE}
done

echo "✅ All 6 services started"
systemctl status matrix-setup_executor_monitor --no-pager | head -5
REMOTE_SERVICES

echo ""
echo "═══════════════════════════════════════════════════════"
echo "✅ DEPLOYMENT COMPLETE!"
echo ""
echo "📊 Check status:    ssh $VPS_USER@$VPS_IP 'systemctl status matrix-setup_executor_monitor'"
echo "📋 View logs:       ssh $VPS_USER@$VPS_IP 'tail -f $REMOTE_DIR/logs/setup_executor_monitor.log'"
echo "🔄 Restart all:     ssh $VPS_USER@$VPS_IP 'systemctl restart matrix-setup_executor_monitor'"
echo ""
echo "⚠️  IMPORTANT: Verifică .env pe VPS să conțină toate credentials:"
echo "   ssh $VPS_USER@$VPS_IP 'cat $REMOTE_DIR/.env'"
echo "═══════════════════════════════════════════════════════"
