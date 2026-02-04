# 🧹 WORKSPACE CLEANUP AUDIT - 30 Ianuarie 2026

**Executat:** 30 Ianuarie 2026, 15:55  
**Status Sistem:** V3.3 Hybrid Entry LIVE și funcțional  
**Dimensiune Totală:** 355MB (logs: 168MB, venv: 118MB, data: 8.1MB, charts: 12MB)

---

## 📊 REZUMAT AUDIT

### **Statistici Generale:**
- **Python Scripts:** 61 fișiere .py
- **Documentație Markdown:** 60 fișiere .md (~22,305 linii)
- **Shell Scripts:** 18 fișiere .sh
- **C# cBots:** 6 fișiere .cs
- **Logs Directory:** 168MB (cel mai mare consumer spațiu)

---

## 🗑️ CATEGORIE 1: FIȘIERE OBSOLETE - ȘTERGERE RECOMANDATĂ

### **A) Webhook/TradingView System (DEPRECAT)**

**Context:** Sistemul inițial era bazat pe webhook TradingView. Acum folosim scanner local Python + cTrader.

**Fișiere de șters:**
```bash
# Python scripts
rm main.py                          # Entry point pentru webhook server (deprecat)
rm restart_webhook.py               # Restart helper pentru webhook (nu mai există webhook_server.py)
rm scan_live_markets.py            # Webhook-based scanner (înlocuit de daily_scanner.py)

# Documentație
rm README.md                        # Descrie sistemul webhook TradingView (outdated)
rm TRADINGVIEW_WEBHOOK_SETUP.md    # Setup guide pentru webhook (nu mai folosim)

# Shell scripts
rm start_realtime_monitor.sh       # Pornea realtime_monitor.py (deprecat)
```

**Justificare:** 
- `main.py` importă `webhook_server.py` care NU există în workspace
- `scan_live_markets.py` trimite semnale la `http://localhost:5001/webhook` (server inexistent)
- README.md descrie "Webhook TradingView cu AI" - sistemul actual e complet diferit

---

### **B) Alpha Vantage Removal (FINALIZAT)**

**Context:** Plan complet de eliminare Alpha Vantage după migrare la cTrader ProtoOA.

**Fișiere de șters:**
```bash
rm PLAN_STERGERE_ALPHA_VANTAGE.md  # Plan de migrare COMPLET (deja executat)
```

**Justificare:**
- Grep search: 0 matches pentru "alpha.*vantage|AlphaVantage|ALPHA_VANTAGE" în *.py
- Planul a fost finalizat cu succes, documentația e redundantă

---

### **C) Test Scripts Vechi (2025-01-15)**

**Context:** Test files pentru pullback strategy din implementări intermediare V3.0/V3.1.

**Fișiere de șters:**
```bash
# Test scripts vechi (15 ianuarie 2025)
rm test_pullback_functions.py           # Test basic pullback logic (V3.0)
rm test_pullback_live_pairs.py          # Test pe pairs live (V3.1)
rm pullback_test_results_20260115_*.json # 4 fișiere rezultate (outdated)

# Test scripts intermediare
rm test_v3_entry_confirmation.py        # V3.0 entry system (înlocuit de V3.3)
rm test_improvements.py                 # Generic improvements test (vague purpose)
rm debug_backtest.py                    # Debug helper (nu mai e folosit)
```

**Justificare:**
- V3.3 Hybrid Entry implementat (30 ianuarie) - test files V3.0/V3.1 nu mai sunt relevante
- `test_v3_3_continuation.py` (30 ianuarie) e singura versiune actuală

---

### **D) Backtest Output Files (RAW TEXT)**

**Context:** Output logs brute din backtest runs. Rezultatele importante sunt în fișierele Markdown.

**Fișiere de șters:**
```bash
rm backtest_output.txt              # Output brut backtest (rezultat final în .md)
rm backtest_live_output.txt         # Output brut live backtest
rm backtest_pullback_output.txt     # Output brut pullback test
rm backtest_scale_in_output.txt     # Output brut scale-in test (191KB)
```

