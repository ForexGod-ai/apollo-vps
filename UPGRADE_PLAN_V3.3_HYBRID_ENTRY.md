# 🚀 UPGRADE PLAN V3.3 - Hybrid Entry Logic
**Target:** Fix pullback entry bug and restore 625% backtest performance  
**Priority:** CRITICAL  
**Estimated Time:** 1-2 days implementation + 1 week testing  
**Risk Level:** LOW (backward compatible, can rollback to V3.2)

---

## 📋 UPGRADE CHECKLIST

### Phase 1: Code Implementation (Day 1)
- [ ] 1.1 Update `validate_pullback_entry()` in smc_detector.py
- [ ] 1.2 Add `check_continuation_momentum()` function
- [ ] 1.3 Update `_check_pullback_entry()` in setup_executor_monitor.py
- [ ] 1.4 Add `continuation_check_hours` to pairs_config.json
- [ ] 1.5 Reduce timeout from 24h to 12h
- [ ] 1.6 Update entry action types (EXECUTE_ENTRY1_CONTINUATION)
- [ ] 1.7 Update Telegram notification messages

### Phase 2: Testing (Day 2)
- [ ] 2.1 Unit test: Pullback entry (within 10 pips)
- [ ] 2.2 Unit test: Continuation entry (after 6h + momentum)
- [ ] 2.3 Unit test: Timeout handling (reasonable distance)
- [ ] 2.4 Integration test: Full cycle (setup → entry → close)
- [ ] 2.5 Backtest V3.3 with 12-month data
- [ ] 2.6 Compare: V3.3 vs V3.2 vs V2.1

### Phase 3: Paper Trading (Week 1)
- [ ] 3.1 Deploy to paper account (reduced risk: 0.5% per trade)
- [ ] 3.2 Monitor XAUUSD, BTCUSD, GBPJPY (fast movers)
- [ ] 3.3 Verify continuation entries trigger correctly
- [ ] 3.4 Check logs for "EXECUTE_ENTRY1_CONTINUATION" messages
- [ ] 3.5 Track: entry count, win rate, avg R:R

### Phase 4: Live Deployment (Week 2)
- [ ] 4.1 Review paper trading results (min 10 trades)
- [ ] 4.2 Deploy to live account (1% risk per trade)
- [ ] 4.3 Monitor for 3 days (compare to V3.2 performance)
- [ ] 4.4 Gradually increase to 2% risk if stable
- [ ] 4.5 Document lessons learned

---

## 🔧 CODE CHANGES

### 1. Update `smc_detector.py` - Add Continuation Detection

**Location:** After line 2309 (end of file)

