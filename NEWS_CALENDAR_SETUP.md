# 📰 Forex News Calendar - Setup Complet

## 🎯 Sistem de Alerte pentru Evenimente Economice

Sistemul trimite alerte Telegram cu evenimente HIGH-impact care pot mișca piața forex (NFP, CPI, FOMC, etc.)

---

## 📊 Cum Funcționează

### 1. Surse de Date (în ordine):

1. **economic_calendar.json** (MANUAL - sursa principală)
   - Actualizat lunar cu evenimente HIGH-impact
   - Cel mai fiabil, fără limitări API
   - Conține NFP, CPI, FOMC, ECB, BOE, etc.

2. **cTrader Desktop API** (BACKUP - dacă rulează)
   - Localhost:8768 (EconomicCalendarBot)
   - Se folosește doar dacă calendar manual e gol
   - Necesită cTrader Desktop + bot activ

3. ~~**ForexFactory scraping**~~ (ELIMINAT)
   - Avea probleme cu Cloudflare protection
   - Chrome driver crashes
   - Rate limiting issues

---

## 🚀 Setup Rapid

### Step 1: Verifică că alertele funcționează

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
python3 news_calendar_monitor.py
```

Ar trebui să vezi:
```
✅ Using events from 'custom_events_january_2026'
✅ Loaded 10 events from manual calendar
🚨 High impact: 9
✅ Telegram alert sent successfully
```

### Step 2: Verifică automation (4x/zi: 8am, 2pm, 8pm, 2am)

```bash
launchctl list | grep newscalendar
```

Ar trebui să vezi:
```
-       0       com.forexgod.newscalendar
```

### Step 3: Verifică logs

```bash
tail -f logs/news_calendar.log
```

---

## 🗓️ Actualizare Lunară (IMPORTANT!)

**La începutul fiecărei luni**, actualizează evenimente pentru luna următoare:

### Opțiunea 1: Folosind scriptul Python (RECOMANDAT)

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
python3 add_monthly_events.py
```

**Pași:**
1. Deschide `add_monthly_events.py`
2. Găsește secțiunea cu evenimente (ex: `JANUARY_2026_EVENTS`)
3. Copiază structura și adaugă evenimente pentru luna următoare
4. Schimbă numele secțiunii (ex: `FEBRUARY_2026_EVENTS`)
5. Actualizează funcția `update_calendar()` să folosească noua secțiune
6. Rulează script: `python3 add_monthly_events.py`

### Opțiunea 2: Manual în JSON

Editează direct `economic_calendar.json`:

```json
{
  "recurring_events": { ... },
  "custom_events_february_2026": [
    {
      "date": "2026-02-06",
      "time": "13:30",
      "currency": "USD",
      "event": "Non-Farm Employment Change",
      "impact": "High"
    }
  ]
}
```

---

## 📅 Evenimente HIGH-Impact (Watchlist)

### 🔴 SUPER CRITICAL (Major Market Movers)
- **NFP (Non-Farm Payrolls)** - Prima Vineri, 13:30 EST
- **FOMC Rate Decision** - 19:00 EST
- **CPI (Inflation)** - Mid-month, 13:30 EST
- **ECB Rate Decision** - 13:15 CET
- **BOE Rate Decision** - 12:00 GMT

### 🟠 HIGH IMPACT
- Retail Sales (US, UK, CAD)
- GDP Reports
- PMI Flash (Manufacturing, Services)
- Unemployment Rate
- ADP Employment
- Average Hourly Earnings

### Unde găsești datele?
1. **ForexFactory.com** - Calendar view (manual copy)
2. **Investing.com** - Economic Calendar
3. **cTrader Desktop** - Economic Calendar widget (dacă rulează)

---

## 🔧 Troubleshooting

### "No events found!"

```bash
# Verifică calendar manual
cat economic_calendar.json | grep "custom_events_$(date +%B_%Y | tr '[:upper:]' '[:lower:]')"

# Dacă e gol, actualizează pentru luna curentă
python3 add_monthly_events.py
```

### "Telegram alert failed"

```bash
# Verifică credentials
cat .env | grep TELEGRAM

# Test manual
python3 -c "
from notification_manager import send_message
send_message('Test from News Calendar', 'HIGH')
"
```

### "cTrader Desktop not available"

- Normal! Folosim calendar manual ca primary source
- cTrader e doar backup (optional)
- Nu trebuie să ruleze cTrader 24/7

---

## 📊 Status Actual

✅ **January 2026**: 34 evenimente (27 HIGH-impact)
- NFP: 09 Jan, 13:30
- FOMC: 29 Jan, 19:00
- CPI: 13 Jan, 13:30
- ECB: 30 Jan, 13:15

✅ **Automation**: Active (4x/zi)

✅ **Telegram**: Functional

⚠️ **Next Update**: ~February 1, 2026

---

## 🎯 Best Practices

1. **Actualizează calendarul la început de lună**
   - Pune reminder în telefon: "Update forex calendar"
   - Durează 5-10 minute

2. **Verifică logs ocazional**
   ```bash
   tail logs/news_calendar.log
   ```

3. **Test după fiecare update**
   ```bash
   python3 news_calendar_monitor.py
   ```

4. **Backup calendar înainte de editare**
   ```bash
   cp economic_calendar.json economic_calendar.json.backup
   ```

---

## 🚨 Important pentru Trading

Sistemul te alertează ÎNAINTE de evenimente HIGH-impact:
- **Evită să intri în trade** cu 30-60 min înainte
- **Verifică stopuri** înainte de NFP/FOMC
- **Reduce size-ul** în zile cu multiple evenimente HIGH
- **Telegram alert = STAY OUT!**

---

## 📞 Support

Dacă sistemul nu trimite alerte:
1. Verifică logs: `tail -f logs/news_calendar.log`
2. Test manual: `python3 news_calendar_monitor.py`
3. Verifică launchd: `launchctl list | grep newscalendar`
4. Reload job: `launchctl unload ~/Library/LaunchAgents/com.forexgod.newscalendar.plist && launchctl load ~/Library/LaunchAgents/com.forexgod.newscalendar.plist`

---

**Last Updated**: January 3, 2026  
**System Version**: V3.0 (ForexFactory removed, manual primary source)
