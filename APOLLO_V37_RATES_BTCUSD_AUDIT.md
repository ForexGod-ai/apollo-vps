# Audit static: Dobânzi Telegram & Bias BTCUSD

**Proiect:** Glitch in Matrix / Apollo V37  
**Data auditului:** 11 iunie 2026  
**Scope:** Audit static — `daily_scanner.py`, `smc_detector.py`, `telegram_command_center.py`, `news_calendar_monitor.py`  
**Simboluri / module:** Central Bank Rates (`/rates`), BTCUSD (Daily BIAS)  
**Status cod:** Fără modificări — doar diagnostic  

---

## 1. Context și simptome

În rularea live Apollo V37 au fost observate două anomalii:

| # | Anomalie | Simptom |
|---|----------|---------|
| **1** | Central Bank Rates Telegram | Card `/rates` afișează NZD 5.25%, GBP 5.00%, USD 4.75% etc. — neclar dacă datele sunt live sau hardcodate |
| **2** | Bias BTCUSD | Grafic D1 masiv **BEARISH** (LL/LH succesive), dar sistemul a detectat setup **BUY** |

**Obiectiv audit:** identificarea liniilor exacte de cod care produc aceste comportamente + plan de remediere V38.

---

## 2. Metodologie

| Pas | Acțiune |
|-----|---------|
| 1 | Căutare statică sursă card `CENTRAL BANK RATES — 2026` în codebase |
| 2 | Comparare format screenshot Telegram vs `handle_rates_command()` vs `generate_weekly_macro_report()` |
| 3 | Analiză `determine_daily_trend()` și `scan_for_setup()` — reguli V22/V25 |
| 4 | Verificare `lookback_candles` pentru BTCUSD în `pairs_config.json` |
| 5 | Replay local pe cache: `data/historical_cache/BTCUSD_D1_20250206_20260201.csv` (365 bare D1) |
| 6 | Verificare `bias_fallback` și V33 SMART MERGE pentru persistență setup-uri vechi |

---

## 3. Verdict executiv

| Anomalie | Verdict | Severitate |
|----------|---------|------------|
| **1 — Rates Telegram** | Date **100% STATICE** pe calea `/rates`; scraping live există separat, neconectat | **P0** |
| **2 — BTCUSD BUY** | Bug de **recency bias** (V25 + V22); lookback **NU** e cauza; SMART MERGE poate păstra BUY vechi | **P0** |

---

## ANOMALIA 1 — Central Bank Rates Telegram

### 3.0 Status remediere V38 (implementat)

| Componentă | Fișier | Status |
|------------|--------|--------|
| Serviciu central live + cache | `macro_rates.py` | **IMPLEMENTAT** |
| `/rates` Telegram live | `telegram_command_center.py` → `format_rates_telegram_message()` | **IMPLEMENTAT** |
| Weekly macro unificat | `news_calendar_monitor.py` → `macro_rates` | **IMPLEMENTAT** |
| Cache persistent VPS | `data/cb_rates_cache.json` | **IMPLEMENTAT** |
| Cron zilnic 08:00 EET | `auto_scanner_daemon.py` + `scripts/refresh_cb_rates.py` | **IMPLEMENTAT** |
| Swap IC Markets live | `macro_rates.fetch_ic_markets_swaps()` via cTrader :8767 | **IMPLEMENTAT** |

### 3.0.1 Ratele vechi erau corecte?

**Nu.** Dict-ul static din V11.5 reflecta ciclul de varf 2023–2024, nu piata din iunie 2026:

| Moneda | V11.5 hardcodat (GREȘIT) | Piata ~iun 2026 (investing.com live) | Delta |
|--------|--------------------------|--------------------------------------|-------|
| NZD | 5.25% | **2.25%** | -3.00% |
| GBP | 5.00% | **3.75%** | -1.25% |
| USD | 4.75% | **3.75%** | -1.00% |
| EUR | 3.50% | **2.40%** | -1.10% |
| AUD | 4.35% | **4.35%** | 0.00% |
| CAD | 3.75% | **2.25%** | -1.50% |
| CHF | 1.50% | **0.00%** | -1.50% |
| JPY | 0.25% | **1.00%** | +0.75% |

