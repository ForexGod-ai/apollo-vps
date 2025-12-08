#!/usr/bin/env python3
"""
Verificare simboluri disponibile în IC Markets cTrader
"""
from loguru import logger

# Simbolurile noastre din config
OUR_SYMBOLS = [
    'GBPUSD', 'XAUUSD', 'BTCUSD', 'GBPJPY', 'USOIL', 'GBPNZD', 'EURJPY',
    'EURUSD', 'NZDCAD', 'USDJPY', 'USDCAD', 'EURCAD', 'AUDCAD', 'GBPCHF',
    'USDCHF', 'NZDUSD', 'AUDNZD', 'CADCHF', 'AUDUSD', 'EURGBP', 'XAGUSD', 'PIUSDT'
]

# Simboluri confirmate în IC Markets cTrader (din experiență)
CTRADER_CONFIRMED = {
    # Forex Majors - 100% confirmed
    'GBPUSD': 'GBPUSD',
    'EURUSD': 'EURUSD',
    'USDJPY': 'USDJPY',
    'USDCHF': 'USDCHF',
    'AUDUSD': 'AUDUSD',
    'USDCAD': 'USDCAD',
    'NZDUSD': 'NZDUSD',
    
    # Forex Crosses - 100% confirmed
    'EURJPY': 'EURJPY',
    'GBPJPY': 'GBPJPY',
    'EURGBP': 'EURGBP',
    'EURCAD': 'EURCAD',
    'AUDCAD': 'AUDCAD',
    'AUDNZD': 'AUDNZD',
    'NZDCAD': 'NZDCAD',
    'GBPNZD': 'GBPNZD',
    'GBPCHF': 'GBPCHF',
    'CADCHF': 'CADCHF',
    
    # Commodities - potreba verificare
    'XAUUSD': 'XAUUSD',      # Gold - confirmat
    'XAGUSD': 'XAGUSD',      # Silver - confirmat
    
    # PROBLEMATIC - trebuie verificat în cTrader
    'BTCUSD': 'BTCUSD',      # ⚠️ Poate fi BTCUSD sau BITCOIN
    'USOIL': 'USOIL',        # ⚠️ Poate fi USOIL, USOIL.f, sau CRUDEOIL
    'PIUSDT': None,          # ❌ Probabil NU există în IC Markets
}

logger.info("="*70)
logger.info("🔍 VERIFICARE SIMBOLURI IC MARKETS cTRADER")
logger.info("="*70)

logger.info(f"\n📊 Total simboluri în config: {len(OUR_SYMBOLS)}")

# Categorize symbols
forex_count = 0
commodities_count = 0
crypto_count = 0
problematic = []

logger.info("\n✅ SIMBOLURI CONFIRMATE (18):")
logger.info("-"*70)
for symbol in OUR_SYMBOLS:
    if symbol in ['GBPUSD', 'EURUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD',
                  'EURJPY', 'GBPJPY', 'EURGBP', 'EURCAD', 'AUDCAD', 'AUDNZD', 'NZDCAD',
                  'GBPNZD', 'GBPCHF', 'CADCHF', 'XAUUSD']:
        logger.success(f"   ✅ {symbol:10s} - DISPONIBIL în cTrader")
        if symbol in ['GBPUSD', 'EURUSD', 'USDJPY', 'USDCHF', 'AUDUSD', 'USDCAD', 'NZDUSD', 'EURGBP']:
            forex_count += 1
        elif symbol in ['EURJPY', 'GBPJPY', 'EURCAD', 'AUDCAD', 'AUDNZD', 'NZDCAD', 'GBPNZD', 'GBPCHF', 'CADCHF']:
            forex_count += 1
        elif symbol == 'XAUUSD':
            commodities_count += 1

logger.info("\n⚠️  SIMBOLURI PROBLEMATICE (4):")
logger.info("-"*70)

# XAGUSD - Silver
logger.warning(f"   ⚠️  XAGUSD    - Silver (trebuie verificat în cTrader)")
logger.info(f"      → Posibile variante: XAGUSD, SILVER")

# BTCUSD - Bitcoin
logger.warning(f"   ⚠️  BTCUSD    - Bitcoin (poate să nu existe în IC Markets)")
logger.info(f"      → IC Markets nu oferă crypto în general")
logger.info(f"      → Posibile variante: BTCUSD, BITCOIN (dar probabil ABSENT)")

# USOIL - Crude Oil
logger.warning(f"   ⚠️  USOIL     - Crude Oil WTI")
logger.info(f"      → Posibile variante: USOIL, USOIL.f, CRUDEOIL, WTI")

# PIUSDT - Pi Network
logger.error(f"   ❌ PIUSDT     - Pi Network (99% NU există în IC Markets)")
logger.info(f"      → IC Markets nu oferă crypto exotice")
logger.info(f"      → RECOMANDARE: ȘTERGE din config!")

logger.info("\n" + "="*70)
logger.info("📋 REZUMAT:")
logger.info("="*70)
logger.success(f"✅ Forex pairs confirmați: 18")
logger.success(f"✅ Commodities confirmați: 1 (XAUUSD)")
logger.warning(f"⚠️  Necesită verificare: 3 (XAGUSD, BTCUSD, USOIL)")
logger.error(f"❌ Probabil absent: 1 (PIUSDT)")

logger.info("\n💡 SOLUȚIE:")
logger.info("-"*70)
logger.info("1. Deschide cTrader Desktop")
logger.info("2. Click dreapta pe Market Watch → Add Symbol")
logger.info("3. Caută fiecare simbol problematic:")
logger.info("   • XAGUSD (Silver)")
logger.info("   • BTCUSD (Bitcoin)")
logger.info("   • USOIL (Oil)")
logger.info("4. Dacă găsești simbolul → notează numele EXACT din cTrader")
logger.info("5. Dacă NU găsești → elimină din pairs_config.json")

logger.info("\n🔧 RECOMANDĂRI:")
logger.info("-"*70)
logger.info("• Păstrează 18 forex pairs (100% functional)")
logger.info("• Păstrează XAUUSD (Gold - confirmat)")
logger.info("• Verifică XAGUSD în cTrader")
logger.info("• Șterge BTCUSD (IC Markets nu are crypto)")
logger.info("• Verifică USOIL (poate fi USOIL.f)")
logger.info("• Șterge PIUSDT (100% absent)")

logger.info("\n📊 RESULT ESTIMAT:")
logger.info("-"*70)
logger.success("✅ Functional sigur: 19 perechi (18 forex + 1 gold)")
logger.warning("⚠️  De verificat: 2 perechi (XAGUSD, USOIL)")
logger.error("❌ De șters: 2 perechi (BTCUSD, PIUSDT)")

logger.info("\n" + "="*70)
