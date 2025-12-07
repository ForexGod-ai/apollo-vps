"""
Manual sync cTrader history to JSON
Rulează acest script o singură dată pentru a popula trade_history.json
"""
import json
from datetime import datetime

# Date LIVE din cTrader (din screenshot-ul tău)
# Ticket 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16
trades_from_ctrader = [
    # Trade #6
    {
        "ticket": 6,
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
    # Trade #7
    {
        "ticket": 7,
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
    # Trade #8
    {
        "ticket": 8,
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
    # Trade #9
    {
        "ticket": 9,
        "symbol": "GBPUSD",
        "direction": "BUY",
        "entry_price": 1.32200,
        "closing_price": 1.32804,
        "lot_size": 0.06,
        "open_time": "2025-12-03T09:00:00",
        "close_time": "2025-12-03T11:00:00",
        "status": "CLOSED",
        "profit": 35.76,
        "pips": 60.4,
        "balance_after": 1142.32
    },
    # Trade #10
    {
        "ticket": 10,
        "symbol": "GBPUSD",
        "direction": "BUY",
        "entry_price": 1.32201,
        "closing_price": 1.32804,
        "lot_size": 0.06,
        "open_time": "2025-12-03T09:00:00",
        "close_time": "2025-12-03T11:00:00",
        "status": "CLOSED",
        "profit": 35.70,
        "pips": 60.3,
        "balance_after": 1178.02
    },
    # Trade #11
    {
        "ticket": 11,
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
    # Trade #12
    {
        "ticket": 12,
        "symbol": "GBPUSD",
        "direction": "BUY",
        "entry_price": 1.32431,
        "closing_price": 1.33031,
        "lot_size": 0.06,
        "open_time": "2025-12-03T12:00:00",
        "close_time": "2025-12-03T12:00:00",
        "status": "CLOSED",
        "profit": 35.52,
        "pips": 60.0,
        "balance_after": 1248.92
    },
    # Trade #13
    {
        "ticket": 13,
        "symbol": "GBPUSD",
        "direction": "BUY",
        "entry_price": 1.32813,
        "closing_price": 1.33019,
        "lot_size": 0.07,
        "open_time": "2025-12-03T12:00:00",
        "close_time": "2025-12-03T12:00:00",
        "status": "CLOSED",
        "profit": 13.86,
        "pips": 20.6,
        "balance_after": 1262.78
    },
    # Trade #14
    {
        "ticket": 14,
        "symbol": "GBPUSD",
        "direction": "BUY",
        "entry_price": 1.32824,
        "closing_price": 1.33018,
        "lot_size": 0.07,
        "open_time": "2025-12-03T12:00:00",
        "close_time": "2025-12-03T12:00:00",
        "status": "CLOSED",
        "profit": 13.02,
        "pips": 19.4,
        "balance_after": 1275.80
    },
    # Trade #15
    {
        "ticket": 15,
        "symbol": "GBPUSD",
        "direction": "BUY",
        "entry_price": 1.32816,
        "closing_price": 1.33018,
        "lot_size": 0.07,
        "open_time": "2025-12-03T12:00:00",
        "close_time": "2025-12-03T12:00:00",
        "status": "CLOSED",
        "profit": 13.58,
        "pips": 20.2,
        "balance_after": 1289.38
    },
    # Trade #16
    {
        "ticket": 16,
        "symbol": "GBPUSD",
        "direction": "BUY",
        "entry_price": 1.33023,
        "closing_price": 1.33628,
        "lot_size": 0.08,
        "open_time": "2025-12-04T11:00:00",
        "close_time": "2025-12-04T11:00:00",
        "status": "CLOSED",
        "profit": 46.74,
        "pips": 60.5,
        "balance_after": 1336.12
    }
]

# Scrie în fișier
with open('trade_history.json', 'w') as f:
    json.dump(trades_from_ctrader, f, indent=4)

print(f"✅ Sincronizat {len(trades_from_ctrader)} trades din cTrader!")
print(f"💰 Balance final: ${trades_from_ctrader[-1]['balance_after']:.2f}")
print(f"📈 Total profit: ${trades_from_ctrader[-1]['balance_after'] - 1000:.2f}")
