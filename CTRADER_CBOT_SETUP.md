# cTrader cBot Data Provider Setup

## Soluție: cBot care trimite market data prin HTTP

Deoarece ProtoOA API necesită account ID valid pe care nu-l avem, vom folosi **cTrader Automate** (cBots) care rulează direct în aplicația ta cTrader desktop.

### Pasul 1: Creează cBot în cTrader

1. Deschide **cTrader Desktop**
2. Click pe **Automate** tab
3. Click pe **New** → **cBot**
4. Nume: `MarketDataProvider`
5. Copiază codul de mai jos:

```csharp
using System;
using System.Net;
using System.Text;
using cAlgo.API;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class MarketDataProvider : Robot
    {
        private HttpListener listener;
        
        protected override void OnStart()
        {
            // Start HTTP server on port 8765
            listener = new HttpListener();
            listener.Prefixes.Add("http://localhost:8765/");
            listener.Start();
            
            Print("✅ Market Data Provider started on http://localhost:8765/");
            
            // Handle requests in background
            listener.BeginGetContext(HandleRequest, listener);
        }
        
        private void HandleRequest(IAsyncResult result)
        {
            try
            {
                var context = listener.EndGetContext(result);
                var request = context.Request;
                var response = context.Response;
                
                // CORS headers
                response.AddHeader("Access-Control-Allow-Origin", "*");
                response.AddHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
                
                if (request.HttpMethod == "OPTIONS")
                {
                    response.StatusCode = 200;
                    response.Close();
                    listener.BeginGetContext(HandleRequest, listener);
                    return;
                }
                
                // Parse request: /data?symbol=GBPUSD&timeframe=Daily&bars=100
                var query = request.Url.Query;
                var symbol = GetQueryParam(query, "symbol");
                var timeframe = GetQueryParam(query, "timeframe");
                var bars = int.Parse(GetQueryParam(query, "bars") ?? "100");
                
                // Get market data
                var symbolData = MarketData.GetSymbol(symbol);
                var series = MarketData.GetBars(ParseTimeFrame(timeframe), symbol);
                
                // Build JSON response
                var json = new StringBuilder();
                json.Append("{\"symbol\":\"" + symbol + "\",\"bars\":[");
                
                int count = Math.Min(bars, series.Count);
                for (int i = series.Count - count; i < series.Count; i++)
                {
                    var bar = series[i];
                    if (i > series.Count - count) json.Append(",");
                    
                    json.AppendFormat("{{\"time\":\"{0}\",\"open\":{1},\"high\":{2},\"low\":{3},\"close\":{4},\"volume\":{5}}}",
                        bar.OpenTime.ToString("yyyy-MM-dd HH:mm:ss"),
                        bar.Open,
                        bar.High,
                        bar.Low,
                        bar.Close,
                        bar.TickVolume);
                }
                
                json.Append("]}");
                
                // Send response
                byte[] buffer = Encoding.UTF8.GetBytes(json.ToString());
                response.ContentType = "application/json";
                response.ContentLength64 = buffer.Length;
                response.OutputStream.Write(buffer, 0, buffer.Length);
                response.Close();
                
                Print($"✅ Served {count} bars for {symbol}");
            }
            catch (Exception ex)
            {
                Print($"❌ Error: {ex.Message}");
            }
            
            // Continue listening
            listener.BeginGetContext(HandleRequest, listener);
        }
        
        private string GetQueryParam(string query, string param)
        {
            foreach (var part in query.TrimStart('?').Split('&'))
            {
                var kv = part.Split('=');
                if (kv.Length == 2 && kv[0] == param)
                    return Uri.UnescapeDataString(kv[1]);
            }
            return null;
        }
        
        private TimeFrame ParseTimeFrame(string tf)
        {
            switch (tf?.ToUpper())
            {
                case "M1": case "MINUTE": return TimeFrame.Minute;
                case "M5": case "MINUTE5": return TimeFrame.Minute5;
                case "M15": case "MINUTE15": return TimeFrame.Minute15;
                case "H1": case "HOUR": return TimeFrame.Hour;
                case "H4": case "HOUR4": return TimeFrame.Hour4;
                case "D1": case "DAILY": case "D": return TimeFrame.Daily;
                default: return TimeFrame.Daily;
            }
        }
        
        protected override void OnStop()
        {
            listener?.Stop();
            Print("🛑 Market Data Provider stopped");
        }
    }
}
```

### Pasul 2: Build & Start cBot

1. Click **Build** în cTrader Automate
2. Mergi la **Automate** tab în cTrader
3. Găsește `MarketDataProvider` în listă
4. Click **Start** (pe orice simbol/timeframe - nu contează)
5. Verifică în **Log** că vezi: `✅ Market Data Provider started on http://localhost:8765/`

### Pasul 3: Testează din Python

```python
import requests

url = "http://localhost:8765/data"
params = {
    "symbol": "GBPUSD",
    "timeframe": "Daily",
    "bars": 100
}

response = requests.get(url, params=params)
data = response.json()

print(f"✅ Got {len(data['bars'])} bars")
print(f"Latest close: {data['bars'][-1]['close']}")
```

### Pasul 4: Integrare în sistemul nostru

Vom crea un nou client Python care se conectează la acest cBot în loc de ProtoOA.

## Avantaje
- ✅ Nu mai trebuie account ID sau token-uri OAuth
- ✅ Data direct de la IC Markets prin cTrader
- ✅ Funcționează pe macOS
- ✅ Real-time access la toate simbolurile tale

## Dezavantaje
- ⚠️ cTrader trebuie să fie deschis și conectat
- ⚠️ cBot trebuie să ruleze continuu
