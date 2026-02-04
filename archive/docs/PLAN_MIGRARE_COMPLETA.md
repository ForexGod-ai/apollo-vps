# 🎯 PLAN COMPLET - Migrare 100% la Folderul Corect

## 📋 PROBLEMA ACTUALĂ

Sistemul are componente care pot rula din 2 foldere diferite:
- ❌ VECHI: `/Users/forexgod/Desktop/trading-ai-agent apollo/`
- ✅ NOU: `/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/`

**RISC:** Confuzie, procese duplicate, erori de sincronizare

---

## 🔍 AUDIT COMPLET - Ce Trebuie Verificat

### 1. **Procese Python Active**
```bash
# Verifică TOATE procesele Python și folderul lor
ps aux | grep python3 | grep -v grep
lsof -c python3 | grep "/Users/forexgod"
```

### 2. **LaunchAgents / Cron Jobs**
```bash
# LaunchAgents (macOS automation)
ls -la ~/Library/LaunchAgents/*.plist
cat ~/Library/LaunchAgents/com.forexgod.morningscan.plist

# Cron jobs
crontab -l
```

### 3. **Scripts Shell**
- `run_morning_scan.sh`
- `start_all_monitors.sh`
- `setup_morning_cron.sh`
- Orice script care are path hardcodat

### 4. **Configurări Python**
- Import paths în `.env`
- `sys.path` în scripturi
- Working directory în subprocess calls

### 5. **Fișiere de State**
- `.last_trade_check.json`
- `.seen_positions.json`
- `monitoring_setups.json`
- `trade_history.json`

---

## ✅ PLAN DE ACȚIUNE (Când Ajungi la Birou)

### FAZA 1: AUDIT (10 min)

**Script automat de audit:**

```bash
#!/bin/bash
# audit_system.sh - Verifică tot ce rulează și de unde

echo "🔍 SYSTEM AUDIT - ForexGod Trading System"
echo "========================================"
echo ""

echo "1️⃣ PYTHON PROCESSES:"
ps aux | grep python3 | grep -E "(monitor|scanner|trading)" | grep -v grep
echo ""

echo "2️⃣ WORKING DIRECTORIES:"
lsof -c python3 2>/dev/null | grep cwd | grep -v "/Library"
echo ""

echo "3️⃣ LAUNCHAGENTS:"
ls -la ~/Library/LaunchAgents/*.forexgod* 2>/dev/null || echo "None found"
echo ""

echo "4️⃣ CRON JOBS:"
crontab -l 2>/dev/null | grep -v "^#" || echo "None found"
echo ""

echo "5️⃣ FOLDERS EXIST:"
[ -d "/Users/forexgod/Desktop/trading-ai-agent apollo" ] && echo "❌ OLD folder exists" || echo "✅ Old folder removed"
[ -d "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo" ] && echo "✅ NEW folder exists" || echo "❌ NEW folder missing!"
echo ""

echo "6️⃣ RECENT LOG FILES:"
find ~/Desktop -name "*.log" -type f -mmin -60 2>/dev/null | head -10
```

---

### FAZA 2: OPRIRE COMPLETĂ (2 min)

```bash
#!/bin/bash
# stop_all.sh - Oprește TOTUL din ambele foldere

echo "⏹️ Stopping ALL ForexGod processes..."

# Kill toate procesele Python
pkill -9 python3

# Kill procese specifice
pkill -9 -f "daily_scanner"
pkill -9 -f "monitor"
pkill -9 -f "morning_scan"

# Descarcă LaunchAgents
launchctl unload ~/Library/LaunchAgents/com.forexgod.* 2>/dev/null

echo "✅ All processes stopped"
sleep 2
```

---

### FAZA 3: CURĂȚARE FOLDER VECHI (5 min)

```bash
#!/bin/bash
# clean_old_folder.sh

OLD="/Users/forexgod/Desktop/trading-ai-agent apollo"
BACKUP="/Users/forexgod/Desktop/_BACKUP_old_folder_$(date +%Y%m%d)"

if [ -d "$OLD" ]; then
    echo "📦 Backing up old folder..."
    cp -r "$OLD" "$BACKUP"
    
    echo "🗑️ Removing old folder..."
    rm -rf "$OLD"
    
    echo "✅ Old folder removed, backup at: $BACKUP"
else
    echo "✅ Old folder already removed"
fi
```

---

### FAZA 4: UPDATE TOATE PATH-URILE (10 min)

**Fișiere care trebuie actualizate:**

#### A. LaunchAgent - `com.forexgod.morningscan.plist`
```xml
<key>ProgramArguments</key>
<array>
    <string>/bin/bash</string>
    <string>/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/run_morning_scan.sh</string>
</array>

<key>WorkingDirectory</key>
<string>/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo</string>
```

#### B. Toate Shell Scripts
- `run_morning_scan.sh` - update `cd` path
- `start_all_monitors.sh` - update working dir
- `setup_morning_cron.sh` - update PROJECT_DIR

#### C. Python Scripts cu subprocess
Caută în toate `.py`:
```python
# ❌ GREȘIT:
subprocess.Popen(['python3', 'script.py'], cwd='/Users/forexgod/Desktop/trading-ai-agent apollo')

# ✅ CORECT:
subprocess.Popen(['python3', 'script.py'], cwd='/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo')
```

