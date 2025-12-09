#!/usr/bin/env python3
"""
ForexGod Dashboard - Public Tunnel (NO installation needed)
Makes local dashboard PUBLIC using serveo.net SSH tunnel
"""

import subprocess
import time
import signal
import sys

def create_public_tunnel():
    """Create public SSH tunnel using serveo.net"""
    print("=" * 60)
    print("🌍 ForexGod Dashboard - Creating PUBLIC Tunnel")
    print("=" * 60)
    print("📡 Using serveo.net SSH tunnel (FREE)")
    print("🔒 No registration required")
    print("⏱️  Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    try:
        # Create SSH tunnel using serveo.net
        cmd = ["ssh", "-R", "80:localhost:8080", "serveo.net"]
        
        print("🚀 Creating public tunnel...")
        print("⏳ Connecting to serveo.net...\n")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Read output and display URL
        for line in process.stdout:
            print(line.strip())
            if "Forwarding HTTP" in line or "https://" in line:
                print("\n" + "=" * 60)
                print("✅ DASHBOARD PUBLIC LIVE!")
                print("=" * 60)
        
        process.wait()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Tunnel closed")
        print("✅ Dashboard still available locally: http://localhost:8080")
        process.terminate()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Alternative: Try localhost.run")
        print("   ssh -R 80:localhost:8080 localhost.run")

if __name__ == "__main__":
    create_public_tunnel()