**Justificare:**
- Informațiile importante sunt în `BACKTEST_1YEAR_SCALE_IN_RESULTS.md` și `BACKTEST_RAPORT_1AN_COMPLET.md`
- Fișiere .txt brute iau spațiu (191KB) și nu au formatare

---

### **E) Dashboard Backup Vechi**

**Context:** Backup HTML vechi din implementări anterioare.

**Fișiere de șters:**
```bash
rm dashboard.html.old               # Dashboard backup vechi
rm index_OLD_BACKUP.html           # Index backup vechi
```

**Justificare:**
- `dashboard_live.html` și `index.html` sunt versiunile curente active
- Backup-urile nu au date recovery value (sunt regenerabile din cod)

---

### **F) Scripturi Shell Redundante**

**Context:** Multiple scripturi de start/setup care se suprapun sau nu mai sunt folosite.

**Fișiere de șters:**
```bash
rm start_all.sh                     # Generic start (unclear ce pornește)
rm start_monitoring.sh              # Generic monitoring (unclear)
rm start_system.sh                  # Generic system start (unclear)
rm setup_launchd.sh                 # Duplicate cu install_launchd.sh
rm setup_morning_cron.sh            # Cron setup (nu mai folosim cron, avem launchd)
rm run_morning_scan.sh              # Duplicate cu run_morning_scan_unified.sh
```

**Fișiere de păstrat (ACTIVE):**
```bash
# KEEP - Active și folosite
✅ start_all_monitors.sh           # Pornește TOATE monitoarele (used)
✅ install_launchd.sh              # Setup launchd daemons (used)
✅ run_morning_scan_unified.sh     # Morning scan scheduler (used)
✅ setup_news_monitors.sh          # Setup news monitors (used)
✅ configure_24_7.sh               # 24/7 keep-alive config (used)
```

**Justificare:**
- 6 scripturi redundante/unclear purpose
- Păstrăm doar scripturile cu nume clare și funcție specifică

---

### **G) C# cBot Duplicates**

**Context:** Versiuni multiple ale aceluiași cBot.

**Fișiere de șters:**
```bash
rm PythonSignalExecutor_CLEAN.cs    # Versiune "cleaned" (15KB) - păstrăm originalul (16KB)
```

**Fișiere de păstrat (ACTIVE):**
```bash
✅ PythonSignalExecutor.cs          # Main executor bot (31 dec 2025)
✅ MarketDataProvider_v2.cs         # HTTP API data provider (16 dec 2025)
✅ EconomicCalendarBot.cs           # Calendar monitor (14 dec 2025)
✅ EconomicCalendarHTTP.cs          # HTTP calendar (3 ian 2026)
✅ TradeHistorySyncer.cs            # Trade sync (15 dec 2025)
```

**Justificare:**
- `PythonSignalExecutor.cs` e versiunea finală (mai nouă: 31 dec vs 3 ian)
- `_CLEAN.cs` e backup redundant

---

### **H) Documentație Intermediate/Deprecated**

**Context:** Rapoarte și planuri din implementări intermediare care au fost finalizate sau înlocuite.

