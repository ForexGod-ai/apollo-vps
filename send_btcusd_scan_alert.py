#!/usr/bin/env python3
"""
Send BTCUSD Elite Scan Results to Telegram
Formatted with HTML, Star Rating, Entry Zones
"""
from notification_manager import NotificationManager
import json

def send_btcusd_scan_alert():
    """
    📱 Send BTCUSD Elite Scan to Telegram
    """
    nm = NotificationManager()
    
    # Load scan results
    try:
        with open('btcusd_elite_scan_results.json', 'r', encoding='utf-8') as f:
            results = json.load(f)
    except Exception as e:
        print(f"❌ Error loading results: {e}")
        results = {
            'symbol': 'BTCUSD',
            'current_price': 69285.19,
            'trend': 'BEARISH',
            'setup_type': 'CONTINUATION',
            'setup_direction': 'SHORT',
            'total_score': 77,
            'ai_score': 47,
            'recommendation': 'TRADE',
            'order_blocks': [
                {'timeframe': 'Daily', 'direction': 'BULLISH', 'zone_low': 90282, 'zone_high': 90425, 'score': 6},
                {'timeframe': '4H', 'direction': 'BEARISH', 'zone_low': 84130, 'zone_high': 84499, 'score': 6},
                {'timeframe': '1H', 'direction': 'BEARISH', 'zone_low': 77129, 'zone_high': 78177, 'score': 6}
            ],
            'fvgs': [
                {'timeframe': 'Daily', 'direction': 'BULLISH', 'gap_size': 8.302, 'zone_low': 89972, 'zone_high': 97442},
                {'timeframe': '4H', 'direction': 'BEARISH', 'gap_size': 0.485, 'zone_low': 65676, 'zone_high': 65995}
            ]
        }
    
    # Star rating based on score
    score = results['total_score']
    if score >= 90:
        stars = "⭐⭐⭐⭐⭐"
        rating = "PERFECT"
    elif score >= 80:
        stars = "⭐⭐⭐⭐"
        rating = "EXCELLENT"
    elif score >= 70:
        stars = "⭐⭐⭐"
        rating = "GOOD"
    elif score >= 60:
        stars = "⭐⭐"
        rating = "FAIR"
    else:
        stars = "⭐"
        rating = "WEAK"
    
    # Verdict emoji
    if results['recommendation'] == 'TRADE':
        verdict_emoji = "🚀"
        verdict_text = "TRADE SETUP"
    elif results['recommendation'] == 'MONITOR':
        verdict_emoji = "⏳"
        verdict_text = "MONITOR"
    else:
        verdict_emoji = "❌"
        verdict_text = "NO TRADE"
    
    # Get OB info
    obs = results.get('order_blocks', [])
    daily_ob = next((ob for ob in obs if ob['timeframe'] == 'Daily'), None)
    h4_ob = next((ob for ob in obs if ob['timeframe'] == '4H'), None)
    h1_ob = next((ob for ob in obs if ob['timeframe'] == '1H'), None)
    
    # Get FVG info
    fvgs = results.get('fvgs', [])
    daily_fvg = next((fvg for fvg in fvgs if fvg['timeframe'] == 'Daily'), None)
    h4_fvg = next((fvg for fvg in fvgs if fvg['timeframe'] == '4H'), None)
    
    # Build HTML message
    message = f"""<b>🎯 BTCUSD ELITE SCAN - V3.5 ORDER BLOCKS</b>

──────────────────
<b>📊 PRICE ACTION</b>
──────────────────

💰 Current: <b>${results['current_price']:,.2f}</b>
📉 Recent High: <b>$95,496</b> → Low: <b>$59,843</b>
📊 Trend: <b>{results['trend']}</b>
🔄 Setup: <b>{results['setup_type']} {results['setup_direction']}</b>

──────────────────
<b>📦 ORDER BLOCKS DETECTED</b>
──────────────────
"""
    
    if daily_ob:
        message += f"""<b>1️⃣ Daily OB ({daily_ob['direction']})</b>
   📍 Zone: ${daily_ob['zone_low']:,.0f} - ${daily_ob['zone_high']:,.0f}
   💎 Score: {daily_ob['score']}/10
   🎯 Role: Ultimate resistance

"""
    
    if h4_ob:
        message += f"""<b>2️⃣ 4H OB ({h4_ob['direction']})</b>
   📍 Zone: ${h4_ob['zone_low']:,.0f} - ${h4_ob['zone_high']:,.0f}
   💎 Score: {h4_ob['score']}/10
   🎯 Role: Secondary target

"""
    
    if h1_ob:
        message += f"""<b>3️⃣ 1H OB ({h1_ob['direction']}) ⭐ PRIMARY ENTRY</b>
   📍 Zone: ${h1_ob['zone_low']:,.0f} - ${h1_ob['zone_high']:,.0f}
   💎 Score: {h1_ob['score']}/10
   🎯 Role: Entry zone

"""
    
    message += f"""──────────────────
<b>📊 VALID FVG GAPS</b>
──────────────────
"""
    
    if daily_fvg:
        message += f"""
<b>• Daily FVG ({daily_fvg['direction']})</b>
   📏 Gap: <b>{daily_fvg['gap_size']:.2f}%</b> ⭐⭐⭐⭐⭐
   📍 Zone: ${daily_fvg['zone_low']:,.0f} - ${daily_fvg['zone_high']:,.0f}
"""
    
    if h4_fvg:
        message += f"""
<b>• 4H FVG ({h4_fvg['direction']})</b>
   📏 Gap: <b>{h4_fvg['gap_size']:.2f}%</b> ⭐⭐⭐
   📍 Zone: ${h4_fvg['zone_low']:,.0f} - ${h4_fvg['zone_high']:,.0f}
"""
    
    message += f"""
──────────────────
<b>🏆 FINAL VERDICT</b>
──────────────────

📊 Score: <b>{score}/100</b> {stars}
🎯 Rating: <b>{rating}</b>
🧠 AI Confidence: <b>{results.get('ai_score', 0)}/100</b>

{verdict_emoji} <b>{verdict_text}</b>

"""
    
    if results['recommendation'] == 'TRADE' and h1_ob:
        # Calculate R:R
        entry = (h1_ob['zone_low'] + h1_ob['zone_high']) / 2
        sl = h1_ob['zone_high'] + 500  # Buffer above OB
        tp = 59843  # Recent low
        risk = sl - entry
        reward = entry - tp
        rr = reward / risk if risk > 0 else 0
        
        message += f"""──────────────────
<b>📍 TRADING PLAN</b>
──────────────────

<b>SHORT BTCUSD</b>

🎯 Entry Zone: <b>${h1_ob['zone_low']:,.0f} - ${h1_ob['zone_high']:,.0f}</b>
⛔ Stop Loss: <b>${sl:,.0f}</b>
💰 Take Profit: <b>${tp:,.0f}</b> (Recent Low)

📊 Risk:Reward: <b>1:{rr:.1f}</b>

⚠️ Wait for price to reach 1H OB zone
⚠️ Look for bearish confirmation (rejection wick)
⚠️ Use 0.5-1% risk per trade

"""
    
    message += f"""──────────────────
✨ <b>Glitch in Matrix by ФорексГод</b>
🧠 AI-Powered • 💎 Smart Money
──────────────────"""

    # Send message
    try:
        nm.send_telegram_alert(message)
        print("✅ Telegram alert sent!")
        return True
    except Exception as e:
        print(f"❌ Failed to send Telegram: {e}")
        return False


if __name__ == "__main__":
    send_btcusd_scan_alert()
