# 📊 Multi-Timeframe Strategy - Daily → 1H → 4H

**Glitch In Matrix v3.1 - Triple Timeframe Confirmation System**

---

## 🎯 OBIECTIV

Îmbunătățirea sistemului actual (Daily → 4H) prin adăugarea **1H timeframe** ca nivel intermediar de confirmare, rezultând în:

- ✅ **Entry mai rapid** - 1H confirmă pullback finish mai devreme decât 4H
- ✅ **Mai mult profit captat** - intri când 20-30% din mișcare e făcută vs 40-50% cu 4H
- ✅ **Flexibilitate** - 1H primary, 4H fallback (safety net)
- ✅ **Adaptabilitate** - perechi volatile (GBP, XAU) → 1H, perechi lente (CHF, NZD) → 4H

---

## 🏗️ ARHITECTURA ACTUALĂ (v3.0)

### Flow Actual: Daily → 4H

```
┌─────────────────────────────────────────────────────────┐
│ DAILY TIMEFRAME (Strategic Layer)                      │
├─────────────────────────────────────────────────────────┤
│ Scanner runs: 08:00 daily                              │
│                                                         │
│ Detectează:                                            │
│ 1. Daily CHoCH (trend reversal/continuation)          │
│ 2. Daily FVG (premium/discount zone)                  │
│ 3. Entry point (inside FVG at 35%)                    │
│ 4. Stop Loss (from pullback swing)                    │
│ 5. Take Profit (next Daily structure)                 │
│                                                         │
│ Output: Setup cu status MONITORING                     │
└─────────────────────────────────────────────────────────┘
                         ↓
                    Wait for...
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 4H TIMEFRAME (Tactical Layer)                          │
├─────────────────────────────────────────────────────────┤
│ Monitor runs: Every 30 seconds                         │
│                                                         │
│ Așteaptă:                                              │
│ 1. Price touches FVG zone                             │
│ 2. 4H CHoCH confirms pullback finished                │
│    - Lookback: 50 candles (200 hours = 8+ days)      │
│    - Max age: 12 candles (48 hours)                  │
│    - Momentum: ≥1 candle after CHoCH continues trend  │
│                                                         │
│ Când confirmat → EXECUTE trade                        │
└─────────────────────────────────────────────────────────┘
```

### ⚠️ PROBLEME IDENTIFICATE

1. **Gap prea mare Daily → 4H:**
   ```
   Daily CHoCH at 100.00
          ↓ (Pullback starts)
   Price enters FVG at 100.50
          ↓ (Wait for 4H CHoCH...)
   4H CHoCH at 100.80 ← Entry aici
          ↓
   Price reaches 101.50 (TP)
   
   Profit captat: 101.50 - 100.80 = 70 pips
   Profit pierdut: 100.80 - 100.50 = 30 pips (43% din mișcare!)
   ```

2. **Timing inconsistent:**
   - GBP/XAU: 4H CHoCH vine rapid (4-8 ore) → OK
   - USD majors: 4H CHoCH vine în 12-24 ore → Acceptable
   - NZD/AUD/CHF: 4H CHoCH vine în 24-48 ore → **Entry prea târziu**

3. **Miss opportunities:**
   - Unele setups au 1H CHoCH clar la 6-12 ore
   - Dar sistemul așteaptă 4H CHoCH la 24-48 ore
   - Între timp, 50% din mișcare pierdută

---

## 🚀 ARHITECTURA NOUĂ (v3.1)

### Flow Nou: Daily → 1H (Entry 1) → 4H (Entry 2 - Scale In)

