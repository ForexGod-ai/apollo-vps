#!/bin/bash

# ForexGod Dashboard - Deploy to Public Cloud 24/7
# Acest script pregătește dashboard-ul pentru hosting public permanent

echo "🚀 ForexGod Dashboard - Cloud Deploy Setup"
echo "=========================================="

# Check if we're in the right directory
if [ ! -f "trade_history.json" ]; then
    echo "❌ Error: trade_history.json not found!"
    exit 1
fi

# Create deployment package
echo "📦 Creating deployment package..."
mkdir -p deploy_dashboard
cp dashboard_live.html deploy_dashboard/index.html
cp trade_history.json deploy_dashboard/

# Create a simple sync script for updating trade_history.json
cat > deploy_dashboard/sync_trades.sh << 'EOF'
#!/bin/bash
# This script should run on your local machine to sync trades to cloud
# Usage: ./sync_trades.sh

REMOTE_USER="your_user"
REMOTE_HOST="your_server_ip"
REMOTE_PATH="/var/www/html/dashboard"

while true; do
    scp trade_history.json $REMOTE_USER@$REMOTE_HOST:$REMOTE_PATH/
    sleep 30
done
EOF

chmod +x deploy_dashboard/sync_trades.sh

# Create README for deployment
cat > deploy_dashboard/README.md << 'EOF'
# ForexGod Dashboard - Cloud Deployment

## Option 1: Railway.app (EASIEST - FREE)
1. Go to https://railway.app
2. Sign up with GitHub
3. New Project → Deploy from GitHub
4. Upload this folder
5. Railway gives you: https://your-app.railway.app

## Option 2: Vercel (FREE - RECOMMENDED)
1. Install Vercel: npm i -g vercel
2. Run: vercel --prod
3. Auto-deploy on every git push
4. URL: https://your-dashboard.vercel.app

## Option 3: Render.com (FREE - 24/7)
1. Go to https://render.com
2. New → Static Site
3. Connect GitHub repo
4. Deploy: https://your-dashboard.onrender.com

## Option 4: DigitalOcean / AWS / VPS
See DEPLOY_VPS.md for VPS setup instructions.

## Auto-Sync trade_history.json
Run sync_trades.sh on your local machine to keep cloud updated.
EOF

# Create VPS deployment guide
cat > deploy_dashboard/DEPLOY_VPS.md << 'EOF'
# VPS Deployment Guide (24/7 Public Access)

## Prerequisites
- VPS (DigitalOcean, Linode, AWS EC2, etc.)
- Ubuntu 20.04+ recommended
- SSH access

## Step 1: Setup VPS Server

```bash
# SSH to your VPS
ssh root@YOUR_VPS_IP

# Update system
apt update && apt upgrade -y

# Install nginx
apt install nginx -y

# Install Python for file sync
apt install python3 python3-pip -y

# Create web directory
mkdir -p /var/www/html/dashboard
cd /var/www/html/dashboard
```

## Step 2: Configure Nginx

```bash
# Create nginx config
cat > /etc/nginx/sites-available/dashboard << 'NGINXCONF'
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;
    
    root /var/www/html/dashboard;
    index index.html;
    
    location / {
        try_files $uri $uri/ =404;
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        add_header Pragma "no-cache";
        add_header Expires "0";
    }
    
    location /trade_history.json {
        add_header Access-Control-Allow-Origin *;
        add_header Cache-Control "no-cache";
    }
}
NGINXCONF

# Enable site
ln -s /etc/nginx/sites-available/dashboard /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default

# Test and restart nginx
nginx -t
systemctl restart nginx
```

## Step 3: Upload Files

On your local machine:
```bash
scp index.html root@YOUR_VPS_IP:/var/www/html/dashboard/
scp trade_history.json root@YOUR_VPS_IP:/var/www/html/dashboard/
```

## Step 4: Auto-Sync from Local Machine

Create systemd service on your LOCAL Mac:

```bash
# Create launch agent
cat > ~/Library/LaunchAgents/com.forexgod.dashboard.plist << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.forexgod.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/Users/forexgod/Desktop/trading-ai-agent apollo/sync_to_vps.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/dashboard_sync.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/dashboard_sync.err</string>
</dict>
</plist>
PLIST

# Load service
launchctl load ~/Library/LaunchAgents/com.forexgod.dashboard.plist
```

## Step 5: SSL Certificate (HTTPS)

```bash
# On VPS
apt install certbot python3-certbot-nginx -y
certbot --nginx -d YOUR_DOMAIN
```

## Result
✅ Dashboard live at: http://YOUR_VPS_IP or https://YOUR_DOMAIN
✅ Auto-syncs every 30 seconds
✅ Works 24/7 even when laptop closed
EOF

# Create sync script for local machine
cat > sync_to_vps.sh << 'EOF'
#!/bin/bash

# Configuration
VPS_USER="root"
VPS_HOST="YOUR_VPS_IP_HERE"
VPS_PATH="/var/www/html/dashboard"
LOCAL_FILE="/Users/forexgod/Desktop/trading-ai-agent apollo/trade_history.json"

echo "🔄 ForexGod Dashboard - Auto Sync to VPS"

while true; do
    # Check if file exists
    if [ -f "$LOCAL_FILE" ]; then
        # Sync to VPS
        scp -o ConnectTimeout=5 "$LOCAL_FILE" "$VPS_USER@$VPS_HOST:$VPS_PATH/" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "✅ [$(date '+%Y-%m-%d %H:%M:%S')] Synced to VPS"
        else
            echo "⚠️  [$(date '+%Y-%m-%d %H:%M:%S')] Sync failed - will retry"
        fi
    fi
    
    # Wait 30 seconds
    sleep 30
done
EOF

chmod +x sync_to_vps.sh

echo ""
echo "✅ Deployment package created in: deploy_dashboard/"
echo ""
echo "🚀 FASTEST OPTIONS (No VPS needed):"
echo "=================================="
echo ""
echo "1️⃣  Railway.app (FREE, 1-click deploy):"
echo "   → https://railway.app"
echo "   → New Project → Upload deploy_dashboard folder"
echo "   → Get instant URL: https://yourapp.railway.app"
echo ""
echo "2️⃣  Vercel (FREE, auto GitHub sync):"
echo "   → npm i -g vercel"
echo "   → cd deploy_dashboard && vercel --prod"
echo ""
echo "3️⃣  Render.com (FREE, 24/7 hosting):"
echo "   → https://render.com"
echo "   → New Static Site → Upload folder"
echo ""
echo "📡 For VPS deployment (full control):"
echo "   → See deploy_dashboard/DEPLOY_VPS.md"
echo ""
echo "⚡ Quick VPS Setup (if you have one):"
echo "   1. Edit sync_to_vps.sh with your VPS IP"
echo "   2. Run: ./sync_to_vps.sh"
echo "   3. Dashboard syncs every 30 seconds!"
echo ""
