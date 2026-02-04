# 🤖 TELEGRAM BOT COMMANDS GUIDE
## Interactive Two-Way Communication - ФорексГод

**Sistema Nervoasă Completă:** Control complet al sistemului de trading de pe telefon!

---

## 🚀 QUICK START

### **1. Pornire Bot:**

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Pornește bot în background
nohup python3 start_telegram_bot.py > logs/telegram_bot.log 2>&1 &

# Verifică că rulează
ps aux | grep "start_telegram_bot" | grep -v grep
```

### **2. Test Conexiune:**

Deschide Telegram și trimite:
```
/start
```

Bot-ul ar trebui să răspundă cu mesaj de bun venit.

---

## 📱 COMENZI DISPONIBILE

### 🎯 **ACCOUNT MONITORING**

#### **/status** - Dashboard Complet

**Ce face:**
- Account overview (Balance, Equity, P&L)
- Top 3 poziții deschise (cu profit/loss)
- Performance astăzi (trades, win rate, profit)
- Monitoring setups (READY vs MONITORING)
- High-impact news alert (dacă există)

**Exemplu:**
```
/status
```

**Răspuns:**
```
📊 ACCOUNT STATUS

━━━━━━━━━━━━━━━━━━━━━━━━
💰 Account Overview:
Balance: $3,582.20
Equity: $5,889.50
P&L: +$2,307.30 (+64.4%) 🟢

📊 Margin:
Used: $1,245.00 (34.8%)
Free: $2,337.20

━━━━━━━━━━━━━━━━━━━━━━━━
🔥 Open Positions: 11

💚 Winning: 7
❤️ Losing: 4

Top Positions:
1. EURUSD SELL | +$145.20 💚
2. GBPUSD BUY | +$89.00 💚
3. USDJPY SELL | -$32.50 ❤️

━━━━━━━━━━━━━━━━━━━━━━━━
📈 Today's Performance:
Trades: 3 | Wins: 2 | P&L: +$45.00 🟢

━━━━━━━━━━━━━━━━━━━━━━━━
📋 Monitoring Setups: 5
🟢 Ready to execute: 2
⏳ Monitoring: 3

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 2 High-Impact News in next 24h
Use /news for details

━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Updated: 14:35:20
✨ Strategy by ФорексГод ✨
```

---

#### **/balance** - Snapshot Rapid

**Ce face:**
- Balance & Equity
- Floating P&L
- Margin (Used/Free/Level)
- Status margin (Healthy/Moderate/Warning)

**Exemplu:**
```
/balance
```

**Răspuns:**
```
💰 ACCOUNT BALANCE

━━━━━━━━━━━━━━━━━━━━━━━━
📊 Current Status:

Balance: $3,582.20
Equity: $5,889.50
Floating P&L: +$2,307.30 🟢
P&L %: +64.4%

━━━━━━━━━━━━━━━━━━━━━━━━
📈 Margin Info:

Used: $1,245.00
Free: $2,337.20
Level: 473% 🟢 Healthy
Usage: 34.8% of balance
```

---

#### **/positions** - Lista Detaliată Poziții

**Ce face:**
- Toate pozițiile deschise (sortate după P&L)
- Entry, Current price, P&L în $ și pips
- Volume (lots)
- Status: Break-even protected 🛡️ sau Active 🕒

**Exemplu:**
```
/positions
```

**Răspuns:**
```
📊 OPEN POSITIONS (11)

━━━━━━━━━━━━━━━━━━━━━━━━

1. EURUSD 📉 SELL
├─ Entry: 1.12500
├─ Current: 1.12350
├─ P&L: +$145.20 (+15.0 pips) 💚
├─ Volume: 0.10 lots
└─ Status: 🛡️ BE

2. GBPUSD 📈 BUY
├─ Entry: 1.28000
├─ Current: 1.28050
├─ P&L: +$89.00 (+5.0 pips) 💚
├─ Volume: 0.10 lots
└─ Status: Active 🕒

3. USDJPY 📉 SELL
├─ Entry: 145.500
├─ Current: 145.700
├─ P&L: -$32.50 (-20.0 pips) ❤️
├─ Volume: 0.10 lots
└─ Status: Active 🕒

[...8 more positions...]

━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Updated: 14:35:20
✨ Strategy by ФорексГод ✨
```

---

#### **/summary** - Raport Săptămânal

**Ce face:**
- Performance ultimele 7 zile (din SQLite)
- Total profit, win rate, average
- Best/worst trade
- Daily breakdown (profit pe fiecare zi)
- Top 3 performing pairs

**Exemplu:**
```
/summary
```

**Răspuns:**
```
💰 WEEKLY PERFORMANCE REPORT

━━━━━━━━━━━━━━━━━━━━━━━━
📊 Overall Stats (Last 7 Days):

