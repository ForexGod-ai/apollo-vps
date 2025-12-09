#!/usr/bin/env python3
"""
ForexGod Dashboard - Auto Deploy to GitHub Pages
Runs 24/7 and syncs trade_history.json to cloud every 30 seconds
Works even when laptop is closed (needs to run on VPS/server)
"""

import json
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# Configuration
REPO_PATH = Path("/Users/forexgod/Desktop/trading-ai-agent apollo")
TRADE_HISTORY = REPO_PATH / "trade_history.json"
DASHBOARD_HTML = REPO_PATH / "dashboard_live.html"
GH_PAGES_BRANCH = "gh-pages"
SYNC_INTERVAL = 30  # seconds

def setup_gh_pages():
    """Setup GitHub Pages branch if it doesn't exist"""
    print("🔧 Setting up GitHub Pages branch...")
    
    try:
        # Check if gh-pages branch exists
        result = subprocess.run(
            ["git", "rev-parse", "--verify", GH_PAGES_BRANCH],
            cwd=REPO_PATH,
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            # Create orphan branch for gh-pages
            subprocess.run(["git", "checkout", "--orphan", GH_PAGES_BRANCH], cwd=REPO_PATH, check=True)
            subprocess.run(["git", "rm", "-rf", "."], cwd=REPO_PATH, check=True)
            
            # Create initial commit
            with open(REPO_PATH / "index.html", "w") as f:
                f.write("<h1>ForexGod Dashboard - Coming Soon</h1>")
            
            subprocess.run(["git", "add", "index.html"], cwd=REPO_PATH, check=True)
            subprocess.run(["git", "commit", "-m", "Initial gh-pages"], cwd=REPO_PATH, check=True)
            subprocess.run(["git", "push", "origin", GH_PAGES_BRANCH], cwd=REPO_PATH, check=True)
            subprocess.run(["git", "checkout", "main"], cwd=REPO_PATH, check=True)
            
            print("✅ GitHub Pages branch created!")
        else:
            print("✅ GitHub Pages branch already exists")
            
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Error setting up gh-pages: {e}")
        return False
    
    return True

def deploy_to_gh_pages():
    """Deploy dashboard to GitHub Pages"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Switch to gh-pages branch
        subprocess.run(["git", "checkout", GH_PAGES_BRANCH], cwd=REPO_PATH, check=True, capture_output=True)
        
        # Copy files
        shutil.copy(DASHBOARD_HTML, REPO_PATH / "index.html")
        shutil.copy(TRADE_HISTORY, REPO_PATH / "trade_history.json")
        
        # Git add and commit
        subprocess.run(["git", "add", "index.html", "trade_history.json"], cwd=REPO_PATH, check=True)
        
        result = subprocess.run(
            ["git", "commit", "-m", f"Update dashboard - {timestamp}"],
            cwd=REPO_PATH,
            capture_output=True,
            text=True
        )
        
        if "nothing to commit" in result.stdout:
            print(f"⏭️  [{timestamp}] No changes to deploy")
        else:
            # Push to GitHub
            subprocess.run(["git", "push", "origin", GH_PAGES_BRANCH], cwd=REPO_PATH, check=True)
            print(f"✅ [{timestamp}] Dashboard deployed to GitHub Pages!")
        
        # Switch back to main
        subprocess.run(["git", "checkout", "main"], cwd=REPO_PATH, check=True, capture_output=True)
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ [{timestamp}] Deploy failed: {e}")
        # Try to switch back to main
        subprocess.run(["git", "checkout", "main"], cwd=REPO_PATH, capture_output=True)
        return False

def main():
    """Main deployment loop"""
    print("=" * 60)
    print("🚀 ForexGod Dashboard - Auto Deploy to GitHub Pages")
    print("=" * 60)
    print(f"📁 Repository: {REPO_PATH}")
    print(f"📊 Trade History: {TRADE_HISTORY}")
    print(f"🌐 Dashboard: {DASHBOARD_HTML}")
    print(f"⏱️  Sync Interval: {SYNC_INTERVAL} seconds")
    print("=" * 60)
    
    # Check if files exist
    if not TRADE_HISTORY.exists():
        print(f"❌ Error: {TRADE_HISTORY} not found!")
        return
    
    if not DASHBOARD_HTML.exists():
        print(f"❌ Error: {DASHBOARD_HTML} not found!")
        return
    
    # Setup gh-pages branch
    if not setup_gh_pages():
        print("❌ Failed to setup GitHub Pages. Please check your git configuration.")
        return
    
    print("\n🎯 Starting continuous deployment...")
    print("💡 Dashboard will be live at: https://YOUR_USERNAME.github.io/YOUR_REPO/")
    print("🔄 Press Ctrl+C to stop\n")
    
    deploy_count = 0
    
    try:
        while True:
            deploy_count += 1
            print(f"\n🔄 Deploy #{deploy_count}")
            
            if deploy_to_gh_pages():
                print(f"⏳ Waiting {SYNC_INTERVAL} seconds until next sync...")
            else:
                print(f"⚠️  Deploy failed, retrying in {SYNC_INTERVAL} seconds...")
            
            time.sleep(SYNC_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\n⏹️  Deployment stopped by user")
        print(f"📊 Total deployments: {deploy_count}")
        print("✅ Dashboard remains live on GitHub Pages!")

if __name__ == "__main__":
    main()
