#!/usr/bin/env python3
"""
Glitch in Matrix - Full Backtest Engine
Tests strategy on all 21 pairs with historical data

Data Sources:
1. Dukascopy (primary) - free historical data
2. cTrader IC Markets (validation) - via MarketDataProvider

Strategy by ForexGod ✨
"""

import os
import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from pathlib import Path
import logging

# Import existing modules
from smc_detector import SMCDetector, TradeSetup

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/backtest_glitch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HistoricalDataDownloader:
    """Download historical forex data from Dukascopy"""
    
    BASE_URL = "https://datafeed.dukascopy.com/datafeed"
    
    def __init__(self):
        self.cache_dir = Path("data/historical_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def download_pair_data(self, pair: str, start_date: datetime, end_date: datetime, 
                          timeframe: str = "D1") -> pd.DataFrame:
        """
        Download historical data for a pair
        
        Args:
            pair: e.g., "EURUSD"
            start_date: Start date
            end_date: End date  
            timeframe: "D1" or "H4"
        
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        cache_file = self.cache_dir / f"{pair}_{timeframe}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"
        
        # Check cache first
        if cache_file.exists():
            logger.info(f"📦 Loading {pair} {timeframe} from cache...")
            return pd.read_csv(cache_file, parse_dates=['timestamp'])
        
        logger.info(f"📥 Downloading {pair} {timeframe} data from {start_date} to {end_date}...")
        
        # Note: Dukascopy API requires specific format
        # For now, use cTrader as primary source (we already have it!)
        # Alternative: Use yfinance for major pairs or MetaTrader CSV export
        
        # Fallback: Get from cTrader MarketDataProvider
        df = self._fetch_from_ctrader(pair, timeframe, start_date, end_date)
        
        # Save to cache
        if df is not None and not df.empty:
            df.to_csv(cache_file, index=False)
            logger.info(f"✅ Saved {len(df)} bars to cache")
        
        return df
    
    def _fetch_from_ctrader(self, pair: str, timeframe: str, 
                           start_date: datetime, end_date: datetime) -> pd.DataFrame:
        """Fetch data from cTrader MarketDataProvider (localhost:8767)"""
        try:
            # Map pair to cTrader symbol
            symbol_map = {
                'EURUSD': 'EURUSD', 'GBPUSD': 'GBPUSD', 'USDJPY': 'USDJPY',
                'AUDUSD': 'AUDUSD', 'USDCAD': 'USDCAD', 'NZDUSD': 'NZDUSD',
                'USDCHF': 'USDCHF', 'EURGBP': 'EURGBP', 'EURJPY': 'EURJPY',
                'GBPJPY': 'GBPJPY', 'AUDJPY': 'AUDJPY', 'EURAUD': 'EURAUD',
                'EURCHF': 'EURCHF', 'GBPAUD': 'GBPAUD', 'GBPCAD': 'GBPCAD',
                'GBPCHF': 'GBPCHF', 'AUDNZD': 'AUDNZD', 'NZDCAD': 'NZDCAD',
                'BTCUSD': 'BTCUSD', 'XAUUSD': 'XAUUSD', 'XAGUSD': 'XAGUSD'
            }
            
            symbol = symbol_map.get(pair, pair)
            
            # Get bar count based on timeframe (match scanner settings!)
            if timeframe == "D1":
                bar_count = 365  # 1 year (same as scanner)
            elif timeframe == "H4":
                bar_count = 2190  # 1 year synchronized (365 × 6)
            else:  # H1
                bar_count = 100  # Last 100 hours (~4 days) for GBP 2-TF confirmation
            
            # Use query string format (not path params)
            url = f"http://localhost:8767/bars?symbol={symbol}&timeframe={timeframe}&bars={bar_count}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"❌ cTrader API error: {response.status_code}")
                return None
            
            data = response.json()
            
            if not data.get('bars'):
                logger.warning(f"⚠️ No bars returned for {symbol}")
                return None
            
            # Convert to DataFrame
            bars = data['bars']
            df = pd.DataFrame(bars)
            df['timestamp'] = pd.to_datetime(df['time'])
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            logger.info(f"✅ Fetched {len(df)} bars from cTrader for {symbol}")
            return df
            
        except Exception as e:
            logger.error(f"❌ Error fetching from cTrader: {e}")
            return None


class GlitchBacktester:
    """
    Backtest Glitch in Matrix strategy on historical data
    """
    
    def __init__(self):
        self.downloader = HistoricalDataDownloader()
        self.smc_detector = SMCDetector(swing_lookback=5)
        self.results = {}
        
        # Account settings for realistic profit calculation
        self.account_balance = 1000  # Starting balance in $
        self.risk_per_trade_pct = 2.0  # Risk 2% per trade
        self.leverage = 500  # 1:500 leverage
        # Ensure pair_list is always loaded
        self.pair_list = []
        try:
            with open('pairs_config.json', 'r') as f:
                config = json.load(f)
                self.pair_list = [p['symbol'] for p in config['pairs']]
        except Exception as e:
            logger.error(f"Could not load pairs from config: {e}")
    
    def backtest_pair(self, pair: str, months: int = 12) -> Dict:
        """
        Backtest single pair
        
        Args:
            pair: Pair symbol (e.g., "EURUSD")
            months: Number of months to backtest
        
        Returns:
            Dictionary with backtest results
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"🔍 BACKTESTING {pair} - {months} months")
        logger.info(f"{'='*60}")
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=months * 30)
        
        # Download data
        d1_data = self.downloader.download_pair_data(pair, start_date, end_date, "D1")
        h4_data = self.downloader.download_pair_data(pair, start_date, end_date, "H4")
        
        # V3.0: Download 1H data for GBP pairs (2-TF confirmation)
        h1_data = None
        is_gbp = 'GBP' in pair
        if is_gbp:
            logger.info(f"📊 Downloading 1H data for {pair} (GBP 2-TF confirmation)")
            h1_data = self.downloader.download_pair_data(pair, start_date, end_date, "H1")
            if h1_data is None:
                logger.warning(f"⚠️ No 1H data for {pair} (GBP filter may downgrade setups)")
        
        if d1_data is None or h4_data is None or d1_data.empty or h4_data.empty:
            logger.error(f"❌ Failed to get data for {pair}")
            return None
        
        # Replay strategy day by day
        trades = []
        setups_found = 0
        
        logger.info(f"📊 Replaying {len(d1_data)} days of data...")
        logger.info(f"⏰ Starting from index 100 (need context for swing detection)")
        
        # Start from bar 100 to have enough lookback for swing points
        for i in range(100, len(d1_data) - 10):  # Leave 10 bars at end for trade simulation
            current_date = d1_data.iloc[i]['timestamp']
            
            # Get ALL data up to current point (not sliced!)
            d1_slice = d1_data.iloc[:i+1].copy()
            h4_slice = h4_data[h4_data['timestamp'] <= current_date].copy()
            
            # V3.0: Slice 1H data if available (for GBP)
            h1_slice = None
            if h1_data is not None:
                h1_slice = h1_data[h1_data['timestamp'] <= current_date].copy()
            
            if len(d1_slice) < 100 or len(h4_slice) < 100:
                continue  # Not enough data
            
            # Run Glitch detection
            setup = self._detect_glitch_setup(pair, d1_slice, h4_slice, h1_slice)
            
            if setup:
                setups_found += 1
                logger.info(f"📍 Setup found on {current_date.strftime('%Y-%m-%d')}: {setup.get('status')}")
                
            if setup and setup['status'] == 'READY':
                # Simulate trade execution on FUTURE bars
                future_h4 = h4_data[h4_data['timestamp'] > current_date].copy()
                
                if len(future_h4) < 5:
                    continue  # Not enough future data
                
                trade = self._simulate_trade(setup, d1_data.iloc[i+1:], future_h4)
                if trade:
                    trades.append(trade)
                    logger.info(f"📊 Trade #{len(trades)} @ {current_date.strftime('%Y-%m-%d')}: "
                              f"{trade['result']} | Pips: {trade['pnl_pips']:.1f} | "
                              f"USD: ${trade['pnl_usd']:.2f} | R:R: {trade['rr_usd']:.2f}x | "
                              f"Lot: {trade['lot_size']:.2f}")
        
        logger.info(f"✅ Scan complete: {setups_found} setups found, {len(trades)} trades executed")
        
        # Calculate statistics
        if not trades:
            logger.warning(f"⚠️ No trades found for {pair}")
            return {
            }
        
        stats = self._calculate_statistics(pair, trades)
        
        logger.info(f"\n✅ {pair} RESULTS:")
        logger.info(f"   Trades: {stats['trades']}")
        logger.info(f"   Win Rate: {stats['win_rate']:.1f}%")
        logger.info(f"   Avg R:R (USD): {stats['avg_rr_usd']:.2f}x")
        logger.info(f"   Total Pips: {stats['total_pips']:.1f}")
        logger.info(f"   Total USD: ${stats['total_usd']:,.0f}")
        logger.info(f"   Return: {stats['return_pct']:.1f}%")
        logger.info(f"   Max Drawdown: {stats['max_drawdown']:.1f}%")
        
        return stats
    
    def _detect_glitch_setup(self, pair: str, d1_data: pd.DataFrame, 
                            h4_data: pd.DataFrame, h1_data: pd.DataFrame = None) -> Dict:
        """Run Glitch detection logic (same as morning scanner)"""
        try:
            # Prepare DataFrames - rename timestamp to time (required by SMCDetector)
            d1_df = d1_data.copy()
            h4_df = h4_data.copy()
            d1_df['time'] = d1_df['timestamp']
            h4_df['time'] = h4_df['timestamp']
            
            # V3.0: Prepare 1H data for GBP pairs
            df_1h = None
            if h1_data is not None:
                df_1h = h1_data.copy()
                df_1h['time'] = df_1h['timestamp']
            
            # Use SMCDetector.scan_for_setup() directly (same as morning scanner!)
            setup = self.smc_detector.scan_for_setup(
                symbol=pair,
                df_daily=d1_df,
                df_4h=h4_df,
                priority=1,
                df_1h=df_1h  # V3.0: GBP 2-TF confirmation
            )
            
            if setup is None:
                return None
            
            logger.info(f"🎯 Setup found: {setup.strategy_type.upper()} {setup.daily_choch.direction}")
            
            # Convert TradeSetup to dict format
            return {
                'status': 'READY',
                'pair': pair,
                'direction': setup.daily_choch.direction,
                'entry_price': setup.entry_price,
                'sl_price': setup.stop_loss,
                'tp_price': setup.take_profit,
                'strategy_type': setup.strategy_type,
                'rr': setup.risk_reward
            }
            
        except Exception as e:
            logger.debug(f"No setup for {pair}: {e}")
            return None
    
    def _simulate_trade(self, setup: Dict, future_d1: pd.DataFrame, 
                       future_h4: pd.DataFrame) -> Dict:
        """
        Simulate trade execution and outcome
        
        Args:
            setup: Detected setup
            future_d1: Future daily bars
            future_h4: Future H4 bars
        
        Returns:
            Trade result dictionary
        """
        entry = setup.get('entry_price', 0)
        sl = setup.get('sl_price', 0)
        tp = setup.get('tp_price', 0)
        direction = setup.get('direction', 'BUY')
        pair = setup.get('pair', '')
        
        if not all([entry, sl, tp]):
            return None
        
        # Calculate pips based on pair type
        if 'JPY' in pair:
            # JPY pairs: 2 decimal places, 1 pip = 0.01
            pip_multiplier = 100
        elif pair in ['BTCUSD', 'ETHUSD']:
            # Crypto: point = pip (whole numbers)
            pip_multiplier = 1
        elif pair in ['XAUUSD', 'XAGUSD']:
            # Gold/Silver: 1 pip = 0.1 ($0.10)
            pip_multiplier = 10
        else:
            # Standard forex: 4 decimal places, 1 pip = 0.0001
            pip_multiplier = 10000
        
        # Calculate risk/reward in pips
        risk_pips = abs(entry - sl) * pip_multiplier
        reward_pips = abs(tp - entry) * pip_multiplier
        rr = reward_pips / risk_pips if risk_pips > 0 else 0
        
        # Calculate position size based on 2% risk
        risk_amount = self.account_balance * (self.risk_per_trade_pct / 100)  # $200 on $10k
        
        # Calculate pip value and lot size
        if 'JPY' in pair:
            # For USDJPY: 1 lot = $1000, 1 pip (0.01) = $10 per lot
            pip_value_per_lot = 10
        elif pair in ['BTCUSD']:
            # BTC: 1 lot = 1 BTC, 1 point = $1 per lot (approx)
            pip_value_per_lot = 1
        elif pair in ['XAUUSD']:
            # Gold: 1 lot = 100 oz, 1 pip ($0.10) = $10 per lot
            pip_value_per_lot = 10
        else:
            # Standard forex: 1 lot = 100,000 units, 1 pip = $10 per lot
            pip_value_per_lot = 10
        
        # Lot size = Risk Amount / (Stop Loss in Pips × Pip Value)
        lot_size = risk_amount / (risk_pips * pip_value_per_lot) if risk_pips > 0 else 0.01
        
        # Cap lot size based on leverage (margin = position value / leverage)
        max_position_value = self.account_balance * self.leverage  # $10k × 500 = $5M
        
        if pair in ['BTCUSD']:
            position_value = lot_size * entry  # BTC price × lot
        elif pair in ['XAUUSD']:
            position_value = lot_size * 100 * entry  # 100 oz per lot
        else:
            position_value = lot_size * 100000  # Standard lot = 100k units
        
        if position_value > max_position_value:
            lot_size = max_position_value / (100000 if pair not in ['BTCUSD', 'XAUUSD'] else entry)
        
        # Ensure minimum lot size
        lot_size = max(0.01, min(lot_size, 50))  # Between 0.01 and 50 lots
        
        # Simulate trade progression through future bars
        for i, bar in future_h4.iterrows():
            high = bar['high']
            low = bar['low']
            
            if direction == 'BUY':
                # Check if TP hit
                if high >= tp:
                    profit_pips = reward_pips
                    profit_usd = profit_pips * pip_value_per_lot * lot_size
                    return {
                        'result': 'WIN',
                        'pnl_pips': profit_pips,
                        'pnl_usd': profit_usd,
                        'rr_pips': rr,
                        'rr_usd': profit_usd / risk_amount,  # Real R:R in $
                        'entry': entry,
                        'exit': tp,
                        'lot_size': lot_size,
                        'bars_held': i
                    }
                # Check if SL hit
                if low <= sl:
                    loss_pips = -risk_pips
                    loss_usd = -risk_amount  # Loss is exactly 2% risk
                    return {
                        'result': 'LOSS',
                        'pnl_pips': loss_pips,
                        'pnl_usd': loss_usd,
                        'rr_pips': -1,
                        'rr_usd': -1,
                        'entry': entry,
                        'exit': sl,
                        'lot_size': lot_size,
                        'bars_held': i
                    }
            else:  # SELL
                # Check if TP hit
                if low <= tp:
                    profit_pips = reward_pips
                    profit_usd = profit_pips * pip_value_per_lot * lot_size
                    return {
                        'result': 'WIN',
                        'pnl_pips': profit_pips,
                        'pnl_usd': profit_usd,
                        'rr_pips': rr,
                        'rr_usd': profit_usd / risk_amount,
                        'entry': entry,
                        'exit': tp,
                        'lot_size': lot_size,
                        'bars_held': i
                    }
                # Check if SL hit
                if high >= sl:
                    loss_pips = -risk_pips
                    loss_usd = -risk_amount
                    return {
                        'result': 'LOSS',
                        'pnl_pips': loss_pips,
                        'pnl_usd': loss_usd,
                        'rr_pips': -1,
                        'rr_usd': -1,
                        'entry': entry,
                        'exit': sl,
                        'lot_size': lot_size,
                        'bars_held': i
                    }
        
        # Trade still open (no result yet)
        return None
    
    def _calculate_statistics(self, pair: str, trades: List[Dict]) -> Dict:
        """Calculate backtest statistics including USD P&L"""
        wins = [t for t in trades if t['result'] == 'WIN']
        losses = [t for t in trades if t['result'] == 'LOSS']
        
        total_trades = len(trades)
        win_count = len(wins)
        loss_count = len(losses)
        
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate in both pips and USD
        total_pips = sum(t['pnl_pips'] for t in trades)
        total_usd = sum(t['pnl_usd'] for t in trades)
        
        avg_rr_pips = np.mean([t['rr_pips'] for t in wins]) if wins else 0
        avg_rr_usd = np.mean([t['rr_usd'] for t in wins]) if wins else 0
        
        # Calculate max drawdown in USD
        equity_curve = []
        running_usd = self.account_balance
        peak = self.account_balance
        max_dd = 0
        
        for t in trades:
            running_usd += t['pnl_usd']
            equity_curve.append(running_usd)
            
            if running_usd > peak:
                peak = running_usd
            dd = ((peak - running_usd) / peak * 100) if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        final_balance = self.account_balance + total_usd
        return_pct = (total_usd / self.account_balance * 100)
        
        return {
            'pair': pair,
            'trades': total_trades,
            'wins': win_count,
            'losses': loss_count,
            'win_rate': win_rate,
            'total_pips': total_pips,
            'total_usd': total_usd,
            'return_pct': return_pct,
            'final_balance': final_balance,
            'avg_win_pips': np.mean([t['pnl_pips'] for t in wins]) if wins else 0,
            'avg_loss_pips': np.mean([t['pnl_pips'] for t in losses]) if losses else 0,
            'avg_win_usd': np.mean([t['pnl_usd'] for t in wins]) if wins else 0,
            'avg_loss_usd': np.mean([t['pnl_usd'] for t in losses]) if losses else 0,
            'avg_rr_pips': avg_rr_pips,
            'avg_rr_usd': avg_rr_usd,
            'max_drawdown': max_dd,
            'profit_factor': abs(sum(t['pnl_usd'] for t in wins) / sum(t['pnl_usd'] for t in losses)) if losses else 0
        }
    
    def backtest_all_pairs(self, months: int = 12) -> Dict:
        """
        Backtest all pairs from pairs_config.json (Glitch 2.0)
        
        Args:
            months: Number of months to backtest
        
        Returns:
            Dictionary with all results
        """
        all_results = []
        
        for pair in self.pair_list:
            result = self.backtest_pair(pair, months)
            if result:
                all_results.append(result)
        
        # Generate summary report
        self._generate_summary_report(all_results)
        
        return all_results
    
    def _generate_summary_report(self, results: List[Dict]):
        """Generate summary report with USD metrics"""
        logger.info(f"\n{'='*100}")
        logger.info(f"📊 GLITCH IN MATRIX - BACKTEST SUMMARY")
        logger.info(f"Account: ${self.account_balance:,.0f} | Risk: {self.risk_per_trade_pct}% | Leverage: 1:{self.leverage}")
        logger.info(f"{'='*100}\n")
        
        # Sort by total USD profit
        results_sorted = sorted(results, key=lambda x: x.get('total_usd', 0), reverse=True)
        
        logger.info(f"{'Pair':<10} {'Trades':<8} {'Win%':<8} {'Total Pips':<12} {'Total USD':<14} {'Return%':<10} {'Avg R:R':<10} {'Max DD%':<10}")
        logger.info(f"{'-'*100}")
        
        total_usd = 0
        total_pips = 0
        total_trades = 0
        
        for r in results_sorted:
            max_dd = r.get('max_drawdown', 0)
            avg_rr = r.get('avg_rr_usd', 0)
            return_pct = r.get('return_pct', 0)
            usd = r.get('total_usd', 0)
            
            logger.info(f"{r['pair']:<10} {r['trades']:<8} {r['win_rate']:<8.1f} {r['total_pips']:<12.1f} ${usd:<13,.0f} {return_pct:<10.1f}% {avg_rr:<10.2f}x {max_dd:<10.1f}%")
            
            total_trades += r['trades']
            total_pips += r['total_pips']
            total_usd += usd
        
        overall_return = (total_usd / self.account_balance * 100) if self.account_balance > 0 else 0
        logger.info(f"{'-'*100}")
        logger.info(f"OVERALL: {total_trades} trades | {total_pips:,.1f} pips | ${total_usd:,.0f} profit | {overall_return:.1f}% return")
        
        # Top 3 performers
        logger.info(f"\n🏆 TOP PERFORMERS (USD):")
        for i, r in enumerate(results_sorted[:3], 1):
            if r['trades'] > 0:
                logger.info(f"{i}. {r['pair']}: ${r.get('total_usd', 0):,.0f} ({r.get('return_pct', 0):.1f}% return) - {r['win_rate']:.0f}% WR over {r['trades']} trades")
        
        # Bottom 3 performers
        logger.info(f"\n❌ WEAK PERFORMERS (USD):")
        for i, r in enumerate(list(reversed(results_sorted))[:3], 1):
            if r['trades'] > 0:
                logger.info(f"{i}. {r['pair']}: ${r.get('total_usd', 0):,.0f} ({r.get('return_pct', 0):.1f}% return) - {r['win_rate']:.0f}% WR over {r['trades']} trades")
        
        # Save to JSON
        report_file = Path("data/backtest_results.json")
        report_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(report_file, 'w') as f:
            json.dump(results_sorted, f, indent=2)
        
        logger.info(f"\n✅ Full results saved to: {report_file}")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Backtest Glitch in Matrix strategy')
    parser.add_argument('--pair', type=str, help='Single pair to test (e.g., EURUSD)')
    parser.add_argument('--months', type=int, default=12, help='Months to backtest (default: 12)')
    parser.add_argument('--all', action='store_true', help='Test all 21 pairs')
    
    args = parser.parse_args()
    
    backtester = GlitchBacktester()
    
    if args.all:
        logger.info("🚀 Starting backtest on ALL 21 pairs...")
        backtester.backtest_all_pairs(months=args.months)
    elif args.pair:
        logger.info(f"🚀 Starting backtest on {args.pair}...")
        backtester.backtest_pair(args.pair, months=args.months)
    else:
        logger.info("ℹ️ Usage:")
        logger.info("  Single pair:  python3 backtest_glitch_full.py --pair EURUSD --months 12")
        logger.info("  All pairs:    python3 backtest_glitch_full.py --all --months 12")


if __name__ == "__main__":
    main()