---

### FAZA 5: VALIDARE (5 min)

```bash
#!/bin/bash
# validate_setup.sh - Verifică că totul e corect

CORRECT_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

cd "$CORRECT_DIR"

echo "🧪 VALIDATION TESTS"
echo "==================="
echo ""

# Test 1: Folder corect
echo "1. Working directory check:"
if [ "$PWD" == "$CORRECT_DIR" ]; then
    echo "   ✅ In correct folder"
else
    echo "   ❌ Wrong folder: $PWD"
fi

# Test 2: Fișiere critice există
echo ""
echo "2. Critical files exist:"
for file in daily_scanner.py trade_monitor.py position_monitor.py; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ $file MISSING!"
    fi
done

# Test 3: Python imports funcționează
echo ""
echo "3. Python imports test:"
python3 -c "import sys; sys.path.insert(0, '.'); from daily_scanner import DailyScanner; print('   ✅ Imports OK')" 2>&1

# Test 4: cBot connection
echo ""
echo "4. cBot connection test:"
python3 -c "from ctrader_cbot_client import CTraderCBotClient; c = CTraderCBotClient(); print('   ✅ cBot OK' if c.is_available() else '   ❌ cBot not running')"

# Test 5: LaunchAgent correct path
echo ""
echo "5. LaunchAgent configuration:"
if grep -q "Glitch in Matrix" ~/Library/LaunchAgents/com.forexgod.morningscan.plist 2>/dev/null; then
    echo "   ✅ LaunchAgent has correct path"
else
    echo "   ⚠️  LaunchAgent needs update or doesn't exist"
fi

echo ""
echo "======================================"
```

---

### FAZA 6: PORNIRE SISTEM (5 min)

```bash
#!/bin/bash
# start_production.sh - Pornește TOTUL din folderul corect

CORRECT_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

cd "$CORRECT_DIR"

echo "🚀 Starting ForexGod Production System"
echo "======================================"
echo ""

# 1. Verifică cBot
echo "1. Checking cBot connection..."
python3 -c "from ctrader_cbot_client import CTraderCBotClient; c = CTraderCBotClient(); exit(0 if c.is_available() else 1)"
if [ $? -eq 0 ]; then
    echo "   ✅ cBot running"
else
    echo "   ❌ cBot NOT running - start it first!"
    exit 1
fi

# 2. Pornește monitoare
echo ""
echo "2. Starting monitors..."
bash start_all_monitors.sh

# 3. Încarcă LaunchAgent
echo ""
echo "3. Loading LaunchAgent..."
launchctl load ~/Library/LaunchAgents/com.forexgod.morningscan.plist 2>/dev/null
echo "   ✅ Morning scan scheduled for 08:00"

# 4. Final check
echo ""
echo "4. Final status check:"
sleep 3
bash check_status.sh

echo ""
echo "======================================"
echo "✅ PRODUCTION SYSTEM STARTED!"
echo ""
echo "📊 Monitor logs:"
echo "   tail -f logs/trade_monitor.log"
echo ""
```

---

## 🛡️ VERIFICĂRI AUTOMATE (Preventie)

**Script care verifică ZILNIC că totul rulează din folderul corect:**

```bash
#!/bin/bash
# daily_health_check.sh - Rulează automat la 00:00

CORRECT_DIR="/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"

# Verifică procese
bad_processes=$(ps aux | grep python3 | grep "trading-ai-agent apollo" | grep -v "Glitch in Matrix" | grep -v grep | wc -l)

if [ "$bad_processes" -gt 0 ]; then
    # ALERTA! Procese din folder greșit
    curl -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
         -d "chat_id=$TELEGRAM_CHAT_ID" \
         -d "text=⚠️ WARNING: $bad_processes processes running from WRONG folder!"
    
    # Oprește-le automat
    pkill -9 -f "trading-ai-agent apollo" | grep -v "Glitch in Matrix"
fi
```

---

## 📝 CHECKLIST FINAL

Când termini migrarea, bifează:

- [ ] Audit complet rulat și verificat
- [ ] Toate procesele oprite
- [ ] Folder vechi șters/redenumit
- [ ] LaunchAgent actualizat cu path nou
- [ ] Toate shell scripts actualizate
- [ ] Toate Python scripts verificate pentru hardcoded paths
- [ ] Teste de validare PASSED
- [ ] Monitoare pornite și rulează DIN FOLDERUL CORECT
- [ ] Daily scanner testat
- [ ] Telegram notifications funcționează
- [ ] Health check automat configurat

---

## 🎯 REZULTAT FINAL

După migrare vei avea:

✅ **UN SINGUR FOLDER ACTIV:** `Glitch in Matrix/trading-ai-agent apollo`
✅ **ZERO confuzii** - folderul vechi NU MAI EXISTĂ
✅ **TOATE procesele** confirmă că rulează din folderul corect
✅ **MONITORING automat** pentru procese rogue
✅ **BACKUP complet** înainte de ștergere

---

**Timp estimat total:** 30-40 minute
**Risc:** Scăzut (cu backup)
**Beneficiu:** Sistem 100% curat și predictibil

**Când ajungi la birou, începem cu `audit_system.sh` și vedem exact ce trebuie făcut! 🚀**