Total Profit: +$340.50 🟢
Total Trades: 25
Wins: 18 ✅ | Losses: 7 ❌
Win Rate: 72.0%

Average: $13.62
Best Trade: $85.00 💎
Worst Trade: -$45.00

━━━━━━━━━━━━━━━━━━━━━━━━
📅 Daily Breakdown:

Mon: 3 trades | +$45.00 🟢
Tue: 5 trades | +$120.00 🟢
Wed: 4 trades | +$175.50 🟢
Thu: 6 trades | +$25.00 🟢
Fri: 4 trades | -$20.00 🔴
Sat: 2 trades | -$10.00 🔴
Sun: 1 trades | +$5.00 🟢

━━━━━━━━━━━━━━━━━━━━━━━━
🏆 Top Performing Pairs:

EURUSD: 8 trades | +$185.00 🟢
GBPUSD: 5 trades | +$95.00 🟢
USDJPY: 4 trades | +$60.00 🟢

━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Generated: 2026-02-03 14:35
✨ Strategy by ФорексГод ✨
```

---

### 🎯 **TRADING STATUS**

#### **/setups** - Monitoring Setups

**Ce face:**
- Lista setup-uri monitorizate
- READY (gata de executat) vs MONITORING (așteptând confirmare)
- Entry price, direction, R:R

**Exemplu:**
```
/setups
```

**Răspuns:**
```
📋 MONITORING SETUPS (5)

━━━━━━━━━━━━━━━━━━━━━━━━

🟢 READY TO EXECUTE (2):

• USDCHF 📉 SHORT
  Entry: 0.87500 | R:R 1:5.2

• AUDUSD 📈 LONG
  Entry: 0.65200 | R:R 1:4.8

⏳ MONITORING (3):

• USDCAD 📉 SHORT
  Waiting for confirmation...

• NZDUSD 📈 LONG
  Waiting for confirmation...

• EURJPY 📉 SHORT
  Waiting for confirmation...

━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Updated: 14:35:20
✨ Strategy by ФорексГод ✨
```

---

#### **/news** - High-Impact News

**Ce face:**
- Evenimente high-impact următoarele 48h
- Currency affected
- Time & event name
- Trading recommendations

**Exemplu:**
```
/news
```

**Răspuns:**
```
📰 HIGH-IMPACT NEWS (Next 48h)

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Upcoming Events:

🔴 USD @ Wed 14:30
   FOMC Interest Rate Decision

🔴 EUR @ Wed 12:45
   ECB Press Conference

🔴 GBP @ Thu 09:00
   GDP Quarterly Growth

🔴 USD @ Fri 13:30
   Non-Farm Payrolls (NFP)

━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ Affected Currencies:
USD, EUR, GBP

💡 Recommendation:
Avoid trading these pairs before news release.
Consider closing positions 30min before.

━━━━━━━━━━━━━━━━━━━━━━━━
⏰ Updated: 14:35:20
✨ Strategy by ФорексГод ✨
```

---

### ❓ **HELP**

#### **/help** - Lista Comenzi

**Ce face:**
- Afișează toate comenzile disponibile
- Descriere scurtă pentru fiecare
- Tips de utilizare

**Exemplu:**
```
/help
```

---

#### **/start** - Bun Venit

**Ce face:**
- Mesaj de bun venit
- Overview funcționalități
- Lista comenzi principale

---

## 🔧 INTEGRARE ÎN SISTEM

### **Adaugă la Service Watchdog:**

Modifică `service_watchdog.py` pentru a monitoriza bot-ul:

```python
# În CRITICAL_SERVICES dict
'telegram_bot': {
    'process_name': 'start_telegram_bot.py',
    'start_command': 'nohup python3 start_telegram_bot.py > logs/telegram_bot.log 2>&1 &',
    'priority': 'MEDIUM',
    'name': 'Telegram Bot Handler',
    'description': 'Interactive commands & reporting'
}
```

---

### **Adaugă la Startup Script:**

În `start_all_monitors.sh` sau `start_system.sh`:

```bash
# Start Telegram Bot Handler
echo "🤖 Starting Telegram Bot Handler..."
nohup python3 start_telegram_bot.py > logs/telegram_bot.log 2>&1 &
sleep 2
```

---

## 🎯 DAILY PERFORMANCE REPORT (AUTOMAT)

### **Funcție Nouă în telegram_notifier.py:**

```python
# Trimite raport zilnic automat
notifier = TelegramNotifier()
notifier.send_daily_performance_report(include_news=True)
```

### **Setup Cron pentru Raport Zilnic:**

Adaugă în crontab (`crontab -e`):

```bash
# Daily performance report la 00:05 (după close piață)
5 0 * * * cd /path/to/project && python3 -c "from telegram_notifier import TelegramNotifier; TelegramNotifier().send_daily_performance_report()"
```

Sau folosește launchd (macOS) - creeză `com.forexgod.dailyreport.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.forexgod.dailyreport</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/python3</string>
        <string>-c</string>
        <string>from telegram_notifier import TelegramNotifier; TelegramNotifier().send_daily_performance_report()</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo</string>
    
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>0</integer>
        <key>Minute</key>
        <integer>5</integer>
    </dict>
    
    <key>StandardOutPath</key>
    <string>/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/logs/daily_report.log</string>
    
    <key>StandardErrorPath</key>
    <string>/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/logs/daily_report_error.log</string>
