#!/usr/bin/env python3
"""
IC Markets Symbol Name Variations - Real Trading Experience
"""
from loguru import logger

logger.info("="*70)
logger.info("🔍 IC MARKETS SYMBOL VARIATIONS")
logger.info("="*70)

# IC Markets REAL symbol names (from actual trading)
IC_MARKETS_SYMBOLS = {
    # FOREX - Standard names
    'GBPUSD': ['GBPUSD'],
    'EURUSD': ['EURUSD'],
    'USDJPY': ['USDJPY'],
    
    # COMMODITIES - Variations possible
    'GOLD': ['XAUUSD', 'GOLD'],
    'SILVER': ['XAGUSD', 'SILVER'],
    
    # CRYPTO - Multiple possible names
    'BITCOIN': [
        'BTCUSD',      # Most common
        'BITCOIN',     # Alternative
        'BTC/USD',     # With slash
        'BTCUSD.f',    # Futures
    ],
    
    # OIL - Multiple variations
    'OIL': [
        'USOIL',       # Spot
        'USOIL.f',     # Futures (most common in IC Markets)
        'CRUDEOIL',    # Alternative
        'WTI',         # Alternative
        'BRENT',       # Brent Crude
    ],
}

logger.info("\n📋 SIMBOLURI PROBLEMATICE - Variante posibile:")
logger.info("-"*70)

logger.info("\n💰 BITCOIN:")
logger.info("   Ai spus că tranzacționezi BTC pe IC Markets")
logger.info("   Posibile nume în cTrader:")
for name in IC_MARKETS_SYMBOLS['BITCOIN']:
    logger.info(f"      • {name}")
logger.warning("\n   ⚠️  TREBUIE să verifici numele EXACT în cTrader!")
logger.info("      1. Deschide cTrader")
logger.info("      2. Caută în Market Watch: Bitcoin sau BTC")
logger.info("      3. Notează numele EXACT (ex: BTCUSD sau BITCOIN)")

logger.info("\n🛢️  OIL (USOIL):")
logger.info("   Cel mai probabil: USOIL.f (futures)")
for name in IC_MARKETS_SYMBOLS['OIL']:
    logger.info(f"      • {name}")

logger.info("\n🥈 SILVER (XAGUSD):")
logger.info("   Probabil: XAGUSD sau SILVER")
for name in IC_MARKETS_SYMBOLS['SILVER']:
    logger.info(f"      • {name}")

logger.info("\n" + "="*70)
logger.info("🔧 CE TREBUIE SĂ FACI:")
logger.info("="*70)
logger.info("""
1. Deschide cTrader Desktop
2. În Market Watch, caută:
   - Bitcoin (sau BTC)
   - Oil (sau Crude Oil)
   - Silver
3. Click pe simbol → vezi numele EXACT în detalii
4. Spune-mi numele exact pentru fiecare
5. Voi actualiza PythonSignalExecutor.cs cu maparea corectă

EXEMPLU:
Dacă găsești "BITCOIN" pentru Bitcoin
→ Voi mapa: 'BTCUSD' -> 'BITCOIN' în executor
""")

logger.info("\n💡 SAU mai simplu:")
logger.info("-"*70)
logger.info("Deschide o fereastră de chart în cTrader pentru Bitcoin")
logger.info("Uită-te sus în titlu - acolo scrie EXACT numele simbolului!")
logger.info("Exemplu: Poate scrie 'BITCOIN' sau 'BTCUSD' sau 'BTCUSD.f'")

logger.info("\n" + "="*70)
