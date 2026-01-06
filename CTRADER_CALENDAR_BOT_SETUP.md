# 🤖 cTrader Economic Calendar Bot - Setup Complet

## 🎯 Ce Face Bot-ul?

Extrage evenimente economice din cTrader Desktop și le expune pe **localhost:8768** pentru Python să le citească automat.

**Avantaje:**
- ✅ Date LIVE direct din cTrader (fără scraping)
- ✅ Auto-update când cTrader Desktop rulează
- ✅ Nu necesită API keys sau rate limits
- ✅ Gratuit - folosește cTrader Desktop gratuit

---

## 📋 Instalare Rapidă

### Step 1: Copiază Bot-ul în cTrader

```bash
# Deschide folderul cTrader Algos
open ~/Documents/cAlgo/Sources/Robots

# Sau calea alternativă:
open ~/Library/Application\ Support/cTrader/Algo/Sources/Robots
```

**Copiază fișierul:**
```bash
cp "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/EconomicCalendarBot.cs" \
   ~/Documents/cAlgo/Sources/Robots/
```

### Step 2: Deschide cTrader Desktop

1. Pornește **cTrader Desktop** (nu cTrader Web)
2. Loghează-te cu contul tău IC Markets (demo sau live - nu contează)
3. Du-te la **Automate** tab (sus în meniu)

### Step 3: Compilează Bot-ul

1. În lista din stânga (Robots), găsește **EconomicCalendarBot**
2. Click pe el → se deschide codul
3. Click **Build** (butonul cu ciocan) sau apasă `F6`
4. Verifică în panoul de jos: `Build succeeded` ✅

### Step 4: Pornește Bot-ul

1. În lista Robots, găsește **EconomicCalendarBot** (acum compilat)
2. Click dreapta → **Add to chart**
3. Alege orice simbol (ex: EURUSD) și timeframe (ex: H1) - nu contează
4. În panoul **Instance**, verifică:
   - ✅ Bot rulează (buton verde)
   - ✅ Log arată: `✅ HTTP server started successfully on http://localhost:8768/`

---

## 🧪 Testare

### Test 1: Verifică server-ul

```bash
# În terminal Mac:
curl http://localhost:8768/calendar
```

**Output așteptat:**
```json
{
  "status": "success",
  "events": [
    {
      "time": "2026-01-09T13:30:00Z",
      "currency": "USD",
      "impact": "High",
      "event": "Non-Farm Payrolls",
      "actual": "",
      "forecast": "180K",
      "previous": "227K"
    }
  ]
}
```

### Test 2: Verifică Python connection

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
python3 -c "
from news_calendar_monitor import NewsCalendarMonitor
monitor = NewsCalendarMonitor()
events = monitor.fetch_ctrader_calendar(days_ahead=7)
print(f'✅ Got {len(events)} events from cTrader!')
"
```

### Test 3: Verifică alerte Telegram

```bash
python3 news_calendar_monitor.py
```

Ar trebui să vezi:
```
📅 Fetching calendar from cTrader Desktop...
✅ Loaded X events from cTrader calendar
✅ Telegram alert sent successfully
```

---

## 🔧 Troubleshooting

### ❌ "Cannot connect to cTrader Desktop on localhost:8768"

**Cauze:**
1. cTrader Desktop nu rulează
2. Bot-ul nu e pornit în cTrader
3. Port-ul 8768 e ocupat de alt program

**Soluții:**
```bash
# Check dacă port-ul e ocupat
lsof -i :8768

# Dacă e ocupat de alt proces, schimbă port-ul în bot (ex: 8769)
# Și actualizează în news_calendar_monitor.py linia cu localhost:8768
```

### ❌ "Build failed" în cTrader

**Cauză**: cTrader Desktop version incompatibilă

**Soluție**: 
1. Verifică versiunea cTrader: Help → About
2. Dacă e foarte veche, update cTrader Desktop
3. Sau simplifică bot-ul (șterge features avansate)

### ❌ Bot pornește dar Python nu primește date

**Verifică:**
```bash
# 1. Server-ul răspunde?
curl -v http://localhost:8768/calendar

# 2. cTrader are evenimente în calendar?
# Deschide cTrader → Tools → Economic Calendar
# Ar trebui să vezi NFP, CPI, FOMC, etc.

