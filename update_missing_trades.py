#!/usr/bin/env python3
"""
Manual Trade History Updater
Adaugă tranzacțiile lipsă manual
"""

import json
from datetime import datetime
from loguru import logger

logger.info("="*70)
logger.info("📝 MANUAL TRADE HISTORY UPDATE")
logger.info("="*70)

# Read current history
with open('trade_history.json', 'r') as f:
    trades = json.load(f)

logger.info(f"\n📊 Current status:")
logger.info(f"   Trades in file: {len(trades)}")
logger.info(f"   Last balance: ${trades[-1]['balance_after']:.2f}")
logger.info(f"   Last ticket: #{trades[-1]['ticket']}")

logger.info(f"\n⚠️  Need to add 4 more trades (from 11 to 15)")
logger.info(f"\n📋 Please provide details for missing trades:")
logger.info(f"   Format: Symbol, Direction, Entry, Exit, Profit, Date")

# AICI ADAUGI MANUAL TRANZACȚIILE LIPSĂ
# Exemplu:
new_trades = [
    # {
    #     "ticket": 2012,
    #     "symbol": "GBPUSD",
    #     "direction": "BUY",
    #     "entry_price": 1.33100,
    #     "closing_price": 1.33700,
    #     "lot_size": 0.08,
    #     "open_time": "2025-12-05T10:00:00",
    #     "close_time": "2025-12-05T11:00:00",
    #     "status": "CLOSED",
    #     "profit": 46.00,
    #     "pips": 60.0,
    #     "balance_after": 1382.12
    # },
    # Add 3 more...
]

if new_trades:
    trades.extend(new_trades)
    
    with open('trade_history.json', 'w') as f:
        json.dump(trades, f, indent=4)
    
    logger.success(f"\n✅ Updated! Added {len(new_trades)} trades")
    logger.success(f"   New total: {len(trades)} trades")
    logger.success(f"   New balance: ${trades[-1]['balance_after']:.2f}")
else:
    logger.warning("\n⚠️  No new trades to add!")
    logger.info("\nEdit this file and add trade details in the 'new_trades' list")

logger.info("\n" + "="*70)
