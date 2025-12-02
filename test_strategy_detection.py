"""
Test Strategy Detection - CONTINUITY vs REVERSAL
Verifică dacă spatiotemporal_analyzer.py detectează corect ambele strategii
"""

import MetaTrader5 as mt5
from loguru import logger
import sys

# Import analyzer
from spatiotemporal_analyzer import SpatioTemporalAnalyzer

def test_nzdusd():
    """
    Test NZDUSD - Ar trebui să detecteze REVERSAL BULLISH
    (Era bearish, a făcut CHoCH, acum retestează FVG)
    """
    logger.info("\n" + "="*80)
    logger.info("🧪 TEST 1: NZDUSD - Expected: REVERSAL BULLISH")
    logger.info("="*80)
    
    analyzer = SpatioTemporalAnalyzer("NZDUSD")
    narrative = analyzer.analyze_market()
    
    # Check strategy type from scenarios
    if narrative.expected_scenarios:
        detected_strategy = narrative.expected_scenarios[0].get('strategy_type', 'UNKNOWN')
        logger.info(f"\n✅ DETECTED STRATEGY: {detected_strategy}")
        
        if detected_strategy == 'REVERSAL_BULLISH':
            logger.info("   ✅ CORRECT! NZDUSD is REVERSAL BULLISH setup")
            logger.info("   📋 Era BEARISH → CHoCH bullish → Retestează FVG → Entry LONG")
        else:
            logger.warning(f"   ❌ WRONG! Expected REVERSAL_BULLISH but got {detected_strategy}")
    
    # Print full narrative
    analyzer.print_narrative(narrative)
    
    return narrative


def test_other_pairs():
    """
    Test alte perechi pentru a găsi exemple de CONTINUITY
    """
    test_symbols = ["GBPUSD", "EURUSD", "XAUUSD", "BTCUSD"]
    
    for symbol in test_symbols:
        logger.info("\n" + "="*80)
        logger.info(f"🧪 TEST: {symbol}")
        logger.info("="*80)
        
        try:
            analyzer = SpatioTemporalAnalyzer(symbol)
            narrative = analyzer.analyze_market()
            
            if narrative.expected_scenarios:
                detected_strategy = narrative.expected_scenarios[0].get('strategy_type', 'UNKNOWN')
                logger.info(f"\n✅ DETECTED STRATEGY: {detected_strategy}")
                
                if detected_strategy.startswith('CONTINUITY'):
                    logger.info(f"   📊 {symbol} shows CONTINUITY strategy!")
                    logger.info("   📋 Trend stabilit → Pullback → 4H CHoCH confirmă → Continue trend")
                elif detected_strategy.startswith('REVERSAL'):
                    logger.info(f"   🔄 {symbol} shows REVERSAL strategy!")
                    logger.info("   📋 CHoCH pe Daily → Retest FVG → 4H CHoCH confirmă → Nou trend")
                else:
                    logger.info(f"   ⚠️ {symbol} is RANGING - no clear setup")
            
            # Print brief summary
            logger.info(f"\n📊 {symbol} Summary:")
            logger.info(f"   State: {narrative.current_state}")
            logger.info(f"   Price Position: {narrative.price_position}")
            logger.info(f"   Recommendation: {narrative.recommendation}")
            
        except Exception as e:
            logger.error(f"   ❌ Error analyzing {symbol}: {e}")
        
        logger.info("\n")


def main():
    """
    Main test suite
    """
    if not mt5.initialize():
        logger.error("❌ MT5 initialization failed!")
        return
    
    try:
        logger.info("\n" + "🎯"*40)
        logger.info("STRATEGY DETECTION TEST SUITE")
        logger.info("Testing: CONTINUITY vs REVERSAL detection")
        logger.info("🎯"*40 + "\n")
        
        # Test 1: NZDUSD (should be REVERSAL)
        nzdusd_narrative = test_nzdusd()
        
        input("\nPress Enter to test other pairs...")
        
        # Test 2: Other pairs (looking for CONTINUITY examples)
        test_other_pairs()
        
        logger.info("\n" + "="*80)
        logger.info("✅ TEST SUITE COMPLETE!")
        logger.info("="*80)
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