# 3. Bot-ul logează ceva?
# Verifică în cTrader Instance panel → Log tab
```

---

## 🚀 Automation Setup

### Opțiune A: cTrader rulează NON-STOP (RECOMANDAT pentru VPS)

Dacă ai VPS sau Mac-ul rulează 24/7:

1. **Setează cTrader să pornească automat la startup**
2. **Setează bot-ul să pornească automat în cTrader:**
   - Click dreapta pe bot → **Properties**
   - Bifează: **Start automatically on login**
3. **Python va avea date LIVE mereu**

### Opțiune B: cTrader rulează doar când tranzacționezi (MAC local)

Dacă folosești Mac-ul local și închizi cTrader:

1. **Primary source**: `economic_calendar.json` (actualizat manual lunar)
2. **Backup source**: cTrader (când rulează)
3. **Python folosește calendar manual când cTrader e închis**

```bash
# La început de lună, actualizează manual:
python3 add_monthly_events.py
```

---

## 📊 Cum Funcționează Fluxul

```
┌─────────────────────┐
│  cTrader Desktop    │ ← Date LIVE de la IC Markets
│  (EconomicCalendar  │
│   widget built-in)  │
└──────────┬──────────┘
           │
           │ HTTP :8768
           ▼
┌─────────────────────┐
│ EconomicCalendarBot │ ← Expune date pe localhost
│ (C# cBot în cTrader)│
└──────────┬──────────┘
           │
           │ GET /calendar
           ▼
┌─────────────────────┐
│ news_calendar_      │ ← Fetch evenimente + trimite Telegram
│ monitor.py          │
└─────────────────────┘
           │
           ▼
┌─────────────────────┐
│ Telegram Alerts     │ ← Primești notificări HIGH-impact
│ (4x/zi automat)     │
└─────────────────────┘
```

---

## 🎯 Best Practice

### Pentru VPS (Trading 24/7):
✅ Instalează cTrader Desktop pe VPS  
✅ Pornește EconomicCalendarBot non-stop  
✅ Python preia date automat de la cTrader  
✅ Zero manual work!

### Pentru Mac Local (Trading part-time):
✅ cTrader Desktop + bot când tranzacționezi  
✅ Calendar manual (add_monthly_events.py) pentru backup  
✅ Python folosește ambele surse (fallback automat)  
✅ ~5 min/lună pentru update manual

---

## 📅 Verificare Status

```bash
# Check dacă bot-ul rulează
curl http://localhost:8768/calendar 2>/dev/null && echo "✅ cTrader bot ACTIVE" || echo "❌ cTrader bot OFFLINE"

# Verifică toate surse
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
python3 -c "
from news_calendar_monitor import NewsCalendarMonitor
import json

monitor = NewsCalendarMonitor()

# Test 1: Manual calendar
print('📖 Testing manual calendar...')
manual = monitor.fetch_manual_calendar(7)
print(f'   Manual: {len(manual)} events')

# Test 2: cTrader
print('📡 Testing cTrader API...')
ctrader = monitor.fetch_ctrader_calendar(7)
print(f'   cTrader: {len(ctrader)} events')

print()
if len(manual) > 0:
    print('✅ READY: Manual calendar has events')
elif len(ctrader) > 0:
    print('✅ READY: cTrader API working')
else:
    print('❌ WARNING: No data source available!')
"
```

---

## 🔄 Weekly Auto-Update (Bonus)

Dacă vrei să exporți automat evenimente din cTrader în JSON:

```bash
# Rulează o dată pe săptămână (duminică seara)
curl http://localhost:8768/calendar > /tmp/ctrader_calendar.json

# Merge automat în economic_calendar.json
python3 -c "
import json
from datetime import datetime

# Load cTrader data
with open('/tmp/ctrader_calendar.json') as f:
    data = json.load(f)

# Convert to our format
events = []
for e in data.get('events', []):
    events.append({
        'date': e['time'][:10],
        'time': e['time'][11:16],
        'currency': e['currency'],
        'event': e['event'],
        'impact': e['impact'],
        'forecast': e.get('forecast', ''),
        'previous': e.get('previous', '')
    })

# Save
month = datetime.now().strftime('%B_%Y').lower()
with open('economic_calendar.json') as f:
    cal = json.load(f)

cal[f'custom_events_{month}'] = events

with open('economic_calendar.json', 'w') as f:
    json.dump(cal, f, indent=2)

print(f'✅ Updated calendar with {len(events)} events from cTrader')
"
```

---

**Last Updated**: January 3, 2026  
**cTrader Version**: 5.0+ compatible  
**Status**: Bot code ready, needs installation in cTrader Desktop
