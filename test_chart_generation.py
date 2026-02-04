#!/usr/bin/env python3
"""
Test chart generation with TradingView style
"""
import sys
import json
from datetime import datetime
from chart_generator import ChartGenerator
from smc_detector import TradeSetup, CHoCH, FVG
from daily_scanner import CTraderDataProvider

def create_test_setup_from_monitoring():
    """Load setup from monitoring_setups.json"""
    try:
        with open('monitoring_setups.json', 'r') as f:
            data = json.load(f)
        
        if not data.get('setups'):
            print("❌ No setups in monitoring_setups.json")
            return None
        
        # Use first setup (USDCHF)
        setup_data = data['setups'][0]
        print(f"📊 Loading setup: {setup_data['symbol']} {setup_data['direction'].upper()}")
        
        # Create CHoCH object (Daily)
        daily_choch = CHoCH(
            index=0,  # We don't have exact index
            direction='bearish',  # SELL setup
            break_price=setup_data['entry_price'],
            previous_trend='bullish',
            candle_time=datetime.fromisoformat(setup_data['setup_time']),
            swing_broken=None  # We don't have swing point data
        )
        
        # Create FVG object
        fvg = FVG(
            index=0,
            direction='bearish',
            top=setup_data['fvg_zone_top'],
            bottom=setup_data['fvg_zone_bottom'],
            middle=(setup_data['fvg_zone_top'] + setup_data['fvg_zone_bottom']) / 2,
            candle_time=datetime.fromisoformat(setup_data['setup_time']),
            is_filled=False,
            associated_choch=daily_choch
        )
        
        # Create TradeSetup object
        setup = TradeSetup(
            symbol=setup_data['symbol'],
            daily_choch=daily_choch,
            fvg=fvg,
            h4_choch=None,
            entry_price=setup_data['entry_price'],
            stop_loss=setup_data['stop_loss'],
            take_profit=setup_data['take_profit'],
            risk_reward=setup_data['risk_reward'],
            setup_time=datetime.fromisoformat(setup_data['setup_time']),
            priority=setup_data['priority'],
            strategy_type=setup_data['strategy_type'],
            status=setup_data['status']
        )
        
        # Add direction attribute (not in dataclass but needed by chart_generator)
        setup.direction = setup_data['direction']
        
        return setup
    
    except Exception as e:
        print(f"❌ Error loading setup: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("🎨 Testing TradingView-style chart generation...")
    
    # 1. Load setup from monitoring
    setup = create_test_setup_from_monitoring()
    if not setup:
        sys.exit(1)
    
    print(f"✅ Setup loaded: {setup.symbol}")
    print(f"   Entry: {setup.entry_price}")
    print(f"   SL: {setup.stop_loss}")
    print(f"   TP: {setup.take_profit}")
    print(f"   R:R: 1:{setup.risk_reward:.1f}")
    print(f"   FVG: {setup.fvg.top} -> {setup.fvg.bottom}")
    
    # 2. Fetch Daily data
    print(f"\n📈 Fetching Daily data for {setup.symbol}...")
    data_provider = CTraderDataProvider()
    
    if not data_provider.connect():
        print("❌ cTrader cBot not available")
        sys.exit(1)
    
    df_daily = data_provider.get_historical_data(setup.symbol, 'D1', 100)
    
    if df_daily is None or df_daily.empty:
        print("❌ No data available")
        sys.exit(1)
    
    print(f"✅ Got {len(df_daily)} daily candles")
    
    # 3. Generate chart
    print("\n🎨 Generating TradingView-style chart...")
    chart_gen = ChartGenerator(dark_theme=True)
    
    output_path = f"test_chart_{setup.symbol}_{datetime.now().strftime('%H%M%S')}.png"
    result = chart_gen.create_daily_chart(
        symbol=setup.symbol,
        df=df_daily,
        setup=setup,
        save_path=output_path,
        timeframe="Daily"
    )
    
    if result:
        print(f"\n✅ Chart saved: {result}")
        print("\n📋 Chart includes:")
        print("   🟣 Purple FVG zone")
        print("   🔴 Red CHoCH marker (bearish)")
        print("   🟠 Orange Entry line")
        print("   🔴 Red SL dashed line")
        print("   🟢 Green TP dashed line")
        print("   🌑 TradingView dark theme (#131722)")
    else:
        print("\n❌ Chart generation failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
