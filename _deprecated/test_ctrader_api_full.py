"""
Test complete cTrader Open API implementation with all 21 pairs
Includes OAuth2 token refresh and data fetching
"""

import sys
from loguru import logger
from ctrader_data_client import get_ctrader_client

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>", level="INFO")

def test_all_pairs():
    """Test all 21 trading pairs with cTrader Open API"""
    
    # All 21 pairs from morning scanner
    all_pairs = [
        # Forex Majors (8)
        'GBPUSD', 'EURUSD', 'USDJPY', 'USDCHF',
        'AUDUSD', 'USDCAD', 'NZDUSD', 'EURGBP',
        
        # Forex Crosses (9)
        'EURJPY', 'GBPJPY', 'EURCAD', 'AUDCAD',
        'AUDNZD', 'NZDCAD', 'GBPNZD', 'GBPCHF', 'CADCHF',
        
        # Commodities (2)
        'XAUUSD',  # Gold
        'XAGUSD',  # Silver
        
        # Crypto (1)
        'BTCUSD',  # Bitcoin
        
        # Energy (1)
        'USOIL'    # Oil
    ]
    
    logger.info("=" * 80)
    logger.info("🧪 TESTING CTRADER OPEN API - ALL 21 PAIRS")
    logger.info("=" * 80)
    
    # Initialize client
    client = get_ctrader_client()
    
    # Test results
    successful = []
    failed = []
    
    for i, symbol in enumerate(all_pairs, 1):
        logger.info(f"\n[{i}/21] Testing {symbol}...")
        
        try:
            # Fetch 5 daily candles
            df = client.get_historical_data(symbol, 'D1', 5)
            
            if df is not None and not df.empty:
                logger.success(f"✅ {symbol} - Got {len(df)} candles")
                
                # Show latest price
                latest = df.iloc[-1]
                logger.info(f"   💰 Close: {latest['close']:.5f} | High: {latest['high']:.5f} | Low: {latest['low']:.5f}")
                
                successful.append(symbol)
            else:
                logger.error(f"❌ {symbol} - No data received")
                failed.append(symbol)
                
        except Exception as e:
            logger.error(f"❌ {symbol} - Error: {e}")
            failed.append(symbol)
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 80)
    logger.success(f"✅ Successful: {len(successful)}/21 pairs")
    
    if successful:
        logger.info(f"   {', '.join(successful)}")
    
    if failed:
        logger.error(f"\n❌ Failed: {len(failed)}/21 pairs")
        logger.error(f"   {', '.join(failed)}")
    
    logger.info("\n" + "=" * 80)
    
    # Test critical pairs (commodities + crypto)
    logger.info("\n🎯 CRITICAL PAIRS TEST (Commodities + Crypto)")
    logger.info("=" * 80)
    
    critical_pairs = ['XAUUSD', 'XAGUSD', 'BTCUSD', 'USOIL']
    critical_success = sum(1 for pair in critical_pairs if pair in successful)
    
    logger.info(f"Critical pairs working: {critical_success}/{len(critical_pairs)}")
    
    for pair in critical_pairs:
        status = "✅" if pair in successful else "❌"
        logger.info(f"   {status} {pair}")
    
    logger.info("=" * 80)
    
    # Final verdict
    if len(successful) >= 18:  # 85%+ success rate
        logger.success("\n🎉 EXCELLENT! cTrader Open API is working properly!")
    elif len(successful) >= 13:  # Better than Alpha Vantage
        logger.warning("\n⚠️  GOOD - Better than Alpha Vantage, but some pairs missing")
    else:
        logger.error("\n❌ NEEDS ATTENTION - Many pairs failing")
    
    return len(successful), len(failed)


if __name__ == "__main__":
    successful, failed = test_all_pairs()
    
    # Exit code based on results
    if failed == 0:
        sys.exit(0)  # Perfect
    elif successful >= 18:
        sys.exit(0)  # Good enough
    else:
        sys.exit(1)  # Needs work