```
┌─────────────────────────────────────────────────────────┐
│ DAILY TIMEFRAME (Strategic Layer)                      │
├─────────────────────────────────────────────────────────┤
│ Scanner runs: 08:00 daily                              │
│                                                         │
│ Detectează:                                            │
│ • Daily CHoCH + FVG                                    │
│ • Calculează Entry/SL/TP                              │
│                                                         │
│ Output: Setup cu status MONITORING                     │
│         Strategy: SCALE_IN (1H → 4H double entry)     │
└─────────────────────────────────────────────────────────┘
                         ↓
                    Wait for...
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 1H TIMEFRAME (Entry 1 - Aggressive) ⭐ NEW             │
├─────────────────────────────────────────────────────────┤
│ Monitor runs: Every 30 seconds                         │
│ Priority: HIGH (check 1H first)                        │
│                                                         │
│ Condiții:                                              │
│ 1. ✅ Price in FVG zone                               │
│ 2. ✅ 1H CHoCH detected                               │
│    - Lookback: 50 candles (50 hours = 2+ days)       │
│    - Max age: 12 candles (12 hours)                  │
│    - Momentum: ≥1 candle continues trend              │
│ 3. ✅ 1H CHoCH aligned with Daily direction           │
│                                                         │
│ Action: EXECUTE ENTRY 1                                │
│ • Position size: 50% of planned capital               │
│ • Entry: Current price (early entry)                  │
│ • SL: From pullback swing                             │
│ • Status: PARTIAL_FILLED (waiting 4H confirmation)    │
│                                                         │
│ ⏰ Start 4H confirmation timer (max 48h)              │
└─────────────────────────────────────────────────────────┘
                         │
                    Continue monitoring...
                         ↓
┌─────────────────────────────────────────────────────────┐
│ 4H TIMEFRAME (Entry 2 - Scale In Confirmation)        │
├─────────────────────────────────────────────────────────┤
│ Activare: ALWAYS checked după Entry 1 (1H)            │
│ Timeout: Max 48h după Entry 1                         │
│                                                         │
│ Scenarii:                                              │
│                                                         │
│ 🟢 Scenario A: 4H CHoCH CONFIRMĂ (best case)         │
│    ├─ 4H CHoCH detected în 12-48h                    │
│    ├─ Price still trending                            │
│    └─ Action:                                          │
│       • EXECUTE ENTRY 2                               │
│       • Position size: 50% (remaining capital)        │
│       • Adjust SL to breakeven for Entry 1            │
│       • Status: FULL_FILLED (double conviction)       │
│       • Total position: 100% capital                  │
│                                                         │
│ 🟡 Scenario B: 4H CHoCH NU confirmă dar 1H profitabil│
│    ├─ După 48h, no 4H CHoCH                          │
│    ├─ Dar Entry 1 in profit > 20 pips                │
│    └─ Action:                                          │
│       • KEEP Entry 1 only                             │
│       • Move SL to breakeven                          │
│       • Status: SINGLE_ENTRY (1H only)                │
│       • Let it run to TP                              │
│                                                         │
│ 🔴 Scenario C: 4H NU confirmă și 1H în pierdere     │
│    ├─ După 48h, no 4H CHoCH                          │
│    ├─ Entry 1 in loss sau flat                       │
│    └─ Action:                                          │
│       • CLOSE Entry 1 @ breakeven/small loss          │
│       • Status: CLOSED_EARLY (no confirmation)        │
│       • Capital freed for other setups                │
└─────────────────────────────────────────────────────────┘
                         │
                    After 72 hours total...
                         ↓
                  ⏰ SETUP EXPIRED
              (If no action taken)
```

---

## 📐 LOGICA DETALIATĂ - SCALE IN STRATEGY

### Priority System: 1H Entry → 4H Scale In

