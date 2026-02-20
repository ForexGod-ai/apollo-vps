# 🎯 GLITCH IN MATRIX V2.0 - DEPLOYMENT GUIDE

## ✨ Comandir ФорексГод ✨

**Data:** 16 Februarie 2026  
**Status:** ✅ SYSTEM OPERATIONAL

---

## 📊 SYSTEM OVERVIEW

### **Official 15 Pairs**
```
EURUSD   GBPUSD   USDJPY   USDCHF   AUDUSD
USDCAD   NZDUSD   EURGBP   EURJPY   GBPJPY
AUDJPY   CHFJPY   EURCHF   GBPCHF   BTCUSD
```

### **Current Status (from latest audit)**
- ✅ **5/15 Active** (EURUSD, USDCHF, USDCAD, GBPJPY, BTCUSD)
- ⚪ **10/15 Idle** (Available for new setups)
- ✅ **0 Risk Issues**
- ✅ **0 Unauthorized Pairs**

---

## 🚀 NEW LAUNCHER V2.0

### **File:** `start_execution_v2.py`

### **Key Features:**

#### 1. **Absolute Path Binding** 🔗
```python
ROOT_PATH = Path("/Users/forexgod/GlitchMatrix")
SIGNALS_FILE = ROOT_PATH / "signals.json"
```

**No more relative paths!** Both Python and cTrader now use:
```
/Users/forexgod/GlitchMatrix/signals.json
```

#### 2. **Sequential Startup** 🎯
```
STEP 1: Cleanup Old Processes (pkill -9 -f monitor)
STEP 2: Clear signals.json (write [])
STEP 3: Verify 15 Pairs Status
STEP 4: Launch Monitoring Layer (CRITICAL)
STEP 5: Launch Position Monitor (optional)
STEP 6: Launch Watchdog Guardian (optional)
```

#### 3. **BTC Volume Fix** 💉
In `ctrader_executor.py`:
```python
# BTC_VOLUME_FIX: Inject raw units for crypto
if symbol in ['BTCUSD', 'ETHUSD', 'XRPUSD', 'LTCUSD']:
    if lot_size < 1.0:
        raw_units = int(lot_size * 100000)  # 0.01 lots = 1000 units
        if raw_units < 100:
            raw_units = 100
        signal["RawUnits"] = raw_units
```

**Result:** cTrader receives both `lot_size` AND `RawUnits` to prevent rounding to 0.

#### 4. **Visual Confirmation** ✅
```
✅ [OK] Monitor Ready: EURUSD
✅ [OK] Monitor Ready: USDCHF
✅ [OK] Monitor Ready: USDCAD
✅ [OK] Monitor Ready: GBPJPY
✅ [OK] Monitor Ready: BTCUSD
⚪ [IDLE] No Active Setup: GBPUSD
⚪ [IDLE] No Active Setup: USDJPY
... (10 more idle pairs)
```

---

## 🎮 USAGE

### **Start Monitoring:**
```bash
cd "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo"
./start_execution_v2.py
```

**Or:**
```bash
.venv/bin/python start_execution_v2.py
```

### **Stop Monitoring:**
```bash
./stop_execution.py
```

### **Run Audit:**
```bash
./matrix_audit.py
```

---

## 🔧 CTRADER SETUP (CRITICAL!)

### **Step 1: Rebuild cBot**
1. Open cTrader → Automate
2. Select `PythonSignalExecutorV31`
3. Press **F5** (Build)
4. Wait for "Build successful"

### **Step 2: Update Parameter**
1. Go to Instances tab
2. Click Settings on PythonSignalExecutorV31
3. Set **Signal File Path** to:
   ```
   /Users/forexgod/GlitchMatrix/signals.json
   ```
4. Click **Save**

### **Step 3: Restart cBot**
1. Click **STOP** (red button)
2. Wait 3 seconds
3. Click **START** (green button)

### **Step 4: Verify MATRIX LINK**
Check cTrader log for:
```
🔗 MATRIX LINK: Citesc semnale din calea absolută -> /Users/forexgod/GlitchMatrix/signals.json
```

---

## 📊 VERIFICATION CHECKLIST

### **Python Side:**
```bash
# Check MATRIX LINK in Python log
grep "MATRIX LINK" setup_monitor.log

# Expected output:
🔗 MATRIX LINK: Scriu semnale în -> /Users/forexgod/GlitchMatrix/signals.json
```

### **cTrader Side:**
- [ ] cBot parameter shows: `/Users/forexgod/GlitchMatrix/signals.json`
- [ ] cBot log shows: `🔗 MATRIX LINK: Citesc semnale din...`
- [ ] Both paths match **EXACTLY**

