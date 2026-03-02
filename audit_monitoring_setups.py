#!/usr/bin/env python3
"""
🔍 AUDIT MONITORING SETUPS - Live Diagnostic Tool
──────────────────
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

Real-time analysis of all monitoring setups:
- Reads monitoring_setups.json
- Fetches LIVE prices from cTrader API
- Analyzes each setup status (waiting, in-zone, invalidated)
- Shows exact distance in pips to entry zone

Usage:
    python3 audit_monitoring_setups.py
──────────────────
"""

import json
import sys
import requests
from datetime import datetime
from pathlib import Path
from loguru import logger

# Configure logger
logger.remove()
logger.add(
    sys.stdout,
    format="<level>{message}</level>",
    level="INFO",
    colorize=True
)

MONITORING_SETUPS_FILE = "monitoring_setups.json"
CTRADER_API_URL = "http://localhost:8767/price"


class SetupAuditor:
    """Live diagnostic tool for monitoring setups"""
    
    def __init__(self):
        self.base_path = Path(__file__).parent
        self.setups_file = self.base_path / MONITORING_SETUPS_FILE
    
    def get_live_price(self, symbol: str) -> float:
        """
        Fetch live price from cTrader API
        
        Args:
            symbol: Trading pair (e.g., EURUSD, GBPJPY)
        
        Returns:
            Current bid price or 0.0 if error
        """
        try:
            url = f"{CTRADER_API_URL}?symbol={symbol}"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                # MarketDataProvider returns bars array, use last close as current price
                bars = data.get('bars', [])
                if bars:
                    return bars[-1].get('close', 0.0)
                else:
                    logger.warning(f"⚠️  No bars data for {symbol}")
                    return 0.0
            else:
                logger.warning(f"⚠️  API error for {symbol}: {response.status_code}")
                return 0.0
        
        except Exception as e:
            logger.error(f"❌ Failed to fetch price for {symbol}: {e}")
            return 0.0
    
    def calculate_pips(self, symbol: str, price1: float, price2: float) -> float:
        """
        Calculate distance in pips between two prices
        
        Args:
            symbol: Trading pair
            price1: First price
            price2: Second price
        
        Returns:
            Distance in pips (absolute value)
        """
        # JPY pairs: 1 pip = 0.01
        if 'JPY' in symbol:
            pip_value = 0.01
        # Gold (XAU): 1 pip = 0.10
        elif 'XAU' in symbol:
            pip_value = 0.10
        # Most forex pairs: 1 pip = 0.0001
        else:
            pip_value = 0.0001
        
        pips = abs(price1 - price2) / pip_value
        return round(pips, 1)
    
    def parse_fvg_zone(self, fvg_zone_str: str) -> tuple:
        """
        Parse FVG zone string to extract top and bottom
        
        Args:
            fvg_zone_str: String like "1.08234-1.08456" or "1.08234 - 1.08456"
        
        Returns:
            Tuple of (bottom, top) as floats
        """
        try:
            # Remove spaces and split by dash
            parts = fvg_zone_str.replace(' ', '').split('-')
            if len(parts) == 2:
                bottom = float(parts[0])
                top = float(parts[1])
                return (min(bottom, top), max(bottom, top))
            else:
                return (0.0, 0.0)
        except:
            return (0.0, 0.0)
    
    def analyze_setup_status(self, setup: dict, current_price: float) -> dict:
        """
        Analyze setup status based on current price vs FVG zone
        
        Args:
            setup: Setup dictionary
            current_price: Current market price
        
        Returns:
            Status dictionary with analysis
        """
        direction = setup.get('direction', 'unknown').upper()
        
        # Get FVG zone from either format
        fvg_zone = setup.get('fvg_zone', '')
        if not fvg_zone:
            # Try alternative format (fvg_zone_top/bottom)
            fvg_top = setup.get('fvg_zone_top', 0)
            fvg_bottom = setup.get('fvg_zone_bottom', 0)
            if fvg_top and fvg_bottom:
                fvg_zone = f"{fvg_bottom}-{fvg_top}"
        
        fvg_bottom, fvg_top = self.parse_fvg_zone(fvg_zone)
        
        if fvg_bottom == 0.0 or fvg_top == 0.0:
            return {
                'status': 'ERROR',
                'reason': 'Invalid FVG zone format',
                'emoji': '❌',
                'color': 'red'
            }
        
        fvg_mid = (fvg_bottom + fvg_top) / 2
        symbol = setup.get('symbol', setup.get('pair', 'UNKNOWN'))
        
        # BUY SETUP (looking for bullish entry)
        if direction == 'BUY':
            if current_price > fvg_top:
                # Price above FVG - waiting for pullback
                distance_pips = self.calculate_pips(symbol, current_price, fvg_top)
                return {
                    'status': 'WAITING_PULLBACK',
                    'reason': f'Așteaptă pullback de {distance_pips} pips',
                    'detail': f'Prețul ({current_price:.5f}) peste FVG ({fvg_top:.5f})',
                    'emoji': '⏳',
                    'color': 'yellow',
                    'distance_pips': distance_pips
                }
            
            elif fvg_bottom <= current_price <= fvg_top:
                # Price IN FVG - monitoring for confirmation
                return {
                    'status': 'IN_ZONE',
                    'reason': f'Prețul este ÎN ZONĂ! Monitorizează 4H pentru CHoCH/Confirmare',
                    'detail': f'Prețul ({current_price:.5f}) în FVG ({fvg_bottom:.5f}-{fvg_top:.5f})',
                    'emoji': '🎯',
                    'color': 'green',
                    'distance_pips': 0.0
                }
            
            else:
                # Price below FVG bottom - zone invalidated
                distance_pips = self.calculate_pips(symbol, current_price, fvg_bottom)
                return {
                    'status': 'INVALIDATED',
                    'reason': f'Zona invalidată (FVG spart cu {distance_pips} pips)',
                    'detail': f'Prețul ({current_price:.5f}) sub FVG ({fvg_bottom:.5f})',
                    'emoji': '🔴',
                    'color': 'red',
                    'distance_pips': distance_pips
                }
        
        # SELL SETUP (looking for bearish entry)
        elif direction == 'SELL':
            if current_price < fvg_bottom:
                # Price below FVG - waiting for pullback
                distance_pips = self.calculate_pips(symbol, current_price, fvg_bottom)
                return {
                    'status': 'WAITING_PULLBACK',
                    'reason': f'Așteaptă pullback de {distance_pips} pips',
                    'detail': f'Prețul ({current_price:.5f}) sub FVG ({fvg_bottom:.5f})',
                    'emoji': '⏳',
                    'color': 'yellow',
                    'distance_pips': distance_pips
                }
            
            elif fvg_bottom <= current_price <= fvg_top:
                # Price IN FVG - monitoring for confirmation
                return {
                    'status': 'IN_ZONE',
                    'reason': f'Prețul este ÎN ZONĂ! Monitorizează 4H pentru CHoCH/Confirmare',
                    'detail': f'Prețul ({current_price:.5f}) în FVG ({fvg_bottom:.5f}-{fvg_top:.5f})',
                    'emoji': '🎯',
                    'color': 'green',
                    'distance_pips': 0.0
                }
            
            else:
                # Price above FVG top - zone invalidated
                distance_pips = self.calculate_pips(symbol, current_price, fvg_top)
                return {
                    'status': 'INVALIDATED',
                    'reason': f'Zona invalidată (FVG spart cu {distance_pips} pips)',
                    'detail': f'Prețul ({current_price:.5f}) peste FVG ({fvg_top:.5f})',
                    'emoji': '🔴',
                    'color': 'red',
                    'distance_pips': distance_pips
                }
        
        return {
            'status': 'UNKNOWN',
            'reason': 'Direction unknown',
            'emoji': '❓',
            'color': 'gray'
        }
    
    def load_setups(self) -> list:
        """Load monitoring setups from JSON file"""
        if not self.setups_file.exists():
            logger.error(f"❌ File not found: {self.setups_file}")
            return []
        
        try:
            with open(self.setups_file, 'r') as f:
                data = json.load(f)
            
            setups = data.get('setups', [])
            logger.info(f"✅ Loaded {len(setups)} setups from {self.setups_file.name}")
            return setups
        
        except Exception as e:
            logger.error(f"❌ Failed to load setups: {e}")
            return []
    
    def run_audit(self):
        """Main audit function"""
        print("\n" + "="*80)
        print("🔍 MONITORING SETUPS - LIVE DIAGNOSTIC AUDIT")
        print("="*80)
        print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"📁 Source: {self.setups_file.name}")
        print("="*80 + "\n")
        
        # Load setups
        setups = self.load_setups()
        
        if not setups:
            logger.warning("⚠️  No setups found!")
            return
        
        # Filter only MONITORING status
        active_setups = [s for s in setups if s.get('status', '').upper() == 'MONITORING']
        
        if not active_setups:
            logger.warning("⚠️  No active MONITORING setups found!")
            logger.info(f"ℹ️  Total setups: {len(setups)} (all closed or invalid)")
            return
        
        logger.info(f"📊 Active setups: {len(active_setups)}/{len(setups)}\n")
        
        # Analyze each setup
        for idx, setup in enumerate(active_setups, 1):
            symbol = setup.get('symbol', setup.get('pair', 'UNKNOWN'))
            direction = setup.get('direction', 'unknown').upper()
            
            # Get FVG zone
            fvg_zone = setup.get('fvg_zone', '')
            if not fvg_zone:
                fvg_top = setup.get('fvg_zone_top', 0)
                fvg_bottom = setup.get('fvg_zone_bottom', 0)
                if fvg_top and fvg_bottom:
                    fvg_zone = f"{fvg_bottom:.5f}-{fvg_top:.5f}"
                else:
                    fvg_zone = 'N/A'
            
            detected_at = setup.get('detected_at', setup.get('setup_time', 'N/A'))
            
            print(f"\n{'─'*80}")
            print(f"📌 SETUP #{idx}: {symbol} - {direction}")
            print(f"{'─'*80}")
            
            # Fetch live price
            logger.info(f"📡 Fetching live price for {symbol}...")
            current_price = self.get_live_price(symbol)
            
            if current_price == 0.0:
                logger.error(f"❌ Could not fetch price for {symbol}")
                print(f"   ⚠️  Status: API Error (cTrader connection failed)")
                continue
            
            # Parse FVG zone
            fvg_bottom, fvg_top = self.parse_fvg_zone(fvg_zone)
            
            # Analyze status
            analysis = self.analyze_setup_status(setup, current_price)
            
            # Display results
            print(f"   📊 Current Price: {current_price:.5f}")
            print(f"   🎯 FVG Zone: {fvg_zone} (Bottom: {fvg_bottom:.5f}, Top: {fvg_top:.5f})")
            print(f"   📅 Detected At: {detected_at}")
            print(f"\n   {analysis['emoji']} STATUS: {analysis['status']}")
            print(f"   💡 {analysis['reason']}")
            
            if 'detail' in analysis:
                print(f"   ℹ️  {analysis['detail']}")
            
            if analysis.get('distance_pips', 0) > 0:
                print(f"   📏 Distance: {analysis['distance_pips']} pips")
            
            # Additional info
            if analysis['status'] == 'IN_ZONE':
                print(f"\n   ✅ ACȚIUNE RECOMANDATĂ:")
                print(f"      → Monitorizează următorul 4H candle close")
                print(f"      → Așteaptă CHoCH (Change of Character)")
                print(f"      → Verifică confluență cu Order Block")
            
            elif analysis['status'] == 'WAITING_PULLBACK':
                print(f"\n   ⏳ ACȚIUNE RECOMANDATĂ:")
                print(f"      → Așteaptă revenirea prețului în FVG zone")
                print(f"      → Monitorizează rejection de la zona curentă")
            
            elif analysis['status'] == 'INVALIDATED':
                print(f"\n   🔴 ACȚIUNE RECOMANDATĂ:")
                print(f"      → Setup invalidat - șterge din monitoring")
                print(f"      → Caută noi setups pe Daily timeframe")
        
        # Summary
        print(f"\n{'='*80}")
        print("📊 SUMMARY:")
        print(f"{'='*80}")
        
        status_counts = {}
        for setup in active_setups:
            symbol = setup.get('symbol', setup.get('pair', ''))
            current_price = self.get_live_price(symbol)
            if current_price > 0:
                analysis = self.analyze_setup_status(setup, current_price)
                status = analysis['status']
                status_counts[status] = status_counts.get(status, 0) + 1
        
        for status, count in status_counts.items():
            emoji = '🎯' if status == 'IN_ZONE' else '⏳' if status == 'WAITING_PULLBACK' else '🔴'
            print(f"   {emoji} {status}: {count} setup(s)")
        
        print(f"\n{'='*80}")
        print("✅ AUDIT COMPLETE!")
        print(f"{'='*80}\n")


def main():
    """Entry point"""
    try:
        auditor = SetupAuditor()
        auditor.run_audit()
    except KeyboardInterrupt:
        print("\n\n⚠️  Audit interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
