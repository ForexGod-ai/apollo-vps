"""
Test single cTrader API call with full debug output
"""

import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Get credentials
account_id = os.getenv('CTRADER_ACCOUNT_ID')
access_token = os.getenv('CTRADER_ACCESS_TOKEN')
demo = True

# API URL
base_url = "https://demo-openapi.ctrader.com" if demo else "https://openapi.ctrader.com"

logger.info("=" * 80)
logger.info("🧪 TESTING SINGLE CTRADER API CALL")
logger.info("=" * 80)
logger.info(f"Account ID: {account_id}")
logger.info(f"Token: {access_token[:20]}...{access_token[-10:]}")
logger.info(f"API Base: {base_url}")

# Test 1: Account info
logger.info("\n" + "=" * 80)
logger.info("TEST 1: Account Info")
logger.info("=" * 80)

url = f"{base_url}/v3/accounts/{account_id}"
headers = {
    'Authorization': f'Bearer {access_token}',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
}

logger.info(f"URL: {url}")
logger.info(f"Headers: {headers}")

response = requests.get(url, headers=headers, timeout=10)

logger.info(f"Status Code: {response.status_code}")
logger.info(f"Response Headers: {dict(response.headers)}")
logger.info(f"Response Body: {response.text}")

# Test 2: Trendbars for GBPUSD
logger.info("\n" + "=" * 80)
logger.info("TEST 2: Trendbars (GBPUSD)")
logger.info("=" * 80)

end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
start_time = end_time - (5 * 86400000)  # 5 days ago

url = f"{base_url}/v3/accounts/{account_id}/trendbars"
params = {
    'symbolName': 'GBPUSD',
    'periodicity': 'D1',
    'from': start_time,
    'to': end_time,
    'count': 5
}

logger.info(f"URL: {url}")
logger.info(f"Params: {params}")
logger.info(f"Headers: {headers}")

response = requests.get(url, headers=headers, params=params, timeout=10)

logger.info(f"Status Code: {response.status_code}")
logger.info(f"Response Headers: {dict(response.headers)}")
logger.info(f"Response Body: {response.text}")

# Test 3: Try with different symbol format
logger.info("\n" + "=" * 80)
logger.info("TEST 3: Alternative Endpoints")
logger.info("=" * 80)

# Try different endpoint patterns
test_urls = [
    f"{base_url}/v3/trendbars",
    f"{base_url}/v2/trendbars",
    f"{base_url}/trendbars",
    f"{base_url}/v3/symbols",
]

for test_url in test_urls:
    logger.info(f"\nTrying: {test_url}")
    try:
        response = requests.get(test_url, headers=headers, params={'symbolName': 'GBPUSD'}, timeout=5)
        logger.info(f"  Status: {response.status_code}")
        if response.status_code != 404:
            logger.info(f"  Body: {response.text[:200]}")
    except Exception as e:
        logger.error(f"  Error: {e}")

logger.info("\n" + "=" * 80)
logger.info("✅ Test Complete")
logger.info("=" * 80)
