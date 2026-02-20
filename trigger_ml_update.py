#!/usr/bin/env python3
"""
🧠 AUTO-LEARNING TRIGGER
──────────────────
✨ Glitch in Matrix by ФорексГод ✨
🧠 AI-Powered • 💎 Smart Money

Triggers ML optimizer after every closed trade
System learns NON-STOP from experience
──────────────────
"""

import subprocess
import sys
from pathlib import Path
from datetime import datetime
import json


def trigger_ml_update():
    """Run strategy optimizer to update learned rules"""
    print("\n" + "━" * 60)
    print("🧠 AUTO-LEARNING TRIGGERED")
    print("━" * 60)
    print(f"⏰ Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("📚 Updating AI knowledge base...")
    print("━" * 60 + "\n")
    
    try:
        # Run strategy optimizer
        result = subprocess.run(
            [sys.executable, "strategy_optimizer.py"],
            capture_output=True,
            text=True,
            timeout=120  # 2 minute timeout
        )
        
        if result.returncode == 0:
            print("✅ ML OPTIMIZER COMPLETED")
            print("\n📊 Output:")
            print(result.stdout)
            
            # Update last learning timestamp
            timestamp_file = Path("last_ml_update.json")
            timestamp_file.write_text(json.dumps({
                "last_update": datetime.now().isoformat(),
                "status": "success"
            }, indent=2))
            
            return True
        else:
            print("❌ ML OPTIMIZER FAILED")
            print(f"\nError:\n{result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ ML optimizer timeout (>2 minutes)")
        return False
    except Exception as e:
        print(f"❌ Error triggering ML update: {e}")
        return False


if __name__ == "__main__":
    success = trigger_ml_update()
    sys.exit(0 if success else 1)
