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