</dict>
</plist>
```

Load cu:
```bash
launchctl load ~/Library/LaunchAgents/com.forexgod.dailyreport.plist
```

---

## 📊 RAPORT ZILNIC MANUAL

### **Trimite On-Demand:**

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

python3 -c "from telegram_notifier import TelegramNotifier; TelegramNotifier().send_daily_performance_report(include_news=True)"
```

### **Sau prin script Python:**

```python
from telegram_notifier import TelegramNotifier

# Initialize
notifier = TelegramNotifier()

# Send daily report
notifier.send_daily_performance_report(include_news=True)
```

---

## 🔒 SECURITATE

### **Chat ID Protection:**

Bot-ul răspunde DOAR la comenzi din:
- `TELEGRAM_CHAT_ID` specificat în `.env`

Orice alt user care trimite comenzi va fi ignorat.

### **Verificare:**

```python
# În telegram_bot_handler.py, toate comenzile verifică implicit:
if update.message.chat_id != int(self.chat_id):
    return  # Ignore unauthorized users
```

---

## 🧪 TESTING

### **1. Test Conexiune Bot:**

```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

python3 -c "from telegram_notifier import TelegramNotifier; bot = TelegramNotifier(); bot.test_connection()"
```

### **2. Test Comenzi Individuale:**

```python
from telegram_bot_handler import TradingBotHandler

bot = TradingBotHandler()

# Test status report
print(bot._generate_status_report())

# Test weekly summary
print(bot._generate_weekly_summary())

# Test positions
print(bot._generate_positions_report())
```

### **3. Test Daily Report:**

```bash
python3 -c "from telegram_notifier import TelegramNotifier; TelegramNotifier().send_daily_performance_report()"
```

---

## 📱 UTILIZARE ZILNICĂ

### **Morning Routine:**

1. Deschide Telegram
2. Trimite `/status` - Vezi overview rapid
3. Trimite `/news` - Verifică high-impact events
4. Trimite `/setups` - Vezi ce setup-uri sunt READY

### **During Trading:**

- `/positions` - Check P&L live
- `/balance` - Verify margin level
- `/status` - Quick refresh

### **Evening Review:**

- `/summary` - Analizează săptămâna
- Raportul automat (00:05) - Review zilnic

---

## 🚀 BENEFITS

✅ **Control Total:** Monitorizezi contul de oriunde  
✅ **Real-Time:** Date actualizate la fiecare 30s  
✅ **News Integration:** Alerte automate high-impact  
✅ **Performance Tracking:** Weekly analytics din SQLite  
✅ **Break-Even Status:** Vezi care poziții sunt protejate  
✅ **Mobile-Friendly:** Formatare perfectă pe telefon  
✅ **Non-Blocking:** Bot rulează în background (nu blochează trading)  

---

## 🛠️ TROUBLESHOOTING

### **Bot nu răspunde:**

```bash
# Verifică dacă rulează
ps aux | grep "start_telegram_bot" | grep -v grep

# Check logs
tail -50 logs/telegram_bot.log

# Restart
pkill -f "start_telegram_bot.py"
sleep 2
nohup python3 start_telegram_bot.py > logs/telegram_bot.log 2>&1 &
```

### **Error: Missing python-telegram-bot:**

```bash
pip install python-telegram-bot==20.7
```

### **Error: Database locked:**

SQLite este accesat simultan - normal. Bot-ul folosește `connect()` cu timeout.

---

## 📋 QUICK REFERENCE

**Start Bot:**
```bash
nohup python3 start_telegram_bot.py > logs/telegram_bot.log 2>&1 &
```

**Stop Bot:**
```bash
pkill -f "start_telegram_bot.py"
```

**Check Status:**
```bash
ps aux | grep "start_telegram_bot" | grep -v grep
```

**View Logs:**
```bash
tail -f logs/telegram_bot.log
```

**Test Commands:**
```
/status
/summary
/positions
/balance
/setups
/news
/help
```

---

**🎯 GATA DE VPS!** Bot-ul este complet asincron și nu blochează execuția tranzacțiilor.

**✨ Strategy by ФорексГод ✨**  
**🧠 Glitch in Matrix Trading System**  
**💎 + AI Validation + Interactive Control**
