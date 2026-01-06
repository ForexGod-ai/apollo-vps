"""
V3.0 BACKTEST - 12 Month Validation
Compares V2.1 vs V3.0 on NZDUSD, GBPUSD, XTIUSD
Tests: Strict Entry Confirmation, FVG Quality Scoring, GBP Filtering
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
import json
from pathlib import Path

from smc_detector import SMCDetector, TradeSetup
from ctrader_cbot_client import CTraderCBotClient


class BacktestResult:
    """Store backtest results for comparison"""
    def __init__(self, version: str):
        self.version = version
        self.trades: List[Dict] = []
        self.blocked_trades: List[Dict] = []  # V3.0: Trades blocked by filters
        
    def add_trade(self, trade: Dict):
        """Add executed trade"""
        self.trades.append(trade)
    
    def add_blocked(self, trade: Dict, reason: str):
        """Add blocked trade (V3.0 only)"""
        self.blocked_trades.append({**trade, 'block_reason': reason})
    
    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics"""
        if not self.trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'total_profit': 0,
                'max_drawdown': 0,
                'avg_rr': 0,
                'blocked_count': len(self.blocked_trades)
            }
        
        df = pd.DataFrame(self.trades)
        
        wins = df[df['profit'] > 0]
        losses = df[df['profit'] <= 0]
        
        win_rate = (len(wins) / len(df)) * 100
        total_profit = df['profit'].sum()
        
        # Calculate drawdown
        df['cumulative'] = df['profit'].cumsum()
        df['running_max'] = df['cumulative'].cummax()
        df['drawdown'] = df['running_max'] - df['cumulative']
        max_drawdown = df['drawdown'].max()
        
        # Average R:R
        avg_rr = df['risk_reward'].mean()
        
        return {
            'total_trades': len(df),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(win_rate, 2),
            'total_profit': round(total_profit, 2),
            'max_drawdown': round(max_drawdown, 2),
            'avg_rr': round(avg_rr, 2),
            'avg_profit_per_trade': round(total_profit / len(df), 2),
            'blocked_count': len(self.blocked_trades)
        }
    
    def get_blocked_analysis(self) -> Dict:
        """Analyze blocked trades to see if they would have been winners or losers"""
        if not self.blocked_trades:
            return {
                'blocked_total': 0,
                'blocked_winners': 0,
                'blocked_losers': 0,
                'blocked_win_rate': 0,
                'saved_capital': 0,
                'missed_profit': 0,
                'net_benefit': 0
            }
        
        df = pd.DataFrame(self.blocked_trades)
        
        # Count how many blocked trades would have been winners vs losers
        winners = df[df['profit'] > 0]
        losers = df[df['profit'] <= 0]
        
        saved_capital = abs(losers['profit'].sum()) if len(losers) > 0 else 0
        missed_profit = winners['profit'].sum() if len(winners) > 0 else 0
        
        return {
            'blocked_total': len(df),
            'blocked_winners': len(winners),
            'blocked_losers': len(losers),
            'blocked_win_rate': round((len(winners) / len(df)) * 100, 2) if len(df) > 0 else 0,
            'saved_capital': round(saved_capital, 2),
            'missed_profit': round(missed_profit, 2),
            'net_benefit': round(saved_capital - missed_profit, 2)
        }


