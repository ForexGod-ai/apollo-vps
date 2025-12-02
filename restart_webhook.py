"""
Restart helper - oprește procesul pe port 5001 și repornește webhook_server
"""
import os
import subprocess
import time

print("\n🔄 RESTART WEBHOOK SERVER")
print("="*60)

# Find and kill process on port 5001
print("\n1. Stopping old server...")
try:
    result = subprocess.run(
        ['powershell', '-Command', 
         "(Get-NetTCPConnection -LocalPort 5001 -ErrorAction SilentlyContinue).OwningProcess | Get-Unique | ForEach-Object { Stop-Process -Id $_ -Force }"],
        capture_output=True,
        text=True
    )
    print("✅ Old server stopped")
    time.sleep(2)
except Exception as e:
    print(f"⚠️ Could not stop old server: {e}")

# Start new server
print("\n2. Starting webhook server...")
print("   Server will run in this terminal...")
print("   Press Ctrl+C to stop\n")
print("="*60)

os.system("python webhook_server.py")