**Fișiere de șters:**
```bash
# Intermediate implementation docs (V3.0 → V3.3)
rm V3.0_ENTRY_CONFIRMATION_SYSTEM.md     # V3.0 entry system (înlocuit de V3.3)
rm V3.0_IMPLEMENTATION_COMPLETE.md       # V3.0 completion report (outdated)
rm V3.0_SIMPLIFIED_LOGIC.md              # V3.0 simplification (outdated)

# Intermediate status reports
rm IMPLEMENTATION_COMPLETE.md            # Generic completion (unclear ce versiune)
rm FINAL_SYSTEM_STATUS.md                # "Final" status (but V3.3 e mai recent)
rm CURRENT_SYSTEM_STATUS.md              # "Current" status (V3.2, nu V3.3)
rm SYSTEM_STATUS_REPORT.md               # Status report V2.1 (very old)

# Intermediate comparison reports
rm BEFORE_AFTER_COMPARISON.md            # Before/after comparison (unclear ce versiuni)
rm CONTINUITY_VS_REVERSAL_FINAL.md       # Continuity analysis (integrated în V3.3)

# Old audit reports
rm SYSTEM_AUDIT_2026-01-05.md            # Audit din 5 ianuarie (25 zile în urmă)
rm ENTRY_SYSTEM_AUDIT_2026-01-08.md      # Entry audit din 8 ianuarie (22 zile în urmă)
rm ENTRY_PROBLEM_ROOT_CAUSE.md           # Root cause analysis (rezolvat în V3.3)

# Old implementation plans (finalizate)
rm GLITCH_OPTIMIZATION_PLAN.md           # Optimization plan (finalizat)
rm GLITCH_V2.1_IMPLEMENTATION.md         # V2.1 implementation (vechi)
rm V3.2_PULLBACK_PLAN.md                 # V3.2 plan (finalizat)

# Multiple "PLAN_" documents (finalizate)
rm PLAN_COMPLET_FINAL.md                 # Plan "final" (unclear)
rm PLAN_MIGRARE_COMPLETA.md              # Migration plan (finalizat)
rm PLAN_PERFECTIONARE_BOT.md             # Bot perfection plan (vague)
rm PLAN_PERFECTIONARE_GLITCH.md          # Glitch perfection plan (duplicate)
rm PLAN_ACTIVARE_CTRADER_PROTOOA.md      # cTrader activation plan (finalizat)

# Multiple "RAPORT_" documents (duplicate info)
rm RAPORT_COMPLET_PROIECT.md             # Complete project report (duplicate)
rm RAPORT_FINAL_COMPLET.md               # "Final complete" report (duplicate)
rm RAPORT_SURSA_DATE.md                  # Data source report (outdated)

# Change logs
rm CHANGELOG_2025-12-14.md               # Changelog din 14 decembrie 2025 (6 săptămâni în urmă)
```

**Fișiere de păstrat (CURRENT DOCS):**
```bash
✅ COMPREHENSIVE_AUDIT_REPORT_2025-01-30.md    # Latest audit (30 ian 2026) - 19KB
✅ UPGRADE_PLAN_V3.3_HYBRID_ENTRY.md           # Current V3.3 plan (30 ian 2026) - 22KB
✅ V3.2_PULLBACK_STRATEGY.md                   # V3.2 strategy baseline (12 ian 2026) - 23KB
✅ BACKTEST_RAPORT_1AN_COMPLET.md              # Complete 1-year backtest results
✅ BACKTEST_1YEAR_SCALE_IN_RESULTS.md          # Scale-in backtest results (8 ian)

✅ AI_STRATEGY_ANALYSIS_REPORT.md              # SMC strategy analysis
✅ AI_STRATEGY_DOCUMENTATION.md                # Strategy documentation
✅ SCANNER_ARCHITECTURE_DEEP_DIVE.md           # Scanner architecture

✅ CTRADER_API_SETUP.md                        # cTrader API setup (active)
✅ CTRADER_API_ANALYSIS.md                     # cTrader API analysis
✅ CTRADER_CBOT_SETUP.md                       # cBot setup guide
✅ CTRADER_CALENDAR_BOT_SETUP.md               # Calendar bot setup
✅ LIVE_CTRADER_SETUP.md                       # Live cTrader integration

✅ NEWS_ALERT_SYSTEM_GUIDE.md                  # News system guide
✅ NEWS_CALENDAR_SETUP.md                      # Calendar setup
✅ ECONOMIC_CALENDAR_BOT_SETUP.md              # Economic calendar bot

✅ MORNING_SCAN_SETUP.md                       # Morning scan setup
✅ MORNING_SCANNER_README.md                   # Scanner README

✅ VPS_DEPLOYMENT_GUIDE.md                     # VPS deployment
✅ WINDOWS_VPS_DEPLOYMENT_GUIDE.md             # Windows VPS guide

✅ MULTI_TIMEFRAME_STRATEGY.md                 # Multi-timeframe analysis
✅ CHART_ANNOTATIONS_GUIDE.md                  # Chart annotations
✅ DATA_PROVIDERS_COMPARISON.md                # Data providers comparison

✅ FIX_CTRADER_ACCOUNT.md                      # cTrader account fix
✅ FIX_TELEGRAM_NOTIFICATIONS.md               # Telegram fix
✅ KEEP_MAC_ALIVE.md                           # Mac keep-alive guide
✅ GHID_PENTRU_OWNER.md                        # Owner guide (Romanian)
✅ IMPORTANT_README.md                         # Important notes
✅ README_PRODUCTION.md                        # Production README
✅ PYTHON_SIGNAL_EXECUTOR_GUIDE.md             # Python executor guide
```

