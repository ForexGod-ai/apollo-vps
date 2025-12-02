"""
⏰ MORNING SCAN SCHEDULER - 09:00 Daily
Rulează complete_scan_with_charts.py automat în fiecare zi la 09:00
"""

import schedule
import time
import subprocess
import os
from datetime import datetime
from loguru import logger

SCAN_SCRIPT = "complete_scan_with_charts.py"
SCAN_TIME = "09:00"

def run_morning_scan():
    """Rulează scanarea dimineții"""
    logger.info("=" * 80)
    logger.info(f"⏰ MORNING SCAN TRIGGERED - {datetime.now().strftime('%d %B %Y %H:%M:%S')}")
    logger.info("=" * 80)
    
    try:
        # Rulează scanarea
        result = subprocess.run(
            ["python", SCAN_SCRIPT],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✅ Morning scan completed successfully!")
        else:
            logger.error(f"❌ Scan failed with error:\n{result.stderr}")
    
    except Exception as e:
        logger.error(f"❌ Error running scan: {e}")

def main():
    logger.info("\n" + "=" * 80)
    logger.info("🌅 MORNING SCAN SCHEDULER - GLITCH IN MATRIX")
    logger.info("=" * 80)
    logger.info(f"📅 Scheduled time: {SCAN_TIME} daily")
    logger.info(f"📊 Script: {SCAN_SCRIPT}")
    logger.info(f"⏰ Current time: {datetime.now().strftime('%H:%M:%S')}")
    logger.info("=" * 80)
    logger.info("\n🔄 Scheduler running... Press Ctrl+C to stop\n")
    
    # Setează programarea
    schedule.every().day.at(SCAN_TIME).do(run_morning_scan)
    
    # Test imediat la pornire (opțional - comentează dacă nu vrei)
    # logger.info("🧪 Running initial test scan...")
    # run_morning_scan()
    
    # Loop principal
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    except KeyboardInterrupt:
        logger.info("\n\n⏹️ Scheduler stopped by user")
        logger.info("=" * 80)

if __name__ == "__main__":
    main()
