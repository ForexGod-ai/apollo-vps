# cTrader Open API Setup Guide

## 🎯 Overview
This guide explains how to get **LIVE real-time data** from IC Markets broker using cTrader Open API instead of delayed Yahoo Finance data.

## 📋 Prerequisites
- IC Markets account (demo or live)
- cTrader account linked to IC Markets

## 🔑 Step 1: Get API Credentials

### Option A: Using Access Token (Recommended - Easiest)

1. Go to **cTrader Open API Portal**: https://connect.spotware.com/
2. Login with your cTrader account
3. Navigate to: **My Apps** → **Create New App**
4. Fill in:
   - **App Name**: "Trading AI Bot"
   - **Redirect URI**: `http://localhost:5000/callback` (not needed for server apps)
   - **Permissions**: Select "Read account data" + "Read market data"
5. Click **Create**
6. Copy the generated **Access Token** (long string starting with "eyJ...")
7. Add to `.env` file:
   ```bash
   CTRADER_ACCESS_TOKEN=eyJhbGc...your_token_here
   ```

### Option B: Using OAuth2 Credentials (Advanced)

1. In the same app page, find:
   - **Client ID** (looks like: `123456_abc...`)
   - **Client Secret** (long string)
2. Add to `.env`:
   ```bash
   CTRADER_CLIENT_ID=123456_abc...
   CTRADER_CLIENT_SECRET=your_secret_here
   ```

## ⚙️ Step 2: Configure Environment

Edit `.env` file:

```bash
# IC Markets Account Info
CTRADER_ACCOUNT_ID=9709773          # Your account number
CTRADER_SERVER=demo.icmarkets.com   # or live.icmarkets.com
CTRADER_DEMO=True                    # False for live account

# API Credentials (from Step 1)
CTRADER_ACCESS_TOKEN=eyJhbGc...     # OR use Client ID/Secret:
CTRADER_CLIENT_ID=123456_abc...
CTRADER_CLIENT_SECRET=your_secret...
```

## 🧪 Step 3: Test Connection

Run test script:

```bash
python ctrader_data_client.py
```

Expected output:
```
🔗 cTrader LIVE Data Client initialized
   Account: 9709773
   Mode: DEMO
   Endpoint: https://demo.icmarkets.com
📊 Fetching LIVE data: GBPUSD D1 (100 bars)...
✅ Got 100 LIVE candles from IC Markets
```

## 📊 Step 4: Verify in Morning Scan

Run morning scan:

```bash
python morning_strategy_scan.py
```

Watch for:
- ✅ `Got X LIVE candles from IC Markets` = **SUCCESS** (real broker data)
- ⚠️ `falling back to yfinance` = **FALLBACK** (still using delayed data)

## 🔧 Troubleshooting

### Issue: "No access token available"
**Solution**: Make sure `CTRADER_ACCESS_TOKEN` is set in `.env` file

### Issue: "API returned status 401"
**Solution**: Token expired or invalid - regenerate from cTrader portal

### Issue: "API returned status 404"
**Solution**: Symbol not available on IC Markets - check symbol name mapping in `ctrader_data_client.py`

### Issue: Still showing "fallback to yfinance"
**Solution**: 
1. Check `.env` has correct credentials
2. Verify IC Markets account is active
3. Check internet connection to IC Markets servers
4. View logs for specific error message

## 🎯 Benefits of Real cTrader Data

| Feature | Yahoo Finance (Old) | cTrader API (New) |
|---------|-------------------|-------------------|
| **Latency** | 15-20 minutes delay | Real-time (< 1 sec) |
| **Accuracy** | Approximate prices | Exact broker prices |
| **Availability** | Limited symbols | All IC Markets pairs |
| **Reliability** | Rate limits, outages | Direct broker feed |
| **Silver (XAGUSD)** | ❌ Not available | ✅ Available |
| **Pi (PIUSDT)** | ❌ Not available | ✅ Available |

## 📝 API Endpoints Used

```python
# Historical OHLC Data
GET https://demo.icmarkets.com/v1/ohlc
Parameters:
  - symbolName: GBPUSD
  - timeframe: D1, H4, H1, M15
  - from: timestamp_ms
  - to: timestamp_ms
  - count: number of bars

Response:
{
  "data": [
    {
      "timestamp": 1701648000000,
      "open": 1.2650,
      "high": 1.2680,
      "low": 1.2640,
      "close": 1.2670,
      "volume": 15000
    },
    ...
  ]
}
```

## 🚀 Next Steps

Once cTrader API is working:
1. ✅ Real-time morning scans with accurate prices
2. ✅ Enable XAGUSD and PIUSDT trading
3. ✅ Reduce false signals from delayed data
4. ✅ Better entry/exit timing (real broker prices)

## 📞 Support

If issues persist:
- Check IC Markets account status: https://secure.icmarkets.com/
- cTrader API docs: https://help.ctrader.com/open-api/
- Contact IC Markets support about API access