```python
def check_continuation_momentum(
    df_h1: pd.DataFrame,
    direction: str,
    lookback_candles: int = 3,
    atr_multiplier: float = 1.5
) -> dict:
    """
    V3.3: Check if price shows strong continuation momentum
    
    Requirements:
    1. 3+ consecutive candles in trend direction
    2. ATR not contracting (momentum maintained)
    3. No significant counter-trend wicks
    
    Args:
        df_h1: 1H timeframe dataframe
        direction: 'bullish' or 'bearish'
        lookback_candles: Number of recent candles to check (default 3)
        atr_multiplier: ATR expansion threshold (default 1.5)
    
    Returns:
        {
            'has_momentum': bool,
            'consecutive_candles': int,
            'atr_expanding': bool,
            'current_price': float,
            'momentum_score': float (0-100)
        }
    """
    if len(df_h1) < lookback_candles + 14:  # Need 14 for ATR
        return {'has_momentum': False, 'reason': 'Insufficient data'}
    
    recent_candles = df_h1.iloc[-lookback_candles:]
    current_price = df_h1.iloc[-1]['close']
    
    # Check 1: Consecutive candles in trend direction
    consecutive_count = 0
    for idx, candle in recent_candles.iterrows():
        if direction == 'bullish':
            is_bullish = candle['close'] > candle['open']
            if is_bullish:
                consecutive_count += 1
            else:
                break  # Stop if bearish candle found
        else:
            is_bearish = candle['close'] < candle['open']
            if is_bearish:
                consecutive_count += 1
            else:
                break
    
    # Check 2: ATR expansion (momentum strength)
    atr_current = (df_h1['high'] - df_h1['low']).rolling(14).mean().iloc[-1]
    atr_previous = (df_h1['high'] - df_h1['low']).rolling(14).mean().iloc[-15]
    atr_expanding = atr_current >= (atr_previous * 0.9)  # Allow slight contraction
    
    # Check 3: Price movement strength (total pips moved)
    price_start = recent_candles.iloc[0]['open']
    price_end = current_price
    price_move_pct = abs(price_end - price_start) / price_start * 100
    
    # Check 4: Counter-trend wick analysis (rejection wicks reduce confidence)
    rejection_wicks = 0
    for idx, candle in recent_candles.iterrows():
        body = abs(candle['close'] - candle['open'])
        total_range = candle['high'] - candle['low']
        
        if direction == 'bullish':
            upper_wick = candle['high'] - max(candle['open'], candle['close'])
            if upper_wick > body * 1.5:  # Upper wick > 1.5x body = rejection
                rejection_wicks += 1
        else:
            lower_wick = min(candle['open'], candle['close']) - candle['low']
            if lower_wick > body * 1.5:
                rejection_wicks += 1
    
    # Calculate momentum score (0-100)
    score = 0
    score += min(consecutive_count / lookback_candles * 40, 40)  # Max 40 pts
    score += 20 if atr_expanding else 0  # 20 pts for ATR
    score += min(price_move_pct * 20, 30)  # Max 30 pts for price move
    score -= rejection_wicks * 10  # Penalty for rejection wicks
    score = max(0, min(100, score))
    
    # Decision: Has momentum if score ≥ 60
    has_momentum = (consecutive_count >= 3 and score >= 60)
    
    return {
        'has_momentum': has_momentum,
        'consecutive_candles': consecutive_count,
        'atr_expanding': atr_expanding,
        'current_price': round(current_price, 5),
        'momentum_score': round(score, 1),
        'price_move_pct': round(price_move_pct, 2),
        'rejection_wicks': rejection_wicks
    }
```

---

### 2. Update `setup_executor_monitor.py` - Hybrid Entry Logic

**Location:** Replace `_check_pullback_entry()` method (lines 145-285)

