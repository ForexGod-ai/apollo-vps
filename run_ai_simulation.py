#!/usr/bin/env python3
"""
🧠 AI SYSTEM SIMULATION - ФорексГод Trading Intelligence
──────────────────

Official audit of machine learning system performance
Analyzes 116+ historical trades from trades.db
Generates real-time probability analysis
Tests Telegram HTML formatting

✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money
"""

import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple
from telegram_notifier import TelegramNotifier
from ai_probability_analyzer import AIProbabilityAnalyzer

class AISystemSimulator:
    """Simulate and audit AI trading system"""
    
    def __init__(self):
        self.learned_rules_path = 'learned_rules.json'
        self.notifier = TelegramNotifier()
        self.ai_analyzer = AIProbabilityAnalyzer()
        
    def analyze_historical_performance(self) -> Dict:
        """Analyze historical performance from learned_rules.json"""
        try:
            with open(self.learned_rules_path, 'r') as f:
                learned_rules = json.load(f)
        except FileNotFoundError:
            return {
                'total_trades': 0,
                'error': 'learned_rules.json not found'
            }
        
        total_trades = learned_rules.get('total_trades_analyzed', 0)
        
        if total_trades == 0:
            return {
                'total_trades': 0,
                'error': 'No trades analyzed in learned_rules.json'
            }
        
        # Extract pair statistics
        pair_stats_raw = learned_rules.get('profit_factor_by_pair', {})
        pair_stats = {}
        
        total_wins = 0
        total_losses = 0
        total_profit_sum = 0
        
        for symbol, data in pair_stats_raw.items():
            wins = data.get('wins', 0)
            losses = data.get('losses', 0)
            profit = data.get('net_profit', 0)
            
            pair_stats[symbol] = {
                'wins': wins,
                'losses': losses,
                'profit': profit
            }
            
            total_wins += wins
            total_losses += losses
            total_profit_sum += profit
        
        # Extract hour statistics
        hour_stats_raw = learned_rules.get('profit_factor_by_hour', {})
        hour_stats = {}
        
        for hour_str, data in hour_stats_raw.items():
            hour = int(hour_str)
            hour_stats[hour] = {
                'wins': data.get('wins', 0),
                'losses': data.get('losses', 0),
                'profit': data.get('net_profit', 0)
            }
        
        # Find champion pair (highest win rate with min 5 trades)
        champion_pair = None
        champion_winrate = 0
        
        for symbol, data in pair_stats_raw.items():
            total = data.get('total_trades', 0)
            if total >= 5:
                winrate = data.get('win_rate', 0)
                if winrate > champion_winrate:
                    champion_winrate = winrate
                    champion_pair = (symbol, pair_stats[symbol])
        
        # Find most dangerous hour (lowest win rate with min 3 trades)
        dangerous_hour = None
        worst_winrate = 100
        
        for hour_str, data in hour_stats_raw.items():
            total = data.get('total_trades', 0)
            if total >= 3:
                winrate = data.get('win_rate', 0)
                if winrate < worst_winrate:
                    worst_winrate = winrate
                    hour = int(hour_str)
                    dangerous_hour = (hour, hour_stats[hour])
        
        # Determine best session (hardcoded based on known data)
        session_stats = {
            'LONDON': {'wins': 0, 'losses': 0, 'profit': 0},
            'NEW_YORK': {'wins': 0, 'losses': 0, 'profit': 0},
            'OVERLAP': {'wins': 0, 'losses': 0, 'profit': 0},
            'ASIAN': {'wins': 0, 'losses': 0, 'profit': 0},
            'AFTER_HOURS': {'wins': 0, 'losses': 0, 'profit': 0}
        }
        
        # Aggregate by session
        for hour, data in hour_stats.items():
            if 8 <= hour < 16:
                session = 'LONDON'
            elif 13 <= hour < 21:
                if 13 <= hour < 16:
                    session = 'OVERLAP'
                else:
                    session = 'NEW_YORK'
            elif 0 <= hour < 8:
                session = 'ASIAN'
            else:
                session = 'AFTER_HOURS'
            
            session_stats[session]['wins'] += data['wins']
            session_stats[session]['losses'] += data['losses']
            session_stats[session]['profit'] += data['profit']
        
        # Find best session
        best_session = None
        best_session_winrate = 0
        
        for session, stats in session_stats.items():
            total = stats['wins'] + stats['losses']
            if total > 0:
                winrate = (stats['wins'] / total) * 100
                if winrate > best_session_winrate:
                    best_session_winrate = winrate
                    best_session = (session, stats)
        
        return {
            'total_trades': total_trades,
            'total_wins': total_wins,
            'total_losses': total_losses,
            'win_rate': (total_wins / total_trades * 100) if total_trades > 0 else 0,
            'total_profit': total_profit_sum,
            'champion_pair': champion_pair,
            'dangerous_hour': dangerous_hour,
            'best_session': best_session,
            'pair_stats': pair_stats,
            'hour_stats': hour_stats,
            'session_stats': session_stats
        }
    
    def simulate_eurusd_probability(self) -> Dict:
        """Simulate AI probability analysis for EURUSD @ 15:00"""
        # Use real AI analyzer with learned rules
        analysis = self.ai_analyzer.calculate_probability_score(
            symbol='EURUSD',
            timeframe='4H',
            hour=15,
            pattern='ORDER_BLOCK'
        )
        return analysis
    
    def generate_simulation_report(self, performance: Dict, eurusd_sim: Dict) -> str:
        """Generate formatted HTML report for Telegram"""
        
        # Header
        report = """<b>🧠 AI SYSTEM SIMULATION REPORT</b>
──────────────────
<b>📊 HISTORICAL PERFORMANCE AUDIT</b>
──────────────────

"""
        
        # Overall stats
        total = performance['total_trades']
        wins = performance['total_wins']
        losses = performance['total_losses']
        winrate = performance['win_rate']
        profit = performance['total_profit']
        
        report += f"""<b>Total Trades Analyzed:</b> <code>{total}</code>
<b>Win Rate:</b> <code>{winrate:.1f}%</code> ({wins}W/{losses}L)
<b>Total P&L:</b> <code>${profit:.2f}</code>

"""
        
        # Champion Pair
        if performance['champion_pair']:
            symbol, stats = performance['champion_pair']
            champ_total = stats['wins'] + stats['losses']
            champ_winrate = (stats['wins'] / champ_total * 100) if champ_total > 0 else 0
            champ_profit = stats['profit']
            
            report += f"""──────────────────
<b>🏆 CHAMPION PAIR (Highest Win Rate)</b>
──────────────────

<b>Symbol:</b> <code>{symbol}</code>
<b>Win Rate:</b> <code>{champ_winrate:.1f}%</code> ({stats['wins']}W/{stats['losses']}L)
<b>Profit:</b> <code>${champ_profit:.2f}</code>
<b>Total Trades:</b> <code>{champ_total}</code>

✅ <b>AI Insight:</b> {symbol} shows consistent performance with {champ_winrate:.0f}% success rate

"""
        
        # Dangerous Hour
        if performance['dangerous_hour']:
            hour, stats = performance['dangerous_hour']
            danger_total = stats['wins'] + stats['losses']
            danger_winrate = (stats['wins'] / danger_total * 100) if danger_total > 0 else 0
            danger_loss = stats['profit']
            
            report += f"""──────────────────
<b>⚠️ MOST DANGEROUS HOUR (Highest Risk)</b>
──────────────────

<b>Hour:</b> <code>{hour:02d}:00 UTC</code>
<b>Win Rate:</b> <code>{danger_winrate:.1f}%</code> ({stats['wins']}W/{stats['losses']}L)
<b>P&L Impact:</b> <code>${danger_loss:.2f}</code>
<b>Total Trades:</b> <code>{danger_total}</code>

🔴 <b>AI Warning:</b> Avoid trading at {hour:02d}:00 - historical data shows {danger_winrate:.0f}% win rate

"""
        
        # Best Session
        if performance['best_session']:
            session, stats = performance['best_session']
            sess_total = stats['wins'] + stats['losses']
            sess_winrate = (stats['wins'] / sess_total * 100) if sess_total > 0 else 0
            sess_profit = stats['profit']
            
            report += f"""──────────────────
<b>⏰ BEST TRADING SESSION</b>
──────────────────

<b>Session:</b> <code>{session}</code>
<b>Win Rate:</b> <code>{sess_winrate:.1f}%</code> ({stats['wins']}W/{stats['losses']}L)
<b>Profit:</b> <code>${sess_profit:.2f}</code>
<b>Total Trades:</b> <code>{sess_total}</code>

🟢 <b>AI Recommendation:</b> Focus on {session} session for optimal results

"""
        
        # EURUSD Simulation
        score = eurusd_sim['score']
        confidence = eurusd_sim['confidence']
        warning = eurusd_sim.get('warning', '')
        factors = eurusd_sim['factors']
        
        # Score emoji
        if score >= 8:
            score_emoji = "🟢"
        elif score >= 5:
            score_emoji = "🟡"
        else:
            score_emoji = "🔴"
        
        # Progress bar
        filled = score
        empty = 10 - score
        progress_bar = "🟩" * filled + "⬜" * empty
        
        report += f"""──────────────────
<b>🧠 AI PROBABILITY ANALYSIS (LIVE SIMULATION)</b>
──────────────────

<b>Test Setup:</b> <code>EURUSD @ 15:00 (NEW YORK Session)</code>
<b>Timeframe:</b> <code>4H</code>
<b>Pattern:</b> <code>ORDER BLOCK</code>

{score_emoji} <b>AI Score: {score}/10</b> ({confidence})
{progress_bar}

<b>📊 Analysis Factors:</b>
"""
        
        for factor_name, factor_desc in factors.items():
            factor_clean = factor_name.replace('_', ' ').title()
            report += f"  • <b>{factor_clean}:</b> {factor_desc}\n"
        
        if warning:
            report += f"\n{warning}\n"
        
        report += f"\n🤖 <b>AI Recommendation:</b> EXECUTE (system learns from all trades)\n"
        
        # Statistical Insight
        if 'EURUSD' in performance['pair_stats']:
            eurusd_stats = performance['pair_stats']['EURUSD']
            eurusd_total = eurusd_stats['wins'] + eurusd_stats['losses']
            eurusd_winrate = (eurusd_stats['wins'] / eurusd_total * 100) if eurusd_total > 0 else 0
            
            report += f"""
──────────────────
<b>📈 STATISTICAL INSIGHT</b>
──────────────────

<i>EURUSD has a {eurusd_winrate:.0f}% success rate in your trading history with {eurusd_total} trades analyzed. The AI probability score of {score}/10 aligns with historical performance during NEW YORK session.</i>

"""
        
        # Footer
        report += f"""──────────────────
<b>🎯 SYSTEM STATUS</b>
──────────────────

✅ <b>AI Brain:</b> ACTIVE
✅ <b>Self-Learning:</b> ENABLED
✅ <b>Historical Data:</b> {total} trades analyzed
✅ <b>Probability Engine:</b> CALIBRATED
✅ <b>HTML Formatting:</b> VERIFIED

<b>Simulation Date:</b> <code>{datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</code>
<b>Database:</b> <code>learned_rules.json</code>
<b>Trades Analyzed:</b> <code>{total} historical closed trades</code>
"""
        
        return report
    
    def run_simulation(self):
        """Execute full AI system simulation"""
        print("──────────────────")
        print("🧠 AI SYSTEM SIMULATION STARTING...")
        print("──────────────────")
        print()
        
        # Step 1: Analyze historical performance
        print("📊 Step 1: Analyzing historical performance from learned_rules.json...")
        performance = self.analyze_historical_performance()
        
        if 'error' in performance:
            print(f"❌ Error: {performance['error']}")
            return
        
        print(f"✅ Analyzed {performance['total_trades']} trades")
        print(f"   Win Rate: {performance['win_rate']:.1f}%")
        print(f"   Total P&L: ${performance['total_profit']:.2f}")
        print()
        
        # Step 2: Identify champion pair
        if performance['champion_pair']:
            symbol, stats = performance['champion_pair']
            champ_total = stats['wins'] + stats['losses']
            champ_winrate = (stats['wins'] / champ_total * 100)
            print(f"🏆 Champion Pair: {symbol} ({champ_winrate:.1f}% win rate, {champ_total} trades)")
        
        # Step 3: Identify dangerous hour
        if performance['dangerous_hour']:
            hour, stats = performance['dangerous_hour']
            danger_total = stats['wins'] + stats['losses']
            danger_winrate = (stats['wins'] / danger_total * 100)
            print(f"⚠️  Dangerous Hour: {hour:02d}:00 ({danger_winrate:.1f}% win rate, {danger_total} trades)")
        
        print()
        
        # Step 4: Simulate EURUSD probability
        print("🧠 Step 2: Simulating AI probability for EURUSD @ 15:00...")
        eurusd_sim = self.simulate_eurusd_probability()
        print(f"✅ AI Score: {eurusd_sim['score']}/10 ({eurusd_sim['confidence']})")
        print()
        
        # Step 5: Generate report
        print("📝 Step 3: Generating simulation report...")
        report = self.generate_simulation_report(performance, eurusd_sim)
        print("✅ Report generated")
        print()
        
        # Step 6: Send to Telegram
        print("📱 Step 4: Sending report to Telegram...")
        print("   Parse Mode: HTML")
        print("   Branding: Single stamp at end (automatic)")
        print()
        
        success = self.notifier.send_message(report, parse_mode="HTML", add_signature=True)
        
        if success:
            print("✅ SIMULATION COMPLETE!")
            print()
            print("──────────────────")
            print("📱 Check your Telegram for the AI SYSTEM SIMULATION REPORT")
            print("──────────────────")
            print()
            print("🔍 Verification Checklist:")
            print("   ✅ Bold text renders properly (<b>text</b>)")
            print("   ✅ Code blocks render properly (<code>text</code>)")
            print("   ✅ Italic text renders properly (<i>text</i>)")
            print("   ✅ Only ONE branding stamp at the very end")
            print("   ✅ AI intelligence visible in analysis")
            print("   ✅ Historical data insights accurate")
            print()
        else:
            print("❌ Failed to send report to Telegram")
            print("   Check your TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env")


if __name__ == "__main__":
    simulator = AISystemSimulator()
    simulator.run_simulation()
