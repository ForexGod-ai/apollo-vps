# Economic Calendar Bot Setup Guide

## Overview
EconomicCalendarBot exposes cTrader's Economic Calendar via HTTP API, allowing Python to fetch upcoming news events reliably.

## Architecture
```
cTrader Desktop → EconomicCalendarBot.cs → HTTP localhost:8768 → news_calendar_monitor.py → Telegram
```

## Installation Steps

### 1. Install cBot in cTrader

1. Open **cTrader Desktop**
2. Click **Automate** tab
3. Click **New** → **cBot**
4. Replace default code with `EconomicCalendarBot.cs`
5. Click **Build** (Ctrl+B)
6. Look for "Build succeeded" message

### 2. Start the Bot

1. In Automate tab, find **EconomicCalendarBot**
2. Click **Run** or drag to chart
3. You should see in the Log:
   ```
   🚀 Economic Calendar Bot starting...
   ✅ HTTP server started successfully on http://localhost:8768/
   📅 Economic Calendar data available at /calendar
   ```

### 3. Test the Connection

Test from terminal:
```bash
# Check if bot is running
curl http://localhost:8768/health

# Get calendar events
curl http://localhost:8768/calendar | python3 -m json.tool
```

Expected response:
```json
{
  "success": true,
  "events": [...],
  "count": 25,
  "fetched_at": "2025-12-14 12:00:00"
}
```

### 4. Configure Python Monitor

The `news_calendar_monitor.py` is already configured to use cTrader as primary source with ForexFactory as fallback.

**No changes needed!** Just ensure:
- `.env` file has `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
- cTrader Desktop is running with EconomicCalendarBot active

### 5. Test Full Flow

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
python3 news_calendar_monitor.py
```

You should see:
```
🚀 Starting Daily News Check...
📡 Attempting to fetch from cTrader Desktop...
📅 Fetching calendar from cTrader Desktop...
📊 Received 25 events from cTrader
✅ Parsed 25 calendar events
📊 Total events: 25
🚨 High impact: 12
✅ Telegram alert sent successfully
✅ Daily news check complete!
```

## API Endpoints

### GET /calendar
Returns upcoming economic calendar events for next 7 days.

**Response:**
```json
{
  "success": true,
  "events": [
    {
      "time": "2025-12-15 15:30:00",
      "timestamp": 1734277800,
      "currency": "CAD",
      "impact": "High",
      "event": "CPI m/m",
      "actual": null,
      "forecast": "0.1%",
      "previous": "0.2%",
      "is_high_impact": true,
      "country": "CA"
    }
  ],
  "count": 25,
  "fetched_at": "2025-12-14 12:00:00",
  "period": {
    "start": "2025-12-14",
    "end": "2025-12-21",
    "days": 7
  }
}
```

### GET /health
Health check endpoint.

**Response:**
```json
{
  "status": "ok",
  "timestamp": "2025-12-14T12:00:00",
  "service": "EconomicCalendarBot"
}
```

## Automated Schedule

Once tested, the LaunchAgents will run automatically:

**Daily Checks** (4x per day):
- 08:00 - Morning scan before London open
- 14:00 - Mid-day check
- 20:00 - Evening check before Asian session
- 02:00 - Night check during Asian hours

**Weekly Report** (Sunday 21:00):
- Full week overview
- All HIGH impact events
- Currency-grouped summary

## Troubleshooting

### "Cannot connect to cTrader Desktop on localhost:8768"

**Solution:**
1. Check if cTrader Desktop is running
2. Check if EconomicCalendarBot is active (green play button)
3. Look in cTrader Log for "HTTP server started successfully"
4. Try restarting the cBot

### "No high impact events found"

**Possible causes:**
1. No major news scheduled for next 7 days (rare)
2. Calendar not loaded in cTrader yet (wait a few minutes)
3. Check cTrader Economic Calendar tab manually

### Python fallback to ForexFactory

If you see:
```
⚠️ cTrader unavailable, falling back to ForexFactory...
```

This means:
- cTrader Desktop not running, OR
- EconomicCalendarBot not active, OR
- Port 8768 blocked

System will try ForexFactory (less reliable) as backup.

## Advantages Over ForexFactory Scraping

✅ **Reliable** - No anti-bot protection
✅ **Complete Data** - All events, not just filtered subset  
✅ **Fast** - Local connection, instant response
✅ **Accurate** - Official data from cTrader/Spotware
✅ **No Rate Limits** - Can query as often as needed
✅ **Structured JSON** - Clean, typed data
✅ **Real-time Updates** - Calendar updates automatically

## Next Steps

1. Install EconomicCalendarBot in cTrader ✅
2. Test connection with `curl` ✅
3. Run `python3 news_calendar_monitor.py` ✅
4. If all works, install LaunchAgents: `bash setup_news_monitors.sh`
5. Check Telegram for alerts! 🎉

## Integration with Trading System

The news monitor integrates with your existing "Glitch in Matrix" SMC system:

- **Morning Scanner** (08:00) - Checks news before scanning for setups
- **Position Monitor** - Warns if holding positions during news
- **Risk Management** - Suggests closing trades 30min before major events
- **Dashboard** - Could display upcoming news (future enhancement)

---

**Status**: ✅ Ready for deployment  
**Port**: 8768  
**Data Source**: cTrader Economic Calendar  
**Fallback**: ForexFactory (web scraping)  
**Alerts**: Telegram  
**Schedule**: 4x daily + weekly report