```python
def validate_choch_confirmation_scale_in(setup, current_time):
    """
    Scale-in validation: 
    - Entry 1 (50% capital) on 1H CHoCH
    - Entry 2 (50% capital) on 4H CHoCH
    - Smart exit if 4H doesn't confirm
    """
    
    setup_age_hours = calculate_age(setup.created_at, current_time)
    has_entry1 = setup.get('entry1_filled', False)
    entry1_time = setup.get('entry1_time')
    entry1_price = setup.get('entry1_price')
    
    # ═══════════════════════════════════════════════════════
    # LEVEL 1: CHECK EXPIRY (highest priority)
    # ═══════════════════════════════════════════════════════
    if setup_age_hours > 72:
        # If Entry 1 exists but no Entry 2 → close Entry 1
        if has_entry1:
            return {
                'action': 'CLOSE_ENTRY1',
                'reason': 'Setup expired, 4H never confirmed',
                'status': 'EXPIRED',
                'close_at': 'current_market_price'
            }
        else:
            return {
                'action': 'EXPIRE',
                'reason': 'No entry taken in 72h',
                'status': 'EXPIRED'
            }
    
    # ═══════════════════════════════════════════════════════
    # LEVEL 2: CHECK 1H CHoCH (Entry 1 - 50% capital)
    # ═══════════════════════════════════════════════════════
    if not has_entry1:
        # No Entry 1 yet → check for 1H CHoCH
        h1_choch = check_1h_choch(setup)
        
        if h1_choch.detected and h1_choch.valid:
            return {
                'action': 'EXECUTE_ENTRY1',
                'timeframe': '1H',
                'choch': h1_choch,
                'position_size': 0.5,  # 50% capital
                'entry_type': 'AGGRESSIVE',
                'status': 'PARTIAL_FILLED',
                'next_step': 'Wait for 4H CHoCH (max 48h)',
                'setup_age': setup_age_hours
            }
        else:
            # 1H not confirmed yet
            return {
                'action': 'WAIT',
                'waiting_for': '1H CHoCH (Entry 1)',
                'status': 'MONITORING',
                'setup_age': setup_age_hours
            }
    
    # ═══════════════════════════════════════════════════════
    # LEVEL 3: CHECK 4H CHoCH (Entry 2 - Scale In)
    # ═══════════════════════════════════════════════════════
    # Entry 1 already filled → check for 4H confirmation
    entry1_age_hours = calculate_age(entry1_time, current_time)
    current_price = get_current_price(setup['symbol'])
    
    # Calculate Entry 1 P&L
    if setup['direction'] == 'BUY':
        entry1_pnl_pips = (current_price - entry1_price) * 10000
    else:
        entry1_pnl_pips = (entry1_price - current_price) * 10000
    
    # Check 4H CHoCH
    h4_choch = check_4h_choch(setup)
    
    if h4_choch.detected and h4_choch.valid:
        # 🟢 Scenario A: 4H CONFIRMĂ → Scale In (Entry 2)
        return {
            'action': 'EXECUTE_ENTRY2',
            'timeframe': '4H',
            'choch': h4_choch,
            'position_size': 0.5,  # Remaining 50% capital
            'entry_type': 'CONFIRMATION',
            'status': 'FULL_FILLED',
            'entry1_pnl': entry1_pnl_pips,
            'total_position': 1.0,  # 100% capital now
            'sl_adjustment': 'Move Entry1 SL to breakeven',
            'setup_age': setup_age_hours
        }
    
    # 4H not confirmed yet → decision based on Entry 1 performance
    if entry1_age_hours >= 48:
        # Been 48h since Entry 1, no 4H confirmation
        
        if entry1_pnl_pips >= 20:
            # 🟡 Scenario B: Entry 1 profitable, keep it
            return {
                'action': 'KEEP_ENTRY1_ONLY',
                'reason': 'Entry 1 profitable, no 4H needed',
                'status': 'SINGLE_ENTRY',
                'entry1_pnl': entry1_pnl_pips,
                'sl_adjustment': 'Move to breakeven',
                'let_run_to_tp': True
            }
        else:
            # 🔴 Scenario C: Entry 1 not profitable, close it
            return {
                'action': 'CLOSE_ENTRY1',
                'reason': 'No 4H confirmation, Entry 1 not profitable',
                'status': 'CLOSED_EARLY',
                'entry1_pnl': entry1_pnl_pips,
                'close_at': 'breakeven_or_small_loss',
                'capital_freed': True
            }
    
    # ═══════════════════════════════════════════════════════
    # LEVEL 4: CONTINUE MONITORING (Entry 1 active, waiting 4H)
    # ═══════════════════════════════════════════════════════
    return {
        'action': 'WAIT',
        'waiting_for': '4H CHoCH (Entry 2 scale in)',
        'status': 'PARTIAL_FILLED',
        'entry1_active': True,
        'entry1_pnl': entry1_pnl_pips,
        'entry1_age': entry1_age_hours,
        'timeout_in': 48 - entry1_age_hours  # Hours remaining
    }
```

