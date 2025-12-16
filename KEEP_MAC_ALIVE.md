# 🖥️ Keep MacBook Running 24/7 for News Alerts

## Option 1: System Settings (Recommended)

### Step 1: Prevent Sleep When Lid Closed
```bash
# Allow Mac to run with lid closed when connected to power
sudo pmset -c sleep 0
sudo pmset -c disablesleep 1

# Keep display off but system awake
sudo pmset -c displaysleep 5
```

### Step 2: Energy Saver Settings
1. Open **System Settings** → **Battery**
2. **Power Adapter** tab:
   - ✅ Prevent automatic sleeping when display is off
   - ✅ Wake for network access
   - ⚠️ Set display sleep to 5-10 minutes (save screen)

### Step 3: Verify Settings
```bash
# Check current power settings
pmset -g

# Should show:
# sleep          0 (AC power)
# disablesleep   1
```

## Option 2: Third-Party Apps

### Amphetamine (FREE - App Store)
- **Best option**: Prevents sleep, scheduled keep-awake
- Download: Mac App Store → "Amphetamine"
- Configure:
  - Enable "Start at login"
  - Create trigger: "Keep awake indefinitely when plugged in"
  - ✅ Allow display sleep (saves screen)

### Caffeine (FREE)
- Simple menu bar app
- Click icon to prevent sleep
- Less features than Amphetamine

## Option 3: Terminal Command (Quick Test)

```bash
# Keep Mac awake until you press Ctrl+C
caffeinate

# Keep awake for 8 hours
caffeinate -t 28800

# Keep awake while process runs
caffeinate -i python3 news_calendar_monitor.py
```

## ⚠️ Important Considerations

### Pros of MacBook 24/7:
- ✅ No monthly VPS cost
- ✅ Easy to debug locally
- ✅ cTrader Desktop accessible (if needed later)

### Cons of MacBook 24/7:
- ❌ Power consumption (~10-15W = ~$2-3/month electricity)
- ❌ Wear on hardware (battery, SSD)
- ❌ If Mac crashes/restarts, alerts stop
- ❌ Limited portability (must stay plugged in)
- ❌ Network dependency (home internet must be stable)

### Pros of VPS:
- ✅ True 24/7 reliability
- ✅ 99.9% uptime guarantee
- ✅ Professional infrastructure
- ✅ Can run multiple bots/services
- ✅ MacBook free for other work

### Cons of VPS:
- ❌ Monthly cost ($5-10)
- ❌ Requires SSH knowledge
- ❌ No GUI (terminal only)

## 🎯 Recommended Setup

For your **60-day demo period** (Dec 13 - Feb 11):

### Short Term (Demo Period):
**Use MacBook 24/7** with Amphetamine app
- Cost: $0
- Setup time: 5 minutes
- Perfect for testing

### Long Term (If Bot Profitable):
**Move to VPS** after demo proves successful
- Cost: $5/month
- One-time setup: 30 minutes
- Professional solution

## 🚀 Quick Setup for MacBook 24/7

```bash
# 1. Configure power settings
sudo pmset -c sleep 0
sudo pmset -c disablesleep 1
sudo pmset -c displaysleep 10

# 2. Install Amphetamine from App Store
# (Manual step - open App Store)

# 3. Test LaunchAgents are running
launchctl list | grep forexgod

# Should show:
# com.forexgod.newscalendar - 0 (running)
# com.forexgod.weeklynews - 0 (running)

# 4. Test alert manually
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
python3 news_calendar_monitor.py

# 5. Check logs
tail -f logs/news_calendar.log
```

## 📊 Power Consumption Estimate

MacBook Air M1/M2 running 24/7:
- Idle with display off: ~5-8W
- Cost per month: ~$1.50 (at $0.12/kWh)
- **Cheaper than VPS for demo period!**

## 🔄 Backup Plan

Even with 24/7 setup, create **backup notification**:

```bash
# Add to crontab - sends email if system reboots
@reboot echo "MacBook restarted - News alerts may be interrupted" | mail -s "Alert System Reboot" your@email.com
```

Or use **Telegram notification on system startup**:

```python
# startup_notification.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

message = "🔄 MacBook restarted - News alert system is back online"
requests.post(
    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
    json={"chat_id": CHAT_ID, "text": message}
)
```

Add to LaunchAgent for startup:
```bash
launchctl load com.forexgod.startup-notification.plist
```

## ✅ Final Checklist

- [ ] Set power settings: `sudo pmset -c sleep 0`
- [ ] Install Amphetamine app (or use caffeinate)
- [ ] Enable "Prevent sleep when plugged in"
- [ ] Verify LaunchAgents running: `launchctl list | grep forexgod`
- [ ] Test manual alert: `python3 news_calendar_monitor.py`
- [ ] Connect MacBook to stable power source
- [ ] Connect to reliable WiFi network
- [ ] (Optional) Setup startup notification
- [ ] Monitor for 48 hours to ensure stability

## 🎯 Decision Matrix

| Scenario | Recommended Solution |
|----------|---------------------|
| **60-day demo only** | MacBook 24/7 + Amphetamine |
| **Bot proves profitable** | Migrate to VPS ($5/mo) |
| **Multiple bots running** | VPS from start |
| **Travel frequently** | VPS required |
| **Home internet unstable** | VPS required |
| **Want to use MacBook portable** | VPS required |

---

**For your current situation (demo period):**
→ Use **MacBook 24/7** for next 2 months
→ If profitable, invest in VPS for long-term stability
→ Cost during demo: $0 setup + ~$1.50/month electricity = **FREE**

💡 **Bonus**: You can still use MacBook normally - alerts run in background!
