#!/usr/bin/env python3
"""
Quick test - Official OpenApiPy with single pair
"""
from loguru import logger
from ctrader_data_client import get_ctrader_client
import time

logger.info("🧪 Testing Official OpenApiPy with GBPUSD...")

client = get_ctrader_client()

# Test GBPUSD
df = client.get_historical_data('GBPUSD', 'D1', 100)

if df is not None and not df.empty:
    logger.success(f"✅ GBPUSD: {len(df)} candles")
    logger.info(f"📊 Latest: {df.tail(1).to_dict('records')[0]}")
    logger.success("\n🎯 OFFICIAL OpenApiPy WORKING! Ready for all 21 pairs!")
else:
    logger.error("❌ GBPUSD failed")

client.disconnect()
