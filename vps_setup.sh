#!/bin/bash

# ============================================
# VPS Setup Script - Trading AI Agent
# Run this on your VPS after first login
# ============================================

set -e  # Exit on error

echo "🚀 Starting VPS setup for Trading AI Agent..."
echo ""

# Update system
echo "📦 Updating system packages..."
apt-get update
apt-get upgrade -y

# Install Python 3.11
echo "🐍 Installing Python 3.11..."
apt-get install -y software-properties-common
add-apt-repository -y ppa:deadsnakes/ppa
apt-get update
apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Install Git
echo "📥 Installing Git..."
apt-get install -y git

# Install required system packages
echo "📦 Installing system dependencies..."
apt-get install -y build-essential libssl-dev libffi-dev wget curl

# Create bot user (if running as root)
if [ "$EUID" -eq 0 ]; then
    echo "👤 Creating bot user..."
    useradd -m -s /bin/bash forexgod || true
    usermod -aG sudo forexgod || true
fi

# Setup project directory
echo "📁 Setting up project directory..."
cd /home/forexgod || cd /root
PROJECT_DIR="/home/forexgod/trading-ai-agent"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Clone repository (or create empty structure)
echo "📥 Setting up project files..."
mkdir -p logs
mkdir -p data

# Create Python virtual environment
echo "🐍 Creating Python virtual environment..."
python3.11 -m venv venv
source venv/bin/activate

# Install Python packages
echo "📦 Installing Python dependencies..."
cat > requirements.txt << 'EOF'
requests>=2.31.0
websocket-client>=1.6.0
python-dotenv>=1.0.0
loguru>=0.7.0
pandas>=2.0.0
numpy>=1.24.0
pytz>=2023.3
EOF

pip install --upgrade pip
pip install -r requirements.txt

# Create systemd service files
echo "⚙️  Creating systemd services..."

# Trading Monitor Service
cat > /etc/systemd/system/trading-monitor.service << EOF
[Unit]
Description=Trading AI Agent Monitor
After=network.target

[Service]
Type=simple
User=forexgod
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python3 position_monitor.py --loop
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/position_monitor.log
StandardError=append:$PROJECT_DIR/logs/position_monitor_error.log

[Install]
WantedBy=multi-user.target
EOF

# Trade Monitor Service
cat > /etc/systemd/system/trade-monitor.service << EOF
[Unit]
Description=Trading AI Trade Monitor
After=network.target

[Service]
Type=simple
User=forexgod
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python3 trade_monitor.py --loop
Restart=always
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/trade_monitor.log
StandardError=append:$PROJECT_DIR/logs/trade_monitor_error.log

[Install]
WantedBy=multi-user.target
EOF

# Dashboard Service
cat > /etc/systemd/system/trading-dashboard.service << EOF
[Unit]
Description=Trading AI Dashboard
After=network.target

[Service]
Type=simple
User=forexgod
WorkingDirectory=$PROJECT_DIR
Environment="PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin"
ExecStart=$PROJECT_DIR/venv/bin/python3 -m http.server 8080
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Setup firewall
echo "🔒 Configuring firewall..."
ufw allow 22/tcp      # SSH
ufw allow 8080/tcp    # Dashboard
ufw --force enable

# Create .env template
echo "📝 Creating .env template..."
cat > .env.example << EOF
# Telegram Configuration
TELEGRAM_BOT_TOKEN=YOUR_BOT_TOKEN_HERE
TELEGRAM_CHAT_ID=YOUR_CHAT_ID_HERE

# cTrader Configuration
CTRADER_ACCESS_TOKEN=YOUR_ACCESS_TOKEN_HERE
CTRADER_ACCOUNT_ID=9709773

# API Keys (optional)
ALPHA_VANTAGE_KEY=YOUR_KEY_HERE
EOF

# Set permissions
if [ -d "/home/forexgod" ]; then
    chown -R forexgod:forexgod "$PROJECT_DIR"
fi

echo ""
echo "============================================"
echo "✅ VPS SETUP COMPLETE!"
echo "============================================"
echo ""
echo "📝 NEXT STEPS:"
echo ""
echo "1. Upload your bot files:"
echo "   scp -r * root@YOUR_VPS_IP:$PROJECT_DIR/"
echo ""
echo "2. Configure credentials:"
echo "   nano $PROJECT_DIR/.env"
echo ""
echo "3. Start services:"
echo "   systemctl enable trading-monitor"
echo "   systemctl start trading-monitor"
echo "   systemctl enable trade-monitor"
echo "   systemctl start trade-monitor"
echo "   systemctl enable trading-dashboard"
echo "   systemctl start trading-dashboard"
echo ""
echo "4. Check status:"
echo "   systemctl status trading-monitor"
echo "   tail -f $PROJECT_DIR/logs/trade_monitor.log"
echo ""
echo "5. Access dashboard:"
echo "   http://YOUR_VPS_IP:8080/dashboard_live.html"
echo ""
echo "🚀 Your trading bot is ready for 24/7 operation!"
