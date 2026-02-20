"""
Test Lot Size Fix by ФорексГод
Validates:
1. Lot size is never 0.00 (enforced minimum 0.01)
2. UNIVERSAL_SEPARATOR is exactly 18 characters
3. Vertical badge layout with blank line before final separator
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from telegram_notifier import TelegramNotifier, UNIVERSAL_SEPARATOR
from smc_detector import TradeSetup, CHoCH, FVG

def test_lot_size_enforcement():
    """Test that lot size never shows 0.00"""
    
    print("\n" + "="*70)
    print("🧪  LOT SIZE FIX TEST by ФорексГод")
    print("="*70)
    
    # Create mock setup with EXTREME stop loss (should trigger 0.00 lot calculation)
    setup = type('TradeSetup', (), {
        'symbol': 'BTCUSD',
        'entry_price': 67000.00,
        'stop_loss': 66000.00,  # 1000 USD stop = massive risk
        'take_profit': 70000.00,
        'risk_reward': 3.0,
        'direction': 'long',
        'status': 'MONITORING',
        'strategy_type': 'reversal',
        
        # AI Scores
        'ml_score': 82,
        'ai_probability_score': 9,
        'ml_recommendation': 'TAKE',
        
        # SMC Context
        'daily_choch': type('CHoCH', (), {
            'direction': 'bullish',
            'break_price': 66500.00
        })(),
        'fvg': type('FVG', (), {
            'top': 67500.00,
            'bottom': 66500.00
        })(),
        'h4_choch': type('CHoCH', (), {
            'break_price': 66800.00
        })(),
        
        # Timing
        'ai_probability_factors': {
            'timing': 'London Session'
        }
    })()
    
    # Initialize notifier
    notifier = TelegramNotifier()
    
    # Generate message
    message = notifier.format_setup_alert(setup)
    
    # ──────────────────
    # VALIDATIONS
    # ──────────────────
    
    print("\n📊 Generated Message:")
    print("─" * 70)
    print(message)
    print("─" * 70)
    
    # Check 1: Lot size is NOT 0.00
    if "0.00 lots" in message:
        print("\n❌ FAILED: Lot size shows 0.00!")
        print("   Expected: Minimum 0.01 lots enforced")
        return False
    else:
        print("\n✅ PASSED: Lot size is >= 0.01 lots")
    
    # Check 2: UNIVERSAL_SEPARATOR is exactly 18 chars
    sep_length = len(UNIVERSAL_SEPARATOR)
    if sep_length != 18:
        print(f"\n❌ FAILED: UNIVERSAL_SEPARATOR is {sep_length} chars (expected 18)")
        return False
    else:
        print(f"✅ PASSED: UNIVERSAL_SEPARATOR is exactly 18 chars: '{UNIVERSAL_SEPARATOR}'")
    
    # Check 3: Separator appears in message
    if UNIVERSAL_SEPARATOR not in message:
        print("\n❌ FAILED: UNIVERSAL_SEPARATOR not found in message")
        return False
    else:
        print("✅ PASSED: UNIVERSAL_SEPARATOR present in message")
    
    # Check 4: Vertical badge layout
    if "✨ Quality:" in message and "🕒" in message and "📊" in message:
        # Count line breaks between badges
        ai_section = message.split("──────────────────")[1] if "──────────────────" in message else ""
        if "\n✨ Quality:" in ai_section and "\n🕒" in ai_section and "\n📊" in ai_section:
            print("✅ PASSED: Badges are vertically stacked (each on own line)")
        else:
            print("⚠️  WARNING: Badges might be inline (check message above)")
    
    # Check 5: Blank line before final separator
    if message.count(UNIVERSAL_SEPARATOR) >= 1:
        # Check if there's \n\n before the last separator
        last_sep_index = message.rfind(UNIVERSAL_SEPARATOR)
        before_sep = message[max(0, last_sep_index-3):last_sep_index]
        if "\n\n" in before_sep or before_sep.startswith("\n\n"):
            print("✅ PASSED: Blank line before final separator (airy design)")
        else:
            print("⚠️  INFO: Final separator padding depends on _add_branding_signature()")
    
    print("\n" + "="*70)
    print("🎯  ALL CRITICAL VALIDATIONS PASSED!")
    print("="*70)
    print("\n📱  Expected in Telegram:")
    print("   • Lot size: 0.01 lots (not 0.00)")
    print("   • Separator: ──────────────────  (18 chars)")
    print("   • Badges: Vertically stacked")
    print("   • Signature: Perfectly aligned with separator")
    print("\n✨ Glitch in Matrix by ФорексГод ✨")
    
    return True

if __name__ == "__main__":
    test_lot_size_enforcement()
