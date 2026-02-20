#!/usr/bin/env python3
"""
🧠 AI PROBABILITY ANALYZER
──────────────────
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

Calculates probability score (1-10) based on historical data
Analyzes: Symbol, Timeframe, Hour, Session (London/NY)
NON-BLOCKING: Always allows trade execution
──────────────────
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


class AIProbabilityAnalyzer:
    """Analyzes trade probability based on learned rules"""
    
    def __init__(self):
        self.learned_rules_file = Path("learned_rules.json")
        self.learned_rules = self._load_learned_rules()
    
    def _load_learned_rules(self) -> dict:
        """Load learned rules from file"""
        if not self.learned_rules_file.exists():
            return {}
        
        try:
            with open(self.learned_rules_file, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    
    def _get_trading_session(self, hour: int) -> str:
        """Determine trading session based on hour (UTC)"""
        # London Session: 08:00-16:00 UTC
        if 8 <= hour < 16:
            return "LONDON"
        # New York Session: 13:00-21:00 UTC (overlap 13:00-16:00)
        elif 13 <= hour < 21:
            return "NEW_YORK"
        # Overlap Session: 13:00-16:00 UTC
        elif 13 <= hour < 16:
            return "OVERLAP"
        # Asian Session: 00:00-08:00 UTC
        elif 0 <= hour < 8:
            return "ASIAN"
        # After hours: 21:00-00:00 UTC
        else:
            return "AFTER_HOURS"
    
    def calculate_probability_score(
        self,
        symbol: str,
        timeframe: str = "4H",
        hour: Optional[int] = None,
        pattern: Optional[str] = None
    ) -> Dict:
        """
        Calculate probability score (1-10) based on learned rules
        
        Returns:
            {
                'score': 7,  # 1-10
                'confidence': 'MEDIUM',
                'factors': {
                    'symbol_quality': 'Excellent (PF: 2.54)',
                    'timeframe_quality': 'Strong',
                    'timing': 'Good - London session',
                    'historical_context': '32 trades analyzed'
                },
                'recommendation': 'EXECUTE',
                'warning': None  # or "⚠️ LOW PROBABILITY WARNING"
            }
        """
        if not self.learned_rules or self.learned_rules.get('total_trades_analyzed', 0) == 0:
            return {
                'score': 5,  # Neutral
                'confidence': 'UNKNOWN',
                'factors': {
                    'ml_status': 'No historical data - run strategy_optimizer.py first'
                },
                'recommendation': 'EXECUTE',
                'warning': None
            }
        
        # Get current hour if not provided
        if hour is None:
            hour = datetime.now().hour
        
        # Determine session
        session = self._get_trading_session(hour)
        
        # Start with neutral score (5/10)
        score = 5.0
        factors = {}
        
        # 1. Symbol Quality (+/- 2 points)
        if symbol in self.learned_rules.get('profit_factor_by_pair', {}):
            pair_data = self.learned_rules['profit_factor_by_pair'][symbol]
            pf = pair_data['profit_factor']
            win_rate = pair_data['win_rate']
            total_trades = pair_data['total_trades']
            
            if pf >= 2.0:
                score += 2
                factors['symbol_quality'] = f"Excellent (PF: {pf:.2f}, {win_rate:.0f}% win rate, {total_trades} trades)"
            elif pf >= 1.5:
                score += 1.5
                factors['symbol_quality'] = f"Very Good (PF: {pf:.2f}, {win_rate:.0f}% win rate)"
            elif pf >= 1.0:
                score += 1
                factors['symbol_quality'] = f"Good (PF: {pf:.2f}, {win_rate:.0f}% win rate)"
            elif pf >= 0.5:
                score -= 1
                factors['symbol_quality'] = f"Below Average (PF: {pf:.2f}, {win_rate:.0f}% win rate)"
            else:
                score -= 2
                factors['symbol_quality'] = f"Poor (PF: {pf:.2f}, {win_rate:.0f}% win rate, {total_trades} trades)"
        else:
            factors['symbol_quality'] = "Unknown - no historical data for this pair"
        
        # 2. Timeframe Quality (+/- 1.5 points)
        if timeframe in self.learned_rules.get('profit_factor_by_timeframe', {}):
            tf_data = self.learned_rules['profit_factor_by_timeframe'][timeframe]
            pf = tf_data['profit_factor']
            
            if pf >= 1.5:
                score += 1.5
                factors['timeframe_quality'] = f"Strong ({timeframe}: PF {pf:.2f})"
            elif pf >= 1.0:
                score += 1
                factors['timeframe_quality'] = f"Decent ({timeframe}: PF {pf:.2f})"
            else:
                score -= 1
                factors['timeframe_quality'] = f"Weak ({timeframe}: PF {pf:.2f})"
        else:
            factors['timeframe_quality'] = f"{timeframe} - no historical data"
        
        # 3. Timing Analysis (+/- 2.5 points)
        blackout_hours = [p['hour_start'] for p in self.learned_rules.get('blackout_periods', [])]
        
        if hour in blackout_hours:
            # Find blackout details
            blackout = next(
                (p for p in self.learned_rules.get('blackout_periods', []) if p['hour_start'] == hour),
                None
            )
            if blackout:
                score -= 2.5
                factors['timing'] = f"🔴 BLACKOUT HOUR ({hour}:00 - {blackout['win_rate']:.1f}% win rate, {blackout['total_trades']} trades)"
        else:
            score += 1.5
            factors['timing'] = f"✅ Good timing ({hour}:00 - {session} session)"
        
        # 4. Pattern Quality (+/- 1 point) - if provided
        if pattern and pattern in self.learned_rules.get('pattern_success_rate', {}):
            pattern_data = self.learned_rules['pattern_success_rate'][pattern]
            win_rate = pattern_data['win_rate']
            total = pattern_data['total_trades']
            
            if win_rate >= 60:
                score += 1
                factors['pattern_quality'] = f"Reliable ({pattern}: {win_rate:.0f}% success, {total} trades)"
            elif win_rate >= 50:
                score += 0.5
                factors['pattern_quality'] = f"Decent ({pattern}: {win_rate:.0f}% success)"
            else:
                score -= 1
                factors['pattern_quality'] = f"Risky ({pattern}: {win_rate:.0f}% success, {total} trades)"
        
        # Cap score between 1-10
        score = max(1, min(10, score))
        score = round(score)
        
        # Determine confidence level
        if score >= 8:
            confidence = "VERY HIGH"
        elif score >= 7:
            confidence = "HIGH"
        elif score >= 5:
            confidence = "MEDIUM"
        elif score >= 3:
            confidence = "LOW"
        else:
            confidence = "VERY LOW"
        
        # Historical context
        total_analyzed = self.learned_rules.get('total_trades_analyzed', 0)
        factors['historical_context'] = f"Based on {total_analyzed} historical trades"
        
        # Warning for low probability
        warning = None
        if score < 5:
            warning = "⚠️ PROBABILITATE SCĂZUTĂ CONFORM ISTORICULUI!"
        
        return {
            'score': score,
            'confidence': confidence,
            'factors': factors,
            'recommendation': 'EXECUTE',  # ALWAYS execute (non-blocking)
            'warning': warning
        }
    
    def format_telegram_analysis(self, analysis: Dict, symbol: str) -> str:
        """
        Format AI analysis for Telegram message
        
        Returns formatted text section to add to trade alert
        """
        score = analysis['score']
        confidence = analysis['confidence']
        factors = analysis['factors']
        warning = analysis['warning']
        
        # Score visualization (1-10 scale)
        filled_bars = score
        empty_bars = 10 - score
        score_bar = "🟩" * filled_bars + "⬜" * empty_bars
        
        # Confidence emoji
        if score >= 8:
            score_emoji = "🟢"
        elif score >= 5:
            score_emoji = "🟡"
        else:
            score_emoji = "🔴"
        
        message = f"""