---

## 🔍 VALIDARE CHoCH DETALIATĂ

### 1H CHoCH Validation (Primary)

```python
def validate_1h_choch(df_1h, daily_trend, fvg):
    """
    Validează 1H CHoCH pentru confirmare pullback finish
    
    Parameters:
    - df_1h: DataFrame cu 225 candles 1H (225 hours = 9+ days)
    - daily_trend: 'bullish' sau 'bearish' (din Daily CHoCH)
    - fvg: FVG object (Daily FVG zone)
    
    Returns:
    - detected: bool
    - valid: bool
    - choch: CHoCH object
    - age_candles: int
    """
    
    # Step 1: Detect all 1H CHoCHs
    all_chochs = detect_choch(df_1h)
    
    # Step 2: Filter RECENT CHoCHs (last 50 candles = 50 hours)
    recent_chochs = [
        ch for ch in all_chochs
        if ch.index >= len(df_1h) - 50
    ]
    
    if not recent_chochs:
        return {'detected': False, 'reason': 'No recent 1H CHoCH'}
    
    # Step 3: Validate each CHoCH
    for choch in recent_chochs:
        
        # ─────────────────────────────────────────────
        # Validation 1: DIRECTION ALIGNMENT
        # ─────────────────────────────────────────────
        if choch.direction != daily_trend:
            continue  # CHoCH nu se aliniază cu Daily trend
        
        # ─────────────────────────────────────────────
        # Validation 2: AGE CHECK (max 12 candles = 12h)
        # ─────────────────────────────────────────────
        choch_age = len(df_1h) - 1 - choch.index
        if choch_age > 12:
            continue  # CHoCH prea vechi (>12 ore)
        
        # ─────────────────────────────────────────────
        # Validation 3: LOCATION CHECK (after FVG touch)
        # ─────────────────────────────────────────────
        choch_time = df_1h.iloc[choch.index]['time']
        fvg_time = fvg.candle_time
        
        if choch_time < fvg_time:
            continue  # CHoCH înainte de FVG formation (invalid)
        
        # ─────────────────────────────────────────────
        # Validation 4: MOMENTUM CONFIRMATION
        # ─────────────────────────────────────────────
        # Check if at least 1 candle AFTER CHoCH continues trend
        candles_after = df_1h.iloc[choch.index + 1:]
        
        if len(candles_after) < 1:
            continue  # Nu sunt candles după CHoCH (too fresh)
        
        if daily_trend == 'bullish':
            # Count bullish candles after CHoCH
            bullish_count = sum(
                1 for _, c in candles_after.iterrows()
                if c['close'] > c['open']
            )
            if bullish_count < 1:
                continue  # Nu există bullish momentum
        
        else:  # bearish
            # Count bearish candles after CHoCH
            bearish_count = sum(
                1 for _, c in candles_after.iterrows()
                if c['close'] < c['open']
            )
            if bearish_count < 1:
                continue  # Nu există bearish momentum
        
        # ─────────────────────────────────────────────
        # ✅ ALL VALIDATIONS PASSED
        # ─────────────────────────────────────────────
        return {
            'detected': True,
            'valid': True,
            'choch': choch,
            'age_candles': choch_age,
            'age_hours': choch_age * 1,  # 1H candles
            'timeframe': '1H'
        }
    
    # ❌ No valid CHoCH found
    return {
        'detected': len(recent_chochs) > 0,
        'valid': False,
        'reason': 'CHoCH detected but failed validation'
    }
```

