# Plan: eliminare fals-pozitive „cTRADER SYNC STALE” (Telegram)

> **Data:** 2026-10-03  
> **Branch:** `cursor/v36-3-radar-live-sync`  
> **Status:** **V57.1 implementat** (2026-10-03) — `broker_data_freshness.py`, `ctrader_sync_daemon.py`  
> **Scop:** document pentru review (ex. Gemini) înainte de cod

---

## 1. Problema raportată

- Telegram primește **„cTRADER SYNC STALE”** (și spam la ~5 minute).
- În paralel: **TradeHistorySyncer** rulează în cTrader, **Dashboard PRO** arată balance/equity live.
- Utilizatorul consideră alerta **fals-pozitivă**: botul și dashboard-ul funcționează.

**Mesaj tipic Telegram:**

- Titlu: `cTRADER SYNC STALE`
- Cauză: `TradeHistorySyncer offline — port 8767 inaccesibil`
- URL afișat: `http://localhost:8767/`
- Acțiune sugerată: Stop + Start TradeHistorySyncer, `Invoke-RestMethod http://localhost:8767/`

---

## 2. Arhitectură (cine face ce)

```
cTrader Desktop
  ├── TradeHistorySyncer (cBot)     → port 8767 HTTP + scrie trade_history.json
  ├── CalendarBOT                   → 8768 (calendar / JSON file)
  ├── DATA-Market                   → 8010 OHLCV
  └── PhytonSignalExecutor          → semnale

VPS / Windows — Python
  ├── ctrader_sync_daemon.py        → poll 8767 la ~30s → actualizează trade_history.json + SQLite
  ├── dashboard_server.py           → servește dashboard (citește trade_history.json)
  ├── watchdog_monitor.py           → repornește procese
  └── telegram_command_center.py    → comenzi /status (NU trimite STALE)

Telegram STALE → doar ctrader_sync_daemon.py (sync_loop, după ~5 min eșec consecutive)
```

**Important:** alerta **nu** vine din `telegram_command_center.py`. Fix-ul principal = **sync daemon + broker freshness**, nu command center.

---

## 3. Diagnostic (de ce dashboard OK dar Telegram zice offline)

| Layer | Ce se întâmplă |
|-------|----------------|
| cBot | Scrie direct `trade_history.json` (path configurat în cTrader) + servește JSON pe HTTP |
| Dashboard | Citește `trade_history.json` via HTTP static — **nu depinde** de succesul Python→8767 |
| Daemon | `requests.get(TRADE_SYNC_URL)` — dacă eșuează 5+ min → Telegram STALE |

**Concluzie:** cBot poate fi sănătos (fișier proaspăt) în timp ce **Python nu reușește HTTP** → fals-pozitiv.

### 3.1 Dovadă VPS (PowerShell, 2026-10-03)

| Comandă | Rezultat observat |
|---------|-------------------|
| `Invoke-RestMethod http://127.0.0.1:8767/` | **HTTP 400 — Invalid Hostname** |
| `Invoke-RestMethod http://localhost:8767/` | **HTTP 400 — Invalid Hostname** (atipic; de investigat) |
| Output cu `sync_healthy=True` | Posibil citire `trade_history.json` sau comandă cu Host header corect |

**Cauză tehnică (127.0.0.1):** în `TradeHistorySyncer.cs`, HttpListener este înregistrat **doar** ca:

```csharp
_httpListener.Prefixes.Add($"http://localhost:{HttpPort}/");
```

Request la `http://127.0.0.1:8767/` trimite `Host: 127.0.0.1` → **400 Invalid Hostname** (comportament așteptat).

**Implicație:** fallback-ul „folosește 127.0.0.1 în loc de localhost” ca URL principal **poate agrava** problema, nu o rezolvă.

### 3.2 Test recomandat pe VPS

```powershell
# Workaround Host header (ar trebui să meargă dacă cBot ascultă pe localhost)
Invoke-RestMethod -Uri "http://127.0.0.1:8767/" -Headers @{ Host = "localhost" }

# Compară cu fișierul
Get-Content .\trade_history.json -Raw | ConvertFrom-Json | Select -ExpandProperty account
```

