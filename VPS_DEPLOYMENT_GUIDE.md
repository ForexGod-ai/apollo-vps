# 🚀 VPS Deployment Guide - Trading AI Agent

## 📋 Prerequisites
- DigitalOcean account (sau alt VPS provider)
- SSH access la VPS
- Python 3.10+

---

## 🎯 Step 1: Create VPS (DigitalOcean)

1. **Sign up**: https://www.digitalocean.com/
2. **Create Droplet**:
   - **Image**: Ubuntu 22.04 LTS
   - **Plan**: Basic $6/month (1GB RAM, 1 vCPU)
   - **Datacenter**: Frankfurt 1 (sau Amsterdam)
   - **Authentication**: SSH key (mai sigur) SAU password
3. **Get IP**: Note your VPS IP (ex: `134.209.123.45`)

---

## 🎯 Step 2: Connect to VPS

```bash
# Connect via SSH
ssh root@YOUR_VPS_IP

# Example:
ssh root@134.209.123.45
```

---

## 🎯 Step 3: Deploy bot (AUTOMATED)

### **Option A: Full automated deployment**

Pe **MacBook** (local), rulează:
```bash
cd "/Users/forexgod/Desktop/trading-ai-agent apollo"
./deploy_to_vps.sh YOUR_VPS_IP
```

### **Option B: Manual deployment**

Pe **VPS** (după SSH connect):
```bash
# Download deployment script
wget https://raw.githubusercontent.com/YOUR_REPO/deploy_vps.sh
chmod +x deploy_vps.sh

# Run deployment
./deploy_vps.sh
```

---

## 🎯 Step 4: Configure credentials

Pe **VPS**:
```bash
cd ~/trading-ai-agent
nano .env
```

Add:
```env
TELEGRAM_BOT_TOKEN=8246975960:AAG...
TELEGRAM_CHAT_ID=YOUR_CHAT_ID
CTRADER_ACCESS_TOKEN=YOUR_TOKEN
CTRADER_ACCOUNT_ID=9709773
```

---

## 🎯 Step 5: Start services

```bash
# Start all monitors
./start_monitoring.sh

# Check status
launchctl list | grep forexgod  # macOS
systemctl status trading-monitor # Linux VPS

# View logs
tail -f logs/trade_monitor.log
```

---

## 📊 Management Commands (VPS)

```bash
# Check services
systemctl status trading-monitor
systemctl status trading-dashboard

# Restart
systemctl restart trading-monitor

# View logs
journalctl -u trading-monitor -f
tail -f logs/trade_monitor.log

# Update bot
cd ~/trading-ai-agent
git pull
systemctl restart trading-monitor
```

---

## 🔒 Security Setup

```bash
# Create non-root user
adduser forexgod
usermod -aG sudo forexgod

# Setup firewall
ufw allow 22/tcp      # SSH
ufw allow 8080/tcp    # Dashboard
ufw enable

# Disable root SSH login
nano /etc/ssh/sshd_config
# Set: PermitRootLogin no
systemctl restart sshd
```

---

## 💰 Cost Breakdown

| Service | Cost/Month |
|---------|------------|
| VPS (DigitalOcean) | $6.00 |
| cTrader API | FREE |
| Telegram Bot | FREE |
| **TOTAL** | **$6.00/month** |

---

## ✅ Benefits of VPS

- ✅ **24/7 uptime** (nu depinde de laptop)
- ✅ **99.9% availability** (datacenter garantat)
- ✅ **Fast internet** (1 Gbps în datacenter)
- ✅ **Low latency** (aproape de IC Markets servers)
- ✅ **No electricity cost** (laptop poate fi închis)
- ✅ **Remote access** (SSH de oriunde)
- ✅ **Auto-restart** (systemd services)
- ✅ **Scalable** (poți upgrade RAM/CPU)

---

## 🎯 Next Steps

1. **Create DigitalOcean account** → https://www.digitalocean.com/
2. **Deploy bot cu scriptul** → `./deploy_to_vps.sh`
3. **Configure credentials** → `.env` file
4. **Start monitoring** → `./start_monitoring.sh`
5. **Test Telegram** → Așteaptă următorul TP/SL

**Need help?** Ping me! 🚀