```python
def _check_pullback_entry(self, setup: dict, df_h1, symbol: str) -> dict:
    """
    V3.3 HYBRID ENTRY: Pullback OR Continuation
    
    Flow:
    1. Check if CHoCH already detected (stored in setup)
    2. If not, detect 1H CHoCH in FVG zone
    3. Calculate Fibonacci 50% from CHoCH swing
    4. Check if current price within tolerance of Fibo 50%
    5. If YES → EXECUTE_ENTRY1 (optimal pullback entry)
    6. If NO (after 6h) → Check continuation momentum
       - If strong momentum → EXECUTE_ENTRY1_CONTINUATION
       - If weak momentum → KEEP_MONITORING
    7. If timeout (12h) → Force entry or skip based on distance
    """
    direction = setup['direction']  # 'buy' or 'sell'
    fvg_top = setup.get('fvg_zone_top', 0)
    fvg_bottom = setup.get('fvg_zone_bottom', 0)
    
    # Check if CHoCH already detected
    choch_detected = setup.get('choch_1h_detected', False)
    choch_timestamp = setup.get('choch_1h_timestamp')
    fibo_data = setup.get('fibo_data')
    
    if not choch_detected:
        # ========== STEP 1: DETECT 1H CHoCH ==========
        choch_list = self.smc_detector.detect_choch(df_h1)
        
        if not choch_list:
            return {
                'action': 'KEEP_MONITORING',
                'reason': 'No 1H CHoCH detected yet'
            }
        
        # Find most recent CHoCH matching direction and in FVG zone
        matching_choch = None
        for choch in reversed(choch_list):
            choch_price = choch.break_price
            choch_direction = choch.direction
            
            # Check if CHoCH is in FVG zone
            in_fvg = fvg_bottom <= choch_price <= fvg_top
            
            # Check if direction matches
            direction_match = (
                (direction == 'buy' and choch_direction == 'bullish') or
                (direction == 'sell' and choch_direction == 'bearish')
            )
            
            if in_fvg and direction_match:
                matching_choch = choch
                break
        
        if not matching_choch:
            return {
                'action': 'KEEP_MONITORING',
                'reason': f'No {direction} CHoCH in FVG zone yet'
            }
        
        # CHoCH found! Calculate Fibonacci
        choch_idx = matching_choch.index
        choch_timestamp = df_h1.index[choch_idx]
        
        fibo_data = calculate_choch_fibonacci(
            df_h1=df_h1,
            choch_idx=choch_idx,
            direction='bullish' if direction == 'buy' else 'bearish'
        )
        
        logger.info(f"   ✅ {symbol}: 1H CHoCH detected at {matching_choch.break_price:.5f}")
        logger.info(f"   📊 Fibo 50%: {fibo_data['fibo_50']:.5f}, Range: {fibo_data['swing_range']:.1f} pips")
    
    # ========== STEP 2: CHECK PULLBACK TO FIBO 50% ==========
    pullback_result = validate_pullback_entry(
        df_h1=df_h1,
        fibo_data=fibo_data,
        direction='bullish' if direction == 'buy' else 'bearish',
        tolerance_pips=self.pullback_config['tolerance_pips'],
        sl_buffer_pips=self.pullback_config['sl_buffer_pips'],
        swing_lookback=self.pullback_config['swing_lookback_candles']
    )
    
    if pullback_result['pullback_reached']:
        # ✅ PULLBACK REACHED - OPTIMAL ENTRY!
        logger.success(f"   🎯 {symbol}: Pullback reached! Distance: {pullback_result['distance_to_fibo']:.1f} pips")
        return {
            'action': 'EXECUTE_ENTRY1',
            'entry_type': 'PULLBACK',
            'entry_price': pullback_result['entry_price'],
            'stop_loss': pullback_result['stop_loss'],
            'choch_timestamp': choch_timestamp.isoformat() if hasattr(choch_timestamp, 'isoformat') else str(choch_timestamp),
            'fibo_data': fibo_data,
            'sl_distance_pips': pullback_result['sl_distance_pips']
        }
    
    # ========== STEP 3: CHECK CONTINUATION MOMENTUM (V3.3 NEW) ==========
    from pandas import to_datetime, Timestamp
    current_time = df_h1.index[-1]
    if not isinstance(current_time, (Timestamp, pd.Timestamp)):
        current_time = to_datetime(current_time)
    if isinstance(choch_timestamp, str):
        choch_timestamp = to_datetime(choch_timestamp)
    elif isinstance(choch_timestamp, (int, float)):
        try:
            choch_timestamp = df_h1.index[int(choch_timestamp)]
            if not isinstance(choch_timestamp, (Timestamp, pd.Timestamp)):
                choch_timestamp = to_datetime(choch_timestamp)
        except Exception:
            choch_timestamp = to_datetime(choch_timestamp, unit='s')
    elif not isinstance(choch_timestamp, (Timestamp, pd.Timestamp)):
        choch_timestamp = to_datetime(choch_timestamp)
    
    choch_age_hours = (current_time - choch_timestamp).total_seconds() / 3600
    continuation_check_hours = self.pullback_config.get('continuation_check_hours', 6)
    
    if choch_age_hours >= continuation_check_hours:
        # After 6 hours, check for continuation momentum
        from smc_detector import check_continuation_momentum
        
        momentum_result = check_continuation_momentum(
            df_h1=df_h1,
            direction='bullish' if direction == 'buy' else 'bearish',
            lookback_candles=3
        )
        
        if momentum_result['has_momentum']:
            # ✅ CONTINUATION MOMENTUM DETECTED - EXECUTE!
            current_price = momentum_result['current_price']
            
            # Calculate ATR-based stop loss (tighter than swing-based)
            atr = (df_h1['high'] - df_h1['low']).rolling(14).mean().iloc[-1]
            
            if direction == 'buy':
                stop_loss = current_price - (2 * atr)
            else:
                stop_loss = current_price + (2 * atr)
            
            sl_distance_pips = abs(current_price - stop_loss) * 10000
            
            logger.success(f"   🚀 {symbol}: Continuation momentum! Score: {momentum_result['momentum_score']}/100")
            logger.info(f"   📊 Consecutive candles: {momentum_result['consecutive_candles']}, Move: {momentum_result['price_move_pct']:.2f}%")
            
            return {
                'action': 'EXECUTE_ENTRY1_CONTINUATION',
                'entry_type': 'CONTINUATION',
                'entry_price': current_price,
                'stop_loss': round(stop_loss, 5),
                'choch_timestamp': choch_timestamp.isoformat() if hasattr(choch_timestamp, 'isoformat') else str(choch_timestamp),
                'fibo_data': fibo_data,
                'sl_distance_pips': round(sl_distance_pips, 1),
                'momentum_score': momentum_result['momentum_score']
            }
        else:
            logger.info(f"   ⏳ {symbol}: No pullback and weak momentum (score: {momentum_result['momentum_score']}/100)")
    
    # ========== STEP 4: CHECK TIMEOUT (12h) ==========
    timeout_hours = self.pullback_config.get('pullback_timeout_hours', 12)
    
    if choch_age_hours > timeout_hours:
        logger.warning(f"   ⏰ {symbol}: Timeout ({choch_age_hours:.1f}h > {timeout_hours}h)")
        
        # Check if price is within reasonable distance (1.5% of Fibo 50%)
        current_price = pullback_result['current_price']
        fibo_50 = fibo_data['fibo_50']
        distance_pct = abs(current_price - fibo_50) / fibo_50 * 100
        
        if distance_pct < 1.5:  # Within 1.5% = reasonable
            if self.pullback_config['on_timeout_action'] == 'force_entry':
                logger.warning(f"   🔴 Forcing entry at {current_price:.5f} (distance: {distance_pct:.2f}%)")
                return {
                    'action': 'TIMEOUT_FORCE_ENTRY',
                    'entry_price': current_price,
                    'stop_loss': pullback_result['stop_loss'],
                    'reason': f'Timeout exceeded ({choch_age_hours:.1f}h), distance reasonable'
                }
        else:
            logger.warning(f"   ❌ Price too far ({distance_pct:.2f}% > 1.5%), skipping")
            return {
                'action': 'EXPIRE',
                'reason': f'Timeout + price too far from optimal ({distance_pct:.2f}%)'
            }
    
    # ⏳ WAITING FOR PULLBACK OR MOMENTUM
    logger.info(f"   ⏳ {symbol}: Waiting ({choch_age_hours:.1f}h) - Distance: {pullback_result['distance_to_fibo']:.1f} pips")
    if choch_age_hours >= continuation_check_hours:
        logger.info(f"   💡 Continuation check active (will execute if momentum score ≥ 60)")
    
    return {
        'action': 'KEEP_MONITORING',
        'reason': f"Waiting for pullback or momentum ({pullback_result['distance_to_fibo']:.1f} pips away)",
        'choch_timestamp': choch_timestamp.isoformat() if hasattr(choch_timestamp, 'isoformat') else str(choch_timestamp),
        'fibo_data': fibo_data,
        'distance_to_fibo': pullback_result['distance_to_fibo'],
        'choch_age_hours': round(choch_age_hours, 1)
    }
```