---

## 4. Ce există deja în cod (branch)

**Commit `dc026ed`** (parțial implementat):

| Feature | Fișier |
|---------|--------|
| `TRADE_SYNC_URL` / `resolve_trade_sync_url()` | `broker_data_freshness.py` |
| Backoff Telegram: 5 min → 1 h → 12 h | `ctrader_sync_daemon.py` |
| Log HTTP status, JSONDecodeError, body preview | `ctrader_sync_daemon.py` |
| Respingere payload stale (`last_update` > 120s) | `broker_data_freshness.py` |
| Fallback disk: HTTP stale dar `trade_history.json` fresh | `ctrader_sync_daemon.py` (_load_fresh_from_disk) |

**Ce lipsește (V57.1 propus):**

- Alias env `CTRADER_SYNC_URL`
- Fetch multi-attempt (localhost + 127.0.0.1 cu `Host: localhost`)
- HTTP 400 ≠ „offline”
- **Mod degradat:** HTTP eșuează dar disk fresh → `sync_once` success, **fără Telegram**
- Telegram doar când **și** HTTP **și** disk sunt stale
- Erori JSON/parse: log only, fără STALE
- Opțional: persist backoff la restart daemon
- Opțional: al doilea prefix `127.0.0.1` în TradeHistorySyncer.cs (+ netsh urlacl)
- `telegram_command_center.py`: `/status` să folosească `resolve_trade_sync_url()` (consistență)

**Notă deploy:** reset monitoare / watchdog **nu** înlocuiește `git pull` + restart `ctrader_sync_daemon.py` cu cod nou.

---

## 5. Cerințe utilizator (3 reguli) vs plan

| # | Cerință | Evaluare |
|---|---------|----------|
| 1 | Env `CTRADER_SYNC_URL`, evită hardcod localhost | Da — alias + env; **default rămâne `http://localhost:8767/`** (compatibil cBot); retry cu IP + `Host: localhost` |
| 2 | ConnectionError/Timeout = bot picat; JSON/400 = log, fără „indisponibil” | Da — clasificare erori + nu STALE pe parse/400 |
| 3 | Backoff 5m / 1h / 12h | Parțial în cod — necesită deploy VPS |

**Regulă suplimentară (critica pentru cazul dashboard live):**

> Dacă `trade_history.json` este proaspăt (`is_payload_fresh`), **nu trimite STALE** chiar dacă HTTP 8767 eșuează.

---

## 6. Implementare propusă V57.1 (detaliu)

### 6.1 `broker_data_freshness.py`

- `resolve_trade_sync_url()`: `CTRADER_SYNC_URL` → `TRADE_SYNC_URL` → `CTRADER_API_URL` → default `http://localhost:8767/`
- Funcție `trade_sync_fetch_attempts()` → listă `(url, headers)` pentru daemon

### 6.2 `ctrader_sync_daemon.py`

1. **Multi-attempt fetch** în `fetch_ctrader_data()`
2. **Mod degradat** în `sync_once()`: disk fresh → success, log `DEGRADED`, fără contor Telegram
3. **`_telegram_alert_eligible(failure_kind)`** — tabel:

| failure_kind | Telegram STALE? |
|--------------|-----------------|
| offline, timeout | Doar dacă disk **nu** e fresh |
| stale (HTTP OK, date vechi) | Doar dacă disk **nu** e fresh |
| invalid, error, hostname_mismatch (400) | **Nu** — doar log |

4. Păstrează backoff existent; opțional persist în `data/ctrader_sync_alert_state.json`

### 6.3 `TradeHistorySyncer.cs` (opțional)

- Al doilea prefix: `http://127.0.0.1:8767/`
- Windows: `netsh http add urlacl url=http://127.0.0.1:8767/ user=Everyone` (admin)

### 6.4 `.env.example`

```env
CTRADER_SYNC_URL=http://localhost:8767/
TRADE_SYNC_URL=http://localhost:8767/
```

