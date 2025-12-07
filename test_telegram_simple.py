"""Test Telegram Connection"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

print('🚀 Testare conexiune Telegram...\n')
print(f'Token: {token[:10]}...{token[-10:]}')
print(f'Chat ID: {chat_id}\n')

url = f'https://api.telegram.org/bot{token}/sendMessage'
message = """🤖 *ForexGod AI Bot - CONECTAT!* 🤖

✅ Sistemul este LIVE și sincronizat!
✅ Auto-trade ACTIVAT
✅ Morning scan la 09:00
✅ cTrader conectat

💰 Cont: $1,336.12
📊 15 trades executate
📈 Profit: $336.12

🔥 *Gata să scanez piața!* ��"""

data = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
response = requests.post(url, json=data)

if response.status_code == 200:
    print('✅ TELEGRAM CONECTAT CU SUCCES!')
    print(f'✅ Mesaj trimis la: 🔮 ForexGod - Glitch in Matrix 🧠')
    print(f'\n🎯 Verifică Telegram acum!')
else:
    print(f'❌ Eroare: {response.status_code}')
    print(response.text)