---

### 3. Update `pairs_config.json` - Add Continuation Settings

**Location:** Line 156 (pullback_strategy section)

```json
{
  "pullback_strategy": {
    "enabled": true,
    "fibo_level": 0.5,
    "tolerance_pips": 10,
    "pullback_timeout_hours": 12,
    "continuation_check_hours": 6,
    "swing_lookback_candles": 5,
    "sl_buffer_pips": 10,
    "on_timeout_action": "force_entry",
    "continuation_momentum_threshold": 60
  }
}
```

**Changes:**
- `pullback_timeout_hours`: 24 → 12 (faster timeout)
- `continuation_check_hours`: **NEW** - check momentum after 6h
- `continuation_momentum_threshold`: **NEW** - minimum score to execute continuation entry

---

### 4. Update Telegram Notifications

**Location:** `notification_manager.py` or `telegram_notifier.py`

Add new entry type messages:

```python
def format_entry_notification(symbol, entry_type, entry_price, sl, tp, reason):
    """Format entry notification with type"""
    
    if entry_type == 'PULLBACK':
        icon = "🎯"
        entry_msg = f"{icon} PULLBACK ENTRY (optimal)"
    elif entry_type == 'CONTINUATION':
        icon = "🚀"
        entry_msg = f"{icon} CONTINUATION ENTRY (momentum)"
    else:
        icon = "📍"
        entry_msg = f"{icon} TIMEOUT ENTRY (forced)"
    
    message = f"""
{entry_msg}

💰 {symbol}
Entry: {entry_price:.5f}
SL: {sl:.5f}
TP: {tp:.5f}

📊 Reason: {reason}
"""
    return message
```