Cardul vechi afisa NZD/JPY +5.00% carry — real ~+1.25%. Decizii macro gresite.

### 3.1 Verdict (audit initial — pre-V38)

Cardul din screenshot (`🏦 CENTRAL BANK RATES — 2026`, bare vizuale `▰▱`, TOP CARRY NZD/JPY +5.00% etc.) corespunde **1:1** cu comanda `/rates`. **Nu există API, scraping sau timestamp de actualizare** pe această cale.

### 3.2 Sursa exactă — `/rates` (STATIC)

**Fișier:** `telegram_command_center.py`  
**Funcție:** `handle_rates_command()`  
**Linii critice:** 1653–1707

```python
# telegram_command_center.py:1653–1666
def handle_rates_command(self) -> str:
    """/rates — Central Bank rates + top carry pairs (V11.5)"""
    try:
        # Rates hardcoded 2026
        RATES = {
            'NZD': ('🇳🇿', 5.25),
            'GBP': ('🇬🇧', 5.00),
            'USD': ('🇺🇸', 4.75),
            'AUD': ('🇦🇺', 4.35),
            'CAD': ('🇨🇦', 3.75),
            'EUR': ('🇪🇺', 3.50),
            'CHF': ('🇨🇭', 1.50),
            'JPY': ('🇯🇵', 0.25),
        }
```

| Element | Linie | Detaliu |
|---------|-------|---------|
| Dict static `RATES` | **1657–1666** | Valori introduse manual, etichetate „hardcoded 2026” |
| Titlu card | **1673** | `CENTRAL BANK RATES — 2026` |
| Clasificare Strong/Weak | **1668–1670** | Prag fix ≥ 3.50% |
| Top 3 carry pairs | **1682–1705** | Calculate din același dict static |
| Footer branding | **217–224** (`send_message`) | `AUTHORED BY ФорексГод` / `ГЛИТЧ ИН МАТРИКС` |

**Acces:** `/rates` este în `PUBLIC_COMMANDS` (linia **124**) — oricine din grup poate primi cardul.

### 3.3 A doua sursă — weekly macro (PARȚIAL dinamic, NELEGAT de `/rates`)

**Fișier:** `news_calendar_monitor.py`

| Componentă | Linii | Comportament |
|------------|-------|--------------|
| Baseline static | **124–133** | `CENTRAL_BANK_RATES` — aceleași valori ca `/rates` |
| Scraping live | **879–953** | `fetch_live_cb_rates()` → investing.com |
| Merge live + static | **955–973** | `_get_effective_rates()` — live override hardcoded |
| Raport săptămânal | **975+** | `generate_weekly_macro_report()` — titlu **MACRO WEEKLY TABLE**, format diferit |

Fluxul dinamic există **doar** pentru raportul de luni 09:00 EET. Comanda `/rates` **nu** apelează `_get_effective_rates()`.

### 3.4 Răspuns la întrebarea critică

| Întrebare | Răspuns |
|-----------|---------|
| Date extrase din API macro actualizat? | **NU** pe `/rates` |
| Dict static manual? | **DA** — `telegram_command_center.py:1657–1666` |
| Unde mutăm pe flux dinamic? | Refactor: `/rates` → `_get_effective_rates()` din `news_calendar_monitor.py` (sau modul comun `macro_rates.py`) |

### 3.5 Remediere V38 — IMPLEMENTAT