**Justificare:**
- 27 fișiere Markdown de șters (documentation debt cleanup)
- Păstrăm 34 fișiere Markdown ACTIVE (setup guides, current strategy docs, recent audits)

---

### **I) Verify/Update Scripts (One-Time Use)**

**Context:** Scripturi de verificare/update one-time pentru migrări sau fix-uri specifice.

**Fișiere de șters:**
```bash
rm verify_all_trades.py             # One-time verify după migrare
rm verify_ctrader_symbols.py        # One-time symbol verification
rm verify_ctrader_live_symbols.py   # One-time live symbols check
rm verify_new_trades.py             # One-time new trades check
rm update_missing_trades.py         # One-time update pentru trades lipsă
rm update_ctrader_live.py           # One-time update cTrader live data
rm fix_timestamps.py                # One-time fix pentru timestamps (9 ian)
rm repost_trades.py                 # One-time repost helper
```

**Justificare:**
- Scripturi one-time pentru fix-uri/migrări specifice
- Nu mai sunt necesare după execuție
- `check_setup_staleness.py` (30 ian) și `check_setup_status.py` sunt suficiente pentru verificări

---

### **J) TradingView Chart Generator (DEPRECAT)**

**Context:** Scripturi pentru screenshot-uri TradingView. Nu mai folosim TradingView.

**Fișiere de șters:**
```bash
rm tradingview_chart_generator.py
rm tradingview_desktop_screenshot.py
rm tradingview_native_screenshot.py
rm tradingview_login_helper.py
rm tradingview_saved_charts.json       # 0 bytes config
rm test_chart.png                      # Test screenshots
rm test_chart_gbpusd.png
rm test_chart_real.png
rm test_chart_reset.png
```

**Justificare:**
- Sistemul de charting TradingView nu mai e folosit
- `chart_generator.py` (16 ian) e versiunea actuală pentru chart generation

---

### **K) Morning Scan Logs Vechi**

**Context:** Log files vechi din morning scans.

**Fișiere de șters:**
```bash
rm morning_scan_20260109_102837.log    # Log din 9 ianuarie (21 zile în urmă)
```

**Justificare:**
- Logs vechi (3 săptămâni) - informația e în Telegram notifications sau trade history

---

### **L) Duplicate Dashboard Logs**

**Context:** Log file pentru dashboard (34KB).

**Evaluare:** KEEP - poate fi useful pentru debugging
```bash
✅ dashboard.log  # KEEP - recent activity log (10 ian)
```

---

### **M) Sync Scripts (Unclear Usage)**

**Context:** Scripturi de sincronizare cu usage neclar.

**Fișiere de evaluat:**
```bash
? sync_positions.py               # Sincronizare poziții (unclear cu ce)
? sync_trade_history.sh          # Shell wrapper pentru sync
? realtime_monitor.py            # Realtime monitoring (unclear dacă e folosit)
```

