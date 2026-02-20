"""
BTC RE-CALCULATION TEST with V5.1 Crypto Rules
- SL: 2% from entry (proper crypto scaling)
- Lot Size: $200 risk on new SL distance
- Clean prices: 2 decimals max
- Integer pips: No decimals
"""

import json
import os
import time
from datetime import datetime
from ctrader_executor import CTraderExecutor
from telegram_notifier import TelegramNotifier
from dotenv import load_dotenv

load_dotenv()

# Initialize components
executor = CTraderExecutor()
notifier = TelegramNotifier()

print("\n" + "="*60)
print("🪙 BTCUSD RE-CALCULATION with V5.1 CRYPTO RULES")
print("="*60)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1: DEFINE ENTRY PRICE & CALCULATE PROPER SL/TP
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

symbol = "BTCUSD"
direction = "SELL"
entry_price = 67258.25  # Current BTC price

# 🚨 NEW CRYPTO RULE: SL must be 1.5% - 2% from entry (or 1.5x ATR, whichever larger)
# For SELL: SL goes ABOVE entry
sl_percentage = 0.02  # 2% for safe margin
sl_distance = entry_price * sl_percentage
stop_loss = entry_price + sl_distance  # SELL → SL above entry

# TP calculation: Risk-Reward 1:5 (aggressive crypto target)
risk_reward = 5.0
tp_distance = sl_distance * risk_reward
take_profit = entry_price - tp_distance  # SELL → TP below entry

# Clean prices to 2 decimals (V5.1 requirement)
entry_price = round(entry_price, 2)
stop_loss = round(stop_loss, 2)
take_profit = round(take_profit, 2)

print(f"\n📊 BTCUSD SELL SETUP (Crypto Scaled)")
print(f"   Entry: ${entry_price:,.2f}")
print(f"   SL: ${stop_loss:,.2f} (+{sl_distance:,.2f} = {sl_percentage*100}%)")
print(f"   TP: ${take_profit:,.2f} (-{tp_distance:,.2f} = {risk_reward}x reward)")

# Calculate pips (for BTC: 1 pip = 1.0 unit)
pip_size = 1.0
sl_pips = int(round(abs(entry_price - stop_loss) / pip_size))  # INTEGER
tp_pips = int(round(abs(take_profit - entry_price) / pip_size))  # INTEGER

print(f"\n📏 DISTANCES (Crypto Scaling)")
print(f"   SL Pips: {sl_pips} (INTEGER, no decimals)")
print(f"   TP Pips: {tp_pips} (INTEGER, no decimals)")
print(f"   Risk:Reward = 1:{risk_reward}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2: CALCULATE LOT SIZE ($200 RISK on new SL distance)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Risk manager will calculate lot size, but we simulate here
risk_amount = 200.0  # $200 fixed risk
pip_value = 1.0  # For BTC: $1 per micro lot per $1 move

# Formula: LotSize = Risk_Amount / (SL_Distance_in_Price * Pip_Value)
lot_size = risk_amount / (sl_distance * pip_value)
lot_size = round(lot_size, 2)

# V5.1 FIX: Enforce minimum 0.01 lots
if lot_size < 0.01:
    print(f"\n⚠️  Lot size {lot_size:.4f} below minimum - forcing to 0.01")
    lot_size = 0.01

print(f"\n💰 LOT SIZE CALCULATION")
print(f"   Risk Amount: ${risk_amount:.2f}")
print(f"   SL Distance: ${sl_distance:.2f} ({sl_pips} pips)")
print(f"   Pip Value: ${pip_value:.2f} per micro lot")
print(f"   Calculated Lot: {lot_size:.2f} lots")
print(f"   Expected Loss if SL hit: ${lot_size * sl_distance:.2f}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3: EXECUTE TRADE (will validate with Risk Manager)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print(f"\n🚀 EXECUTING BTCUSD SELL with V5.1 Crypto Rules...")
print(f"   This will trigger Risk Manager validation...")

result = executor.execute_trade(
    symbol=symbol,
    direction=direction,
    entry_price=entry_price,
    stop_loss=stop_loss,
    take_profit=take_profit,
    lot_size=lot_size,  # Risk manager will recalculate
    comment="V5.1 Crypto Scaled - 2% SL + $200 Risk",
    status="READY"  # Bypass 4H confirmation for test
)

if result:
    print(f"\n✅ Signal dispatched to signals.json")
    
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # STEP 4: SEND TELEGRAM NOTIFICATION (Bloomberg Column Format)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
    # Wait for queue to write signal
    print(f"\n⏳ Waiting for signal queue to write...")
    time.sleep(3)
    
    try:
        with open('signals.json', 'r') as f:
            signal = json.load(f)
        
        if signal.get('Symbol') == 'BTCUSD':
            actual_lot = signal.get('LotSize', lot_size)
            actual_sl_pips = signal.get('StopLossPips', sl_pips)
            actual_tp_pips = signal.get('TakeProfitPips', tp_pips)
            actual_entry = signal.get('EntryPrice', entry_price)
            actual_sl = signal.get('StopLoss', stop_loss)
            actual_tp = signal.get('TakeProfit', take_profit)
            
            print(f"\n📄 SIGNAL WRITTEN TO signals.json:")
            print(f"   Entry: ${actual_entry:,.2f}")
            print(f"   SL: ${actual_sl:,.2f} ({actual_sl_pips} pips)")
            print(f"   TP: ${actual_tp:,.2f} ({actual_tp_pips} pips)")
            print(f"   Lot: {actual_lot} lots")
            
            # Bloomberg Column Format (18 characters width)
            message = f"""
🪙 <b>BTCUSD SELL SIGNAL</b> (V5.1 Crypto Scaled)

<pre>
╔══════════════════╗
║   ENTRY ZONE     ║
╠══════════════════╣
║ Price   {actual_entry:>8.2f} ║
║ SL      {actual_sl:>8.2f} ║
║ TP      {actual_tp:>8.2f} ║
╠══════════════════╣
║   RISK METRICS   ║
╠══════════════════╣
║ SL Pips    {actual_sl_pips:>5} ║
║ TP Pips    {actual_tp_pips:>5} ║
║ R:R        1:{risk_reward:.1f} ║
║ Lot Size   {actual_lot:>5.2f} ║
║ Risk $    {risk_amount:>6.2f} ║
╚══════════════════╝
</pre>

🎯 <b>V5.1 CRYPTO RULES:</b>
• SL: 2% from entry ({sl_percentage*100}%)
• Pips: INTEGER only ({actual_sl_pips}, not {actual_sl_pips}.5)
• Prices: 2 decimals max
• Lot: Minimum 0.01 enforced

⚡ <b>READY FOR cTrader EXECUTION</b>
"""
            
            notifier.send_message(message, parse_mode="HTML")
            print(f"\n📱 Telegram notification sent!")
            
        else:
            print(f"\n⚠️  Signal in signals.json is not BTCUSD (found {signal.get('Symbol')})")
            print(f"   New signal may still be in queue...")
            
    except FileNotFoundError:
        print(f"\n⚠️  signals.json not found - signal may still be queued")
    except json.JSONDecodeError as e:
        print(f"\n⚠️  Could not parse signals.json: {e}")
    except Exception as e:
        print(f"\n⚠️  Error reading signal: {e}")
else:
    print(f"\n❌ Trade rejected by Risk Manager")
    print(f"   Check logs above for rejection reason")

print("\n" + "="*60)
print("✅ BTCUSD RE-CALCULATION COMPLETE")
print("="*60 + "\n")
