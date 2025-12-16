"""Simple Flask test"""
from flask import Flask

app = Flask(__name__)

@app.route('/')
def index():
    return '<h1>Dashboard Active!</h1>'

@app.route('/health')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    print("🚀 Starting test server on http://127.0.0.1:8080")
    app.run(host='127.0.0.1', port=8080, debug=False, use_reloader=False, threaded=True)
