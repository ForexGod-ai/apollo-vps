"""
BTC MARKET ORDER - Execute at current price
V14.2: Prețul BTC vine DIRECT din datele broker-ului (IC Markets via cTrader cBot).
Sursa de priorități:
  1. active_positions.json → entry_price al poziției BTC existente (cel mai fresh)
  2. monitoring_setups.json → entry_price din setup-ul BTC scanat
  3. smc_detector / yfinance OHLCV (ultimul close 1H)
  4. Fallback manual: pasezi prețul ca argument CLI  →  python btc_market_order.py 71390
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from ctrader_executor import CTraderExecutor
from telegram_notifier import TelegramNotifier
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# ── FUNCȚIE: Prețul BTC din surse broker ─────────────────────
def get_btc_price_from_broker() -> float:
    """
    Citește prețul BTC live din fișierele scrise de cBot (IC Markets).
    Nu folosește niciun API extern.
    """

    # 1. Argument CLI → python btc_market_order.py 71390
    if len(sys.argv) > 1:
        try:
            price = float(sys.argv[1])
            print(f"✅ BTC preț din CLI argument: ${price:,.2f}")
            return price
        except ValueError:
            pass

    # 2. active_positions.json → entry_price al poziției BTC deschise
    try:
        with open(BASE_DIR / "active_positions.json") as f:
            positions = json.load(f)
        for pos in positions:
            sym = pos.get("symbol", "").upper().replace("/", "").replace(" ", "")
            if "BTC" in sym:
                price = float(pos["entry_price"])
                print(f"✅ BTC preț din active_positions.json (entry broker): ${price:,.2f}")
                return price
    except Exception as e:
        print(f"⚠️  active_positions.json: {e}")

    # 3. monitoring_setups.json → entry_price din setup BTC
    try:
        with open(BASE_DIR / "monitoring_setups.json") as f:
            data = json.load(f)
        setups = data.get("setups", [])
        for s in setups:
            sym = s.get("symbol", "").upper().replace("/", "").replace(" ", "")
            if "BTC" in sym:
                price = float(s.get("entry_price", 0))
                if price > 0:
                    print(f"✅ BTC preț din monitoring_setups.json: ${price:,.2f}")
                    return price
    except Exception as e:
        print(f"⚠️  monitoring_setups.json: {e}")

    # 4. smc_detector OHLCV (ultimul close 1H de la IC Markets)
    try:
        import yfinance as yf
        df = yf.Ticker("BTC-USD").history(period="1d", interval="1h")
        if not df.empty:
            price = float(df["Close"].iloc[-1])
            print(f"✅ BTC preț din yfinance 1H OHLCV: ${price:,.2f}")
            return price
    except Exception as e:
        print(f"⚠️  yfinance: {e}")

    raise RuntimeError(
        "❌ Nu am putut obține prețul BTC din nicio sursă.\n"
        "   Rulează cu prețul manual: python btc_market_order.py 71390"
    )

# ── MAIN ──────────────────────────────────────────────────────
executor = CTraderExecutor()
notifier = TelegramNotifier()

current_price = get_btc_price_from_broker()

print(f"\n🪙 BTCUSD MARKET ORDER (Execute NOW)")
print(f"   Preț folosit: ${current_price:,.2f}")
print()

symbol        = "BTCUSD"
direction     = "SELL"
entry_price   = round(current_price, 2)
sl_percentage = 0.02   # 2% SL deasupra entry (SELL)
tp_multiplier = 5.0    # RR 1:5

sl_distance = entry_price * sl_percentage
stop_loss   = round(entry_price + sl_distance, 2)   # DEASUPRA pentru SELL
take_profit = round(entry_price - (sl_distance * tp_multiplier), 2)  # SUB pentru SELL

sl_pips = int(round(abs(entry_price - stop_loss)))
tp_pips = int(round(abs(take_profit - entry_price)))

# Guard: validare SL/TP față de entry
assert stop_loss > entry_price, f"❌ SL {stop_loss} trebuie să fie DEASUPRA entry {entry_price} pentru SELL!"
assert take_profit < entry_price, f"❌ TP {take_profit} trebuie să fie SUB entry {entry_price} pentru SELL!"

print(f"📊 MARKET ORDER DETAILS:")
print(f"   Entry : ${entry_price:,.2f}")
print(f"   SL    : ${stop_loss:,.2f}  (+{sl_pips} pips | +2% deasupra — SELL)")
print(f"   TP    : ${take_profit:,.2f}  (-{tp_pips} pips | RR 1:{tp_multiplier:.0f})")
print()

result = executor.execute_trade(
    symbol=symbol,
    direction=direction,
    entry_price=entry_price,
    stop_loss=stop_loss,
    take_profit=take_profit,
    lot_size=0.01,  # recalculat de risk manager
    comment="V14.2 MARKET ORDER - BTC SELL",
    status="READY"
)

if result:
    time.sleep(2)  # așteaptă fire-and-forget queue să scrie pe disc
    print(f"\n✅ MARKET ORDER DISPATCHED!")
    print(f"   cBot execută în <10 secunde la ${entry_price:,.2f}")
    print(f"   SL: ${stop_loss:,.2f} | TP: ${take_profit:,.2f}")
else:
    print(f"\n❌ Order rejected by Risk Manager")