---

## 🧪 TESTING STRATEGY

### Unit Tests

Create `tests/test_v3_3_hybrid_entry.py`:

```python
import pytest
from smc_detector import check_continuation_momentum, validate_pullback_entry
import pandas as pd

class TestV33HybridEntry:
    
    def test_pullback_entry_optimal(self):
        """Test pullback entry within 10 pips"""
        df_h1 = create_mock_data(price_at_fibo=True, distance_pips=5)
        fibo_data = {'fibo_50': 1.5000}
        
        result = validate_pullback_entry(df_h1, fibo_data, 'bullish', tolerance_pips=10)
        
        assert result['pullback_reached'] == True
        assert result['distance_to_fibo'] <= 10
    
    def test_continuation_momentum_strong(self):
        """Test continuation entry with 3 bullish candles"""
        df_h1 = create_mock_data(consecutive_bullish=3, atr_expanding=True)
        
        result = check_continuation_momentum(df_h1, direction='bullish')
        
        assert result['has_momentum'] == True
        assert result['consecutive_candles'] >= 3
        assert result['momentum_score'] >= 60
    
    def test_continuation_momentum_weak(self):
        """Test rejection when momentum too weak"""
        df_h1 = create_mock_data(consecutive_bullish=1, atr_contracting=True)
        
        result = check_continuation_momentum(df_h1, direction='bullish')
        
        assert result['has_momentum'] == False
        assert result['momentum_score'] < 60
    
    def test_timeout_reasonable_distance(self):
        """Test force entry when timeout + distance < 1.5%"""
        # Distance = 1.2% (reasonable)
        assert should_force_entry(distance_pct=1.2) == True
    
    def test_timeout_unreasonable_distance(self):
        """Test skip when timeout + distance > 1.5%"""
        # Distance = 3.5% (too far)
        assert should_force_entry(distance_pct=3.5) == False
```

### Integration Test

```python
def test_full_cycle_xauusd_continuation():
    """
    Test XAUUSD continuation scenario (missed trade case)
    
    Scenario:
    1. Daily CHoCH bullish @ 4318
    2. 1H CHoCH detected @ 4320
    3. Price rallies to 4500 without pullback (6 hours later)
    4. Check continuation momentum → should EXECUTE
    """
    setup = {
        'symbol': 'XAUUSD',
        'direction': 'buy',
        'fvg_zone_top': 4350,
        'fvg_zone_bottom': 4280,
        'choch_1h_timestamp': '2025-01-26T10:00:00',
        'fibo_data': {'fibo_50': 4318.87}
    }
    
    # Mock data: 6 hours later, price at 4500, 3 consecutive bullish candles
    df_h1 = create_xauusd_continuation_data()
    
    monitor = SetupExecutorMonitor()
    result = monitor._check_pullback_entry(setup, df_h1, 'XAUUSD')
    
    assert result['action'] == 'EXECUTE_ENTRY1_CONTINUATION'
    assert result['entry_type'] == 'CONTINUATION'
    assert result['entry_price'] > 4318.87  # Entered above Fibo 50%
    assert 'momentum_score' in result
```

---

## 📊 BACKTEST COMPARISON

Run backtest with all 3 versions and compare:

```bash
# V2.1 (Original)
python backtest_1year.py --version v2.1 --strategy simple

# V3.2 (Current)
python backtest_1year.py --version v3.2 --strategy pullback

# V3.3 (New Hybrid)
python backtest_1year.py --version v3.3 --strategy hybrid
```

**Expected Results:**

| Metric | V2.1 (Original) | V3.2 (Pullback) | V3.3 (Hybrid) | Target |
|--------|-----------------|-----------------|---------------|--------|
| Total Trades | 139 | ~80 | ~120 | 100-130 |
| Win Rate | 72% | 78% | 75% | 70-80% |
| Total Return | 625% | ~350% | ~550% | 500-600% |
| Avg R:R | 5.2 | 6.8 | 5.9 | 5.0-7.0 |
| XAUUSD Trades | 18 | 10 | 16 | 15-18 |
| Missed Setups | 0% | 30% | <10% | <15% |