1. `macro_rates.py` — fetch investing.com, cache JSON (`TTL 6h`), fallback iun 2026
2. `handle_rates_command()` — live + timestamp + sectiune swap cTrader IC Markets
3. `news_calendar_monitor.py` — acelasi serviciu pentru raport saptamanal
4. `scripts/refresh_cb_rates.py` + `auto_scanner_daemon.py` — refresh zilnic 08:00 EET + alerta Telegram la schimbare >= 0.25%

**Nota:** cTrader/IC Markets expune **swap overnight** (pips/zi), nu rate oficiale Fed/ECB. Cardul V38 combina ambele: macro oficial (investing.com) + carry real broker (localhost:8767).

---

## ANOMALIA 2 — BTCUSD BUY pe structură D1 bearish

### 4.1 Verdict

Bug de **logică structurală (recency bias)**, nu de lookback insuficient. Sistemul prioritizează ultimul break mic (BOS bullish din consolidare) peste structura macro bearish (LL/LH).

### 4.2 Regula V25 — cauză principală

**Fișier:** `smc_detector.py`  
**Funcție:** `scan_for_setup()`  
**Linii:** 3167–3185

```python
# smc_detector.py:3167–3185
if latest_choch and latest_bos:
    if latest_choch.index >= latest_bos.index:
        latest_signal = latest_choch
        strategy_type = 'reversal'
    else:
        latest_signal = latest_bos
        strategy_type = 'continuation'
...
current_trend = latest_signal.direction
```

**Filozofie V25 (3154–3165):** cel mai recent break structural = ancora biasului. CHoCH și BOS sunt echivalente ca declanșatori.

### 4.3 Replay pe cache BTCUSD (365 bare D1)

Semnale detectate (`detect_choch_and_bos`):

| Tip | Index | Direcție | Dată |
|-----|-------|----------|------|
| CHoCH | 337 | bullish | 2026-01-04 |
| BOS | 346 | bullish | 2026-01-13 |
| CHoCH | 353 | bearish | 2026-01-20 |

**Regula V25 aplicată:**

| Ultim CHoCH | Ultim BOS | Condiție V25 | Bias rezultat |
|-------------|-----------|--------------|---------------|
| bullish @ **337** | bullish @ **346** | `337 < 346` → **BOS câștigă** | **BULLISH / BUY** |
| bearish @ **353** | bullish @ **346** | `353 >= 346` → **CHoCH câștigă** | **BEARISH / SHORT** |

**Fereastra BUY eronat:** ~13–19 ianuarie 2026 — BOS bullish minor din consolidarea din dreapta-jos bate CHoCH-ul bullish anterior, **înainte** ca bearish CHoCH @353 să fie format.

**Pullback din mijlocul graficului** (aceeași logică):

| Cutoff bare | Semnal dominant | Bias |
|-------------|-----------------|------|
| 320 | CHoCH bullish @305 | **BULLISH** |
| 340 | CHoCH bullish @337 | **BULLISH** |

Trei BOS bullish din mijlocul graficului + bounce minor → sistemul interpretează trend shift, deși macro-ul (LL/LH) rămâne bearish.

### 4.4 `lookback_candles` — NU e problema

**Fișier:** `pairs_config.json` — liniile **151–152**

```json
"lookback_candles": {
  "daily": 365,
```

365 bare D1 ≈ 1 an de istoric. Botul **vede** structura majoră din stânga. Problema nu e orbirea datelor, ci **prioritatea semnalului**.

### 4.5 `determine_daily_trend()` — aceeași eroare, docstring contradictoriu

**Fișier:** `smc_detector.py`  
**Funcție:** `determine_daily_trend()`  
**Linii:** 1815–1955

**Docstring (1837–1846)** promite:

> Dacă ultimele 150 bare arată LL + LH (bearish macro) și ultimul CHoCH e bullish → Bias = BEARISH.

**Implementare V22 (1948–1953)** face invers:

```python
# smc_detector.py:1948–1953
if latest_signal:
    final_bias = latest_signal.direction
    ...
    elif macro_trend_swings != 'neutral':
        confidence = f"HIGH (Body-close {signal_type} {final_bias.upper()} — overrides swing pattern {macro_trend_swings.upper()})"
```

