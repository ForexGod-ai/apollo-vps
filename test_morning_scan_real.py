"""
TEST MORNING SCAN REAL - ForexGod Trading AI
Simulează scanul de dimineață 09:00 cu DATE REALE de piață
"""

import sys
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger
from typing import Optional

from smc_detector import SMCDetector
from chart_generator import ChartGenerator
from telegram_notifier import TelegramNotifier

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="INFO")


def get_real_forex_data(symbol: str, bars: int = 100) -> Optional[pd.DataFrame]:
    """
    Get REAL forex data from Yahoo Finance
    
    Forex symbols in Yahoo Finance format:
    EURUSD=X, GBPUSD=X, USDJPY=X, etc.
    """
    try:
        # Convert to Yahoo Finance format
        yahoo_symbols = {
            'EURUSD': 'EURUSD=X',
            'GBPUSD': 'GBPUSD=X',
            'USDJPY': 'USDJPY=X',
            'USDCHF': 'USDCHF=X',
            'AUDUSD': 'AUDUSD=X',
            'USDCAD': 'USDCAD=X',
            'NZDUSD': 'NZDUSD=X',
            'EURJPY': 'EURJPY=X',
            'GBPJPY': 'GBPJPY=X',
            'EURGBP': 'EURGBP=X',
            'EURCAD': 'EURCAD=X',
            'AUDCAD': 'AUDCAD=X',
            'AUDNZD': 'AUDNZD=X',
            'NZDCAD': 'NZDCAD=X',
            'GBPNZD': 'GBPNZD=X',
            'GBPCHF': 'GBPCHF=X',
            'CADCHF': 'CADCHF=X',
            'XAUUSD': 'GC=F',  # Gold Futures
            'BTCUSD': 'BTC-USD',
            'USOIL': 'CL=F'  # Crude Oil Futures
        }
        
        yahoo_symbol = yahoo_symbols.get(symbol, f"{symbol}=X")
        
        logger.info(f"📊 Fetching REAL data for {symbol} ({yahoo_symbol})...")
        
        # Get last 150 days of DAILY data
        end_date = datetime.now()
        start_date = end_date - timedelta(days=150)
        
        ticker = yf.Ticker(yahoo_symbol)
        df = ticker.history(start=start_date, end=end_date, interval='1d')
        
        if df.empty:
            logger.warning(f"⚠️  No data for {symbol}")
            return None
        
        # Take last 'bars' candles
        df = df.tail(bars).copy()
        
        # Rename columns to match our format
        df = df.rename(columns={
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume'
        })
        
        # Add time column
        df['time'] = df.index
        df = df.reset_index(drop=True)
        
        # Keep only needed columns
        df = df[['time', 'open', 'high', 'low', 'close', 'volume']]
        
        logger.success(f"✅ Got {len(df)} REAL candles for {symbol}")
        logger.info(f"   Current price: {df['close'].iloc[-1]:.5f}")
        logger.info(f"   Date range: {df['time'].iloc[0].strftime('%Y-%m-%d')} to {df['time'].iloc[-1].strftime('%Y-%m-%d')}")
        
        return df
        
    except Exception as e:
        logger.error(f"❌ Error getting data for {symbol}: {e}")
        return None


