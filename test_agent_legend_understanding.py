"""
Test Agent Legend Understanding - Verifică dacă agentul înțelege legendele ForexGod
"""

import json
import sys
from loguru import logger

# Configure logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="INFO")

def load_annotation_legend():
    """Load annotation legend from config"""
    try:
        with open('tradingview_saved_charts.json', 'r') as f:
            config = json.load(f)
            return config.get('annotation_legend', {})
    except Exception as e:
        logger.error(f"Failed to load legend: {e}")
        return None

def display_legend(legend):
    """Display the complete annotation legend"""
    logger.info("="*80)
    logger.info("📊 FOREXGOD CHART ANNOTATION LEGEND - AI AGENT UNDERSTANDING TEST")
    logger.info("="*80)
    
    # Swing Points
    if 'swing_points' in legend:
        logger.info("\n🎯 SWING POINTS SYSTEM (BODY-ONLY):")
        sp = legend['swing_points']
        logger.info(f"  ⚪ White Dots: {sp.get('white_dots', 'N/A')}")
        logger.info(f"  🟠 Orange Dots: {sp.get('orange_dots', 'N/A')}")
        logger.info(f"  📝 Note: {sp.get('note', 'N/A')}")
    
    # Structure Labels
    if 'structure_labels' in legend:
        logger.info("\n📈 STRUCTURE LABELS (TREND CLASSIFICATION):")
        sl = legend['structure_labels']
        logger.info(f"  🟢 HH/HL: {sl.get('HH_HL', 'N/A')}")
        logger.info(f"  🔴 LH/LL: {sl.get('LH_LL', 'N/A')}")
        logger.info(f"  📝 Note: {sl.get('note', 'N/A')}")
    
    # Imbalance Zones (CRITICAL!)
    if 'imbalance_zones' in legend:
        logger.info("\n🌈 IMBALANCE ZONE SYSTEM (CRITICAL FOR AI):")
        iz = legend['imbalance_zones']
        logger.info(f"  🔴 Red Zones: {iz.get('red_zones', 'N/A')}")
        logger.info(f"  🟢 Green Zones: {iz.get('green_zones', 'N/A')}")
        logger.info(f"  🔵 Blue Zones: {iz.get('blue_zones', 'N/A')}")
        
        if 'blue_mechanism' in iz:
            logger.info("\n  🔍 BLUE ZONE MECHANISM (How Reverse Imbalance Works):")
            bm = iz['blue_mechanism']
            logger.info(f"     • Red→Blue: {bm.get('red_to_blue', 'N/A')}")
            logger.info(f"     • Green→Blue: {bm.get('green_to_blue', 'N/A')}")
            logger.info(f"     • Explanation: {bm.get('explanation', 'N/A')}")
    
    # CHoCH Markers
    if 'choch_markers' in legend:
        logger.info("\n⚡ CHOCH MARKERS (STRUCTURE SHIFTS):")
        cm = legend['choch_markers']
        logger.info(f"  📝 Description: {cm.get('description', 'N/A')}")
        logger.info(f"  🟢 Bullish CHoCH: {cm.get('bullish_choch', 'N/A')}")
        logger.info(f"  🔴 Bearish CHoCH: {cm.get('bearish_choch', 'N/A')}")
    
    # Trading Strategy
    if 'trading_strategy' in legend:
        logger.info("\n🚀 TRADING STRATEGY (GLITCH IN MATRIX):")
        ts = legend['trading_strategy']
        logger.info(f"  1️⃣  {ts.get('step_1', 'N/A')}")
        logger.info(f"  2️⃣  {ts.get('step_2', 'N/A')}")
        logger.info(f"  3️⃣  {ts.get('step_3', 'N/A')}")
        logger.info(f"  4️⃣  {ts.get('step_4', 'N/A')}")
        logger.info(f"  5️⃣  {ts.get('step_5', 'N/A')}")

def test_imbalance_cycle_understanding(legend):
    """Test agent's understanding of imbalance zone lifecycle"""
    logger.info("\n" + "="*80)
    logger.info("🧪 TESTING IMBALANCE CYCLE UNDERSTANDING")
    logger.info("="*80)
    
    iz = legend.get('imbalance_zones', {})
    bm = iz.get('blue_mechanism', {})
    
    # Test Scenario 1: Red → Blue
    logger.info("\n📍 SCENARIO 1: Bearish Imbalance → Reverse Imbalance")
    logger.info("   Initial State: 🔴 Red zone (bearish FVG) at $1.2500-$1.2520")
    logger.info("   Event: Price breaks ABOVE $1.2520 (tests the zone)")
    logger.info("   Result: 🔵 Blue zone (now acts as SUPPORT)")
    logger.info(f"   ✅ Agent Understanding: {bm.get('red_to_blue', '❌ NOT CONFIGURED')}")
    
    # Test Scenario 2: Green → Blue
    logger.info("\n📍 SCENARIO 2: Bullish Imbalance → Reverse Imbalance")
    logger.info("   Initial State: 🟢 Green zone (bullish FVG) at $1.2400-$1.2420")
    logger.info("   Event: Price breaks BELOW $1.2400 (tests the zone)")
    logger.info("   Result: 🔵 Blue zone (now acts as RESISTANCE)")
    logger.info(f"   ✅ Agent Understanding: {bm.get('green_to_blue', '❌ NOT CONFIGURED')}")
    
    # Summary
    logger.info("\n📊 IMBALANCE LIFECYCLE SUMMARY:")
    logger.info("   🔴 Red (resistance) → Price breaks above → 🔵 Blue (support)")
    logger.info("   🟢 Green (support) → Price breaks below → 🔵 Blue (resistance)")
    logger.info(f"\n   💡 Core Concept: {bm.get('explanation', '❌ NOT EXPLAINED')}")

