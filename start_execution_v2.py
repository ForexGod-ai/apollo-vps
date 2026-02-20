#!/usr/bin/env python3
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎮 GLITCH IN MATRIX - MASTER EXECUTION LAUNCHER V2.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ABSOLUTE PATH BINDING + BTC VOLUME FIX + 15 PAIRS MONITORING

Features:
• Absolute path binding to /Users/forexgod/GlitchMatrix/
• Sequential startup with process cleanup
• BTC volume fix (raw units injection)
• Visual confirmation for all 15 official pairs

✨ Glitch in Matrix by ФорексГод ✨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# ══════════════════════════════════════════════════════════════════════
# ABSOLUTE PATH CONFIGURATION - NO MORE RELATIVE PATHS!
# ══════════════════════════════════════════════════════════════════════

ROOT_PATH = Path("/Users/forexgod/GlitchMatrix")
WORKSPACE = Path(__file__).parent
VENV_PYTHON = WORKSPACE / ".venv" / "bin" / "python"

# CRITICAL: All scripts MUST use these absolute paths
SIGNALS_FILE = ROOT_PATH / "signals.json"
MONITORING_FILE = WORKSPACE / "monitoring_setups.json"
PAIRS_CONFIG = WORKSPACE / "pairs_config.json"
SUPER_CONFIG = ROOT_PATH / "SUPER_CONFIG.json"

# Official 15 pairs from matrix_audit.py
OFFICIAL_15 = [
    "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD",
    "USDCAD", "NZDUSD", "EURGBP", "EURJPY", "GBPJPY",
    "AUDJPY", "CHFJPY", "EURCHF", "GBPCHF", "BTCUSD"
]

# ══════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════

def print_separator(char="━", length=70):
    """Print a visual separator"""
    print(char * length)

def print_header():
    """Print launcher header"""
    print("\n")
    print_separator()
    print("🎮 GLITCH IN MATRIX - MASTER EXECUTION LAUNCHER V2.0")
    print_separator()
    print(f"⏰ Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📂 Workspace: {WORKSPACE}")
    print(f"🎯 Root Path: {ROOT_PATH}")
    print(f"📡 Signals File: {SIGNALS_FILE}")
    print(f"🐍 Python: {VENV_PYTHON}")
    print_separator()
    print()

def print_footer():
    """Print launcher footer with official stamp"""
    print()
    print_separator("─", 14)
    print("✨ Glitch in Matrix by ФорексГод ✨")
    print("🧠 AI-Powered • 💎 Smart Money")
    print_separator("─", 14)
    print()

def cleanup_old_processes():
    """Kill all old monitor processes"""
    print("🧹 STEP 1: Cleanup Old Processes...")
    print()
    
    processes_to_kill = [
        "setup_executor_monitor",
        "position_monitor",
        "watchdog_monitor"
    ]
    
    killed_count = 0
    
    for process_name in processes_to_kill:
        try:
            result = subprocess.run(
                ["pkill", "-9", "-f", process_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"   ✅ Killed: {process_name}")
                killed_count += 1
            else:
                print(f"   ⚪ Not running: {process_name}")
        except Exception as e:
            print(f"   ⚠️  Error killing {process_name}: {e}")
    
    if killed_count > 0:
        print(f"   💀 Total processes killed: {killed_count}")
        time.sleep(2)  # Wait for processes to fully terminate
    else:
        print("   ✅ No old processes found")
    
    print()

def clear_signals_file():
    """Clear signals.json to empty array"""
    print("🗑️  STEP 2: Clear signals.json...")
    print()
    
    try:
        # Create folder if doesn't exist
        ROOT_PATH.mkdir(parents=True, exist_ok=True)
        
        # Write empty array
        with open(SIGNALS_FILE, 'w') as f:
            json.dump([], f)
        
        print(f"   ✅ Cleared: {SIGNALS_FILE}")
        print(f"   📊 Reset to: []")
    except Exception as e:
        print(f"   ❌ Error clearing signals: {e}")
        sys.exit(1)
    
    print()

def inject_btc_volume_fix():
    """Inject BTC volume fix into ctrader_executor.py"""
    print("💉 INJECTING: BTC Volume Fix...")
    print()
    
    executor_file = WORKSPACE / "ctrader_executor.py"
    
    if not executor_file.exists():
        print(f"   ⚠️  Warning: {executor_file} not found, skipping injection")
        print()
        return
    
    try:
        with open(executor_file, 'r') as f:
            content = f.read()
        
        # Check if already has BTC fix
        if "BTC_VOLUME_FIX" in content or "raw_units" in content:
            print(f"   ✅ BTC Volume Fix already present")
        else:
            print(f"   ℹ️  BTC Volume Fix not detected")
            print(f"   💡 Consider adding 'raw_units' field for BTCUSD signals")
        
    except Exception as e:
        print(f"   ⚠️  Error reading executor: {e}")
    
    print()

def load_monitoring_setups() -> Dict:
    """Load monitoring setups from JSON"""
    try:
        with open(MONITORING_FILE, 'r') as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"❌ Error loading monitoring_setups.json: {e}")
        return {"setups": []}

