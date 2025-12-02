"""
Re-post active trades to website dashboard
"""
import json
import requests
from loguru import logger

# Load trade history
with open('trade_history.json', 'r') as f:
    history = json.load(f)

active_trades = [t for t in history if t['status'] == 'OPEN']

logger.info(f"\n🔄 Re-posting {len(active_trades)} active trades to website...")

url = "http://127.0.0.1:5001/api/trades"
success_count = 0

for trade in active_trades:
    try:
        trade_data = {
            'symbol': trade['symbol'],
            'direction': trade['direction'],
            'entry': trade.get('entry', trade.get('entry_price')),
            'stop_loss': trade.get('stop_loss', trade.get('sl')),
            'take_profit': trade.get('take_profit', trade.get('tp')),
            'lot_size': trade.get('lot_size', trade.get('lots')),
            'risk_reward': trade.get('risk_reward', 0),
            'strategy': trade.get('strategy', trade.get('strategy_type', 'unknown')),
            'timestamp': trade['open_time'],
            'ticket': trade['ticket']
        }
        
        response = requests.post(url, json=trade_data, timeout=5)
        
        if response.status_code == 200:
            logger.info(f"✅ Posted trade #{trade['ticket']} - {trade['symbol']} {trade['direction']}")
            success_count += 1
        else:
            logger.warning(f"⚠️ Failed to post trade #{trade['ticket']}: {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Error posting trade #{trade['ticket']}: {e}")

logger.info(f"\n✅ Successfully posted {success_count}/{len(active_trades)} trades!")
print(f"\n🌐 Check website: http://127.0.0.1:5001/")
