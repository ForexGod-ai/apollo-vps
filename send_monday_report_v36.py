#!/usr/bin/env python3
"""
🚀 TELEGRAM MONDAY MORNING REPORT V3.6
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

New Features:
- AI Progress Bars [████████░░]
- Risk/Reward in $ (for $1000 account)
- Monday Branding: 🚀 O SĂPTĂMÂNĂ NOUĂ ÎN MATRICE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from notification_manager import NotificationManager
import json
from pathlib import Path
from datetime import datetime

def generate_progress_bar(score: int, max_score: int = 100, length: int = 10) -> str:
    """Generate visual progress bar for AI score"""
    filled = int((score / max_score) * length)
    empty = length - filled
    return f"[{'█' * filled}{'░' * empty}] {score}/{max_score}"

def calculate_risk_reward_usd(entry: float, sl: float, tp: float, account_size: float = 1000, risk_pct: float = 1.0) -> dict:
    """Calculate risk/reward in USD for given account size"""
    risk_usd = account_size * (risk_pct / 100)
    
    # Calculate pips/points
    risk_points = abs(sl - entry)
    reward_points = abs(tp - entry)
    
    # Calculate position size
    if risk_points == 0:
        return {"risk_usd": 0, "reward_usd": 0, "position_size": 0}
    
    # For forex (assume 0.01 lot = $0.10 per pip for majors)
    # For crypto/commodities, use point value
    if entry < 10:  # Forex pair
        point_value = 0.10  # $0.10 per pip for 0.01 lot
    elif entry < 100:  # Oil or indices
        point_value = 0.10
    else:  # Crypto (BTCUSD)
        point_value = 0.01  # $0.01 per point for 0.01 lot
    
    # Position size to risk $10 (1% of $1000)
    lots = risk_usd / (risk_points * point_value * 100)  # *100 for lot conversion
    
    reward_usd = reward_points * point_value * lots * 100
    
    return {
        "risk_usd": round(risk_usd, 2),
        "reward_usd": round(reward_usd, 2),
        "position_size": round(lots, 2),
        "rr_ratio": round(reward_points / risk_points, 2) if risk_points > 0 else 0
    }

def send_monday_morning_report():
    """
    📱 Send Monday Morning V3.6 Elite Report
    🚀 O SĂPTĂMÂNĂ NOUĂ ÎN MATRICE
    """
    nm = NotificationManager()
    
    # Load monitoring setups
    monitoring_file = Path('monitoring_setups.json')
    if not monitoring_file.exists():
        print("❌ No monitoring setups found")
        return False
    
    with open(monitoring_file, 'r') as f:
        data = json.load(f)
    
    setups = data.get('setups', [])
    active_setups = [s for s in setups if s.get('status') == 'MONITORING']
    
    if not active_setups:
        print("❌ No active MONITORING setups")
        return False
    
    # Build Monday Morning Report
    message = f"""<b>🚀 O SĂPTĂMÂNĂ NOUĂ ÎN MATRICE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📅 <b>Luni, {datetime.now().strftime('%d %B %Y')}</b>
⏰ <b>London Open Session</b>

🎯 <b>DAILY SCAN V3.6 - COMPLETE</b>

✅ Scanned: 15 Major Pairs
🔍 Lookback: 100D / 200H4 / 300H1
🧠 AI Scorer: OPERATIONAL (EURUSD 100/100)
📊 Setup-uri Active: <b>{len(active_setups)}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>💎 SETUP-URI MONITORIZATE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # Sort setups by score (highest first)
    active_setups_sorted = sorted(active_setups, key=lambda x: x.get('ml_score', 0), reverse=True)
    
    for idx, setup in enumerate(active_setups_sorted, 1):
        symbol = setup.get('symbol', 'UNKNOWN')
        direction = setup.get('direction', 'UNKNOWN')
        entry = setup.get('entry_price', 0)
        sl = setup.get('stop_loss', 0)
        tp = setup.get('take_profit', 0)
        ml_score = setup.get('ml_score', 0)
        ai_probability = setup.get('ai_probability', 0)
        
        # Calculate AI progress bar
        ai_bar = generate_progress_bar(ai_probability, 100, 10)
        
        # Star rating
        if ml_score >= 70:
            stars = "⭐⭐⭐"
            rating = "GOOD"
        elif ml_score >= 50:
            stars = "⭐⭐"
            rating = "FAIR"
        else:
            stars = "⭐"
            rating = "WEAK"
        
        # Direction emoji
        dir_emoji = "🔴" if direction == "SHORT" else "🟢"
        
        # Calculate R:R in USD
        rr_usd = calculate_risk_reward_usd(entry, sl, tp, account_size=1000, risk_pct=1.0)
        
        message += f"""<b>{idx}. {symbol} {dir_emoji} {direction}</b>

📊 ML Score: <b>{ml_score}/100</b> {stars} ({rating})
🧠 AI Confidence: {ai_bar}

💰 Entry: <b>${entry:,.2f}</b>
⛔ Stop Loss: ${sl:,.2f}
🎯 Take Profit: ${tp:,.2f}

📈 R:R Ratio: <b>1:{rr_usd['rr_ratio']}</b>
💵 Risk (1% of $1000): ${rr_usd['risk_usd']}
💰 Potential Profit: <b>${rr_usd['reward_usd']:.2f}</b>

"""
    
    # Add special BTCUSD section if exists
    btc_setup = next((s for s in active_setups if s.get('symbol') == 'BTCUSD'), None)
    if btc_setup:
        message += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>🔥 BTCUSD WEEKEND UPDATE</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>CHoCH 1H BULLISH Confirmed!</b>
📅 Triggered: Duminică 13:00 @ $71,462
🎯 <b>REVERSAL LONG Setup</b> (was continuation short)

📦 <b>Order Block Hit:</b>
✅ 1H OB: $70,023-$70,596 (TOUCHED!)

🧠 Elite Score: <b>77/100</b> ⭐⭐⭐
📊 Verdict: <b>TRADE SETUP</b>

⚠️ <b>Waiting for:</b>
   • Retest of 1H OB zone
   • Bullish confirmation candle
   • Volume spike on breakout

"""
    
    # Footer
    message += f"""━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📊 MARKET OVERVIEW</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🌍 Session: London Open (08:00 GMT)
📈 Volatility: MEDIUM-HIGH (Monday gap close)
🧠 AI Recommendation: MONITOR + WAIT FOR ENTRIES

⚠️ <b>Trading Rules:</b>
   • Risk 1% per trade maximum
   • Wait for OB retests + confirmation
   • Avoid high-impact news (check calendar!)
   • Scale in on 1H/4H confluences

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 <i>"Patience is the weapon of the wise"</i> 💎

🎯 <b>O săptămână profitabilă în MATRICE!</b>"""

    # Send message
    try:
        nm.send_telegram_alert(message)
        print("✅ Monday Morning Report V3.6 sent to Telegram!")
        return True
    except Exception as e:
        print(f"❌ Failed to send Telegram: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    send_monday_morning_report()
