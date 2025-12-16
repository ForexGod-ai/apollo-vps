# 📰 News Calendar Alert System - Complete Setup Guide

## ✅ System Status

**WORKING SOLUTION**: Manual JSON calendar with automated Telegram alerts

### What Works:
- ✅ Manual economic calendar (`economic_calendar.json`)
- ✅ Automated Telegram alerts 4x daily (08:00, 14:00, 20:00, 02:00)
- ✅ Weekly report on Sunday 21:00
- ✅ All 34 high-impact events can be monitored
- ✅ Critical keyword detection (NFP, FOMC, CPI, ECB, BOE, etc.)

### What Doesn't Work:
- ❌ ForexFactory scraping (only returns 3 events, blocks multi-day)
- ❌ cTrader Desktop API (Economic Calendar not exposed)
- ❌ Investing.com API (date format errors)

---

## 🚀 Quick Start

### 1. Test Current Setup

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
python3 news_calendar_monitor.py
```

**Expected output:**
```
✅ Loaded 11 events from manual calendar
📊 Total events: 11
🚨 High impact: 11
✅ Telegram alert sent successfully
```

### 2. Check Telegram

Open your Telegram bot chat - you should see alert like:

```
⚠️ HIGH IMPACT NEWS ALERT ⚠️

🚨 AVOID TRADING DURING THESE TIMES 🚨

📅 Sunday, December 15
🇨🇦 03:30 PM - Canada CPI m/m ⏰ in 15h
...
```

---

## 📅 Weekly Calendar Update Process

Every **Sunday evening** (before 21:00 weekly report):

### Step 1: Check ForexFactory Website

Open browser: https://www.forexfactory.com/calendar

- Filter to show only **HIGH impact** events (red icons)
- Look at upcoming **7 days**
- Focus on: USD, EUR, GBP, JPY, AUD, NZD, CAD, CHF

### Step 2: Use Interactive Update Tool

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
python3 update_calendar.py
```

**Example session:**
```
📅 ADD NEW EVENT TO CALENDAR

📆 Date (YYYY-MM-DD): 2025-12-20
⏰ Time (HH:MM in UTC): 19:00
💱 Currency: USD
📰 Event name: FOMC Statement
🎯 Impact: High
📊 Forecast (press Enter to skip): 
📊 Previous (press Enter to skip): 

✅ Added: 2025-12-20 19:00 - USD FOMC Statement
```

### Step 3: Manual JSON Edit (Alternative)

Edit `economic_calendar.json` directly:

```json
{
  "recurring_events": { ... },
  "custom_events_december_2025": [
    {
      "date": "2025-12-20",
      "time": "19:00",
      "currency": "USD",
      "event": "FOMC Statement",
      "impact": "High"
    }
  ]
}
```

---

## 🔔 Automated Schedule Setup

### Install LaunchAgents (One-Time)

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
bash setup_news_monitors.sh
```

**This creates:**
- Daily alerts: 08:00, 14:00, 20:00, 02:00 (UTC)
- Weekly report: Sunday 21:00 (UTC)

### Check If Running

```bash
# List active jobs
launchctl list | grep forexgod

# Should show:
# com.forexgod.newscalendar
# com.forexgod.weeklynews
```

### Stop/Restart

```bash
# Stop daily alerts
launchctl unload ~/Library/LaunchAgents/com.forexgod.newscalendar.plist

# Restart
launchctl load ~/Library/LaunchAgents/com.forexgod.newscalendar.plist
```

---

## 🎯 Critical Events to Monitor

### Always Add These:

| Event | Currency | Typical Date | Impact |
|-------|----------|--------------|--------|
| Non-Farm Payrolls (NFP) | USD | First Friday of month | 🔥🔥🔥 |
| FOMC Statement & Rate | USD | 8x per year (see schedule) | 🔥🔥🔥 |
| CPI (Inflation) | USD | Mid-month (13th-15th) | 🔥🔥🔥 |
| ECB Rate Decision | EUR | 8x per year | 🔥🔥 |
| BOE Rate Decision | GBP | 8x per year | 🔥🔥 |
| GDP (Quarterly) | All majors | Quarterly | 🔥🔥 |
| Retail Sales | USD, GBP, EUR | Monthly | 🔥 |
| PMI Flash | EUR, GBP | ~20th of month | 🔥 |

### 2025 FOMC Meeting Dates:
- Jan 28-29
- Mar 18-19
- **Apr 29-30** ⚠️
- Jun 17-18
- Jul 29-30
- Sep 16-17
- Oct 28-29
- **Dec 9-10** ⚠️

### 2025 ECB Meeting Dates:
- Jan 30
- Mar 6
- **Apr 17** ⚠️
- Jun 5
- Jul 24
- Sep 11
- Oct 30
- Dec 18

---

## 📱 Telegram Alert Format

```
⚠️ HIGH IMPACT NEWS ALERT ⚠️

🚨 AVOID TRADING DURING THESE TIMES 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 Monday, December 16