### 4H CHoCH Validation (Fallback - Same Logic)

```python
def validate_4h_choch(df_4h, daily_trend, fvg):
    """
    Validare identică cu 1H, doar timeframe diferit:
    - Lookback: 50 candles = 200 hours (8+ days)
    - Max age: 12 candles = 48 hours
    - Momentum: ≥1 candle after CHoCH
    """
    # Same validation logic as 1H
    # Only difference: 
    #   - age_hours = choch_age * 4 (4H candles)
    #   - timeframe = '4H'
```

---

## ⏰ TIMING EXAMPLES - SCALE IN STRATEGY

### Exemplu 1: 4H Confirmă (Best Case - Full Scale In)

```
Day 1, 08:00 - Daily Scanner
├─ EURUSD Daily CHoCH + FVG detected
├─ Entry target: 1.1000 (inside FVG)
├─ SL: 1.0950
├─ TP: 1.1150
└─ Status: MONITORING (waiting 1H CHoCH for Entry 1)

Day 1, 14:00 (6 hours later) - 1H CHoCH detected → ENTRY 1
├─ 1H CHoCH confirmed pullback finish
├─ Action: EXECUTE ENTRY 1 (50% capital)
├─ Entry 1 filled: 1.1005
├─ Position: 0.5 lot BUY @ 1.1005
├─ SL: 1.0950
├─ Status: PARTIAL_FILLED (waiting 4H CHoCH for Entry 2)
└─ Timer: 48h countdown for 4H confirmation

Day 2, 04:00 (14 hours after Entry 1) - 4H CHoCH detected → ENTRY 2
├─ 4H CHoCH confirmed trend continuation
├─ Current price: 1.1025 (Entry 1 in +20 pips profit)
├─ Action: EXECUTE ENTRY 2 (50% capital)
├─ Entry 2 filled: 1.1025
├─ Total position: 1.0 lot BUY
│  ├─ Entry 1: 0.5 lot @ 1.1005
│  └─ Entry 2: 0.5 lot @ 1.1025
├─ Average entry: 1.1015
├─ SL adjustment: Move Entry 1 SL to 1.1005 (breakeven)
├─ Status: FULL_FILLED (double conviction)
└─ Running to TP: 1.1150

Day 3, 08:00 (48 hours after setup)
├─ Price reached: 1.1130
├─ Entry 1 profit: (1.1130 - 1.1005) × 50,000 = +62.5 pips
├─ Entry 2 profit: (1.1130 - 1.1025) × 50,000 = +52.5 pips
├─ Total profit: 115 pips (on 1.0 lot average)
└─ Still running toward TP 1.1150

Result:
✅ Entry 1 timing: EARLY (6h after setup)
✅ Entry 2 timing: CONFIRMATION (20h after setup)
✅ Total profit: 115 pips (75% of move captured)
✅ Risk managed: Entry 1 SL to breakeven after Entry 2
✅ Double conviction: Both 1H and 4H aligned
```

### Exemplu 2: 4H Nu Confirmă dar Entry 1 Profitabil (Single Entry Success)

