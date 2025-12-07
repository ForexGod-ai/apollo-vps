#!/usr/bin/env python3
"""
Manual cTrader Account Sync
Actualizare simplă a balanței din contul tău cTrader
"""

from loguru import logger
import json
from datetime import datetime

def update_balance_manually():
    """
    Actualizează manual balanța în trade_history.json
    Folosește când vezi că balance-ul s-a schimbat în cTrader
    """
    
    logger.info("="*70)
    logger.info("💰 MANUAL BALANCE UPDATE")
    logger.info("="*70)
    
    print("\n📊 Current cTrader Account Status:")
    print("-"*70)
    
    # Citește balance-ul actual
    try:
        with open('trade_history.json', 'r') as f:
            trades = json.load(f)
        
        if trades:
            closed_trades = [t for t in trades if 'CLOSED' in t.get('status', '')]
            initial = 1000.0
            
            if closed_trades:
                last_trade = closed_trades[-1]
                current_balance = last_trade.get('balance_after', initial)
                total_profit = current_balance - initial
                
                print(f"   📈 Current balance in system: ${current_balance:.2f}")
                print(f"   💵 Initial deposit: ${initial:.2f}")
                print(f"   📊 Total profit: ${total_profit:.2f}")
                print(f"   🎯 Closed trades: {len(closed_trades)}")
            else:
                print(f"   📈 Balance: $1,000.00 (initial)")
        else:
            print("   ⚠️  No trades found")
            
    except FileNotFoundError:
        print("   ⚠️  trade_history.json not found")
    
    print("\n" + "-"*70)
    print("🔄 Enter NEW balance from your cTrader account:")
    print("   (Check in cTrader app: Balance value)")
    print("-"*70)
    
    try:
        new_balance_str = input("💰 New balance (e.g., 1450.50): $")
        new_balance = float(new_balance_str.strip().replace('$', '').replace(',', ''))
        
        if new_balance < 0:
            logger.error("❌ Invalid balance!")
            return
        
        print(f"\n✅ You entered: ${new_balance:.2f}")
        confirm = input("   Confirm? (yes/no): ").lower().strip()
        
        if confirm not in ['yes', 'y']:
            logger.info("❌ Cancelled")
            return
        
        # Calculează profitul
        initial_balance = 1000.0
        total_profit = new_balance - initial_balance
        
        # Update .env
        logger.info("\n🔄 Updating .env file...")
        
        with open('.env', 'r') as f:
            env_content = f.read()
        
        # Replace ACCOUNT_BALANCE
        import re
        env_content = re.sub(
            r'ACCOUNT_BALANCE=\d+\.?\d*',
            f'ACCOUNT_BALANCE={new_balance:.2f}',
            env_content
        )
        
        with open('.env', 'w') as f:
            f.write(env_content)
        
        logger.success(f"✅ Updated .env: ACCOUNT_BALANCE={new_balance:.2f}")
        
        # Note about manual sync
        logger.info("\n📝 Note:")
        logger.info("   - Balance updated in .env")
        logger.info("   - System will use this balance for risk calculation")
        logger.info("   - Update again when balance changes significantly")
        logger.info("   - Or after completing new trades")
        
        logger.info("\n" + "="*70)
        logger.success("✅ BALANCE UPDATE COMPLETE!")
        logger.info("="*70)
        logger.info(f"   New balance: ${new_balance:.2f}")
        logger.info(f"   Total profit: ${total_profit:.2f} ({(total_profit/initial_balance)*100:.1f}%)")
        logger.info(f"   Risk per trade (2%): ${new_balance * 0.02:.2f}")
        logger.info("="*70)
        
        print("\n💡 Restart the webhook server to use new balance:")
        print("   python3 main.py")
        
    except ValueError:
        logger.error("❌ Invalid number format!")
    except KeyboardInterrupt:
        logger.info("\n❌ Cancelled by user")
    except Exception as e:
        logger.error(f"❌ Error: {e}")


if __name__ == "__main__":
    update_balance_manually()
