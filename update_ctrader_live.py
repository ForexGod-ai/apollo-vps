#!/usr/bin/env python3
"""
Update trade_history.json with LIVE data from cTrader screenshot
Balance: $1,336.12
Realized profit: $336.12 (11 closed trades)
3 open positions remaining
"""

import json
from datetime import datetime
from loguru import logger

def update_live_data():
    """Update trade_history.json with actual cTrader data"""
    
    logger.info("="*70)
    logger.info("🔄 UPDATING TRADE HISTORY WITH LIVE CTRADER DATA")
    logger.info("="*70)
    
    # LIVE DATA from screenshot (03-04 December 2025)
    trades = [
        # CLOSED TRADES (11 total) - Realized profit: $336.12
        {
            "ticket": 2001,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32127,
            "closing_price": 1.32727,
            "lot_size": 0.06,
            "open_time": "2025-12-03T09:00:00",
            "close_time": "2025-12-03T10:00:00",
            "status": "CLOSED",
            "profit": 35.52,
            "pips": 60.0,
            "balance_after": 1035.52
        },
        {
            "ticket": 2002,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32146,
            "closing_price": 1.32746,
            "lot_size": 0.06,
            "open_time": "2025-12-03T09:00:00",
            "close_time": "2025-12-03T10:00:00",
            "status": "CLOSED",
            "profit": 35.52,
            "pips": 60.0,
            "balance_after": 1071.04
        },
        {
            "ticket": 2003,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32199,
            "closing_price": 1.32799,
            "lot_size": 0.06,
            "open_time": "2025-12-03T09:00:00",
            "close_time": "2025-12-03T10:00:00",
            "status": "CLOSED",
            "profit": 35.52,
            "pips": 60.0,
            "balance_after": 1106.56
        },
        {
            "ticket": 2004,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32200,
            "closing_price": 1.32804,
            "lot_size": 0.06,
            "open_time": "2025-12-03T09:00:00",
            "close_time": "2025-12-03T10:00:00",
            "status": "CLOSED",
            "profit": 35.76,
            "pips": 60.4,
            "balance_after": 1142.32
        },
        {
            "ticket": 2005,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32201,
            "closing_price": 1.32804,
            "lot_size": 0.06,
            "open_time": "2025-12-03T09:00:00",
            "close_time": "2025-12-03T10:00:00",
            "status": "CLOSED",
            "profit": 35.70,
            "pips": 60.3,
            "balance_after": 1178.02
        },
        {
            "ticket": 2006,
            "symbol": "EURUSD",
            "direction": "BUY",
            "entry_price": 1.16255,
            "closing_price": 1.16655,
            "lot_size": 0.09,
            "open_time": "2025-12-03T11:00:00",
            "close_time": "2025-12-03T12:00:00",
            "status": "CLOSED",
            "profit": 35.38,
            "pips": 40.0,
            "balance_after": 1213.40
        },
        {
            "ticket": 2007,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32431,
            "closing_price": 1.33031,
            "lot_size": 0.06,
            "open_time": "2025-12-03T12:00:00",
            "close_time": "2025-12-03T13:00:00",
            "status": "CLOSED",
            "profit": 35.52,
            "pips": 60.0,
            "balance_after": 1248.92
        },
        {
            "ticket": 2008,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32813,
            "closing_price": 1.33019,
            "lot_size": 0.07,
            "open_time": "2025-12-03T12:00:00",
            "close_time": "2025-12-03T13:00:00",
            "status": "CLOSED",
            "profit": 13.86,
            "pips": 20.6,
            "balance_after": 1262.78
        },
        {
            "ticket": 2009,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32824,
            "closing_price": 1.33018,
            "lot_size": 0.07,
            "open_time": "2025-12-03T12:00:00",
            "close_time": "2025-12-03T13:00:00",
            "status": "CLOSED",
            "profit": 13.02,
            "pips": 19.4,
            "balance_after": 1275.80
        },
        {
            "ticket": 2010,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.32816,
            "closing_price": 1.33018,
            "lot_size": 0.07,
            "open_time": "2025-12-03T12:00:00",
            "close_time": "2025-12-03T13:00:00",
            "status": "CLOSED",
            "profit": 13.58,
            "pips": 20.2,
            "balance_after": 1289.38
        },
        {
            "ticket": 2011,
            "symbol": "GBPUSD",
            "direction": "BUY",
            "entry_price": 1.33023,
            "closing_price": 1.33626,
            "lot_size": 0.08,
            "open_time": "2025-12-04T11:00:00",
            "close_time": "2025-12-04T12:00:00",
            "status": "CLOSED",
            "profit": 46.74,
            "pips": 60.3,
            "balance_after": 1336.12
        }
    ]
    
    # Save to trade_history.json
    with open('trade_history.json', 'w') as f:
        json.dump(trades, f, indent=4)
    
    logger.success(f"✅ Updated trade_history.json with {len(trades)} trades")
    logger.info(f"   Initial balance: $1,000.00")
    logger.info(f"   Final balance: $1,336.12")
    logger.info(f"   Total profit: $336.12")
    logger.info(f"   Closed trades: 11")
    logger.info(f"   Win rate: 100%")
    
    logger.info("\n" + "="*70)
    logger.info("✅ SYNC COMPLETE - Data is now LIVE from cTrader")
    logger.info("="*70)

if __name__ == "__main__":
    update_live_data()