| Layer | Linii | Comportament real |
|-------|-------|-------------------|
| Macro swings | **1872–1887** | Doar **ultimele 3** pivoturi; pe BTC: `HH=1 LH=1 HL=1 LL=1` → **neutral** → zero filtru |
| Latest signal | **1902–1916** | Ultimul CHoCH **sau** BOS după index simplu (fără regula V25 choch≥bos) |
| Bias final | **1948–1949** | `final_bias = latest_signal.direction` — swings nu blochează |
| Layer 4 (ierarhie) | **1940–1941** | Declarată dar **neimplementată** pentru decizie |

### 4.6 `bias_fallback` — amplifică aceeași greșeală

**Fișier:** `daily_scanner.py` — liniile **607–628**

```python
# daily_scanner.py:607–614
_bias_dir = self.smc_detector.determine_daily_trend(df_daily)
if _bias_dir in ('bullish', 'bearish'):
    _bias_trade_dir = 'buy' if _bias_dir == 'bullish' else 'sell'
```

Dacă `scan_for_setup()` respinge setup-ul complet, fallback-ul repetă aceeași logică defectă → poate produce **BUY** când trendul e bullish eronat.

### 4.7 MOMENTUM entry — secundar pentru acest caz

**Fișier:** `smc_detector.py` — liniile **3200–3238**

Necesită `consecutive_bos_count >= 3` **și** `strategy_type == 'continuation'`.

Pre-CHoCH BOS pe BTC: mix bearish/bullish în ultimele 5 — **nu** declanșează momentum fals în faza bearish profundă. **Nu e cauza dominantă** pentru BUY eronat.

### 4.8 V33 SMART MERGE — multiplicator de persistență

**Fișier:** `daily_scanner.py` — liniile **892–976**

```python
# daily_scanner.py:973–976
if setup.symbol in preserved_symbols:
    print(f"  ⏭️  [V33 MERGE] {setup.symbol}: deja activ in JSON ... — scan nou ignorat")
    continue
```

**Scenariu zombie BUY:**

1. **13 ian:** scan creează BUY (BOS bullish @346).
2. **20 ian:** CHoCH bearish @353 — scan nou ar produce SHORT.
3. **SMART MERGE** păstrează BUY vechi dacă status activ (`WAITING_D1_PULLBACK`, `MONITORING`, etc.).
4. Scan nou SHORT **ignorat** — simbolul deja în `preserved_symbols`.

**`/btcusd`** (`telegram_command_center.py:1185–1260`) citește direct din `monitoring_setups.json` — **nu recalculează** structura D1.

### 4.9 Confirmare replay local (cod curent + cache complet)

Cu cache D1 + H4, `scan_for_setup('BTCUSD', ...)` returnează acum:

- **BEARISH SHORT** — CHoCH bearish @353 (V25: `353 >= 346`)
- Status: `MONITORING`
- Log: `[V25.0 UNIVERSAL] BTCUSD: BEARISH | CHoCH @bar353 → WAITING_D1_PULLBACK`

BUY-ul raportat corespunde fie perioadei **13–19 ian** (înainte de CHoCH bearish final), fie un setup **păstrat în JSON** de SMART MERGE.

---

## 5. Diagramă flux — de ce BUY pe chart bearish

```
D1: 365 bare — structură macro BEARISH (LL/LH)
        │
        ▼
detect_choch_and_bos()
        │
        ├── Ultim BOS bullish @346 > CHoCH @337
        │       └── V25: strategy=continuation → BULLISH
        │               └── determine_daily_trend = bullish
        │                       └── bias_fallback BUY / setup LONG
        │
        └── Ultim CHoCH bearish @353 >= BOS @346
                └── V25: strategy=reversal → BEARISH (corect)
                        └── DAR: V33 SMART MERGE păstrează BUY vechi din JSON
                                └── /btcusd arată BUY pe chart bearish
```