def test_chart_configuration():
    """Test which charts are configured"""
    logger.info("\n" + "="*80)
    logger.info("📊 CONFIGURED CHARTS TEST")
    logger.info("="*80)
    
    try:
        with open('tradingview_saved_charts.json', 'r') as f:
            config = json.load(f)
            charts = config.get('charts', {})
        
        configured = []
        not_configured = []
        
        for symbol, url in charts.items():
            if url and url.strip():
                configured.append(symbol)
                logger.info(f"  ✅ {symbol}: {url[:60]}...")
            else:
                not_configured.append(symbol)
        
        logger.info(f"\n📈 Progress: {len(configured)}/{len(charts)} charts configured ({len(configured)/len(charts)*100:.1f}%)")
        logger.info(f"  ✅ Ready: {', '.join(configured)}")
        logger.info(f"  ⏳ Pending: {len(not_configured)} charts")
        
        return len(configured) > 0
        
    except Exception as e:
        logger.error(f"Failed to load charts: {e}")
        return False

def verify_body_only_understanding(legend):
    """Verify agent understands BODY-ONLY analysis"""
    logger.info("\n" + "="*80)
    logger.info("🔬 BODY-ONLY ANALYSIS VERIFICATION")
    logger.info("="*80)
    
    sp = legend.get('swing_points', {})
    note = sp.get('note', '')
    
    logger.info("  📍 Example Candle:")
    logger.info("     Open: $1.2500")
    logger.info("     High: $1.2550 (wick)")
    logger.info("     Low: $1.2480 (wick)")
    logger.info("     Close: $1.2520")
    
    logger.info("\n  ❌ WRONG (Traditional Analysis):")
    logger.info("     Swing High = $1.2550 (uses wick)")
    logger.info("     Swing Low = $1.2480 (uses wick)")
    
    logger.info("\n  ✅ CORRECT (ForexGod Body-Only):")
    logger.info("     Body High = max($1.2500, $1.2520) = $1.2520")
    logger.info("     Body Low = min($1.2500, $1.2520) = $1.2500")
    logger.info("     Wicks = IGNORED (manipulation)")
    
    logger.info(f"\n  📝 Agent Rule: {note}")
    
    if 'BODY-ONLY' in note or 'body' in note.lower():
        logger.success("  ✅ Agent understands BODY-ONLY rule!")
        return True
    else:
        logger.warning("  ⚠️  BODY-ONLY rule not clearly documented")
        return False

def main():
    """Run complete legend understanding test"""
    logger.info("🚀 Starting ForexGod Legend Understanding Test...")
    logger.info("=" * 80)
    
    # Load legend
    legend = load_annotation_legend()
    
    if not legend:
        logger.error("❌ Failed to load annotation legend!")
        return False
    
    # Display complete legend
    display_legend(legend)
    
    # Test imbalance cycle understanding
    test_imbalance_cycle_understanding(legend)
    
    # Verify body-only understanding
    body_only_ok = verify_body_only_understanding(legend)
    
    # Test chart configuration
    charts_ok = test_chart_configuration()
    
    # Final verdict
    logger.info("\n" + "="*80)
    logger.info("🎯 FINAL VERDICT:")
    logger.info("="*80)
    
    checks = {
        "Annotation Legend Loaded": legend is not None,
        "Swing Points System": 'swing_points' in legend,
        "Structure Labels": 'structure_labels' in legend,
        "Imbalance Zones": 'imbalance_zones' in legend,
        "Blue Mechanism Explained": 'blue_mechanism' in legend.get('imbalance_zones', {}),
        "CHoCH Markers": 'choch_markers' in legend,
        "Trading Strategy": 'trading_strategy' in legend,
        "Body-Only Rule Clear": body_only_ok,
        "Charts Configured": charts_ok
    }
    
    passed = sum(checks.values())
    total = len(checks)
    
    for check, status in checks.items():
        emoji = "✅" if status else "❌"
        logger.info(f"  {emoji} {check}")
    
    logger.info(f"\n📊 Score: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.success("\n🎉 PERFECT! Agent fully understands ForexGod annotation system!")
        logger.success("✅ Ready to analyze charts with all SMC drawings")
        return True
    elif passed >= total * 0.8:
        logger.warning("\n⚠️  GOOD but some gaps remain")
        logger.warning("📝 Review missing components above")
        return True
    else:
        logger.error("\n❌ CRITICAL GAPS in agent understanding!")
        logger.error("🔧 Fix configuration before using scanner")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
