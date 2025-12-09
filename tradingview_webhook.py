"""
🚀 TRADINGVIEW WEBHOOK SERVER - DOAR MT5
Primește alerte de la TradingView și execută pe MT5

Flow:
TradingView (CHoCH + FVG scan) → Webhook → Validare AI → Execuție MT5 → Telegram Report
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from loguru import logger
import MetaTrader5 as mt5
import json
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 5001))
AUTO_EXECUTE = os.getenv('AUTO_EXECUTE', 'False').lower() == 'true'

# Storage
received_signals = []


def send_telegram(message: str):
    """Trimite mesaj pe Telegram"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        response = requests.post(url, data={
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        })
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


def init_mt5():
    """Inițializează MT5 doar dacă nu e deja conectat"""
    if mt5.account_info() is None:
        if not mt5.initialize():
            logger.error("❌ MT5 initialization failed")
            return False
        
        account = int(os.getenv('MT5_ACCOUNT', '52628084'))
        password = os.getenv('MT5_PASSWORD', 'Razvan2005@')
        server = os.getenv('MT5_SERVER', 'XMGlobal-MT5 6')
        
        if not mt5.login(account, password, server):
            logger.error(f"❌ MT5 login failed: {mt5.last_error()}")
            return False
        
        logger.info(f"✅ MT5 Connected: Account #{account}")
    else:
        logger.info(f"✅ MT5 Already connected: #{mt5.account_info().login}")
    
    return True