```
Day 1, 08:00 - Daily Scanner
├─ GBPUSD Daily CHoCH + FVG detected
├─ Entry target: 1.3500
├─ SL: 1.3450
├─ TP: 1.3650
└─ Status: MONITORING

Day 1, 12:00 (4 hours later) - 1H CHoCH detected → ENTRY 1
├─ 1H CHoCH confirmed
├─ Entry 1 filled: 1.3505
├─ Position: 0.5 lot BUY @ 1.3505
├─ Status: PARTIAL_FILLED (waiting 4H)
└─ Timer: 48h for 4H confirmation

Day 1, 12:00 → Day 3, 12:00 (48 hours)
├─ Price trending up: 1.3505 → 1.3575
├─ Entry 1 P&L: +70 pips (profitable!)
├─ 4H CHoCH: NOT detected (price moved too fast)
└─ Decision time: Keep or close Entry 1?

Day 3, 12:00 (48h after Entry 1) - Management Decision
├─ Entry 1 in +70 pips profit (>20 pips threshold)
├─ Action: KEEP ENTRY 1 ONLY
├─ SL adjustment: Move to breakeven (1.3505)
├─ Status: SINGLE_ENTRY (no Entry 2 needed)
├─ Let run to TP: 1.3650
└─ 4H confirmation not needed (1H was right!)

Day 4, 08:00
├─ Price reached: 1.3620
├─ Entry 1 profit: +115 pips (on 0.5 lot)
└─ Close at TP or trailing

Result:
✅ Entry 1 alone successful
⚠️ Entry 2 never filled (4H too slow)
✅ Profit: 115 pips on 50% capital
💡 Could have been 115 pips on 100% if full entry at 1H
```

### Exemplu 3: 4H Nu Confirmă și Entry 1 în Pierdere (Early Exit)

```
Day 1, 08:00 - Daily Scanner
├─ NZDUSD Daily CHoCH + FVG detected
├─ Entry target: 0.5740
├─ SL: 0.5720
├─ TP: 0.5810
└─ Status: MONITORING

Day 1, 16:00 (8 hours later) - 1H CHoCH detected → ENTRY 1
├─ 1H CHoCH confirmed (looked valid)
├─ Entry 1 filled: 0.5745
├─ Position: 0.5 lot BUY @ 0.5745
├─ Status: PARTIAL_FILLED
└─ Waiting 4H confirmation...

Day 1, 16:00 → Day 3, 16:00 (48 hours)
├─ Price choppy: 0.5745 → 0.5735 → 0.5740 → 0.5738
├─ Entry 1 P&L: -7 pips (slight loss)
├─ 4H CHoCH: NOT detected (no clear trend)
├─ FVG zone: Price re-entering/exiting (invalidation signal)
└─ Decision: 1H was FALSE SIGNAL

Day 3, 16:00 (48h after Entry 1) - Protection Trigger
├─ Entry 1 in -7 pips loss (<20 pips profit threshold)
├─ No 4H confirmation → setup questionable
├─ Action: CLOSE ENTRY 1 @ breakeven
├─ Close at: 0.5744 (-1 pip loss, acceptable)
├─ Status: CLOSED_EARLY
├─ Capital freed: 50% capital available for other setups
└─ Avoided full position loss if had gone to SL

Result:
⚠️ Entry 1 was false signal (1H too aggressive)
✅ 4H protection worked (didn't scale in)
✅ Small loss: -1 pip on 50% capital
✅ Avoided: -20 pips loss if full position taken
💡 Safety net validated: 4H confirmation crucial
```

### Exemplu 4: Ambele Entries Hit SL (Worst Case - Rare)

```
Day 1, 08:00 - Daily Scanner
├─ XAUUSD Daily CHoCH + FVG detected
├─ Entry target: 2050
├─ SL: 2040
├─ TP: 2080
└─ Status: MONITORING

Day 1, 10:00 (2 hours) - 1H CHoCH → ENTRY 1
├─ Entry 1 filled: 2051
├─ Position: 0.5 lot BUY @ 2051
└─ Waiting 4H...

Day 1, 18:00 (8h after Entry 1) - 4H CHoCH → ENTRY 2
├─ 4H confirmed, price at 2055
├─ Entry 2 filled: 2055
├─ Total: 1.0 lot BUY (avg 2053)
├─ SL Entry 1: moved to 2051 (breakeven)
└─ SL Entry 2: 2040 (original)

Day 2, 02:00 - News Spike
├─ Unexpected news → price spikes down
├─ Entry 1 SL hit: 2051 (breakeven, 0 pips)
├─ Entry 2 SL hit: 2040 (-15 pips on 0.5 lot)
└─ Total loss: -7.5 pips (averaged)

Result:
❌ Both entries stopped out
✅ Entry 1 protected at breakeven (0 loss)
⚠️ Entry 2 took -15 pips
💡 Scale in REDUCED loss vs single full entry:
   - Full entry @ 2051 → SL 2040 = -11 pips
   - Scale in avg 2053 → mixed SL = -7.5 pips
   - Saved: 3.5 pips per lot
```