---

## 🚀 DEPLOYMENT PLAN

### Paper Account (Week 1)
```yaml
Risk per Trade: 0.5% (reduced for testing)
Pairs: All 15 pairs
Monitor Focus: XAUUSD, BTCUSD, GBPJPY (fast movers)
Success Criteria:
  - ≥10 trades executed
  - ≥2 continuation entries triggered
  - Win rate ≥ 60%
  - No catastrophic losses (max loss < 2%)
```

### Live Account (Week 2)
```yaml
Risk per Trade: 1% (gradual increase)
Pairs: All 15 pairs
Monitor: 3 days stability check
Increase to 2%: After 5 winning trades
Success Criteria:
  - Match or exceed V3.2 performance
  - Capture 1+ XAUUSD-type continuation setup
  - Win rate ≥ 70%
```

---

## 📝 ROLLBACK PLAN

If V3.3 underperforms, rollback to V3.2:

```bash
# 1. Backup V3.3 code
git commit -m "V3.3 Hybrid Entry - rollback point"
git tag v3.3-backup

# 2. Revert to V3.2
git checkout v3.2-stable

# 3. Restart monitors
./cleanup_system.sh
./configure_24_7.sh

# 4. Verify
tail -f nohup_setup_executor.log
```

---

## 🎯 SUCCESS METRICS

### Short-term (1 week)
- [ ] ≥15 trades executed
- [ ] ≥3 continuation entries (EXECUTE_ENTRY1_CONTINUATION)
- [ ] ≥1 XAUUSD-type setup caught
- [ ] Win rate ≥ 65%
- [ ] Avg R:R ≥ 5.0

### Medium-term (1 month)
- [ ] ≥60 trades executed
- [ ] Total return ≥ +30%
- [ ] Win rate ≥ 70%
- [ ] Missed setups < 15%
- [ ] Max drawdown < 15%

### Long-term (12 months)
- [ ] ≥120 trades
- [ ] Total return ≥ 500%
- [ ] Win rate ≥ 72%
- [ ] Match or exceed V2.1 backtest (625%)

---

## 🔍 MONITORING & ALERTS

### Key Logs to Watch

```bash
# Check for continuation entries
grep "CONTINUATION MOMENTUM" nohup_setup_executor.log

# Check timeout force entries
grep "TIMEOUT FORCE ENTRY" nohup_setup_executor.log

# Check missed setups
grep "EXPIRE" nohup_setup_executor.log | wc -l

# Check entry distribution
grep "EXECUTE_ENTRY1" nohup_setup_executor.log | cut -d: -f4 | sort | uniq -c
```

### Telegram Alerts to Configure

```yaml
New Alerts:
  - "🚀 Continuation entry on {symbol}" (when momentum entry triggers)
  - "⏰ Timeout force entry on {symbol}" (when 12h timeout hits)
  - "📊 Daily V3.3 stats: X pullback / Y continuation / Z timeout"
```

---

## 📚 DOCUMENTATION UPDATES

Files to update after implementation:

- [ ] `DOCUMENTATION.md` - Add V3.3 strategy explanation
- [ ] `AI_STRATEGY_DOCUMENTATION.md` - Update entry logic
- [ ] `TERMINAL_COMMANDS_GUIDE.md` - Add V3.3 testing commands
- [ ] `CHANGELOG_2025-01-30.md` - Document all changes
- [ ] `README.md` - Update version to V3.3

---

## 🤝 NEXT STEPS

1. **Review this plan** with owner (you) and get approval
2. **Implement Phase 1** (code changes) - 1 day
3. **Run tests** (Phase 2) - 1 day
4. **Deploy to paper** (Phase 3) - 1 week
5. **Go live** (Phase 4) - Week 2
6. **Monitor & optimize** - Ongoing

---

**Upgrade Plan Created:** 2025-01-30  
**Target Version:** V3.3 Hybrid Entry Logic  
**Priority:** CRITICAL  
**Status:** ✅ READY FOR IMPLEMENTATION

🚀 **Ready to start coding?**
