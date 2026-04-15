#!/usr/bin/env python3
"""
──────────────────
🎮 GLITCH IN MATRIX - MASTER EXECUTION LAUNCHER V2.0
──────────────────

ABSOLUTE PATH BINDING + BTC VOLUME FIX + 15 PAIRS MONITORING

Features:
• Absolute path binding to /Users/forexgod/GlitchMatrix/
• Sequential startup with process cleanup
• BTC volume fix (raw units injection)
• Visual confirmation for all 15 official pairs

✨ Glitch in Matrix by ФорексГод ✨
──────────────────
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

# Cross-platform: works on Mac, Linux, Windows VPS
ROOT_PATH = Path(__file__).parent
WORKSPACE = ROOT_PATH

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
    """Kill old monitoring processes"""
    print("🧹 CLEANUP: Stopping old processes...")
    
    processes_to_kill = [
        "setup_executor_monitor",
        "position_monitor",
        "watchdog_monitor"
    ]
    
    killed_count = 0
    for process_name in processes_to_kill:
        try:
            # Use pkill to find and kill processes by name
            result = subprocess.run(
                ["pkill", "-9", "-f", process_name],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                print(f"   ✅ Stopped: {process_name}")
                killed_count += 1
            else:
                print(f"   ⚪ Not running: {process_name}")
        except Exception as e:
            print(f"   ⚠️  Error stopping {process_name}: {e}")
    
    if killed_count > 0:
        print(f"   💀 Total processes stopped: {killed_count}")
        time.sleep(2)  # Wait for processes to fully terminate
    else:
        print("   ✅ No old processes found")
    
    print()

def clear_signals_file():
    """Clear signals.json to prevent phantom executions"""
    print("🗑️  CLEANUP: Clearing signals.json...")
    
    signals_file = GLITCH_MATRIX_FOLDER / "signals.json"
    
    try:
        # Create folder if doesn't exist
        GLITCH_MATRIX_FOLDER.mkdir(parents=True, exist_ok=True)
        
        # Write empty object (cBot expects object, not array)
        with open(signals_file, 'w') as f:
            json.dump({}, f)
        
        print(f"   ✅ Cleared: {signals_file}")
        print(f"   📊 Reset to: {{}}")
    except Exception as e:
        print(f"   ⚠️  Error clearing signals: {e}")
    
    print()

def verify_files():
    """Verify required files exist"""
    print("📋 VERIFICATION: Checking required files...")
    
    all_ok = True
    
    for filename in REQUIRED_FILES:
        filepath = WORKSPACE / filename
        if filepath.exists():
            # Try to load and validate JSON
            try:
                with open(filepath, 'r') as f:
                    data = json.load(f)
                
                # For monitoring_setups.json, show setup count
                if filename == "monitoring_setups.json":
                    if isinstance(data, dict) and 'setups' in data:
                        setup_count = len(data['setups'])
                    elif isinstance(data, list):
                        setup_count = len(data)
                    else:
                        setup_count = 0
                    
                    print(f"   ✅ {filename} ({setup_count} active setups)")
                else:
                    print(f"   ✅ {filename}")
            
            except json.JSONDecodeError:
                print(f"   ⚠️  {filename} (Invalid JSON)")
                all_ok = False
        else:
            print(f"   ❌ {filename} (NOT FOUND)")
            all_ok = False
    
    print()
    
    if not all_ok:
        print("❌ Missing required files! Cannot proceed.")
        sys.exit(1)
    
    return True

def check_venv():
    """Verify virtual environment exists"""
    if not VENV_PYTHON.exists():
        print(f"❌ Virtual environment not found: {VENV_PYTHON}")
        print(f"   Please run: python -m venv .venv")
        sys.exit(1)

def start_component(name: str, config: Dict) -> bool:
    """Start a single component in background"""
    
    script_path = WORKSPACE / config["script"]
    log_path = WORKSPACE / config["log"]
    
    # Verify script exists
    if not script_path.exists():
        print(f"   ❌ Script not found: {script_path}")
        if config["critical"]:
            print(f"   🔴 CRITICAL COMPONENT MISSING - Aborting")
            sys.exit(1)
        return False
    
    # Build command
    cmd = [str(VENV_PYTHON), str(script_path)] + config["args"]
    
    try:
        # Start process in background, redirect output to log
        with open(log_path, 'w') as log_file:
            process = subprocess.Popen(
                cmd,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                cwd=WORKSPACE,
                start_new_session=True  # Detach from parent
            )
        
        # Wait briefly to check if process started successfully
        time.sleep(0.5)
        
        # Check if process is still running
        if process.poll() is None:
            print(f"   ✅ Started: PID {process.pid}")
            print(f"   📝 Log: {log_path.name}")
            
            # Wait configured time before next component
            if config["wait"] > 0:
                print(f"   ⏳ Waiting {config['wait']}s for initialization...")
                time.sleep(config["wait"])
            
            return True
        else:
            print(f"   ❌ Failed to start (exited immediately)")
            print(f"   📝 Check log: {log_path}")
            
            if config["critical"]:
                print(f"   🔴 CRITICAL COMPONENT FAILED - Aborting")
                sys.exit(1)
            
            return False
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
        
        if config["critical"]:
            print(f"   🔴 CRITICAL COMPONENT FAILED - Aborting")
            sys.exit(1)
        
        return False

def launch_all_components():
    """Launch all components in order"""
    print("🚀 LAUNCH SEQUENCE: Starting components...")
    print()
    
    success_count = 0
    
    for name, config in COMPONENTS.items():
        print(f"▶️  {config['description']}")
        
        if start_component(name, config):
            success_count += 1
        
        print()
    
    return success_count

def verify_processes_running():
    """Verify launched processes are still running"""
    print("🔍 POST-LAUNCH VERIFICATION: Checking process status...")
    print()
    
    for name, config in COMPONENTS.items():
        script_name = config["script"].replace(".py", "")
        
        try:
            result = subprocess.run(
                ["pgrep", "-f", script_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                print(f"   ✅ {config['description']}")
                print(f"      PID: {', '.join(pids)}")
            else:
                print(f"   ❌ {config['description']}")
                print(f"      Process not found!")
        except Exception as e:
            print(f"   ⚠️  {config['description']}: {e}")
    
    print()

def show_monitoring_status():
    """Show active setups being monitored"""
    print("📊 ACTIVE MONITORING STATUS:")
    print()
    
    monitoring_file = WORKSPACE / "monitoring_setups.json"
    
    try:
        with open(monitoring_file, 'r') as f:
            data = json.load(f)
        
        if isinstance(data, dict) and 'setups' in data:
            setups = data['setups']
        elif isinstance(data, list):
            setups = data
        else:
            setups = []
        
        if not setups:
            print("   ⚠️  No active setups found in monitoring_setups.json")
            print("   💡 Run daily_scanner.py first to find setups")
        else:
            print(f"   🎯 {len(setups)} active setups:")
            print()
            
            for i, setup in enumerate(setups, 1):
                symbol = setup.get('symbol', 'UNKNOWN')
                direction = setup.get('direction', 'unknown').upper()
                status = setup.get('status', 'UNKNOWN')
                entry = setup.get('entry_price', 0)
                
                dir_emoji = "🔴" if direction == "SELL" else "🟢"
                
                print(f"   {i}. {dir_emoji} {symbol} {direction}")
                print(f"      Status: {status} | Entry: {entry:.5f}")
            
            print()
            print(f"   💡 Monitor will check every 30s for execution conditions")
    
    except Exception as e:
        print(f"   ⚠️  Could not read monitoring file: {e}")
    
    print()

def show_next_steps():
    """Show what user should do next"""
    print("📋 NEXT STEPS:")
    print()
    print("   1. Monitor logs in real-time:")
    print("      tail -f setup_monitor.log")
    print()
    print("   2. Check cTrader cBot status:")
    print("      • Open cTrader → Automate → Instances")
    print("      • Verify PythonSignalExecutorV31 is RUNNING")
    print("      • Check cBot log for 'MATRIX LINK' messages")
    print()
    print("   3. Monitor active positions:")
    print("      tail -f position_monitor.log")
    print()
    print("   4. Stop all components:")
    print("      pkill -f 'setup_executor_monitor|position_monitor|watchdog'")
    print()

# ══════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ══════════════════════════════════════════════════════════════════════

def main():
    """Main launcher logic"""
    
    try:
        # Header
        print_header()
        
        # Step 1: Cleanup
        cleanup_old_processes()
        clear_signals_file()
        
        # Step 2: Verification
        check_venv()
        verify_files()
        
        # Step 3: Launch components
        success_count = launch_all_components()
        
        # Step 4: Verify processes
        verify_processes_running()
        
        # Step 5: Show monitoring status
        show_monitoring_status()
        
        # Step 6: Next steps
        show_next_steps()
        
        # Final status
        print_separator()
        total_components = len(COMPONENTS)
        if success_count == total_components:
            print(f"✅ LAUNCH SUCCESS: {success_count}/{total_components} components running")
        elif success_count > 0:
            print(f"⚠️  PARTIAL SUCCESS: {success_count}/{total_components} components running")
        else:
            print(f"❌ LAUNCH FAILED: 0/{total_components} components running")
        print_separator()
        
        # Official stamp
        print_footer()
        
        # Success exit
        if success_count > 0:
            sys.exit(0)
        else:
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Launch interrupted by user")
        print_footer()
        sys.exit(130)
    
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        print_footer()
        sys.exit(1)


if __name__ == "__main__":
    main()