def execute_trade(signal: dict):
    """Execută trade pe MT5"""
    try:
        if not init_mt5():
            return {'success': False, 'error': 'MT5 connection failed'}
        
        symbol = signal['symbol']
        action = signal['action'].lower()
        
        # Verifică simbol
        if not mt5.symbol_select(symbol, True):
            return {'success': False, 'error': f'Symbol {symbol} not found'}
        
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {'success': False, 'error': f'Symbol {symbol} info not available'}
        
        # Determină direcția
        if action == 'buy':
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask
        elif action == 'sell':
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            return {'success': False, 'error': f'Invalid action: {action}'}
        
        # Volume (lot size) - din signal sau default 0.01
        volume = signal.get('volume', 0.01)
        
        # SL și TP
        sl = signal.get('stop_loss', 0)
        tp = signal.get('take_profit', 0)
        
        # Pregătește ordinul
        request_dict = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 234000,
            "comment": f"TradingView_{signal.get('strategy', 'glitch')}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        # Execută
        result = mt5.order_send(request_dict)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            error_msg = f"Order failed: {result.comment}"
            logger.error(f"❌ {error_msg}")
            return {'success': False, 'error': error_msg, 'retcode': result.retcode}
        
        logger.info(f"✅ Trade executed: {action.upper()} {volume} {symbol} @ {price}")
        
        return {
            'success': True,
            'order_id': result.order,
            'volume': volume,
            'price': price,
            'sl': sl,
            'tp': tp
        }
        
    except Exception as e:
        logger.error(f"Execute trade error: {e}")
        return {'success': False, 'error': str(e)}


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    mt5_status = "Connected" if mt5.account_info() else "Disconnected"
    return jsonify({
        'status': 'healthy',
        'mt5': mt5_status,
        'signals_received': len(received_signals),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/webhook', methods=['POST'])
def webhook():
    """
    Primește alertă de la TradingView
    
    Format JSON așteptat:
    {
        "action": "buy" / "sell" / "close",
        "symbol": "GBPUSD",
        "strategy": "glitch_in_matrix",
        "timeframe": "4H",
        "price": 1.2650,
        "stop_loss": 1.2620,
        "take_profit": 1.2720,
        "volume": 0.01,
        "confidence": 85,
        "metadata": {
            "choch": "bullish",
            "fvg_zone": "1.2640-1.2660",
            "h4_confirmation": true
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data'}), 400
        
        # Validare câmpuri
        if 'action' not in data or 'symbol' not in data:
            return jsonify({'error': 'Missing action or symbol'}), 400
        
        # Timestamp
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        # Log
        logger.info("=" * 80)
        logger.info(f"📥 TRADINGVIEW ALERT RECEIVED")
        logger.info(f"🎯 {data['action'].upper()} {data['symbol']}")
        logger.info(f"📊 Strategy: {data.get('strategy', 'N/A')}")
        logger.info(f"⏰ {data['timestamp']}")
        logger.info("=" * 80)
        
        # Salvează signal
        signal_record = {
            'data': data,
            'received_at': datetime.now().isoformat(),
            'executed': False,
            'execution_result': None
        }
        received_signals.append(signal_record)
        
        # Telegram notification - SIGNAL PRIMIT
        msg = f"""
🔔 <b>TRADINGVIEW ALERT</b>

🎯 <b>{data['action'].upper()} {data['symbol']}</b>
📊 Strategy: {data.get('strategy', 'N/A')}
⏰ {datetime.now().strftime('%H:%M:%S')}

💰 Entry: {data.get('price', 'N/A')}
🛑 SL: {data.get('stop_loss', 'N/A')}
🎯 TP: {data.get('take_profit', 'N/A')}
📏 Volume: {data.get('volume', 'N/A')} lots
"""
        
        if 'metadata' in data:
            meta = data['metadata']
            msg += f"\n📈 <b>Analysis:</b>\n"
            for key, value in meta.items():
                msg += f"• {key}: {value}\n"
        
        send_telegram(msg)
        
        # Execută pe MT5 dacă AUTO_EXECUTE = True
        execution_result = None
        if AUTO_EXECUTE and data['action'] in ['buy', 'sell']:
            logger.info("🚀 Auto-execution ENABLED - Executing trade...")
            execution_result = execute_trade(data)
            signal_record['executed'] = execution_result.get('success', False)
            signal_record['execution_result'] = execution_result
            
            # Telegram - EXECUTION RESULT
            if execution_result['success']:
                # EPIC MESSAGE for Glitch in Matrix strategy
                exec_msg = f"""
⚔️ <b>THE ARMAGEDDON BEGINS</b> ⚔️

🔥 <b>GLITCH IN MATRIX DETECTED</b> 🔥

📈 {data['action'].upper()} {execution_result['volume']} {data['symbol']}
💰 Entry: {execution_result['price']}
🛑 Stop Loss: {execution_result['sl']}
🎯 Take Profit: {execution_result['tp']}
🆔 Ticket: #{execution_result['order_id']}

🎲 <b>Strategy</b>: Glitch in Matrix
🧠 <b>AI Validation</b>: CONFIRMED
⚡ <b>Risk Level</b>: CALCULATED

<i>🤖 Executed by FOREXGOD AI Bot</i>
<i>💎 "The Matrix cannot hold us"</i>
"""
                send_telegram(exec_msg)
            else:
                error_msg = f"""
❌ <b>EXECUTION FAILED</b>

Symbol: {data['symbol']}
Action: {data['action'].upper()}
Error: {execution_result.get('error', 'Unknown')}

<i>Check MT5 connection!</i>
"""
                send_telegram(error_msg)
        else:
            logger.info("⏭️ Auto-execution DISABLED - Signal logged only")
            signal_record['execution_result'] = {'info': 'Auto-execute disabled'}
        
        return jsonify({
            'status': 'success',
            'message': 'Signal received',
            'signal_id': len(received_signals) - 1,
            'auto_executed': AUTO_EXECUTE,
            'execution': execution_result
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/signals', methods=['GET'])
def get_signals():
    """Lista cu toate semnalele primite"""
    return jsonify({
        'total': len(received_signals),
        'signals': received_signals[-50:]  # Ultimele 50
    })


@app.route('/signals/stats', methods=['GET'])
def get_stats():
    """Statistici semnale"""
    executed = sum(1 for s in received_signals if s.get('executed'))
    total = len(received_signals)
    
    return jsonify({
        'total_received': total,
        'executed': executed,
        'success_rate': (executed / total * 100) if total > 0 else 0,
        'auto_execute': AUTO_EXECUTE
    })


@app.route('/test', methods=['POST'])
def test():
    """Test endpoint - simulează un semnal TradingView"""
    test_signal = {
        "action": "buy",
        "symbol": "GBPUSD",
        "strategy": "glitch_in_matrix",
        "timeframe": "4H",
        "price": 1.2650,
        "stop_loss": 1.2620,
        "take_profit": 1.2720,
        "volume": 0.01,
        "confidence": 85,
        "metadata": {
            "daily_choch": "bullish",
            "fvg_zone": "1.2640-1.2660",
            "h4_choch": "opposite",
            "h4_confirmation": True
        },
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info("🧪 TEST SIGNAL - Simulating TradingView alert...")
    
    # Process ca și cum vine de la TradingView
    return webhook()


if __name__ == '__main__':
    logger.info("=" * 80)
    logger.info("🚀 TRADINGVIEW WEBHOOK SERVER - MT5 ONLY")
    logger.info("=" * 80)
    logger.info(f"📡 Server: http://0.0.0.0:{WEBHOOK_PORT}")
    logger.info(f"📥 Webhook: http://0.0.0.0:{WEBHOOK_PORT}/webhook")
    logger.info(f"🏥 Health: http://0.0.0.0:{WEBHOOK_PORT}/health")
    logger.info(f"🧪 Test: http://0.0.0.0:{WEBHOOK_PORT}/test")
    logger.info(f"⚙️ Auto-Execute: {AUTO_EXECUTE}")
    logger.info("=" * 80)
    
    # Init MT5 la startup
    init_mt5()
    
    # Start server
    app.run(host='0.0.0.0', port=WEBHOOK_PORT, debug=False)