---

## 📊 EXPECTED PERFORMANCE IMPACT

### Before (Daily → 4H Only)

| Metric | Current (4H only) |
|--------|-------------------|
| **Average entry timing** | 24-48h after setup |
| **% of move captured** | 50-60% |
| **False signals** | Low (3-5%) |
| **Missed opportunities** | Medium (15-20%) |
| **Win rate** | 60-65% |

### After (Daily → 1H → 4H)

| Metric | Expected (1H primary, 4H fallback) |
|--------|-------------------------------------|
| **Average entry timing** | 6-12h (1H) or 24-48h (4H) |
| **% of move captured** | 70-80% (1H) or 50-60% (4H) |
| **False signals** | Medium (8-12%) - 1H mai volatil |
| **Missed opportunities** | Low (5-10%) - fallback la 4H |
| **Win rate** | 60-70% (target +5-10%) |

### Trade-offs

**Pros:**
- ✅ **+20-30% more profit** per trade (earlier entry)
- ✅ **+10-15% more setups** executed (1H confirmă când 4H nu)
- ✅ **Better risk/reward** - entry mai aproape de SL
- ✅ **Flexibility** - fast pairs (1H), slow pairs (4H fallback)

**Cons:**
- ⚠️ **+5-7% false signals** - 1H mai volatil decât 4H
- ⚠️ **Complexity +30%** - triple timeframe analysis
- ⚠️ **Data fetch +50%** - 225 candles × 3 timeframes vs 2

**Net Impact:** ✅ **Positive** - profit gains outweigh false signal risk

---

## 🎯 CONFIGURARE PER PERECHE

### pairs_config.json - New Settings

```json
{
  "pairs": [
    {
      "symbol": "EURUSD",
      "priority": 1,
      "choch_preference": "1H",
      "fallback_enabled": true,
      "fallback_delay_hours": 24,
      "expiry_hours": 72
    },
    {
      "symbol": "GBPUSD",
      "priority": 1,
      "choch_preference": "1H",
      "fallback_enabled": true,
      "fallback_delay_hours": 16,
      "expiry_hours": 48,
      "notes": "GBP volatile - 1H confirmă rapid, reduce fallback delay"
    },
    {
      "symbol": "NZDUSD",
      "priority": 1,
      "choch_preference": "1H",
      "fallback_enabled": true,
      "fallback_delay_hours": 32,
      "expiry_hours": 96,
      "notes": "NZD lent - mărește fallback delay, permite mai mult timp"
    },
    {
      "symbol": "XAUUSD",
      "priority": 1,
      "choch_preference": "1H",
      "fallback_enabled": true,
      "fallback_delay_hours": 12,
      "expiry_hours": 48,
      "notes": "XAU foarte volatil - 1H perfect, 4H raramente necesar"
    }
  ],
  
  "scanner_settings": {
    "lookback_candles": {
      "daily": 365,
      "h4": 225,
      "h1": 225
    },
    
    "choch_validation": {
      "h1": {
        "lookback": 50,
        "max_age": 12,
        "momentum_confirmation": true,
        "min_candles_after": 1
      },
      "h4": {
        "lookback": 50,
        "max_age": 12,
        "momentum_confirmation": true,
        "min_candles_after": 1
      }
    },
    
    "execution_priority": {
      "primary": "1H",
      "fallback": "4H",
      "default_fallback_delay": 24,
      "default_expiry": 72
    }
  }
}
```

---

## 🧪 TESTING PLAN

### Phase 1: Backtest Comparison

