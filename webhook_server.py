"""
Server Flask pentru primirea webhook-urilor de la TradingView
"""
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from loguru import logger
import hmac
import hashlib
import json
from datetime import datetime
from dotenv import load_dotenv
import os

from signal_processor import SignalProcessor
from ai_validator import AISignalValidator

load_dotenv()

app = Flask(__name__, template_folder='templates')
CORS(app)

# Configurare
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'change_this_secret')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 5001))

# Inițializare procesoare
signal_processor = SignalProcessor()
ai_validator = AISignalValidator()

# Stocare semnale
received_signals = []


def verify_signature(payload, signature):
    """Verifică semnătura webhook-ului pentru securitate"""
    if not signature:
        return False
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint pentru verificarea stării serverului"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'signals_received': len(received_signals)
    })


@app.route('/', methods=['GET'])
def index():
    """Servește dashboard-ul HTML"""
    try:
        return render_template('dashboard.html')
    except Exception as e:
        logger.error(f"Error loading dashboard: {e}")
        return jsonify({'error': 'Dashboard not found', 'details': str(e)}), 404


@app.route('/webhook', methods=['POST'])
def receive_webhook():
    """
    Primește semnale de la TradingView
    
    Format așteptat JSON:
    {
        "action": "buy" | "sell" | "close",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "price": 1.0850,
        "stop_loss": 1.0820,
        "take_profit": 1.0920,
        "strategy": "trend_following",
        "timestamp": "2024-01-01T12:00:00",
        "metadata": {
            "rsi": 65,
            "macd": 0.0012,
            "volume": 12345
        }
    }
    """
    try:
        # Verificare securitate (doar în producție)
        signature = request.headers.get('X-TradingView-Signature')
        enable_signature = os.getenv('WEBHOOK_SIGNATURE_CHECK', 'False').lower() == 'true'
        if enable_signature and signature:
            payload = request.get_data(as_text=True)
            if not verify_signature(payload, signature):
                logger.warning("Webhook cu semnătură invalidă!")
                return jsonify({'error': 'Invalid signature'}), 401
        
        # Parsare date
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        # Validare câmpuri obligatorii
        required_fields = ['action', 'symbol']
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            return jsonify({
                'error': 'Missing required fields',
                'missing': missing_fields
            }), 400
        
        # Adaugă timestamp dacă lipsește
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        # Log semnal primit
        logger.info(f"📥 Semnal primit: {data['action'].upper()} {data['symbol']}")
        
        # Salvează semnal
        received_signals.append({
            'data': data,
            'received_at': datetime.now().isoformat(),
            'processed': False
        })
        
        # Procesare asincronă
        result = signal_processor.process_signal(data, ai_validator)
        
        # Update status
        received_signals[-1]['processed'] = True
        received_signals[-1]['result'] = result
        
        return jsonify({
            'status': 'success',
            'message': 'Signal received and processed',
            'signal_id': len(received_signals) - 1,
            'result': result
        }), 200
        
    except Exception as e:
        logger.error(f"❌ Eroare la procesarea webhook: {e}")
        return jsonify({
            'error': 'Internal server error',
            'message': str(e)
        }), 500


@app.route('/signals', methods=['GET'])
def get_signals():
    """Returnează toate semnalele primite"""
    return jsonify({
        'total': len(received_signals),
        'signals': received_signals[-50:]  # Ultimele 50
    })


@app.route('/api/trades', methods=['GET', 'POST'])
def handle_trades():
    """
    GET: Returnează toate trade-urile active
    POST: Primește un trade nou de la auto_trader
    """
    if request.method == 'GET':
        # Load trade history
        try:
            trades_file = 'received_trades.json'
            if os.path.exists(trades_file):
                with open(trades_file, 'r') as f:
                    trades = json.load(f)
                return jsonify({
                    'success': True,
                    'total': len(trades),
                    'trades': trades
                })
            return jsonify({'success': True, 'total': 0, 'trades': []})
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500
    
    elif request.method == 'POST':
        # Receive new trade
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({'success': False, 'error': 'No data provided'}), 400
            
            # Add timestamp if missing
            if 'timestamp' not in data:
                data['timestamp'] = datetime.now().isoformat()
            
            # Save trade
            trades_file = 'received_trades.json'
            
            if os.path.exists(trades_file):
                with open(trades_file, 'r') as f:
                    trades = json.load(f)
            else:
                trades = []
            
            trades.append(data)
            
            with open(trades_file, 'w') as f:
                json.dump(trades, f, indent=2)
            
            logger.info(f"✅ Trade saved: {data.get('symbol')} {data.get('direction')} @ {data.get('entry')}")
            
            return jsonify({
                'success': True,
                'message': 'Trade received',
                'trade_id': len(trades) - 1
            }), 200
            
        except Exception as e:
            logger.error(f"Error saving trade: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/signals/stats', methods=['GET'])
def get_stats():
    """Returnează statistici despre semnale"""
    processed = sum(1 for s in received_signals if s.get('processed'))
    successful = sum(1 for s in received_signals 
                    if s.get('result', {}).get('executed', False))
    
    return jsonify({
        'total_received': len(received_signals),
        'processed': processed,
        'successful': successful,
        'success_rate': (successful / processed * 100) if processed > 0 else 0
    })


@app.route('/test', methods=['POST'])
def test_signal():
    """Endpoint pentru testare - trimite un semnal de test"""
    test_data = {
        "action": "buy",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "price": 1.0850,
        "stop_loss": 1.0820,
        "take_profit": 1.0920,
        "strategy": "test",
        "timestamp": datetime.now().isoformat()
    }
    
    logger.info("🧪 Procesare semnal de test")
    result = signal_processor.process_signal(test_data, ai_validator)
    
    return jsonify({
        'status': 'test_complete',
        'result': result
    })


def start_webhook_server(host='0.0.0.0', port=None):
    """Pornește serverul webhook"""
    port = port or WEBHOOK_PORT
    
    logger.info("=" * 60)
    logger.info("🚀 Trading AI Agent Webhook Server")
    logger.info("=" * 60)
    logger.info(f"📡 Server pornit pe http://{host}:{port}")
    logger.info(f"📥 Webhook URL: http://{host}:{port}/webhook")
    logger.info(f"🏥 Health check: http://{host}:{port}/health")
    logger.info("=" * 60)
    
    app.run(host=host, port=port, debug=False)


if __name__ == '__main__':
    start_webhook_server()