---

## 6. Tabel defecte Matrix

| # | Defect | Severitate | Fișier | Linie |
|---|--------|------------|--------|-------|
| 1 | `/rates` 100% static, neactualizabil | **P0** | `telegram_command_center.py` | 1657–1666 |
| 2 | V25: ultimul break mic bate macro bearish | **P0** | `smc_detector.py` | 3167–3185 |
| 3 | V22: swings macro nu blochează bias opus | **P0** | `smc_detector.py` | 1948–1953 |
| 4 | Macro swings doar 3 pivoturi → neutral pe BTC | **P1** | `smc_detector.py` | 1872–1887 |
| 5 | SMART MERGE freeze direcție veche | **P1** | `daily_scanner.py` | 973–976 |
| 6 | Docstring vs implementare contradictorii | **P2** | `smc_detector.py` | 1837–1846 vs 1948 |
| 7 | `determine_daily_trend` vs `scan_for_setup` — logici diferite | **P1** | `smc_detector.py` | 1902–1916 vs 3167–3173 |

---

## 7. Remediere propusă V38

### 7.1 Anomalia 1 — Rates dinamice

| Pas | Acțiune |
|-----|---------|
| 1 | Modul comun `macro_rates.py` — extrage scraping + merge |
| 2 | `handle_rates_command()` → `_get_effective_rates()` |
| 3 | Badge live/fallback + timestamp în card Telegram |
| 4 | Sync periodic baseline `CENTRAL_BANK_RATES` |

### 7.2 Anomalia 2 — Macro Anchor

| Pas | Acțiune |
|-----|---------|
| 1 | **Regulă macro obligatorie:** ultimele 4–5 swing highs = LH **și** swing lows = LL → bias **BEARISH locked**; BOS/CHoCH bullish minor nu flip-uiește fără invalidare macro |
| 2 | **V25 patch:** când macro swings = bearish, BOS bullish post-pullback → `MONITORING counter-trend`, nu `WAITING_D1_PULLBACK` LONG |
| 3 | **SMART MERGE refresh:** direcție nouă ≠ direcție activă → `INVALIDATED_BIAS_FLIP` |
| 4 | **Crypto profile:** macro window extins pentru BTCUSD |
| 5 | **Consistență:** `determine_daily_trend()` și `scan_for_setup()` — aceeași regulă V25 (choch≥bos) |

### 7.3 Reguli SMC protejate (nu se modifică)

- Body-close CHoCH/BOS
- P/D guard la READY
- CHoCH ≤3 bars + in FVG (radar)
- `h4_structure_locked`, RR ≥2, MIN_SL 30p

---

## 8. Fișiere auditate

| Fișier | Rol în audit |
|--------|--------------|
| `telegram_command_center.py` | `/rates` static, `/btcusd` din JSON |
| `news_calendar_monitor.py` | Rates live (neconectat la `/rates`) |
| `smc_detector.py` | `determine_daily_trend()`, V25 bias, momentum |
| `daily_scanner.py` | bias_fallback, V33 SMART MERGE |
| `pairs_config.json` | lookback 365 daily pentru BTCUSD |

---

## 9. Concluzie

**Anomalia 1 (REZOLVATĂ V38):** Cardul Telegram foloseste acum `macro_rates.py` — fetch live investing.com + cache pe VPS. Ratele vechi hardcodate (NZD 5.25% etc.) erau depasite cu pana la 3%. cTrader IC Markets furnizeaza swap live, nu rate oficiale CB.

**Anomalia 2 (OPEN):** BTCUSD BUY pe structura bearish — Macro Anchor V38 ramane de implementat (task separat).

---

🔱 **AUTHORED BY ФорексГод** 🔱  
🏛 **GLITCH IN MATRIX — APOLLO V37 AUDIT** 🏛