**Recomandare:** Verifică dacă sunt folosite în `start_all_monitors.sh` sau launchd files:
```bash
grep -l "sync_positions\|realtime_monitor" *.sh *.plist
```

**Dacă NU sunt referențiate:** ȘTERGE
**Dacă SUNT referențiate:** KEEP

---

### **N) Scanner Scripts (Potential Duplicates)**

**Context:** Multiple scripturi de scanning.

**Fișiere ACTIVE (KEEP):**
```bash
✅ daily_scanner.py               # Main scanner (8 ian, 20KB) - PRODUCTION
✅ scan_all_pairs.py             # All pairs scanner (fallback?)
```

**Fișiere de evaluat:**
```bash
? check_patterns.py              # Pattern checker (purpose unclear vs daily_scanner)
```

**Recomandare:** Verifică diferența funcțională între `check_patterns.py` și `daily_scanner.py`

---

## 📦 CATEGORIE 2: FIȘIERE DE ARHIVAT (MOVE TO /archive)

**Context:** Fișiere valoroase din punct de vedere istoric, dar nu mai sunt active.

**Creează folder arhivă:**
```bash
mkdir -p archive/{docs,scripts,tests,backups}
```

**Mută în arhivă:**
```bash
# Old documentation (valuable for history)
mv V3.0_*.md archive/docs/
mv SYSTEM_AUDIT_2026-01-*.md archive/docs/
mv ENTRY_*.md archive/docs/
mv PLAN_*.md archive/docs/
mv RAPORT_*.md archive/docs/
mv CHANGELOG_*.md archive/docs/

# Old test scripts
mv test_pullback_*.py archive/tests/
mv test_v3_entry_confirmation.py archive/tests/
mv test_improvements.py archive/tests/
mv pullback_test_results_*.json archive/tests/

# Old backtest outputs
mv backtest_*_output.txt archive/backups/

# Dashboard backups
mv *_OLD_*.html archive/backups/

# Monitoring setup backup
mv monitoring_setups_backup_*.json archive/backups/
```

---

## 🧼 CATEGORIE 3: CLEANUP LOGS DIRECTORY (168MB)

**Context:** Logs directory consumă cel mai mult spațiu (168MB din 355MB total).

**Strategie cleanup:**
```bash
# 1. Verifică ce fișiere sunt în logs/
ls -lhS logs/ | head -20

# 2. Șterge logs mai vechi de 14 zile
find logs/ -type f -mtime +14 -name "*.log" -delete

# 3. Comprimă logs între 7-14 zile
find logs/ -type f -mtime +7 -mtime -14 -name "*.log" -exec gzip {} \;

# 4. Păstrează doar ultimele 7 zile în format raw
```

**Salvare estimate:** 100-120MB

---

## 📋 CATEGORIE 4: FIȘIERE CRITICE - NU ATINGE

**Core System Files:**
```bash
✅ smc_detector.py                   # Core SMC detection logic (108KB, V3.3)
✅ setup_executor_monitor.py         # Setup executor (31KB, V3.3) - RUNNING PID 67737
✅ daily_scanner.py                  # Daily scanner (20KB) - PRODUCTION
✅ position_monitor.py               # Position monitor (12KB)
✅ trade_monitor.py                  # Trade monitor (9.4KB)
✅ news_calendar_monitor.py          # News monitor (26KB)
✅ ctrader_sync_daemon.py            # cTrader sync (5.5KB)

✅ ctrader_executor.py               # Trade executor (cTrader)
✅ ctrader_cbot_client.py            # cBot HTTP client (5.9KB)
✅ telegram_notifier.py              # Telegram notifications (18KB)
✅ notification_manager.py           # Notification manager
✅ money_manager.py                  # Money management

✅ pairs_config.json                 # Strategy config (5.1KB) - V3.3 params
✅ monitoring_setups.json            # Active setups (1.8KB) - 2 live setups
✅ signals.json                      # Trade signals (320B)
✅ trade_history.json                # Trade history (45KB)
✅ .env                              # Environment secrets (API keys)

✅ index.html                        # Dashboard live
✅ dashboard_live.html               # Dashboard

✅ requirements.txt                  # Python dependencies
✅ .gitignore                        # Git config
```