def test_morning_scan():
    """Run REAL morning scan test"""
    
    logger.info("="*80)
    logger.info("🌅 MORNING SCAN TEST - REAL MARKET DATA")
    logger.info(f"⏰ Simulating: 09:00 {datetime.now().strftime('%Y-%m-%d')}")
    logger.info("="*80)
    
    # Priority pairs (same as morning_strategy_scan.py)
    pairs = [
        {'symbol': 'GBPUSD', 'priority': 1},
        {'symbol': 'XAUUSD', 'priority': 1},
        {'symbol': 'BTCUSD', 'priority': 1},
        {'symbol': 'GBPJPY', 'priority': 1},
        {'symbol': 'USOIL', 'priority': 1},
        {'symbol': 'EURUSD', 'priority': 2},
        {'symbol': 'USDJPY', 'priority': 2},
        {'symbol': 'USDCAD', 'priority': 2},
        {'symbol': 'NZDUSD', 'priority': 2},
        {'symbol': 'AUDNZD', 'priority': 2},
    ]
    
    logger.info(f"\n📊 Analyzing {len(pairs)} priority pairs with REAL market data...\n")
    
    # Initialize
    smc = SMCDetector()
    chart_gen = ChartGenerator()
    
    results = {
        'reversal': [],
        'continuation': [],
        'no_setup': []
    }
    
    # Scan each pair
    for i, pair in enumerate(pairs, 1):
        symbol = pair['symbol']
        priority = pair['priority']
        
        logger.info(f"\n{'='*60}")
        logger.info(f"📍 Progress: {i}/{len(pairs)}")
        logger.info(f"🔍 Analyzing {symbol} (Priority {priority})...")
        logger.info(f"{'='*60}")
        
        # Get REAL market data
        df_daily = get_real_forex_data(symbol, bars=100)
        
        if df_daily is None:
            logger.warning(f"⏭️  Skipping {symbol} - no data available")
            continue
        
        # Detect setup using SMC algorithm
        setup = smc.scan_for_setup(symbol, df_daily, df_daily, priority)
        
        if setup is None:
            logger.info(f"⚪ {symbol}: No valid setup detected")
            results['no_setup'].append(symbol)
            
            # Generate chart anyway
            chart_path = chart_gen.create_daily_chart(
                symbol=symbol,
                df=df_daily,
                setup=None,
                save_path=f"charts/test_scan/{symbol}_daily.png"
            )
            
        else:
            # SETUP FOUND!
            strategy_type = setup.strategy_type
            emoji = "🔴" if strategy_type == 'reversal' else "🟢"
            
            logger.success(f"{emoji} {symbol}: {strategy_type.upper()} setup found!")
            logger.info(f"   Direction: {setup.daily_choch.direction}")
            logger.info(f"   Entry: {setup.entry_price:.5f}")
            logger.info(f"   SL: {setup.stop_loss:.5f}")
            logger.info(f"   TP: {setup.take_profit:.5f}")
            logger.info(f"   R:R: 1:{setup.risk_reward:.2f}")
            logger.info(f"   Status: {setup.status}")
            
            # Generate chart with markers
            chart_path = chart_gen.create_daily_chart(
                symbol=symbol,
                df=df_daily,
                setup=setup,
                save_path=f"charts/test_scan/{symbol}_{strategy_type}.png"
            )
            
            if strategy_type == 'reversal':
                results['reversal'].append({
                    'symbol': symbol,
                    'setup': setup,
                    'chart': chart_path
                })
            else:
                results['continuation'].append({
                    'symbol': symbol,
                    'setup': setup,
                    'chart': chart_path
                })
    
    # Summary
    logger.info("\n" + "="*80)
    logger.info("📊 MORNING SCAN RESULTS (REAL DATA)")
    logger.info("="*80)
    logger.info(f"🔴 REVERSAL setups: {len(results['reversal'])}")
    logger.info(f"🟢 CONTINUATION setups: {len(results['continuation'])}")
    logger.info(f"⚪ No setup: {len(results['no_setup'])}")
    
    if results['reversal']:
        logger.info(f"\n🔴 REVERSAL SETUPS:")
        for r in results['reversal']:
            logger.info(f"   • {r['symbol']}: {r['setup'].daily_choch.direction} | R:R 1:{r['setup'].risk_reward:.2f} | {r['setup'].status}")
    
    if results['continuation']:
        logger.info(f"\n🟢 CONTINUATION SETUPS:")
        for c in results['continuation']:
            logger.info(f"   • {c['symbol']}: {c['setup'].daily_choch.direction} | R:R 1:{c['setup'].risk_reward:.2f} | {c['setup'].status}")
    
    if results['no_setup']:
        logger.info(f"\n⚪ NO SETUP:")
        logger.info(f"   {', '.join(results['no_setup'])}")
    
    logger.info("\n" + "="*80)
    logger.info("📁 Charts saved in: charts/test_scan/")
    logger.info("="*80)
    
    return results


if __name__ == "__main__":
    import os
    os.makedirs("charts/test_scan", exist_ok=True)
    
    results = test_morning_scan()
    
    logger.info("\n✅ REAL MORNING SCAN TEST COMPLETE!")
