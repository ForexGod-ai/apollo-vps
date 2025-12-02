import MetaTrader5 as mt5

print("=" * 80)
print("MT5 CONNECTION & ACCOUNT CHECK")
print("=" * 80)

# Initialize
if not mt5.initialize():
    print(f"❌ MT5 initialization failed!")
    print(f"Error: {mt5.last_error()}")
    exit()

print("✅ MT5 Connected\n")

# Account info
info = mt5.account_info()
if info:
    print(f"Account Number: #{info.login}")
    print(f"Server: {info.server}")
    print(f"Balance: ${info.balance:.2f}")
    print(f"Equity: ${info.equity:.2f}")
    print(f"Profit: ${info.profit:.2f}")
    print(f"Margin: ${info.margin:.2f}")
    print(f"Free Margin: ${info.margin_free:.2f}")
    print(f"Margin Level: {info.margin_level:.2f}%")
else:
    print("❌ Cannot get account info!")

# Open positions
print("\n" + "=" * 80)
print("OPEN POSITIONS")
print("=" * 80)

positions = mt5.positions_get()
if positions:
    print(f"Total: {len(positions)} positions\n")
    for p in positions:
        ptype = "BUY" if p.type == 0 else "SELL"
        print(f"  {p.symbol} {ptype} | Vol: {p.volume} | Entry: {p.price_open} | Current: {p.price_current} | Profit: ${p.profit:.2f}")
else:
    print("No open positions")

# Pending orders
print("\n" + "=" * 80)
print("PENDING ORDERS")
print("=" * 80)

orders = mt5.orders_get()
if orders:
    print(f"Total: {len(orders)} orders\n")
    for o in orders:
        print(f"  {o.symbol} {o.type_description} | Vol: {o.volume_current} | Price: {o.price_open}")
else:
    print("No pending orders")

# History (last 10 trades)
print("\n" + "=" * 80)
print("RECENT TRADE HISTORY (Last 10)")
print("=" * 80)

from datetime import datetime, timedelta
end = datetime.now()
start = end - timedelta(days=7)

deals = mt5.history_deals_get(start, end)
if deals:
    print(f"Total deals in last 7 days: {len(deals)}\n")
    for deal in deals[-10:]:
        dtype = "BUY" if deal.type == 0 else "SELL"
        dtime = datetime.fromtimestamp(deal.time).strftime('%Y-%m-%d %H:%M')
        print(f"  {dtime} | {deal.symbol} {dtype} | Vol: {deal.volume} | Price: {deal.price} | Profit: ${deal.profit:.2f}")
else:
    print("No trade history")

mt5.shutdown()
print("\n" + "=" * 80)
print("✅ Check complete")
print("=" * 80)