🇺🇸 01:30 PM - Non-Farm Employment Change ⏰ in 12h
📊 Forecast: 200K | Previous: 227K
🔥 CRITICAL: Do NOT trade 1 hour before/after!

🇺🇸 01:30 PM - Unemployment Rate ⏰ in 12h
📊 Forecast: 4.2% | Previous: 4.2%

━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 Total high-impact events: 11
⏰ Next alert: Today at 2:00 PM UTC
```

---

## 🛠️ Troubleshooting

### No Telegram Alert Received

**Check 1: Test manually**
```bash
python3 news_calendar_monitor.py
```

**Check 2: Verify Telegram bot token**
```bash
grep TELEGRAM .env
# Should show valid bot token and chat ID
```

**Check 3: Check logs**
```bash
tail -f news_calendar.log
```

### No Events Loading

**Check JSON syntax:**
```bash
python3 -c "import json; print(json.load(open('economic_calendar.json')))"
```

**Should output valid JSON. If error:**
- Check for missing commas
- Check for trailing commas
- Validate dates (YYYY-MM-DD)
- Validate times (HH:MM)

### LaunchAgent Not Running

**Check status:**
```bash
launchctl list | grep forexgod
```

**If not listed:**
```bash
launchctl load ~/Library/LaunchAgents/com.forexgod.newscalendar.plist
```

**Check for errors:**
```bash
tail -f /tmp/news_calendar_*.log
```

---

## 📊 Files Overview

| File | Purpose |
|------|---------|
| `news_calendar_monitor.py` | Main script - fetches events, sends alerts |
| `economic_calendar.json` | Manual calendar database |
| `update_calendar.py` | Interactive tool to add events |
| `weekly_news_report.py` | Weekly summary report |
| `setup_news_monitors.sh` | Install automation |
| `com.forexgod.newscalendar.plist` | Daily alert scheduler |
| `com.forexgod.weeklynews.plist` | Weekly report scheduler |

---

## 🎓 Advanced Usage

### Custom Alert Times

Edit `com.forexgod.newscalendar.plist`:

```xml
<key>StartCalendarInterval</key>
<array>
    <dict>
        <key>Hour</key>
        <integer>8</integer>  <!-- Change this -->
        <key>Minute</key>
        <integer>0</integer>
    </dict>
</array>
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.forexgod.newscalendar.plist
launchctl load ~/Library/LaunchAgents/com.forexgod.newscalendar.plist
```

### Add More Keywords

Edit `news_calendar_monitor.py`:

```python
self.critical_keywords = [
    'Non-Farm', 'NFP', 'Payroll',
    'FOMC', 'Fed', 'Interest Rate',
    'Your New Keyword Here',  # Add here
]
```

### Test Specific Date Range

```bash
python3 -c "
from news_calendar_monitor import NewsCalendarMonitor
monitor = NewsCalendarMonitor()
events = monitor.fetch_manual_calendar(days_ahead=14)  # 14 days
print(f'Found {len(events)} events')
"
```

---

## 📈 Integration with Trading System

This alert system works **alongside** your existing "Glitch in Matrix" SMC system:

1. **Morning Scanner** (08:00) - Identifies setups
2. **News Alert** (08:00, 14:00, 20:00, 02:00) - Warns about upcoming volatility
3. **Dashboard** (localhost:8080) - Shows open positions
4. **Position Monitor** - Manages trades

**Trading Rule:**
- ⛔ **DO NOT** open new trades 1 hour before high-impact news
- ⛔ **DO NOT** hold trades through NFP, FOMC, ECB/BOE rate decisions
- ✅ **CLOSE** all positions before critical events
- ✅ **WAIT** 30-60 minutes after event for volatility to settle

---

## 🆘 Support

If alerts stop working:

1. Test manually: `python3 news_calendar_monitor.py`
2. Check Telegram bot: Send message to bot to verify it's alive
3. Check calendar JSON: Valid syntax?
4. Check LaunchAgent: `launchctl list | grep forexgod`
5. Review logs: `tail -f news_calendar.log`

**Most common issue:** Forgot to update `economic_calendar.json` for new week!

---

## ✅ Success Checklist

- [ ] Tested manual run: `python3 news_calendar_monitor.py`
- [ ] Received test alert on Telegram
- [ ] Installed LaunchAgents: `bash setup_news_monitors.sh`
- [ ] Verified automation: `launchctl list | grep forexgod`
- [ ] Added this week's events to `economic_calendar.json`
- [ ] Set Sunday reminder to update calendar weekly
- [ ] Tested `update_calendar.py` tool
- [ ] Understood critical events list (NFP, FOMC, CPI, etc.)

---

**Demo Period:** Dec 13, 2025 - Feb 11, 2026 (60 days)
**Account:** IC Markets #9709773
**Goal:** Protect capital during news volatility, maximize SMC setup profitability

🎯 **Remember:** The best trade is sometimes NO trade! News alerts keep you safe. 💰