```python
# Test pe același historical data:
# 1. Current system (4H only)
# 2. New system (1H primary, 4H fallback)

backtest_configs = [
    {
        'name': 'Current (4H only)',
        'timeframes': ['Daily', '4H'],
        'choch_source': '4H'
    },
    {
        'name': 'New (1H primary)',
        'timeframes': ['Daily', '1H', '4H'],
        'choch_source': '1H',
        'fallback': '4H',
        'fallback_delay': 24
    }
]

# Compare metrics:
# - Total setups detected
# - Total trades executed
# - Win rate
# - Average profit per trade
# - Average entry timing
# - % of move captured
```

### Phase 2: Paper Trading (2 weeks)

```
Week 1-2: Run both systems in parallel
├─ System A (current): Uses 4H CHoCH only
├─ System B (new): Uses 1H primary, 4H fallback
└─ Compare results daily in spreadsheet

Metrics to track:
- Entry timing difference (hours)
- Profit difference (pips)
- False signals count
- Win rate variance
```

### Phase 3: Live Trading (Gradual Rollout)

```
Week 3: Enable 1H for 3 fast pairs only
├─ GBPUSD, EURUSD, XAUUSD
└─ Monitor closely

Week 4: Enable 1H for 7 more pairs
├─ Add USD majors
└─ Keep monitoring

Week 5+: Full rollout if Week 3-4 successful
└─ Enable all 15 pairs
```

---

## 🚨 RISK MANAGEMENT

### Safeguards Implemented

1. **Fallback Safety Net:**
   - Dacă 1H dă false signal → 4H încă disponibil
   - Nu pierdem oportunități din cauza 1H volatilitate

2. **Expiry Protection:**
   - Max 72h monitoring → previne setups "zombie"
   - Capital nu rămâne blocat în setups invalide

3. **Alignment Validation:**
   - 1H CHoCH TREBUIE aligned cu Daily trend
   - Previne contra-trend entries

4. **Momentum Confirmation:**
   - Minim 1 candle după CHoCH confirmă trend
   - Reduce false breakouts

5. **Age Validation:**
   - Max 12 candles age (12h pentru 1H, 48h pentru 4H)
   - Doar CHoCH recente sunt considerate valide

---

## 📈 SUCCESS CRITERIA

### Minimum Requirements (Go/No-Go)

Pentru a considera 1H integration SUCCESS:

1. ✅ **Win rate ≥ 55%** (minimum acceptable)
2. ✅ **Average profit per trade ≥ current system** 
3. ✅ **False signals ≤ 15%** (max tolerabil)
4. ✅ **Entry timing improvement ≥ 30%** (faster by 8-12h)
5. ✅ **System stability** - zero crashes în 2 weeks paper trading

### Rollback Trigger

Dacă oricare din următoarele:
- ❌ Win rate < 50% after 20 trades
- ❌ False signals > 20%
- ❌ System crashes > 2 in 1 week
- ❌ Data fetch failures > 10%

→ **ROLLBACK** to 4H only system immediately

---

## 📝 NEXT STEPS

1. ✅ **Documentation complete** (acest document)
2. ⏳ **Code implementation:**
   - Update `smc_detector.py` - add `validate_1h_choch()`
   - Update `daily_scanner.py` - fetch 1H data
   - Update `setup_executor_monitor.py` - priority logic
   - Update `pairs_config.json` - add 1H settings
3. ⏳ **Unit testing** - test CHoCH validation isolated
4. ⏳ **Integration testing** - test full flow Daily → 1H → 4H
5. ⏳ **Backtest** - compare 4H vs 1H on historical data
6. ⏳ **Paper trading** - 2 weeks parallel run
7. ⏳ **Live rollout** - gradual 3 → 7 → 15 pairs

---

**Status:** 📚 **DOCUMENTATION COMPLETE** - Ready for implementation review

**Author:** ForexGod  
**Date:** 2026-01-08  
**Version:** v3.1 Strategy Design  
**System:** Glitch In Matrix  
