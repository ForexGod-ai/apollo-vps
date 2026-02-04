#!/usr/bin/env python3
"""
Test ML Scoring Integration
"""
from strategy_optimizer import StrategyOptimizer

print("━" * 60)
print("🧪 TESTING ML SCORING SYSTEM")
print("━" * 60)

optimizer = StrategyOptimizer()

# Test scenarios from YOUR actual trading data
test_scenarios = [
    {
        'name': '✅ BEST: GBPUSD @ 09:00 (Best pair + Best hour)',
        'setup': {'symbol': 'GBPUSD', 'timeframe': '4H', 'hour': 9, 'pattern': 'ORDER_BLOCK'}
    },
    {
        'name': '⚠️ MIXED: GBPUSD @ 10:00 (Best pair + BLACKOUT hour)',
        'setup': {'symbol': 'GBPUSD', 'timeframe': '4H', 'hour': 10, 'pattern': 'ORDER_BLOCK'}
    },
    {
        'name': '🔴 WORST: NZDUSD @ 10:00 (Worst pair + BLACKOUT hour)',
        'setup': {'symbol': 'NZDUSD', 'timeframe': '4H', 'hour': 10, 'pattern': 'ORDER_BLOCK'}
    },
    {
        'name': '🏆 CHAMPION: AUDUSD @ 15:00 (Champion pair + Good hour)',
        'setup': {'symbol': 'AUDUSD', 'timeframe': '4H', 'hour': 15, 'pattern': 'ORDER_BLOCK'}
    },
]

for scenario in test_scenarios:
    print(f"\n{scenario['name']}")
    print("-" * 60)
    
    score = optimizer.calculate_setup_score(scenario['setup'])
    
    emoji = "🟢" if score['score'] >= 75 else "🟡" if score['score'] >= 60 else "🔴"
    print(f"{emoji} Score: {score['score']}/100 ({score['confidence']})")
    print(f"🤖 Recommendation: {score['recommendation']}")
    print(f"📊 Factors:")
    for factor, desc in score['factors'].items():
        print(f"   • {factor}: {desc}")

print("\n" + "━" * 60)
print("✨ Glitch in Matrix by ФорексГод ✨")
print("🧠 AI-Powered • 💎 Smart Money")
print("━" * 60)
