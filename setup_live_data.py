"""
Setup Live Data Sources - IC Markets + TradingView
Configurează surse de date LIVE fără Yahoo Finance
"""

import os
from dotenv import load_dotenv, set_key

load_dotenv()

print("=" * 70)
print("🔥 CONFIGURARE DATE LIVE - IC Markets + TradingView 🔥")
print("=" * 70)
print()

print("📊 SURSE DE DATE DISPONIBILE:")
print()
print("1. 🟢 IC Markets cTrader WebSocket (REAL-TIME)")
print("   ✅ Deja configurat!")
print("   ✅ Account: 9709773")
print("   ✅ Access via cTrader Open API")
print()

print("2. 📈 TradingView (Pentru charturi și analize)")
print("   ✅ Webhook primește semnale de la TradingView alerts")
print("   ✅ Chart generator folosește TradingView styling")
print()

print("3. 🔄 Alpha Vantage (Backup FREE API)")
print("   - 500 requests/day gratuit")
print("   - Sign up: https://www.alphavantage.co/support/#api-key")
print()

# Check current configuration
env_file = "/Users/forexgod/Desktop/trading-ai-agent apollo/.env"

print("=" * 70)
print("📝 CONFIGURAȚIE CURENTĂ:")
print("=" * 70)

ctrader_account = os.getenv('CTRADER_ACCOUNT_ID')
ctrader_token = os.getenv('CTRADER_ACCESS_TOKEN')
alpha_key = os.getenv('ALPHA_VANTAGE_API_KEY', 'Not set')

print(f"✅ cTrader Account: {ctrader_account}")
print(f"✅ cTrader Token: {'***' + ctrader_token[-10:] if ctrader_token else 'Not set'}")
print(f"⚠️  Alpha Vantage Key: {alpha_key}")
print()

print("=" * 70)
print("🚀 ACȚIUNI DISPONIBILE:")
print("=" * 70)
print()
print("1. Testează conexiunea IC Markets cTrader WebSocket")
print("2. Adaugă Alpha Vantage API key (backup)")
print("3. Testează primirea de date LIVE")
print("4. Configurează TradingView alerts pentru webhook")
print()

choice = input("Alege opțiune (1-4) sau ENTER pentru skip: ").strip()

if choice == "1":
    print("\n🔄 Testare conexiune IC Markets...")
    os.system("python3 test_ctrader_live_data.py")
    
elif choice == "2":
    print("\n📝 Adaugă Alpha Vantage API Key")
    print("   Get your FREE key: https://www.alphavantage.co/support/#api-key")
    api_key = input("   Paste API Key: ").strip()
    if api_key:
        set_key(env_file, "ALPHA_VANTAGE_API_KEY", api_key)
        print(f"   ✅ Alpha Vantage API key salvat!")
        
elif choice == "3":
    print("\n🔄 Testare date LIVE...")
    os.system("python3 -c \"from ctrader_data_client import get_ctrader_client; client = get_ctrader_client(); print(client.get_live_data('GBPUSD', 'D1', 100))\"")
    
elif choice == "4":
    webhook_url = f"http://192.168.1.132:5001/webhook"
    print(f"\n📈 CONFIGURARE TRADINGVIEW ALERTS:")
    print(f"   1. Deschide TradingView")
    print(f"   2. Creează alert pe symbol (ex: GBPUSD)")
    print(f"   3. Webhook URL: {webhook_url}")
    print(f"   4. Message format:")
    print("""
   {{
     "action": "{{strategy.order.action}}",
     "symbol": "{{ticker}}",
     "price": {{close}},
     "stop_loss": {{strategy.order.stop_loss}},
     "take_profit": {{strategy.order.take_profit}},
     "timeframe": "{{interval}}",
     "strategy": "tradingview_alert",
     "timestamp": "{{time}}"
   }}
    """)
    
print("\n✅ Setup complet!")
print("🔥 Sistemul folosește IC Markets + TradingView!")