---

## 7. Criterii de succes (acceptance)

1. cBot + dashboard live, JSON `< 120s` → **zero** mesaje STALE pe Telegram
2. Oprire reală TradeHistorySyncer + fișier vechi > 5 min → **o** alertă STALE, apoi backoff 1h / 12h
3. `ctrader_sync.log` arată clar: ConnectionError vs 400 vs DEGRADED vs sync OK
4. `Invoke-RestMethod` cu `Host: localhost` pe 127.0.0.1 returnează account JSON (după fix)

---

## 8. Verificare post-deploy (VPS)

```powershell
cd "C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo"
git pull
# restart ctrader_sync_daemon via watchdog sau manual

Select-String -Path logs\ctrader_sync.log -Pattern "DEGRADED|ConnectionError|400|STALE|Broker stale" | Select-Object -Last 40
Get-Item trade_history.json | Format-List LastWriteTime, Length
```

---

## 9. Prioritate față de alte planuri

- Independent de **PLAN_DEBLOCARE_W_D_4H** (radar / executor).
- Poate fi livrat ca patch mic înainte de deblocarea W→D→4H.

---

## 10. Prompt scurt pentru Gemini (copy-paste)

```
Context: Proiect trading Python pe Windows VPS + cTrader cBots.
TradeHistorySyncer expune HttpListener doar pe http://localhost:8767/ și scrie trade_history.json.
ctrader_sync_daemon.py face GET la 8767; la eșec 5 min trimite Telegram "cTRADER SYNC STALE".

Problema: Dashboard citește trade_history.json (proaspăt), cBot rulează, dar Telegram spune offline.
Pe VPS, Invoke-RestMethod http://127.0.0.1:8767/ → HTTP 400 Invalid Hostname.

Plan V57.1 propus:
1) CTRADER_SYNC_URL, fetch localhost + retry 127.0.0.1 cu Header Host: localhost
2) HTTP 400 / JSON errors → log, nu Telegram "offline"
3) Backoff alerte 5m/1h/12h (parțial existent)
4) Dacă trade_history.json e fresh (<120s), sync success degradat fără Telegram chiar dacă HTTP eșuează

Întrebări pentru tine:
- E corect modul degradat (disk ca sursă de adevăr când HTTP și listener localhost-only diverg)?
- Riscuri de security/ops la netsh urlacl pentru al doilea prefix 127.0.0.1?
- Alternative Windows (force IPv4 localhost, evită ::1 ConnectionError) pentru Python requests?
- Alte false-positive paths în același daemon de verificat?

Fișiere: broker_data_freshness.py, ctrader_sync_daemon.py, TradeHistorySyncer.cs
Document complet: docs/SYNC_STALE_ALERT_PLAN.md
```

---

## 11. Istoric document

| Data | Notă |
|------|------|
| 2026-10-03 | Plan inițial + dovada VPS 400 Invalid Hostname; corecție strategie URL (nu 127.0.0.1 principal) |

---

---

## 12. Prompt implementare Agent (copy-paste după switch Agent)

```
Implementează V57.1 aprobat din docs/SYNC_STALE_ALERT_PLAN.md:

broker_data_freshness.py:
- CTRADER_SYNC_URL în resolve_trade_sync_url()
- trade_sync_fetch_attempts() — 127.0.0.1 cu Header Host: localhost
- disk_payload_fresh(path)

ctrader_sync_daemon.py:
- fetch multi-attempt; 400/JSON = hostname_mismatch/invalid, NU offline
- sync_once: dacă HTTP fail dar disk fresh → DEGRADED success, fără Telegram
- sync_loop: backoff STALE doar când disk_payload_fresh(trade_history.json) == False
- _telegram_alert_eligible: invalid/hostname_mismatch/error → never

.env.example: CTRADER_SYNC_URL=http://localhost:8767/
pytest tests/test_broker_data_freshness.py dacă există
```

---

*Document pentru discuție + handoff implementare. Cod: Agent mode + prompt sec. 12.*