──────────────────
🧠 <b>AI PROBABILITY ANALYSIS</b>
──────────────────
{score_emoji} <b>AI Score: {score}/10</b> ({confidence})
{score_bar}

📊 <b>Analysis Factors:</b>"""
        
        for factor_name, factor_desc in factors.items():
            # Clean up factor name
            factor_clean = factor_name.replace('_', ' ').title()
            message += f"\n  • <b>{factor_clean}:</b> {factor_desc}"
        
        if warning:
            message += f"\n\n{warning}"
        
        message += "\n\n🤖 <b>AI Recommendation:</b> EXECUTE (system learns from all trades)"
        
        return message


# Singleton instance
_analyzer_instance = None

def get_analyzer() -> AIProbabilityAnalyzer:
    """Get or create analyzer instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = AIProbabilityAnalyzer()
    return _analyzer_instance


if __name__ == "__main__":
    # Test analyzer
    analyzer = AIProbabilityAnalyzer()
    
    test_cases = [
        {'symbol': 'GBPUSD', 'timeframe': '4H', 'hour': 14, 'pattern': 'ORDER_BLOCK'},
        {'symbol': 'GBPUSD', 'timeframe': '4H', 'hour': 10, 'pattern': 'ORDER_BLOCK'},
        {'symbol': 'NZDUSD', 'timeframe': '4H', 'hour': 10, 'pattern': 'ORDER_BLOCK'},
        {'symbol': 'AUDUSD', 'timeframe': '4H', 'hour': 15, 'pattern': 'ORDER_BLOCK'},
    ]
    
    print("\n" + "━" * 60)
    print("🧪 TESTING AI PROBABILITY ANALYZER")
    print("━" * 60)
    
    for test in test_cases:
        result = analyzer.calculate_probability_score(**test)
        
        print(f"\n{test['symbol']} @ {test['hour']}:00")
        print(f"  Score: {result['score']}/10 ({result['confidence']})")
        print(f"  Recommendation: {result['recommendation']}")
        if result['warning']:
            print(f"  {result['warning']}")
        print(f"  Factors:")
        for k, v in result['factors'].items():
            print(f"    • {k}: {v}")
    
    print("\n" + "━" * 60)
    print("✨ Glitch in Matrix by ФорексГод ✨")
    print("🧠 AI-Powered • 💎 Smart Money")
    print("━" * 60)