### **Signal Flow Test:**
```bash
# Create test signal
cat > /Users/forexgod/GlitchMatrix/signals.json << 'EOF'
{
  "SignalId": "TEST_PATH_SYNC",
  "Symbol": "EURUSD",
  "Direction": "buy",
  "EntryPrice": 1.10000,
  "StopLoss": 1.09500,
  "TakeProfit": 1.11000
}
EOF

# Wait 15 seconds
sleep 15

# Check if cBot consumed it
cat /Users/forexgod/GlitchMatrix/signals.json
# Should be [] or {} (cleared by cBot)

# Check processed signals
tail ~/GlitchMatrix/processed_signals.txt
# Should contain: TEST_PATH_SYNC
```

---

## 🎯 MONITORING STATUS

### **Active Setups (5/15):**

| Pair | Direction | Entry | Status | Age |
|------|-----------|-------|--------|-----|
| EURUSD | SELL | 1.20393 | ENTRY FILLED | 3.6h |
| USDCHF | SELL | 0.77507 | ENTRY FILLED | 3.6h |
| USDCAD | BUY | 1.34821 | ENTRY FILLED | 3.6h |
| GBPJPY | SELL | 214.142 | ENTRY FILLED | 3.6h |
| BTCUSD | SELL | 78,563 | ENTRY FILLED | 3.6h |

### **Idle Pairs (10/15):**
```
GBPUSD  USDJPY  AUDUSD  NZDUSD  EURGBP
EURJPY  AUDJPY  CHFJPY  EURCHF  GBPCHF
```

**Action:** Run `daily_scanner.py` to find new setups for idle pairs.

---

## 🐛 TROUBLESHOOTING

### **Problem: cBot not executing**
**Check:**
1. Path mismatch: `grep "MATRIX LINK" setup_monitor.log` vs cTrader parameter
2. cBot not running: Check Instances tab
3. Old binary: Rebuild cBot (F5)

### **Problem: "Invalid volume: 0" for BTCUSD**
**Solution:** BTC Volume Fix is now active!
- Check signal JSON for `RawUnits` field
- If missing, rebuild Python executor

### **Problem: Monitors not starting**
**Check:**
1. Virtual environment: `.venv/bin/python` exists
2. Old processes blocking: Run `./stop_execution.py` first
3. Log files: Check `setup_monitor.log` for errors

---

## 📋 DAILY WORKFLOW

### **Morning (8:00 AM):**
```bash
# 1. Check system status
./matrix_audit.py

# 2. If idle pairs > 5, scan for new setups
./daily_scanner.py

# 3. Start monitoring
./start_execution_v2.py
```

### **During Day (Every 4H):**
```bash
# Check active monitors
tail -f setup_monitor.log

# Check positions
tail -f position_monitor.log
```

### **Evening (8:00 PM):**
```bash
# System audit
./matrix_audit.py

# Review closed trades
sqlite3 data/trades.db "SELECT * FROM closed_positions WHERE date(close_time) = date('now');"
```

---

## 🎯 SUCCESS METRICS

### **Path Sync:** ✅
- Python: `/Users/forexgod/GlitchMatrix/signals.json`
- cTrader: `/Users/forexgod/GlitchMatrix/signals.json`
- **Status:** SYNCHRONIZED

### **BTC Volume Fix:** ✅
- `RawUnits` field injected for BTCUSD
- Prevents rounding to 0
- **Status:** ACTIVE

### **15 Pairs Monitoring:** ✅
- Visual confirmation on startup
- Real-time status tracking
- **Status:** OPERATIONAL

### **Sequential Startup:** ✅
- Cleanup → Clear → Verify → Launch
- No phantom signals
- **Status:** CLEAN

---

## 🚨 CRITICAL REMINDERS

1. **ALWAYS** rebuild cBot after code changes
2. **ALWAYS** verify path match (Python vs cTrader)
3. **NEVER** use relative paths (e.g., `signals.json`)
4. **ALWAYS** use absolute paths (e.g., `/Users/forexgod/GlitchMatrix/signals.json`)

---

## 📞 SUPPORT COMMANDS

```bash
# Check if monitors running
ps aux | grep monitor | grep -v grep

# Check MATRIX LINK
grep "MATRIX LINK" setup_monitor.log

# Check signals file
cat /Users/forexgod/GlitchMatrix/signals.json

# Check processed signals
tail ~/GlitchMatrix/processed_signals.txt

# Kill all monitors
pkill -9 -f monitor

# Clear signals manually
echo "[]" > /Users/forexgod/GlitchMatrix/signals.json
```

---

## 🎖️ SYSTEM STATUS

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 GLITCH IN MATRIX V2.0 - FULLY OPERATIONAL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ Absolute Path Binding      ACTIVE
✅ BTC Volume Fix              ACTIVE
✅ Sequential Startup          ACTIVE
✅ 15 Pairs Monitoring         ACTIVE
✅ Risk Management             ACTIVE
✅ Auto-Restart Protection     ACTIVE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

**──────────────**  
**✨ Glitch in Matrix by ФорексГод ✨**  
**🧠 AI-Powered • 💎 Smart Money**  
**──────────────**