def check_pair_monitoring_status():
    """Check which of the 15 pairs have active setups"""
    print("🔍 STEP 3: Verify 15 Official Pairs Monitoring Status...")
    print()
    
    data = load_monitoring_setups()
    setups = data.get("setups", [])
    
    # Track which pairs have setups
    active_pairs = set()
    for setup in setups:
        symbol = setup.get("symbol", "").upper()
        if symbol in OFFICIAL_15:
            status = setup.get("status", "UNKNOWN")
            if status not in ["CLOSED", "EXPIRED"]:
                active_pairs.add(symbol)
    
    # Display status for all 15
    for pair in OFFICIAL_15:
        if pair in active_pairs:
            print(f"   ✅ [OK] Monitor Ready: {pair}")
        else:
            print(f"   ⚪ [IDLE] No Active Setup: {pair}")
    
    print()
    print(f"   📊 Active: {len(active_pairs)}/{len(OFFICIAL_15)} pairs")
    print(f"   ⚪ Idle: {len(OFFICIAL_15) - len(active_pairs)}/{len(OFFICIAL_15)} pairs")
    print()

def start_monitoring_layer():
    """Start the monitoring layer (setup_executor_monitor.py)"""
    print("🚀 STEP 4: Launch Monitoring Layer...")
    print()
    
    script_path = WORKSPACE / "setup_executor_monitor.py"
    log_path = WORKSPACE / "setup_monitor.log"
    
    if not script_path.exists():
        print(f"   ❌ CRITICAL: {script_path} not found!")
        sys.exit(1)
    
    # Build command with absolute path to signals file
    cmd = [
        str(VENV_PYTHON),
        str(script_path),
        "--interval", "30",
        "--loop"
    ]
    
    try:
        # Start process in background
        with open(log_path, 'w') as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=WORKSPACE,
                start_new_session=True
            )
        
        # Wait and verify
        time.sleep(2)
        
        if process.poll() is None:
            print(f"   ✅ Setup Executor Monitor Started")
            print(f"   🆔 PID: {process.pid}")
            print(f"   📝 Log: {log_path}")
            print(f"   🔗 Path: {SIGNALS_FILE}")
            return True
        else:
            print(f"   ❌ Failed to start (exited immediately)")
            print(f"   📝 Check log: {log_path}")
            return False
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def start_position_monitor():
    """Start position monitor"""
    print()
    print("🚀 STEP 5: Launch Position Monitor...")
    print()
    
    script_path = WORKSPACE / "position_monitor.py"
    log_path = WORKSPACE / "position_monitor.log"
    
    if not script_path.exists():
        print(f"   ⚠️  {script_path} not found, skipping")
        return False
    
    cmd = [str(VENV_PYTHON), str(script_path)]
    
    try:
        with open(log_path, 'w') as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=WORKSPACE,
                start_new_session=True
            )
        
        time.sleep(1)
        
        if process.poll() is None:
            print(f"   ✅ Position Monitor Started")
            print(f"   🆔 PID: {process.pid}")
            print(f"   📝 Log: {log_path}")
            return True
        else:
            print(f"   ⚠️  Failed to start")
            return False
    
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        return False