class V3Backtester:
    """Backtest V3.0 improvements vs V2.1"""
    
    def __init__(self):
        self.client = CTraderCBotClient()
        self.detector_v21 = SMCDetector(swing_lookback=5)  # V2.1 detector
        self.detector_v3 = SMCDetector(swing_lookback=5)   # V3.0 detector
        
        # V2.1 vs V3.0 flags
        self.v21_mode = {
            'strict_entry': False,      # V2.1: No 4H CHoCH requirement
            'fvg_quality': False,       # V2.1: Basic quality check
            'continuity_filter': False, # V2.1: No BOS validation
            'gbp_filtering': False      # V2.1: No GBP special rules
        }
        
        self.v3_mode = {
            'strict_entry': True,       # V3.0: Require 4H CHoCH + price in FVG
            'fvg_quality': True,        # V3.0: Score ≥70 (≥75 for GBP)
            'continuity_filter': True,  # V3.0: Require BOS for CONTINUITY
            'gbp_filtering': True       # V3.0: GBP needs ≥80% body + 1H CHoCH
        }
        
        print("✅ V3 Backtester initialized")
        print(f"   V2.1 Mode: Permissive (original logic)")
        print(f"   V3.0 Mode: Strict (all filters enabled)")
    
    def download_data(
        self, 
        symbol: str, 
        start_date: datetime, 
        end_date: datetime
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Download historical data for backtesting
        Returns: (df_daily, df_4h, df_1h)
        """
        print(f"\n📊 Downloading data for {symbol}...")
        
        # Calculate number of candles needed
        days_diff = (end_date - start_date).days
        
        # Daily: 365 days + 100 buffer for lookback
        daily_candles = days_diff + 100
        
        # 4H: 6 candles per day
        h4_candles = (days_diff * 6) + 500
        
        # 1H: Only for GBP pairs
        h1_candles = (days_diff * 24) + 500 if 'GBP' in symbol else 0
        
        df_daily = self.client.get_historical_data(symbol, 'D1', daily_candles)
        df_4h = self.client.get_historical_data(symbol, 'H4', h4_candles)
        df_1h = None
        
        if 'GBP' in symbol:
            df_1h = self.client.get_historical_data(symbol, 'H1', h1_candles)
        
        if df_daily is None or df_4h is None:
            raise Exception(f"Failed to download data for {symbol}")
        
        print(f"   ✅ Daily: {len(df_daily)} candles")
        print(f"   ✅ 4H: {len(df_4h)} candles")
        if df_1h is not None:
            print(f"   ✅ 1H: {len(df_1h)} candles (GBP)")
        
        return df_daily, df_4h, df_1h
    
    def simulate_trade_outcome(
        self,
        setup: TradeSetup,
        df_4h: pd.DataFrame,
        df_daily: pd.DataFrame
    ) -> Dict:
        """
        Simulate trade outcome based on historical data
        Returns: profit/loss and other metrics
        """
        entry = setup.entry_price
        sl = setup.stop_loss
        tp = setup.take_profit
        direction = setup.daily_choch.direction
        
        # Get future price action after setup
        setup_time = setup.setup_time
        
        # Find index in 4H data
        # DataFrame uses 'time' as index (set by cTrader client)
        setup_idx = None
        for i in range(len(df_4h)):
            candle_time = df_4h.index[i]  # time is index
            if candle_time >= setup_time:
                setup_idx = i
                break
        
        if setup_idx is None or setup_idx >= len(df_4h) - 10:
            return None  # Not enough future data
        
        # Simulate trade execution (next 50 4H candles = ~8 days)
        future_candles = df_4h.iloc[setup_idx:setup_idx+50]
        
        hit_sl = False
        hit_tp = False
        exit_price = entry
        bars_in_trade = 0
        
        for i in range(len(future_candles)):
            candle = future_candles.iloc[i]
            bars_in_trade += 1
            
            if direction == 'bullish':
                # LONG trade
                if candle['low'] <= sl:
                    hit_sl = True
                    exit_price = sl
                    break
                elif candle['high'] >= tp:
                    hit_tp = True
                    exit_price = tp
                    break
            else:
                # SHORT trade
                if candle['high'] >= sl:
                    hit_sl = True
                    exit_price = sl
                    break
                elif candle['low'] <= tp:
                    hit_tp = True
                    exit_price = tp
                    break
        
        # Calculate profit
        if direction == 'bullish':
            profit_pips = (exit_price - entry) / 0.0001  # Assume 4-decimal pairs
        else:
            profit_pips = (entry - exit_price) / 0.0001
        
        # Use 1% risk per trade
        account_size = 10000  # $10,000
        risk_per_trade = account_size * 0.01  # $100
        
        risk_pips = abs(entry - sl) / 0.0001
        pip_value = risk_per_trade / risk_pips if risk_pips > 0 else 0
        
        profit_usd = profit_pips * pip_value
        
        return {
            'symbol': setup.symbol,
            'direction': direction,
            'strategy': setup.strategy_type,
            'entry': entry,
            'exit': exit_price,
            'sl': sl,
            'tp': tp,
            'risk_reward': setup.risk_reward,
            'hit_tp': hit_tp,
            'hit_sl': hit_sl,
            'profit': round(profit_usd, 2),
            'profit_pips': round(profit_pips, 2),
            'bars_in_trade': bars_in_trade,
            'setup_time': setup_time
        }
    
    def run_backtest_v21(
        self,
        symbol: str,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame,
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """
        Run V2.1 backtest (permissive logic)
        - No 4H CHoCH requirement
        - Basic FVG quality
        - No CONTINUITY filter
        """
        print(f"\n🔄 Running V2.1 backtest for {symbol}...")
        
        result = BacktestResult("V2.1")
        scanned_candles = 0
        setups_found = 0
        
        # Scan daily candles in backtest period
        for i in range(100, len(df_daily)):
            candle_date = df_daily.index[i]
            
            if candle_date < start_date or candle_date > end_date:
                continue
            
            # Get data up to this point
            df_daily_slice = df_daily.iloc[:i+1]
            
            # Find corresponding 4H data
            h4_end_time = candle_date + timedelta(days=1)
            df_4h_slice = df_4h[df_4h.index <= h4_end_time]
            
            if len(df_4h_slice) < 200:
                continue
            
            # V2.1: Scan without strict filters
            try:
                # V2.1 MODE: Daily CHoCH + FVG = READY (original $88k logic)
                setup = self.detector_v21.scan_for_setup(
                    symbol=symbol,
                    df_daily=df_daily_slice,
                    df_4h=df_4h_slice,
                    priority=1,
                    df_1h=None,
                    require_4h_choch=False  # V2.1: No 4H CHoCH requirement
                )
                
                if setup:
                    setups_found += 1
                    # V2.1: Execute immediately if Daily CHoCH + FVG found
                    # (no 4H CHoCH requirement)
                    trade = self.simulate_trade_outcome(setup, df_4h, df_daily)
                    
                    if trade:
                        result.add_trade(trade)
                        
                        status = "✅ WIN" if trade['profit'] > 0 else "❌ LOSS"
                        print(f"   {status} | {trade['symbol']} {trade['direction'].upper()} | "
                              f"P&L: ${trade['profit']:.2f} | Date: {candle_date.date()}")
            
            except Exception as e:
                # Skip errors
                pass
        
        return result
    
    def run_backtest_v3(
        self,
        symbol: str,
        df_daily: pd.DataFrame,
        df_4h: pd.DataFrame,
        df_1h: Optional[pd.DataFrame],
        start_date: datetime,
        end_date: datetime
    ) -> BacktestResult:
        """
        Run V3.0 backtest (strict logic)
        - Require 4H CHoCH + price in FVG
        - FVG quality score ≥70 (≥75 for GBP)
        - CONTINUITY needs BOS
        - GBP needs 1H CHoCH
        """
        print(f"\n🔄 Running V3.0 backtest for {symbol}...")
        
        result = BacktestResult("V2.1")
        scanned_candles = 0
        setups_found = 0
        
        # Scan daily candles in backtest period
        for i in range(100, len(df_daily)):
            candle_date = df_daily.index[i]
            
            if candle_date < start_date or candle_date > end_date:
                continue
            
            scanned_candles += 1
            
            # Get data up to this point
            df_daily_slice = df_daily.iloc[:i+1]
            
            # Find corresponding 4H data
            h4_end_time = candle_date + timedelta(days=1)
            df_4h_slice = df_4h[df_4h.index <= h4_end_time]
            
            # Get 1H data if available (GBP)
            df_1h_slice = None
            if df_1h is not None:
                df_1h_slice = df_1h[df_1h.index <= h4_end_time]
            
            if len(df_4h_slice) < 200:
                continue
            
            # V3.0: Scan with all strict filters
            try:
                # V3.0 MODE: Daily CHoCH + FVG + 4H CHoCH = READY (strict)
                setup = self.detector_v3.scan_for_setup(
                    symbol=symbol,
                    df_daily=df_daily_slice,
                    df_4h=df_4h_slice,
                    priority=1,
                    df_1h=df_1h_slice,
                    require_4h_choch=True  # V3.0: Strict 4H CHoCH requirement
                )
                
                if setup:
                    # V3.0: Check status before execution
                    if setup.status == 'READY':
                        # Execute trade
                        trade = self.simulate_trade_outcome(setup, df_4h, df_daily)
                        
                        if trade:
                            result.add_trade(trade)
                            
                            status = "✅ WIN" if trade['profit'] > 0 else "❌ LOSS"
                            print(f"   {status} | {trade['symbol']} {trade['direction'].upper()} | "
                                  f"P&L: ${trade['profit']:.2f} | Date: {candle_date.date()}")
                    
                    elif setup.status == 'MONITORING':
                        # Blocked by V3.0 filters
                        # Simulate what would have happened
                        trade = self.simulate_trade_outcome(setup, df_4h, df_daily)
                        
                        if trade:
                            result.add_blocked(trade, "Status: MONITORING (4H/1H/BOS filter)")
                            
                            status = "🚫 BLOCKED"
                            outcome = "would WIN" if trade['profit'] > 0 else "would LOSE"
                            print(f"   {status} | {trade['symbol']} ({outcome}) | "
                                  f"P&L: ${trade['profit']:.2f} | Date: {candle_date.date()}")
            
            except Exception as e:
                # Skip errors
                pass
        
        return result
    
    def generate_report(
        self,
        symbol: str,
        v21_result: BacktestResult,
        v3_result: BacktestResult
    ):
        """Generate comparison report"""
        print(f"\n{'='*80}")
        print(f"📊 BACKTEST REPORT: {symbol}")
        print(f"{'='*80}")
        
        v21_metrics = v21_result.calculate_metrics()
        v3_metrics = v3_result.calculate_metrics()
        v3_blocked = v3_result.get_blocked_analysis()
        
        print(f"\n{'V2.1 (Permissive)':<30} | {'V3.0 (Strict)':<30} | {'Change':<15}")
        print(f"{'-'*30}-+-{'-'*30}-+-{'-'*15}")
        
        # Total Trades
        print(f"{'Total Trades:':<30} | {v21_metrics['total_trades']:<30} | {v3_metrics['total_trades']:<15}")
        
        # Win Rate
        wr_change = v3_metrics['win_rate'] - v21_metrics['win_rate']
        wr_arrow = "📈" if wr_change > 0 else "📉" if wr_change < 0 else "➡️"
        print(f"{'Win Rate:':<30} | {v21_metrics['win_rate']:<29}% | {v3_metrics['win_rate']:<14}% | {wr_arrow} {wr_change:+.1f}%")
        
        # Total Profit
        profit_change = v3_metrics['total_profit'] - v21_metrics['total_profit']
        profit_arrow = "📈" if profit_change > 0 else "📉" if profit_change < 0 else "➡️"
        print(f"{'Total Profit:':<30} | ${v21_metrics['total_profit']:<29} | ${v3_metrics['total_profit']:<14} | {profit_arrow} ${profit_change:+.2f}")
        
        # Max Drawdown
        dd_change = v21_metrics['max_drawdown'] - v3_metrics['max_drawdown']
        dd_arrow = "✅" if dd_change > 0 else "⚠️" if dd_change < 0 else "➡️"
        print(f"{'Max Drawdown:':<30} | ${v21_metrics['max_drawdown']:<29} | ${v3_metrics['max_drawdown']:<14} | {dd_arrow} ${dd_change:+.2f}")
        
        # Avg R:R
        rr_change = v3_metrics['avg_rr'] - v21_metrics['avg_rr']
        print(f"{'Avg Risk:Reward:':<30} | 1:{v21_metrics['avg_rr']:<28} | 1:{v3_metrics['avg_rr']:<13} | {rr_change:+.2f}")
        
        print(f"\n{'='*80}")
        print(f"🚫 V3.0 BLOCKED TRADES ANALYSIS")
        print(f"{'='*80}")
        print(f"Total Blocked: {v3_blocked['blocked_total']}")
        print(f"   └─ Blocked Winners: {v3_blocked['blocked_winners']} (missed profit: ${v3_blocked['missed_profit']})")
        print(f"   └─ Blocked Losers: {v3_blocked['blocked_losers']} (saved capital: ${v3_blocked['saved_capital']})")
        print(f"   └─ Blocked Win Rate: {v3_blocked['blocked_win_rate']}%")
        print(f"   └─ Net Benefit: ${v3_blocked['net_benefit']:.2f}")
        
        benefit_status = "✅ POSITIVE" if v3_blocked['net_benefit'] > 0 else "⚠️ NEGATIVE"
        print(f"\n{benefit_status}: Blocking saved ${abs(v3_blocked['net_benefit']):.2f}")
        
        print(f"\n{'='*80}\n")


def main():
    """Run comprehensive 12-month backtest"""
    print("\n" + "="*80)
    print("🔬 V3.0 BACKTEST - 12 MONTH VALIDATION")
    print("="*80)
    print(f"Comparing: V2.1 (Permissive) vs V3.0 (Strict)")
    print(f"Symbols: NZDUSD, GBPUSD, XTIUSD")
    print(f"Period: {datetime.now() - timedelta(days=365)} to {datetime.now()}")
    print("="*80 + "\n")
    
    backtester = V3Backtester()
    
    # Define test symbols
    symbols = ['NZDUSD', 'GBPUSD', 'XTIUSD']
    
    # Backtest period: March 2024 to January 2026 (full available data)
    end_date = datetime.now()
    start_date = datetime(2024, 3, 18)  # Start of available data
    
    all_results = {}
    
    for symbol in symbols:
        try:
            # Download data
            df_daily, df_4h, df_1h = backtester.download_data(symbol, start_date, end_date)
            
            # Run V2.1 backtest
            v21_result = backtester.run_backtest_v21(symbol, df_daily, df_4h, start_date, end_date)
            
            # Run V3.0 backtest
            v3_result = backtester.run_backtest_v3(symbol, df_daily, df_4h, df_1h, start_date, end_date)
            
            # Generate report
            backtester.generate_report(symbol, v21_result, v3_result)
            
            all_results[symbol] = {
                'v21': v21_result.calculate_metrics(),
                'v3': v3_result.calculate_metrics(),
                'blocked': v3_result.get_blocked_analysis()
            }
        
        except Exception as e:
            print(f"\n❌ Error backtesting {symbol}: {e}")
            continue
    
    # Save results to JSON
    output_file = Path("backtest_results_v3_vs_v21.json")
    with open(output_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    print("\n✅ BACKTEST COMPLETE!\n")


if __name__ == "__main__":
    main()
