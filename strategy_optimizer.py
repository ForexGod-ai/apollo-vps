#!/usr/bin/env python3
"""
🧠 STRATEGY OPTIMIZER - Machine Learning Module
──────────────────
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

SELF-LEARNING SYSTEM:
- Analyzes 116+ closed trades from SQLite
- Identifies best timeframes & pairs (Profit Factor)
- Detects false breakout patterns (Blackout Periods)
- Optimizes SL/TP based on historical data
- Generates learned_rules.json for scanner integration
──────────────────
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Tuple
import statistics


class StrategyOptimizer:
    """Machine Learning optimizer that learns from past trades"""
    
    def __init__(self, db_path: str = "data/trades.db"):
        self.db_path = Path(db_path)
        
        # Load learned rules from file if exists
        self.learned_rules = self._load_learned_rules()
        
        if not self.learned_rules:
            # Default empty rules
            self.learned_rules = {
                "version": "1.0",
                "last_updated": datetime.now().isoformat(),
                "total_trades_analyzed": 0,
                "profit_factor_by_pair": {},
                "profit_factor_by_timeframe": {},
                "blackout_periods": [],
                "optimal_sl_tp": {},
                "pattern_success_rate": {},
                "metadata": {
                    "total_profit": 0,
                    "total_loss": 0,
                    "win_rate": 0,
                    "avg_win": 0,
                    "avg_loss": 0
                }
            }
        
        print("\n" + "━" * 60)
        print("🧠 STRATEGY OPTIMIZER - MACHINE LEARNING MODULE")
        print("━" * 60)
        print("✨ Glitch in Matrix by ФорексГод ✨")
        print("🧠 AI-Powered • 💎 Smart Money")
        print("━" * 60 + "\n")
    
    def _load_learned_rules(self) -> dict:
        """Load learned rules from file"""
        try:
            with open('learned_rules.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except Exception as e:
            print(f"⚠️  Error loading learned rules: {e}")
            return {}
    
    def load_trades_data(self) -> List[Dict]:
        """Load all closed trades from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Access by column name
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    ticket,
                    symbol,
                    direction,
                    volume,
                    open_time,
                    close_time,
                    open_price,
                    close_price,
                    profit,
                    commission,
                    swap,
                    stop_loss,
                    take_profit,
                    comment
                FROM closed_trades
                ORDER BY close_time ASC
            """)
            
            trades = []
            for row in cursor.fetchall():
                trade = {
                    'ticket': row['ticket'],
                    'symbol': row['symbol'],
                    'direction': row['direction'],
                    'volume': row['volume'],
                    'open_time': datetime.fromisoformat(row['open_time'].replace('Z', '+00:00')) if row['open_time'] else None,
                    'close_time': datetime.fromisoformat(row['close_time'].replace('Z', '+00:00')) if row['close_time'] else None,
                    'open_price': row['open_price'] or 0,
                    'close_price': row['close_price'] or 0,
                    'profit': row['profit'],
                    'commission': row['commission'] or 0,
                    'swap': row['swap'] or 0,
                    'stop_loss': row['stop_loss'],
                    'take_profit': row['take_profit'],
                    'comment': row['comment'] or '',
                    'net_profit': row['profit'] + (row['commission'] or 0) + (row['swap'] or 0)
                }
                
                # Calculate trade duration in hours
                if trade['open_time'] and trade['close_time']:
                    duration = trade['close_time'] - trade['open_time']
                    trade['duration_hours'] = duration.total_seconds() / 3600
                else:
                    trade['duration_hours'] = 0
                
                # Extract timeframe from comment if available
                trade['timeframe'] = self._extract_timeframe(trade['comment'])
                
                # Calculate pip movement
                if trade['open_price'] > 0 and trade['close_price'] > 0:
                    if 'JPY' in trade['symbol']:
                        trade['pips'] = abs(trade['close_price'] - trade['open_price']) * 100
                    else:
                        trade['pips'] = abs(trade['close_price'] - trade['open_price']) * 10000
                else:
                    trade['pips'] = 0
                
                trades.append(trade)
            
            conn.close()
            
            print(f"✅ Loaded {len(trades)} closed trades from database")
            return trades
            
        except Exception as e:
            print(f"❌ Error loading trades: {e}")
            return []
    
    def _extract_timeframe(self, comment: str) -> str:
        """Extract timeframe from trade comment"""
        if not comment:
            return "UNKNOWN"
        
        comment = comment.upper()
        
        if '1H' in comment or 'H1' in comment:
            return '1H'
        elif '4H' in comment or 'H4' in comment:
            return '4H'
        elif '15M' in comment or 'M15' in comment:
            return '15M'
        elif 'DAILY' in comment or 'D1' in comment:
            return 'DAILY'
        else:
            return 'UNKNOWN'
    
    def analyze_profit_factor_by_pair(self, trades: List[Dict]) -> Dict:
        """
        Calculate Profit Factor for each currency pair
        Profit Factor = Gross Profit / Gross Loss
        > 1.0 = Profitable
        """
        print("\n📊 ANALYZING PROFIT FACTOR BY PAIR...")
        print("━" * 60)
        
        pair_stats = defaultdict(lambda: {'wins': [], 'losses': []})
        
        for trade in trades:
            symbol = trade['symbol']
            profit = trade['net_profit']
            
            if profit > 0:
                pair_stats[symbol]['wins'].append(profit)
            elif profit < 0:
                pair_stats[symbol]['losses'].append(abs(profit))
        
        results = {}
        
        for symbol, stats in sorted(pair_stats.items()):
            total_wins = sum(stats['wins'])
            total_losses = sum(stats['losses'])
            win_count = len(stats['wins'])
            loss_count = len(stats['losses'])
            total_trades = win_count + loss_count
            
            # Calculate profit factor
            if total_losses > 0:
                profit_factor = total_wins / total_losses
            else:
                profit_factor = float('inf') if total_wins > 0 else 0
            
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            
            avg_win = statistics.mean(stats['wins']) if stats['wins'] else 0
            avg_loss = statistics.mean(stats['losses']) if stats['losses'] else 0
            
            results[symbol] = {
                'profit_factor': round(profit_factor, 2),
                'total_trades': total_trades,
                'wins': win_count,
                'losses': loss_count,
                'win_rate': round(win_rate, 2),
                'total_profit': round(total_wins, 2),
                'total_loss': round(total_losses, 2),
                'avg_win': round(avg_win, 2),
                'avg_loss': round(avg_loss, 2),
                'net_profit': round(total_wins - total_losses, 2),
                'recommendation': 'STRONG' if profit_factor >= 1.5 else 'GOOD' if profit_factor >= 1.0 else 'AVOID'
            }
            
            # Print results
            emoji = "🟢" if profit_factor >= 1.5 else "🟡" if profit_factor >= 1.0 else "🔴"
            print(f"{emoji} {symbol:8s} | PF: {profit_factor:5.2f} | Trades: {total_trades:3d} | "
                  f"Win Rate: {win_rate:5.1f}% | Net: ${total_wins - total_losses:+7.2f}")
        
        return results
    
    def analyze_profit_factor_by_timeframe(self, trades: List[Dict]) -> Dict:
        """Calculate Profit Factor for each timeframe"""
        print("\n📈 ANALYZING PROFIT FACTOR BY TIMEFRAME...")
        print("━" * 60)
        
        tf_stats = defaultdict(lambda: {'wins': [], 'losses': []})
        
        for trade in trades:
            timeframe = trade['timeframe']
            profit = trade['net_profit']
            
            if profit > 0:
                tf_stats[timeframe]['wins'].append(profit)
            elif profit < 0:
                tf_stats[timeframe]['losses'].append(abs(profit))
        
        results = {}
        
        for timeframe, stats in sorted(tf_stats.items()):
            total_wins = sum(stats['wins'])
            total_losses = sum(stats['losses'])
            win_count = len(stats['wins'])
            loss_count = len(stats['losses'])
            total_trades = win_count + loss_count
            
            if total_losses > 0:
                profit_factor = total_wins / total_losses
            else:
                profit_factor = float('inf') if total_wins > 0 else 0
            
            win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
            
            results[timeframe] = {
                'profit_factor': round(profit_factor, 2),
                'total_trades': total_trades,
                'wins': win_count,
                'losses': loss_count,
                'win_rate': round(win_rate, 2),
                'total_profit': round(total_wins, 2),
                'total_loss': round(total_losses, 2),
                'net_profit': round(total_wins - total_losses, 2),
                'recommendation': 'STRONG' if profit_factor >= 1.5 else 'GOOD' if profit_factor >= 1.0 else 'REVIEW'
            }
            
            emoji = "🟢" if profit_factor >= 1.5 else "🟡" if profit_factor >= 1.0 else "🔴"
            print(f"{emoji} {timeframe:8s} | PF: {profit_factor:5.2f} | Trades: {total_trades:3d} | "
                  f"Win Rate: {win_rate:5.1f}% | Net: ${total_wins - total_losses:+7.2f}")
        
        return results
    
    def detect_blackout_periods(self, trades: List[Dict]) -> List[Dict]:
        """
        Detect time periods with high false breakout rates
        Returns list of hours to avoid trading
        """
        print("\n⚠️  DETECTING BLACKOUT PERIODS (False Breakouts)...")
        print("━" * 60)
        
        # Group trades by hour of day
        hourly_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'profits': [], 'losses_list': []})
        
        for trade in trades:
            if not trade['open_time']:
                continue
            
            hour = trade['open_time'].hour
            profit = trade['net_profit']
            
            if profit > 0:
                hourly_stats[hour]['wins'] += 1
                hourly_stats[hour]['profits'].append(profit)
            else:
                hourly_stats[hour]['losses'] += 1
                hourly_stats[hour]['losses_list'].append(abs(profit))
        
        blackout_periods = []
        
        print("\n🕐 Hourly Performance Analysis:")
        print("-" * 60)
        
        for hour in range(24):
            stats = hourly_stats[hour]
            total = stats['wins'] + stats['losses']
            
            if total == 0:
                continue
            
            win_rate = (stats['wins'] / total * 100)
            total_profit = sum(stats['profits'])
            total_loss = sum(stats['losses_list'])
            net = total_profit - total_loss
            
            # Flag as blackout if:
            # 1. Win rate < 30% AND at least 5 trades
            # 2. OR net loss > $50 AND at least 3 trades
            is_blackout = False
            reason = ""
            
            if total >= 5 and win_rate < 30:
                is_blackout = True
                reason = f"Low win rate ({win_rate:.1f}%)"
            elif total >= 3 and net < -50:
                is_blackout = True
                reason = f"High losses (${net:.2f})"
            
            emoji = "🔴" if is_blackout else "🟢" if win_rate >= 50 else "🟡"
            
            print(f"{emoji} {hour:02d}:00-{hour+1:02d}:00 | "
                  f"Trades: {total:3d} | Win Rate: {win_rate:5.1f}% | "
                  f"Net: ${net:+7.2f}")
            
            if is_blackout:
                blackout_periods.append({
                    'hour_start': hour,
                    'hour_end': hour + 1,
                    'total_trades': total,
                    'win_rate': round(win_rate, 2),
                    'net_profit': round(net, 2),
                    'reason': reason,
                    'severity': 'HIGH' if net < -100 or win_rate < 20 else 'MEDIUM'
                })
                print(f"   ⚠️  BLACKOUT DETECTED: {reason}")
        
        if blackout_periods:
            print(f"\n🔴 BLACKOUT PERIODS IDENTIFIED: {len(blackout_periods)}")
            print("   Recommendation: Avoid trading during these hours!")
        else:
            print(f"\n✅ No significant blackout periods detected")
        
        return blackout_periods
    
    def optimize_sl_tp(self, trades: List[Dict]) -> Dict:
        """
        Backtest different SL/TP ratios on historical data
        Find optimal risk/reward that maximizes total profit
        """
        print("\n🎯 OPTIMIZING STOP LOSS & TAKE PROFIT...")
        print("━" * 60)
        
        # Filter trades with valid price data
        valid_trades = [t for t in trades if t['open_price'] > 0 and t['close_price'] > 0]
        
        if len(valid_trades) < 10:
            print("⚠️  Insufficient data for SL/TP optimization (need 10+ trades)")
            return {}
        
        print(f"📊 Backtesting on {len(valid_trades)} trades with valid price data\n")
        
        # Test different SL/TP scenarios
        scenarios = [
            {'name': 'Conservative', 'sl_pips': 30, 'tp_pips': 60, 'rr_ratio': 2.0},
            {'name': 'Balanced', 'sl_pips': 40, 'tp_pips': 80, 'rr_ratio': 2.0},
            {'name': 'Aggressive', 'sl_pips': 50, 'tp_pips': 100, 'rr_ratio': 2.0},
            {'name': 'Tight SL', 'sl_pips': 20, 'tp_pips': 60, 'rr_ratio': 3.0},
            {'name': 'Wide SL', 'sl_pips': 60, 'tp_pips': 120, 'rr_ratio': 2.0},
        ]
        
        results = {}
        
        for scenario in scenarios:
            sl_pips = scenario['sl_pips']
            tp_pips = scenario['tp_pips']
            
            wins = 0
            losses = 0
            total_profit = 0
            
            for trade in valid_trades:
                # Calculate pip movement
                pips_moved = trade['pips']
                
                # Determine if trade would have hit SL or TP
                if trade['direction'] == 'BUY':
                    # BUY trade simulation
                    if pips_moved >= tp_pips:
                        # Hit TP
                        wins += 1
                        total_profit += tp_pips * 10  # Assuming $10/pip
                    elif pips_moved <= -sl_pips:
                        # Hit SL
                        losses += 1
                        total_profit -= sl_pips * 10
                    else:
                        # Neither hit - use actual profit
                        if trade['net_profit'] > 0:
                            wins += 1
                        else:
                            losses += 1
                        total_profit += trade['net_profit']
                else:
                    # SELL trade simulation
                    if pips_moved >= tp_pips:
                        wins += 1
                        total_profit += tp_pips * 10
                    elif pips_moved <= -sl_pips:
                        losses += 1
                        total_profit -= sl_pips * 10
                    else:
                        if trade['net_profit'] > 0:
                            wins += 1
                        else:
                            losses += 1
                        total_profit += trade['net_profit']
            
            total_trades = wins + losses
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
            
            results[scenario['name']] = {
                'sl_pips': sl_pips,
                'tp_pips': tp_pips,
                'rr_ratio': scenario['rr_ratio'],
                'wins': wins,
                'losses': losses,
                'win_rate': round(win_rate, 2),
                'total_profit': round(total_profit, 2),
                'avg_profit_per_trade': round(total_profit / total_trades, 2) if total_trades > 0 else 0
            }
            
            emoji = "🟢" if total_profit > 0 else "🔴"
            print(f"{emoji} {scenario['name']:15s} | SL: {sl_pips:3d} | TP: {tp_pips:3d} | "
                  f"Win Rate: {win_rate:5.1f}% | Total P/L: ${total_profit:+8.2f}")
        
        # Find best scenario
        best_scenario = max(results.items(), key=lambda x: x[1]['total_profit'])
        print(f"\n🏆 BEST STRATEGY: {best_scenario[0]}")
        print(f"   SL: {best_scenario[1]['sl_pips']} pips | TP: {best_scenario[1]['tp_pips']} pips")
        print(f"   Potential Profit: ${best_scenario[1]['total_profit']:+.2f}")
        
        return results
    
    def calculate_pattern_success_rate(self, trades: List[Dict]) -> Dict:
        """
        Calculate success rate for different setup patterns
        Based on comment/setup description
        """
        print("\n🔍 ANALYZING PATTERN SUCCESS RATES...")
        print("━" * 60)
        
        pattern_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'profits': []})
        
        # Extract patterns from comments
        for trade in trades:
            comment = trade.get('comment', '').upper()
            
            # Identify pattern keywords
            patterns = []
            if 'OB' in comment or 'ORDER BLOCK' in comment:
                patterns.append('ORDER_BLOCK')
            if 'FVG' in comment or 'FAIR VALUE' in comment:
                patterns.append('FVG')
            if 'LIQUIDITY' in comment or 'LIQ' in comment:
                patterns.append('LIQUIDITY')
            if 'BREAK' in comment or 'BOS' in comment:
                patterns.append('BREAKOUT')
            if 'RETEST' in comment:
                patterns.append('RETEST')
            
            if not patterns:
                patterns = ['UNKNOWN']
            
            profit = trade['net_profit']
            
            for pattern in patterns:
                if profit > 0:
                    pattern_stats[pattern]['wins'] += 1
                    pattern_stats[pattern]['profits'].append(profit)
                else:
                    pattern_stats[pattern]['losses'] += 1
        
        results = {}
        
        for pattern, stats in sorted(pattern_stats.items()):
            total = stats['wins'] + stats['losses']
            win_rate = (stats['wins'] / total * 100) if total > 0 else 0
            avg_profit = statistics.mean(stats['profits']) if stats['profits'] else 0
            
            results[pattern] = {
                'total_trades': total,
                'wins': stats['wins'],
                'losses': stats['losses'],
                'win_rate': round(win_rate, 2),
                'avg_profit_per_win': round(avg_profit, 2),
                'confidence': 'HIGH' if total >= 10 and win_rate >= 50 else 'MEDIUM' if total >= 5 else 'LOW'
            }
            
            emoji = "🟢" if win_rate >= 50 else "🟡" if win_rate >= 40 else "🔴"
            print(f"{emoji} {pattern:15s} | Trades: {total:3d} | "
                  f"Win Rate: {win_rate:5.1f}% | Avg Win: ${avg_profit:6.2f}")
        
        return results
    
    def generate_learned_rules(self, trades: List[Dict]) -> Dict:
        """
        Generate learned_rules.json with all ML insights
        This file will be used by daily_scanner.py for scoring
        """
        print("\n📝 GENERATING LEARNED RULES...")
        print("━" * 60)
        
        # Run all analyses
        profit_by_pair = self.analyze_profit_factor_by_pair(trades)
        profit_by_timeframe = self.analyze_profit_factor_by_timeframe(trades)
        blackout_periods = self.detect_blackout_periods(trades)
        optimal_sl_tp = self.optimize_sl_tp(trades)
        pattern_success = self.calculate_pattern_success_rate(trades)
        
        # Calculate overall statistics
        total_profit = sum(t['net_profit'] for t in trades if t['net_profit'] > 0)
        total_loss = abs(sum(t['net_profit'] for t in trades if t['net_profit'] < 0))
        wins = len([t for t in trades if t['net_profit'] > 0])
        losses = len([t for t in trades if t['net_profit'] < 0])
        total = wins + losses
        
        # Build learned rules
        self.learned_rules = {
            "version": "1.0",
            "last_updated": datetime.now().isoformat(),
            "total_trades_analyzed": len(trades),
            
            "profit_factor_by_pair": profit_by_pair,
            "profit_factor_by_timeframe": profit_by_timeframe,
            "blackout_periods": blackout_periods,
            "optimal_sl_tp": optimal_sl_tp,
            "pattern_success_rate": pattern_success,
            
            "metadata": {
                "total_profit": round(total_profit, 2),
                "total_loss": round(total_loss, 2),
                "win_rate": round((wins / total * 100) if total > 0 else 0, 2),
                "total_wins": wins,
                "total_losses": losses,
                "avg_win": round(total_profit / wins, 2) if wins > 0 else 0,
                "avg_loss": round(total_loss / losses, 2) if losses > 0 else 0,
                "profit_factor": round(total_profit / total_loss, 2) if total_loss > 0 else 0
            },
            
            "recommendations": {
                "best_pairs": [pair for pair, data in profit_by_pair.items() if data['recommendation'] == 'STRONG'],
                "avoid_pairs": [pair for pair, data in profit_by_pair.items() if data['recommendation'] == 'AVOID'],
                "best_timeframe": max(profit_by_timeframe.items(), key=lambda x: x[1]['profit_factor'])[0] if profit_by_timeframe else None,
                "blackout_hours": [p['hour_start'] for p in blackout_periods],
                "optimal_strategy": max(optimal_sl_tp.items(), key=lambda x: x[1]['total_profit'])[0] if optimal_sl_tp else None
            }
        }
        
        return self.learned_rules
    
    def save_learned_rules(self, filename: str = "learned_rules.json"):
        """Save learned rules to JSON file"""
        filepath = Path(filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(self.learned_rules, f, indent=2)
            
            print(f"\n✅ Learned rules saved to: {filepath}")
            print(f"   Total trades analyzed: {self.learned_rules['total_trades_analyzed']}")
            print(f"   Best pairs: {', '.join(self.learned_rules['recommendations']['best_pairs'][:3])}")
            print(f"   Blackout hours: {len(self.learned_rules['recommendations']['blackout_hours'])}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error saving learned rules: {e}")
            return False
    
    def calculate_setup_score(self, setup: Dict) -> Dict:
        """
        Calculate confidence score for a new setup based on learned rules
        This will be used by daily_scanner.py
        
        Args:
            setup: {
                'symbol': 'EURUSD',
                'timeframe': '4H',
                'hour': 14,
                'pattern': 'ORDER_BLOCK'
            }
        
        Returns:
            {
                'score': 75,  # 0-100
                'confidence': 'HIGH',
                'factors': {...},
                'recommendation': 'TAKE' or 'SKIP'
            }
        """
        if not self.learned_rules or self.learned_rules['total_trades_analyzed'] == 0:
            return {
                'score': 50,
                'confidence': 'UNKNOWN',
                'recommendation': 'REVIEW',
                'factors': {'ml_status': 'No learned rules available - run strategy_optimizer.py first'}
            }
        
        score = 50  # Start neutral
        factors = {}
        
        # 1. Check pair profit factor (+/- 20 points)
        symbol = setup.get('symbol', '')
        if symbol in self.learned_rules['profit_factor_by_pair']:
            pair_data = self.learned_rules['profit_factor_by_pair'][symbol]
            pf = pair_data['profit_factor']
            
            if pf >= 1.5:
                score += 20
                factors['pair_quality'] = f"Excellent (PF: {pf:.2f})"
            elif pf >= 1.0:
                score += 10
                factors['pair_quality'] = f"Good (PF: {pf:.2f})"
            else:
                score -= 20
                factors['pair_quality'] = f"Poor (PF: {pf:.2f})"
        
        # 2. Check timeframe (+/- 15 points)
        timeframe = setup.get('timeframe', '')
        if timeframe in self.learned_rules['profit_factor_by_timeframe']:
            tf_data = self.learned_rules['profit_factor_by_timeframe'][timeframe]
            pf = tf_data['profit_factor']
            
            if pf >= 1.5:
                score += 15
                factors['timeframe_quality'] = f"Strong (PF: {pf:.2f})"
            elif pf >= 1.0:
                score += 8
                factors['timeframe_quality'] = f"Decent (PF: {pf:.2f})"
            else:
                score -= 15
                factors['timeframe_quality'] = f"Weak (PF: {pf:.2f})"
        
        # 3. Check blackout period (-25 points)
        hour = setup.get('hour', datetime.now().hour)
        if hour in self.learned_rules['recommendations']['blackout_hours']:
            score -= 25
            factors['timing'] = f"BLACKOUT HOUR ({hour}:00)"
        else:
            score += 10
            factors['timing'] = f"Good timing ({hour}:00)"
        
        # 4. Check pattern success rate (+/- 15 points)
        pattern = setup.get('pattern', 'UNKNOWN')
        if pattern in self.learned_rules['pattern_success_rate']:
            pattern_data = self.learned_rules['pattern_success_rate'][pattern]
            win_rate = pattern_data['win_rate']
            
            if win_rate >= 60:
                score += 15
                factors['pattern_quality'] = f"Reliable ({win_rate:.1f}% win rate)"
            elif win_rate >= 50:
                score += 8
                factors['pattern_quality'] = f"Decent ({win_rate:.1f}% win rate)"
            else:
                score -= 15
                factors['pattern_quality'] = f"Risky ({win_rate:.1f}% win rate)"
        
        # Cap score between 0-100
        score = max(0, min(100, score))
        
        # Determine confidence and recommendation
        if score >= 75:
            confidence = 'HIGH'
            recommendation = 'TAKE'
        elif score >= 60:
            confidence = 'MEDIUM'
            recommendation = 'TAKE'
        elif score >= 40:
            confidence = 'LOW'
            recommendation = 'REVIEW'
        else:
            confidence = 'VERY LOW'
            recommendation = 'SKIP'
        
        return {
            'score': round(score),
            'confidence': confidence,
            'recommendation': recommendation,
            'factors': factors
        }
    
    def calculate_ai_probability(
        self,
        symbol: str,
        hour: int,
        fvg_quality: float,
        choch_strength: int,
        pattern_type: str
    ) -> int:
        """
        Calculate AI confidence probability score (0-100)
        Used by elite scanners for advanced setup scoring
        
        Args:
            symbol: Trading pair (e.g., 'BTCUSD', 'EURUSD')
            hour: Current hour (0-23)
            fvg_quality: FVG quality score (0-100)
            choch_strength: CHoCH strength (1-10)
            pattern_type: Pattern type ('reversal', 'continuation', etc.)
        
        Returns:
            int: AI confidence score 0-100
        """
        if not self.learned_rules or self.learned_rules['total_trades_analyzed'] == 0:
            # No ML data - return neutral score based on inputs
            return int((fvg_quality * 0.6) + (choch_strength * 4))
        
        score = 50  # Start neutral
        
        # 1. Pair Historical Performance (30% weight, max +/-30 points)
        if symbol in self.learned_rules['profit_factor_by_pair']:
            pair_data = self.learned_rules['profit_factor_by_pair'][symbol]
            pf = pair_data['profit_factor']
            win_rate = pair_data.get('win_rate', 50)
            
            if pf >= 2.0:
                score += 30  # Excellent pair
            elif pf >= 1.5:
                score += 20  # Very good
            elif pf >= 1.0:
                score += 10  # Profitable
            else:
                score -= 30  # Poor performer
                
            # Bonus for high win rate
            if win_rate >= 65:
                score += 5
        
        # 2. Blackout Period Check (20% weight, -20 points penalty)
        if hour in self.learned_rules['recommendations'].get('blackout_hours', []):
            score -= 20  # High risk hour
        else:
            score += 10  # Good timing
        
        # 3. FVG Quality Score (25% weight, max +25 points)
        # Normalize FVG quality to 0-25 range
        fvg_contribution = int(fvg_quality * 0.25)
        score += fvg_contribution
        
        # 4. CHoCH Strength (15% weight, max +15 points)
        # CHoCH strength is 1-10, normalize to 0-15
        choch_contribution = int((choch_strength / 10) * 15)
        score += choch_contribution
        
        # 5. Pattern Type Success Rate (10% weight, max +/-10 points)
        if pattern_type.upper() in self.learned_rules.get('pattern_success_rate', {}):
            pattern_data = self.learned_rules['pattern_success_rate'][pattern_type.upper()]
            pattern_win_rate = pattern_data.get('win_rate', 50)
            
            if pattern_win_rate >= 60:
                score += 10  # Reliable pattern
            elif pattern_win_rate >= 50:
                score += 5   # Decent pattern
            else:
                score -= 10  # Risky pattern
        
        # Cap score between 0-100
        score = max(0, min(100, score))
        
        return int(score)


def main():
    """Main execution"""
    import sys
    
    optimizer = StrategyOptimizer()
    
    # Load trade data
    trades = optimizer.load_trades_data()
    
    if not trades:
        print("❌ No trades found in database")
        return
    
    # Generate learned rules
    learned_rules = optimizer.generate_learned_rules(trades)
    
    # Save to file
    optimizer.save_learned_rules()
    
    # Test scoring on example setups
    print("\n" + "━" * 60)
    print("🧪 TESTING SETUP SCORING...")
    print("━" * 60)
    
    test_setups = [
        {'symbol': 'EURUSD', 'timeframe': '4H', 'hour': 10, 'pattern': 'ORDER_BLOCK'},
        {'symbol': 'GBPUSD', 'timeframe': '1H', 'hour': 3, 'pattern': 'FVG'},
        {'symbol': 'USDJPY', 'timeframe': '4H', 'hour': 14, 'pattern': 'LIQUIDITY'},
    ]
    
    for setup in test_setups:
        score_result = optimizer.calculate_setup_score(setup)
        
        emoji = "🟢" if score_result['score'] >= 75 else "🟡" if score_result['score'] >= 60 else "🔴"
        print(f"\n{emoji} {setup['symbol']} {setup['timeframe']} @ {setup['hour']}:00")
        print(f"   Score: {score_result['score']}/100 ({score_result['confidence']})")
        print(f"   Recommendation: {score_result['recommendation']}")
        
        for factor, desc in score_result['factors'].items():
            print(f"   • {factor}: {desc}")
    
    print("\n" + "━" * 60)
    print("✨ Glitch in Matrix by ФорексГод ✨")
    print("🧠 AI-Powered • 💎 Smart Money")
    print("━" * 60)


if __name__ == "__main__":
    main()