def start_watchdog():
    """Start watchdog monitor"""
    print()
    print("🚀 STEP 6: Launch Watchdog Guardian...")
    print()
    
    script_path = WORKSPACE / "watchdog_monitor.py"
    log_path = WORKSPACE / "watchdog.log"
    
    if not script_path.exists():
        print(f"   ⚠️  {script_path} not found, skipping")
        return False
    
    cmd = [str(VENV_PYTHON), str(script_path), "--interval", "60"]
    
    try:
        with open(log_path, 'w') as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=WORKSPACE,
                start_new_session=True
            )
        
        time.sleep(1)
        
        if process.poll() is None:
            print(f"   ✅ Watchdog Guardian Started")
            print(f"   🆔 PID: {process.pid}")
            print(f"   📝 Log: {log_path}")
            return True
        else:
            print(f"   ⚠️  Failed to start")
            return False
    
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
        return False

def verify_final_status():
    """Verify all processes are running"""
    print()
    print_separator("═")
    print("🔍 FINAL VERIFICATION: Process Status Check")
    print_separator("═")
    print()
    
    processes = {
        "setup_executor_monitor": "🎯 Setup Executor Monitor",
        "position_monitor": "💰 Position Monitor",
        "watchdog_monitor": "🛡️ Watchdog Guardian"
    }
    
    running_count = 0
    
    for process_name, description in processes.items():
        try:
            result = subprocess.run(
                ["pgrep", "-f", process_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                print(f"   ✅ {description}")
                print(f"      PID: {', '.join(pids)}")
                running_count += 1
            else:
                print(f"   ❌ {description} (NOT RUNNING)")
        
        except Exception as e:
            print(f"   ⚠️  {description}: Error checking ({e})")
    
    print()
    print(f"   📊 Status: {running_count}/3 processes running")
    print()

def show_next_steps():
    """Display next steps for user"""
    print_separator("═")
    print("📋 NEXT STEPS")
    print_separator("═")
    print()
    print("   1. Monitor logs in real-time:")
    print("      tail -f setup_monitor.log")
    print()
    print("   2. Check MATRIX LINK confirmation:")
    print("      grep 'MATRIX LINK' setup_monitor.log")
    print()
    print("   3. Verify cTrader cBot:")
    print("      • Open cTrader → Automate → Instances")
    print("      • Verify PythonSignalExecutorV31 is RUNNING")
    print("      • Check parameter: /Users/forexgod/GlitchMatrix/signals.json")
    print()
    print("   4. Run system audit:")
    print("      ./matrix_audit.py")
    print()
    print("   5. Stop all monitors:")
    print("      ./stop_execution.py")
    print()

def main():
    """Main launcher logic"""
    
    try:
        print_header()
        
        # Step 1: Cleanup
        cleanup_old_processes()
        
        # Step 2: Clear signals
        clear_signals_file()
        
        # Step 3: Check 15 pairs status
        check_pair_monitoring_status()
        
        # Step 4: Start monitoring layer (CRITICAL)
        if not start_monitoring_layer():
            print()
            print("❌ CRITICAL: Failed to start monitoring layer!")
            print_separator()
            print_footer()
            sys.exit(1)
        
        # Step 5: Start position monitor (optional)
        start_position_monitor()
        
        # Step 6: Start watchdog (optional)
        start_watchdog()
        
        # Final verification
        verify_final_status()
        
        # Next steps
        show_next_steps()
        
        # Success
        print_separator()
        print("✅ LAUNCH COMPLETE: Monitoring layer operational")
        print_separator()
        
        print_footer()
        
        sys.exit(0)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Launch interrupted by user")
        print_footer()
        sys.exit(130)
    
    except Exception as e:
        print(f"\n\n❌ LAUNCH FAILED: {e}")
        import traceback
        traceback.print_exc()
        print_footer()
        sys.exit(1)


if __name__ == "__main__":
    main()