**cTrader cBots (ACTIVE):**
```bash
✅ PythonSignalExecutor.cs          # Main executor (16KB)
✅ MarketDataProvider_v2.cs         # HTTP API (22KB)
✅ EconomicCalendarBot.cs           # Calendar (8.3KB)
✅ EconomicCalendarHTTP.cs          # HTTP calendar (5.1KB)
✅ TradeHistorySyncer.cs            # Trade sync (8.3KB)
```

**Active Shell Scripts:**
```bash
✅ start_all_monitors.sh
✅ install_launchd.sh
✅ run_morning_scan_unified.sh
✅ setup_news_monitors.sh
✅ configure_24_7.sh
✅ cleanup_system.sh
✅ full_system_audit.sh
```

**launchd Config:**
```bash
✅ com.forexgod.glitch.plist
✅ com.forexgod.morningscan.plist
✅ com.forexgod.newscalendar.plist
✅ com.forexgod.weeklynews.plist
```

---

## 🎯 PLAN DE EXECUȚIE - RECOMANDĂRI

### **Faza 1: ȘTERGERE SAFE (Low Risk)**
```bash
# Webhook/TradingView (deprecat complet)
rm main.py restart_webhook.py scan_live_markets.py
rm README.md TRADINGVIEW_WEBHOOK_SETUP.md
rm tradingview_*.py tradingview_*.json test_chart*.png

# Alpha Vantage (migration finalizată)
rm PLAN_STERGERE_ALPHA_VANTAGE.md

# Test files vechi (>15 zile)
rm test_pullback_*.py test_v3_entry_confirmation.py test_improvements.py
rm pullback_test_results_*.json debug_backtest.py

# Backtest outputs (brute)
rm backtest_*_output.txt

# Backups HTML
rm dashboard.html.old index_OLD_BACKUP.html

# C# duplicates
rm PythonSignalExecutor_CLEAN.cs

# One-time verify scripts
rm verify_*.py update_missing_trades.py update_ctrader_live.py
rm fix_timestamps.py repost_trades.py

# Old logs
rm morning_scan_20260109_102837.log
```

**Economie spațiu:** ~2-3MB  
**Risc:** ZERO (fișiere complet deprecate sau duplicate)

---

### **Faza 2: ARHIVARE (Medium Risk)**
```bash
mkdir -p archive/{docs,scripts,tests,backups}

# Documentation (valuable for history)
mv V3.0_*.md SYSTEM_AUDIT_*.md ENTRY_*.md archive/docs/
mv PLAN_*.md RAPORT_*.md CHANGELOG_*.md archive/docs/
mv IMPLEMENTATION_COMPLETE.md FINAL_SYSTEM_STATUS.md archive/docs/
mv CURRENT_SYSTEM_STATUS.md SYSTEM_STATUS_REPORT.md archive/docs/
mv BEFORE_AFTER_COMPARISON.md CONTINUITY_VS_REVERSAL_FINAL.md archive/docs/
mv GLITCH_*.md V3.2_PULLBACK_PLAN.md archive/docs/

# Backups
mv monitoring_setups_backup_*.json archive/backups/
```

**Economie root directory:** 27 fișiere .md  
**Risc:** LOW (păstrează fișierele, doar le mută)

---

### **Faza 3: CLEANUP SCRIPTS (Medium Risk)**
```bash
# Shell scripts redundante
rm start_all.sh start_monitoring.sh start_system.sh
rm setup_launchd.sh setup_morning_cron.sh run_morning_scan.sh
rm start_realtime_monitor.sh
```

