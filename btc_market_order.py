"""
BTC MARKET ORDER - Execute at current price (66516.60)
"""
import json
from datetime import datetime
from ctrader_executor import CTraderExecutor
from telegram_notifier import TelegramNotifier
from dotenv import load_dotenv

load_dotenv()

executor = CTraderExecutor()
notifier = TelegramNotifier()

# Current BTC price (from chart)
current_price = 66516.60

print(f"\n🪙 BTCUSD MARKET ORDER (Execute NOW)")
print(f"   Current Price: ${current_price:,.2f}")
print()

# Calculate SL/TP with 2% SL
symbol = "BTCUSD"
direction = "SELL"
entry_price = current_price
sl_percentage = 0.02
tp_multiplier = 5.0

# SELL: SL above, TP below
sl_distance = entry_price * sl_percentage
stop_loss = entry_price + sl_distance
take_profit = entry_price - (sl_distance * tp_multiplier)

# Clean prices
entry_price = round(entry_price, 2)
stop_loss = round(stop_loss, 2)
take_profit = round(take_profit, 2)

# Calculate pips (integer)
sl_pips = int(round(abs(entry_price - stop_loss)))
tp_pips = int(round(abs(take_profit - entry_price)))

print(f"📊 MARKET ORDER DETAILS:")
print(f"   Entry: ${entry_price:,.2f} (CURRENT PRICE)")
print(f"   SL: ${stop_loss:,.2f} (+{sl_pips} pips = 2%)")
print(f"   TP: ${take_profit:,.2f} (-{tp_pips} pips)")
print(f"   Risk:Reward: 1:{tp_multiplier}")
print()

# Execute
result = executor.execute_trade(
    symbol=symbol,
    direction=direction,
    entry_price=entry_price,
    stop_loss=stop_loss,
    take_profit=take_profit,
    lot_size=0.01,  # Will be recalculated
    comment="V5.1 MARKET ORDER - Instant Execution",
    status="READY"
)

if result:
    print(f"\n✅ MARKET ORDER DISPATCHED!")
    print(f"   cBot will execute in <10 seconds at ${entry_price:,.2f}")
    
    # Send Telegram
    message = f"""
🪙 <b>BTCUSD SELL - MARKET ORDER</b>

<pre>
╔══════════════════╗
║  INSTANT EXEC    ║
╠══════════════════╣
║ Price   {entry_price:>8.2f} ║
║ SL      {stop_loss:>8.2f} ║
║ TP      {take_profit:>8.2f} ║
╠══════════════════╣
║ SL Pips    {sl_pips:>5} ║
║ TP Pips    {tp_pips:>5} ║
║ R:R        1:{tp_multiplier:.1f} ║
╚══════════════════╝
</pre>

⚡ <b>MARKET ORDER - Executes NOW!</b>
"""
    notifier.send_message(message, parse_mode="HTML")
    print(f"\n📱 Telegram sent!")
else:
    print(f"\n❌ Order rejected by Risk Manager")
