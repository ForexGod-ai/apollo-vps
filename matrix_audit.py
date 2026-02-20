#!/usr/bin/env python3
"""
──────────────────
🎯 GLITCH IN MATRIX - SYSTEM AUDIT REPORT
──────────────────

Rigorous audit of all 15 official trading pairs.
Validates monitoring status, setup health, and risk parameters.

✨ Glitch in Matrix by ФорексГод ✨
──────────────────
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Set

# ──────────────────
# OFFICIAL 15 PARITIES - GLITCH IN MATRIX V3.7
# ──────────────────

OFFICIAL_15 = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "USDCHF",
    "AUDUSD",
    "USDCAD",
    "NZDUSD",
    "EURGBP",
    "EURJPY",
    "GBPJPY",
    "AUDJPY",
    "CHFJPY",
    "EURCHF",
    "GBPCHF",
    "BTCUSD"  # Crypto soldier
]


def print_separator(char="━", length=70):
    """Print visual separator"""
    print(char * length)


def print_header():
    """Print audit header"""
    print("\n")
    print_separator()
    print("🎯 GLITCH IN MATRIX - SYSTEM AUDIT REPORT")
    print_separator()
    print(f"⏰ Audit Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📊 Official Pairs: {len(OFFICIAL_15)}")
    print_separator()
    print()


def print_footer():
    """Print official stamp"""
    print()
    print_separator("─", 14)
    print("✨ Glitch in Matrix by ФорексГод ✨")
    print("🧠 AI-Powered • 💎 Smart Money")
    print_separator("─", 14)
    print()


def load_monitoring_setups() -> Dict:
    """Load monitoring_setups.json"""
    monitoring_file = "monitoring_setups.json"
    
    if not os.path.exists(monitoring_file):
        print(f"❌ ERROR: {monitoring_file} not found!")
        return {"setups": []}
    
    try:
        with open(monitoring_file, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"❌ ERROR loading {monitoring_file}: {e}")
        return {"setups": []}


def get_setup_status(setup: Dict) -> str:
    """Determine setup status from JSON data"""
    status = setup.get("status", "UNKNOWN")
    pullback_status = setup.get("pullback_status", "")
    choch_1h = setup.get("choch_1h_detected", False)
    choch_4h = setup.get("choch_4h_detected", False)
    entry1_filled = setup.get("entry1_filled", False)
    
    # Detailed status logic
    if status == "EXPIRED":
        return "⏰ EXPIRED"
    elif status == "CLOSED":
        return "🔒 CLOSED"
    elif entry1_filled and pullback_status == "PULLBACK_REACHED":
        return "🎯 ENTRY FILLED"
    elif pullback_status == "PULLBACK_REACHED":
        return "✅ PULLBACK REACHED"
    elif pullback_status == "MOMENTUM_ENTRY":
        return "🚀 MOMENTUM ENTRY"
    elif choch_4h:
        return "⏳ WAITING PULLBACK (4H CHoCH ✅)"
    elif choch_1h:
        return "⏳ WAITING 4H CHOCH (1H CHoCH ✅)"
    elif status == "MONITORING":
        return "👀 MONITORING (Waiting CHoCH)"
    else:
        return f"❓ {status}"


def get_timeframe_confirmation(setup: Dict) -> str:
    """Get timeframe confirmation status"""
    choch_1h = setup.get("choch_1h_detected", False)
    choch_4h = setup.get("choch_4h_detected", False)
    
    confirmations = []
    if choch_1h:
        confirmations.append("1H✅")
    else:
        confirmations.append("1H⏳")
    
    if choch_4h:
        confirmations.append("4H✅")
    else:
        confirmations.append("4H⏳")
    
    return " | ".join(confirmations)


def get_risk_health(setup: Dict) -> str:
    """Check risk parameters health"""
    symbol = setup.get("symbol", "")
    entry_price = setup.get("entry_price")
    stop_loss = setup.get("stop_loss")
    take_profit = setup.get("take_profit")
    lot_size = setup.get("lot_size", 0)
    
    # Critical checks
    issues = []
    
    if not entry_price or entry_price == 0:
        issues.append("NO_ENTRY")
    
    if not stop_loss or stop_loss == 0:
        issues.append("NO_SL")
    
    if not take_profit or take_profit == 0:
        issues.append("NO_TP")
    
    if lot_size == 0:
        issues.append("ZERO_LOT")
    
    # Calculate distance for volume validation
    if entry_price and stop_loss:
        distance = abs(entry_price - stop_loss)
        
        # Crypto check
        if 'BTC' in symbol or 'ETH' in symbol:
            if distance < 100:  # BTC should have >$100 SL distance
                issues.append("SL_TOO_TIGHT")
        else:
            # Forex check (convert to pips)
            if 'JPY' in symbol:
                distance_pips = distance * 100
            else:
                distance_pips = distance * 10000
            
            if distance_pips < 10:
                issues.append("SL_TOO_TIGHT")
    
    if issues:
        return f"⚠️  {', '.join(issues)}"
    else:
        return "✅ HEALTHY"


def audit_monitoring_setups():
    """Main audit logic"""
    
    print_header()
    
    # Load monitoring data
    print("📂 LOADING: monitoring_setups.json...")
    data = load_monitoring_setups()
    setups = data.get("setups", [])
    
    print(f"✅ Found {len(setups)} total setup(s) in monitoring\n")
    
    # Track which pairs have setups
    monitored_pairs: Set[str] = set()
    unauthorized_pairs: List[str] = []
    setup_details: Dict[str, List[Dict]] = {}
    
    # Categorize setups
    for setup in setups:
        symbol = setup.get("symbol", "").upper()
        
        if symbol in OFFICIAL_15:
            monitored_pairs.add(symbol)
            if symbol not in setup_details:
                setup_details[symbol] = []
            setup_details[symbol].append(setup)
        else:
            unauthorized_pairs.append(symbol)
    
    # ──────────────────
    # SECTION 1: COVERAGE CHECK
    # ──────────────────
    
    print_separator("═")
    print("📊 SECTION 1: COVERAGE CHECK")
    print_separator("═")
    print()
    
    operational_count = len(monitored_pairs)
    idle_count = len(OFFICIAL_15) - operational_count
    
    print(f"🟢 OPERATIONAL: {operational_count}/{len(OFFICIAL_15)} pairs have active setups")
    print(f"⚪ IDLE: {idle_count}/{len(OFFICIAL_15)} pairs have no setups")
    
    if unauthorized_pairs:
        print(f"🔴 UNAUTHORIZED: {len(unauthorized_pairs)} unknown pair(s) detected")
    
    print()
    
    # List operational pairs
    if monitored_pairs:
        print("🟢 OPERATIONAL PAIRS:")
        for pair in sorted(monitored_pairs):
            count = len(setup_details[pair])
            print(f"   ✅ {pair} ({count} setup{'s' if count > 1 else ''})")
        print()
    
    # List idle pairs
    idle_pairs = set(OFFICIAL_15) - monitored_pairs
    if idle_pairs:
        print("⚪ IDLE PAIRS (No Active Setups):")
        for pair in sorted(idle_pairs):
            print(f"   ⚪ {pair}")
        print()
    
    # List unauthorized pairs
    if unauthorized_pairs:
        print("🔴 UNAUTHORIZED PAIRS (Not in Official 15):")
        for pair in sorted(set(unauthorized_pairs)):
            print(f"   ❌ {pair} - REMOVE FROM MONITORING!")
        print()
    
    # ──────────────────
    # SECTION 2: DETAILED SETUP HEALTH
    # ──────────────────
    
    if setup_details:
        print_separator("═")
        print("🔍 SECTION 2: DETAILED SETUP HEALTH")
        print_separator("═")
        print()
        
        for symbol in sorted(setup_details.keys()):
            setups_list = setup_details[symbol]
            
            for idx, setup in enumerate(setups_list, 1):
                direction = setup.get("direction", "").upper()
                entry_price = setup.get("entry_price", 0)
                stop_loss = setup.get("stop_loss", 0)
                take_profit = setup.get("take_profit", 0)
                lot_size = setup.get("lot_size", 0)
                risk_reward = setup.get("risk_reward", 0)
                
                # Direction emoji
                dir_emoji = "🔴" if direction == "SELL" else "🟢"
                
                print(f"{dir_emoji} {symbol} {direction} (Setup #{idx})")
                print(f"   Status: {get_setup_status(setup)}")
                print(f"   Timeframes: {get_timeframe_confirmation(setup)}")
                print(f"   Entry: {entry_price:,.5f} | SL: {stop_loss:,.5f} | TP: {take_profit:,.5f}")
                print(f"   Lot Size: {lot_size} | R:R: {risk_reward:.2f}")
                print(f"   Risk Health: {get_risk_health(setup)}")
                
                # Setup age
                setup_time = setup.get("setup_time", "")
                if setup_time:
                    try:
                        setup_dt = datetime.fromisoformat(setup_time)
                        age_hours = (datetime.now() - setup_dt).total_seconds() / 3600
                        print(f"   Age: {age_hours:.1f} hours")
                    except:
                        pass
                
                print()
    
    # ──────────────────
    # SECTION 3: RISK PARAMETER VALIDATION
    # ──────────────────
    
    print_separator("═")
    print("⚠️  SECTION 3: RISK PARAMETER VALIDATION")
    print_separator("═")
    print()
    
    risk_issues = []
    
    for symbol, setups_list in setup_details.items():
        for setup in setups_list:
            health = get_risk_health(setup)
            if "⚠️" in health:
                direction = setup.get("direction", "").upper()
                risk_issues.append(f"   ❌ {symbol} {direction}: {health}")
    
    if risk_issues:
        print("🔴 ISSUES DETECTED:")
        for issue in risk_issues:
            print(issue)
    else:
        print("✅ ALL SETUPS HAVE VALID RISK PARAMETERS")
    
    print()
    
    # ──────────────────
    # SECTION 4: FINAL SYSTEM STATUS
    # ──────────────────
    
    print_separator("═")
    print("📋 SECTION 4: FINAL SYSTEM STATUS")
    print_separator("═")
    print()
    
    # Calculate health metrics
    total_setups = len(setups)
    healthy_setups = sum(1 for s in setups if "⚠️" not in get_risk_health(s))
    unhealthy_setups = total_setups - healthy_setups
    
    # System status determination
    if operational_count == len(OFFICIAL_15):
        status_emoji = "🟢"
        status_text = "FULL OPERATIONAL"
    elif operational_count >= len(OFFICIAL_15) * 0.8:  # 80%+
        status_emoji = "🟡"
        status_text = "MOSTLY OPERATIONAL"
    elif operational_count >= len(OFFICIAL_15) * 0.5:  # 50%+
        status_emoji = "🟠"
        status_text = "PARTIAL OPERATIONAL"
    else:
        status_emoji = "🔴"
        status_text = "LOW COVERAGE"
    
    print(f"   {status_emoji} SYSTEM STATUS: [{operational_count}/{len(OFFICIAL_15)} OPERATIONAL]")
    print(f"   📊 Total Setups: {total_setups}")
    print(f"   ✅ Healthy Setups: {healthy_setups}")
    print(f"   ⚠️  Unhealthy Setups: {unhealthy_setups}")
    print(f"   ⚪ Idle Pairs: {idle_count}")
    print(f"   🔴 Unauthorized Pairs: {len(set(unauthorized_pairs))}")
    print()
    
    # Overall assessment
    print(f"   🎯 OVERALL ASSESSMENT: {status_text}")
    
    if risk_issues:
        print(f"   ⚠️  ACTION REQUIRED: Fix {len(risk_issues)} risk issue(s)")
    
    if unauthorized_pairs:
        print(f"   ⚠️  ACTION REQUIRED: Remove {len(set(unauthorized_pairs))} unauthorized pair(s)")
    
    if idle_count > 0:
        print(f"   💡 OPPORTUNITY: {idle_count} pair(s) available for new setups")
    
    print()
    
    # ──────────────────
    # SECTION 5: NEXT ACTIONS
    # ──────────────────
    
    print_separator("═")
    print("📋 SECTION 5: RECOMMENDED ACTIONS")
    print_separator("═")
    print()
    
    actions = []
    
    if unhealthy_setups > 0:
        actions.append("1. Fix risk parameters for unhealthy setups")
    
    if unauthorized_pairs:
        actions.append("2. Remove unauthorized pairs from monitoring_setups.json")
    
    if idle_count > len(OFFICIAL_15) * 0.5:
        actions.append("3. Run daily_scanner.py to find new setups for idle pairs")
    
    if operational_count == len(OFFICIAL_15) and unhealthy_setups == 0:
        actions.append("✅ System is optimal - monitor for execution signals")
    
    if actions:
        for action in actions:
            print(f"   {action}")
    else:
        print("   ✅ No immediate actions required")
    
    print()
    
    # Official stamp
    print_separator()
    print(f"📊 AUDIT COMPLETE: {status_text}")
    print_separator()
    
    print_footer()


def main():
    """Main entry point"""
    try:
        audit_monitoring_setups()
    except KeyboardInterrupt:
        print("\n\n⚠️  Audit interrupted by user")
        print_footer()
    except Exception as e:
        print(f"\n\n❌ ERROR during audit: {e}")
        import traceback
        traceback.print_exc()
        print_footer()


if __name__ == "__main__":
    main()