**Economie:** ~10-15KB  
**Risc:** MEDIUM (verifică că nu sunt folosite în launchd sau alte scripturi)

**Verificare înainte de ștergere:**
```bash
# Check dacă scripturile sunt referențiate
grep -r "start_all.sh\|start_monitoring.sh\|start_system.sh" *.plist *.sh
```

---

### **Faza 4: LOGS CLEANUP (High Impact)**
```bash
# Șterge logs mai vechi de 14 zile
find logs/ -type f -mtime +14 -delete

# Comprimă logs 7-14 zile
find logs/ -type f -mtime +7 -mtime -14 -name "*.log" -exec gzip {} \;
```

**Economie:** 100-120MB (din 168MB)  
**Risc:** LOW (logs vechi nu afectează funcționalitatea)

---

### **Faza 5: EVALUARE MANUALĂ (High Risk)**
```bash
# Verifică usage pentru:
? sync_positions.py
? realtime_monitor.py
? check_patterns.py
? scan_all_pairs.py

# Metodă verificare:
grep -r "sync_positions\|realtime_monitor\|check_patterns" *.sh *.plist *.py
```

**NU ȘTERGE** fără confirmare că nu sunt folosite în production.

---

## 📊 ECONOMIE TOTALĂ ESTIMATE

| Categorie | Fișiere | Spațiu |
|-----------|---------|--------|
| **Webhook/TradingView** | 10-12 | ~1-2MB |
| **Test files vechi** | 8 | ~500KB |
| **Backtest outputs** | 4 | ~300KB |
| **Documentation (arhivat)** | 27 | ~0MB (doar mutat) |
| **Shell scripts** | 7 | ~15KB |
| **One-time scripts** | 10 | ~100KB |
| **Logs cleanup** | - | 100-120MB |
| **TOTAL** | **66+ files** | **~120MB** |

**Final Size:** 355MB → ~235MB (66% reținut)

---

## ✅ ACȚIUNI RECOMANDATE

### **Prioritate 1 (ACUM):**
1. ✅ Faza 1: Ștergere fișiere deprecate (SAFE)
2. ✅ Faza 4: Cleanup logs >14 zile (HIGH IMPACT)

### **Prioritate 2 (Următoarele zile):**
3. ⏳ Faza 2: Arhivare documentație veche
4. ⏳ Faza 5: Evaluare manuală scripturi necunoscute

### **Prioritate 3 (Optional):**
5. ⏳ Faza 3: Cleanup shell scripts (după verificare dependency)

---

## 🚨 ATTENTION POINTS

### **NU ȘTERGE:**
- ❌ `daily_scanner.py` - PRODUCTION scanner
- ❌ `setup_executor_monitor.py` - RUNNING (PID 67737)
- ❌ `pairs_config.json` - V3.3 config
- ❌ `monitoring_setups.json` - Live setups (USDCHF, USDJPY)
- ❌ `smc_detector.py` - Core logic (V3.3)
- ❌ Orice fișier .cs (cTrader cBots active)
- ❌ `start_all_monitors.sh` - Used pentru restart
- ❌ `*.plist` - launchd configs ACTIVE

### **VERIFICĂ ÎNAINTE DE ȘTERGERE:**
- ⚠️ Shell scripts: grep în *.plist și alte *.sh
- ⚠️ Python scripts: grep în start_all_monitors.sh
- ⚠️ Logs: verifică că nu sunt logs critice sub 14 zile

---

## 📝 NOTES

**Generat:** 30 Ianuarie 2026  
**Tool:** Comprehensive workspace audit  
**Purpose:** Reduce technical debt, improve workspace clarity  
**Next Review:** După cleanup, repeat audit în 1 lună

**Status V3.3:** ✅ OPERATIONAL (Monitor PID 67737 running)  
**Active Setups:** 2 (USDCHF, USDJPY) - continuation check active (7.3h)

---

**END OF AUDIT**
