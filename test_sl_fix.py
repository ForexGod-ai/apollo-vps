#!/usr/bin/env python3
"""
Test SL Fix Implementation
Demonstrates the new 30-pip hard floor for forex and 1.5% crypto scale fix
"""

class MockFVG:
    """Mock FVG object for testing"""
    def __init__(self, symbol, direction, bottom, top, candle_time):
        self.symbol = symbol
        self.direction = direction
        self.bottom = bottom
        self.top = top
        self.candle_time = candle_time

class SLFixTester:
    """Test the new SL calculation logic"""
    
    def _get_asset_class(self, symbol: str) -> str:
        """Detect asset class for symbol-specific SL rules"""
        symbol_upper = symbol.upper()
        if any(x in symbol_upper for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOGE']):
            return 'crypto'
        elif any(x in symbol_upper for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            return 'metals'
        elif any(x in symbol_upper for x in ['XTI', 'WTI', 'OIL', 'BRENT']):
            return 'energy'
        elif 'JPY' in symbol_upper:
            return 'jpy_pairs'
        else:
            return 'forex'
    
    def _calculate_minimum_sl_distance(self, symbol: str, entry_price: float, asset_class: str) -> float:
        """
        Calculate MINIMUM SL distance based on asset class
        
        THE 30-PIP HARD FLOOR (Forex):
        - All FX pairs: minimum 30 pips
        
        CRYPTO SCALE FIX:
        - BTC/ETH: minimum 1.5-2% of current price
        
        Returns: minimum distance in price terms
        """
        if asset_class == 'crypto':
            # Crypto: 1.5% minimum for safety (prevents Invalid Volume errors)
            min_pct = 0.015  # 1.5%
            min_distance = entry_price * min_pct
            print(f"[SL MIN] {symbol} (Crypto): 1.5% = {min_distance:.2f}")
            return min_distance
        
        elif asset_class == 'metals':
            # Gold/Silver: 0.8% minimum
            min_pct = 0.008
            min_distance = entry_price * min_pct
            print(f"[SL MIN] {symbol} (Metals): 0.8% = {min_distance:.5f}")
            return min_distance
        
        elif asset_class == 'energy':
            # Oil: 1.0% minimum
            min_pct = 0.010
            min_distance = entry_price * min_pct
            print(f"[SL MIN] {symbol} (Energy): 1.0% = {min_distance:.5f}")
            return min_distance
        
        elif asset_class == 'jpy_pairs':
            # JPY pairs: 30 pips (at 2 decimals: 0.30)
            min_pips = 30
            pip_size = 0.01
            min_distance = min_pips * pip_size
            print(f"[SL MIN] {symbol} (JPY): 30 pips = {min_distance:.2f}")
            return min_distance
        
        else:  # Standard forex
            # THE 30-PIP HARD FLOOR: All forex pairs get 30 pips minimum
            min_pips = 30
            pip_size = 0.0001
            min_distance = min_pips * pip_size  # 0.0030
            print(f"[SL MIN] {symbol} (Forex): 30 pips = {min_distance:.4f}")
            return min_distance
    
    def calculate_lot_size(self, symbol: str, entry: float, stop_loss: float, risk_amount: float = 200.0) -> float:
        """Calculate lot size using The $200 Rule"""
        sl_distance = abs(entry - stop_loss)
        symbol_upper = symbol.upper()
        
        if any(x in symbol_upper for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA']):
            pip_size = 1.0
            pip_value = 1.0
            asset_type = "Crypto"
        elif any(x in symbol_upper for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            pip_size = 0.01
            pip_value = 10.0
            asset_type = "Metals"
        elif 'JPY' in symbol_upper:
            pip_size = 0.01
            pip_value = 10.0
            asset_type = "JPY Pair"
        else:
            pip_size = 0.0001
            pip_value = 10.0
            asset_type = "Forex"
        
        sl_pips = sl_distance / pip_size
        lot_size = risk_amount / (sl_pips * pip_value)
        lot_size = round(max(0.01, min(lot_size, 10.0)), 2)
        
        print(f"\n[LOT CALCULATION] {symbol} ({asset_type})")
        print(f"   Risk Amount: ${risk_amount:.2f}")
        print(f"   SL Distance: {sl_distance:.5f} ({sl_pips:.1f} pips)")
        print(f"   Pip Value: ${pip_value:.2f}")
        print(f"   Calculated Lot: {lot_size:.2f}")
        
        return lot_size
    
    def test_scenario(self, symbol: str, entry: float, swing: float, direction: str = 'bullish'):
        """Test a complete SL calculation scenario"""
        print(f"\n{'='*70}")
        print(f"TEST SCENARIO: {symbol} {direction.upper()}")
        print(f"{'='*70}")
        
        asset_class = self._get_asset_class(symbol)
        print(f"Asset Class: {asset_class}")
        print(f"Entry: {entry}")
        print(f"Swing Point: {swing}")
        
        # Simulate ATR buffer (1.5x ATR)
        atr_buffer = abs(entry - swing) * 0.2  # Simulate 20% ATR
        
        if direction == 'bullish':
            calculated_sl = swing - (1.5 * atr_buffer)
        else:
            calculated_sl = swing + (1.5 * atr_buffer)
        
        print(f"ATR Buffer: {atr_buffer:.5f}")
        print(f"Calculated SL (swing + ATR): {calculated_sl:.5f}")
        
        current_distance = abs(entry - calculated_sl)
        print(f"Current Distance: {current_distance:.5f}")
        
        # Apply minimum enforcement
        min_distance = self._calculate_minimum_sl_distance(symbol, entry, asset_class)
        
        if current_distance < min_distance:
            if direction == 'bullish':
                final_sl = entry - min_distance
            else:
                final_sl = entry + min_distance
            print(f"✅ [SL ENFORCED] {current_distance:.5f} → {min_distance:.5f}")
            print(f"Final SL: {final_sl:.5f}")
        else:
            final_sl = calculated_sl
            print(f"✅ [SL OK] Distance exceeds minimum")
            print(f"Final SL: {final_sl:.5f}")
        
        # Calculate lot size
        lot_size = self.calculate_lot_size(symbol, entry, final_sl)
        
        # Calculate actual risk
        sl_distance = abs(entry - final_sl)
        if any(x in symbol.upper() for x in ['BTC', 'ETH']):
            actual_risk = lot_size * sl_distance * 1.0
        elif any(x in symbol.upper() for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
            actual_risk = lot_size * (sl_distance / 0.01) * 10.0
        elif 'JPY' in symbol.upper():
            actual_risk = lot_size * (sl_distance / 0.01) * 10.0
        else:
            actual_risk = lot_size * (sl_distance / 0.0001) * 10.0
        
        print(f"\n[RISK VALIDATION]")
        print(f"   Target Risk: $200.00")
        print(f"   Actual Risk: ${actual_risk:.2f}")
        print(f"   Variance: ${abs(200 - actual_risk):.2f}")
        
        if abs(200 - actual_risk) <= 20:
            print(f"   Status: ✅ PASS (within $20 tolerance)")
        else:
            print(f"   Status: ⚠️  WARNING (variance > $20)")
        
        return final_sl, lot_size

def main():
    """Run all test scenarios"""
    tester = SLFixTester()
    
    print("\n" + "🔬 SL FIX IMPLEMENTATION TESTS".center(70, "="))
    print("Testing: 30-Pip Hard Floor + Crypto Scale Fix + $200 Risk Alignment\n")
    
    # Test 1: EURUSD (Standard Forex with tight swing)
    tester.test_scenario(
        symbol="EURUSD",
        entry=1.18134,
        swing=1.18100,  # Only 3.4 pips below entry
        direction='bullish'
    )
    
    # Test 2: GBPJPY (JPY Pair with reasonable swing)
    tester.test_scenario(
        symbol="GBPJPY",
        entry=208.674,
        swing=208.550,
        direction='bullish'
    )
    
    # Test 3: BTCUSD (Crypto with tight swing)
    tester.test_scenario(
        symbol="BTCUSD",
        entry=90000.00,
        swing=89500.00,  # $500 below (0.56%)
        direction='bullish'
    )
    
    # Test 4: BTCUSD (Crypto with wide swing)
    tester.test_scenario(
        symbol="BTCUSD",
        entry=90000.00,
        swing=88000.00,  # $2000 below (2.22%)
        direction='bullish'
    )
    
    # Test 5: XAUUSD (Gold)
    tester.test_scenario(
        symbol="XAUUSD",
        entry=2050.00,
        swing=2048.00,
        direction='bullish'
    )
    
    print("\n" + "="*70)
    print("✅ ALL TESTS COMPLETED".center(70))
    print("="*70 + "\n")

if __name__ == "__main__":
    main()
