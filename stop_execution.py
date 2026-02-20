#!/usr/bin/env python3
"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛑 GLITCH IN MATRIX - MASTER EXECUTION STOPPER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Gracefully stops all execution and monitoring components.

✨ Glitch in Matrix by ФорексГод ✨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import subprocess
import time
from datetime import datetime

def print_separator(char="━", length=70):
    """Print a visual separator"""
    print(char * length)

def print_header():
    """Print stopper header"""
    print("\n")
    print_separator()
    print("🛑 GLITCH IN MATRIX - MASTER EXECUTION STOPPER")
    print_separator()
    print(f"⏰ Stop Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_separator()
    print()

def print_footer():
    """Print footer with official stamp"""
    print()
    print_separator("─", 14)
    print("✨ Glitch in Matrix by ФорексГод ✨")
    print("🧠 AI-Powered • 💎 Smart Money")
    print_separator("─", 14)
    print()

def stop_processes():
    """Stop all monitoring processes"""
    print("🛑 STOPPING: Terminating all execution components...")
    print()
    
    processes_to_stop = {
        "setup_executor_monitor": "🎯 Setup Executor Monitor",
        "position_monitor": "💰 Position Monitor",
        "watchdog_monitor": "🛡️ Watchdog Guardian"
    }
    
    stopped_count = 0
    
    for process_name, description in processes_to_stop.items():
        try:
            # Try graceful termination first (SIGTERM)
            result = subprocess.run(
                ["pkill", "-f", process_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"   ✅ Stopped: {description}")
                stopped_count += 1
            else:
                print(f"   ⚪ Not running: {description}")
        
        except Exception as e:
            print(f"   ⚠️  Error stopping {description}: {e}")
    
    # Wait for graceful shutdown
    if stopped_count > 0:
        print()
        print("   ⏳ Waiting for graceful shutdown (2s)...")
        time.sleep(2)
        
        # Force kill any remaining processes
        print("   🔨 Force killing any remaining processes...")
        for process_name in processes_to_stop.keys():
            subprocess.run(
                ["pkill", "-9", "-f", process_name],
                capture_output=True,
                text=True
            )
    
    print()
    print(f"   💀 Total components stopped: {stopped_count}")
    print()

def verify_stopped():
    """Verify all processes are stopped"""
    print("🔍 VERIFICATION: Checking process status...")
    print()
    
    processes_to_check = [
        "setup_executor_monitor",
        "position_monitor",
        "watchdog_monitor"
    ]
    
    still_running = []
    
    for process_name in processes_to_check:
        try:
            result = subprocess.run(
                ["pgrep", "-f", process_name],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pids = result.stdout.strip().split('\n')
                print(f"   ⚠️  Still running: {process_name} (PID: {', '.join(pids)})")
                still_running.append(process_name)
            else:
                print(f"   ✅ Stopped: {process_name}")
        
        except Exception as e:
            print(f"   ⚠️  Error checking {process_name}: {e}")
    
    print()
    
    if still_running:
        print(f"   ⚠️  {len(still_running)} processes still running")
        print(f"   💡 Use: pkill -9 -f 'monitor' to force kill")
    else:
        print(f"   ✅ All processes stopped successfully")
    
    print()

def main():
    """Main stopper logic"""
    
    try:
        print_header()
        stop_processes()
        verify_stopped()
        
        print_separator()
        print("✅ STOP COMPLETE: All execution components terminated")
        print_separator()
        
        print_footer()
    
    except KeyboardInterrupt:
        print("\n\n⚠️  Stop interrupted by user")
        print_footer()
    
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        print_footer()


if __name__ == "__main__":
    main()
