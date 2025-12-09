"""
Quick check - care sunt numele exacte ale simbolurilor pe IC Markets cTrader
"""
import json

# Citeste trade history pentru a vedea ce símboale avem traded
try:
    with open('trade_history.json', 'r') as f:
        trades = json.load(f)
        
    print("📊 Símboale găsite în trade_history.json (IC Markets format):\n")
    
    symbols_seen = set()
    for trade in trades:
        symbol = trade.get('symbol', 'N/A')
        if symbol not in symbols_seen:
            print(f"   ✅ {symbol}")
            symbols_seen.add(symbol)
    
    print(f"\n📋 Total unique symbols: {len(symbols_seen)}")
    print(f"\n💡 IMPORTANTE:")
    print(f"   - Acestea sunt numele EXACT așa cum apar pe IC Markets")
    print(f"   - TradeHistorySyncer.cs primește aceste denumiri direct din cTrader")
    print(f"   - Pentru toate 21 paritatile, verific în cTrader chartul pentru denumiri exacte")
    
except Exception as e:
    print(f"❌ Error: {e}")
