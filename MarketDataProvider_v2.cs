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
            try
            {
                listener = new HttpListener();
                listener.Prefixes.Add("http://localhost:8767/");
                listener.Start();
                
                Print("✅ Server started on http://localhost:8767/");
                
                listener.BeginGetContext(HandleRequest, listener);
            }
            catch (Exception ex)
            {
                Print($"❌ Start error: {ex.Message}");
            }
        }
        
        private void HandleRequest(IAsyncResult result)
        {
            HttpListenerContext context = null;
            
            try
            {
                context = listener.EndGetContext(result);
                var request = context.Request;
                var response = context.Response;
                
                Print($"📥 Request: {request.Url.PathAndQuery}");
                
                // CORS
                response.AddHeader("Access-Control-Allow-Origin", "*");
                
                if (request.HttpMethod == "OPTIONS")
                {
                    response.StatusCode = 200;
                    response.Close();
                    listener.BeginGetContext(HandleRequest, listener);
                    return;
                }
                
                // Health check
                if (request.Url.AbsolutePath == "/health")
                {
                    byte[] buffer = Encoding.UTF8.GetBytes("{\"status\":\"ok\"}");
                    response.ContentType = "application/json";
                    response.ContentLength64 = buffer.Length;
                    response.OutputStream.Write(buffer, 0, buffer.Length);
                    response.Close();
                    listener.BeginGetContext(HandleRequest, listener);
                    return;
                }
                
                // List all available symbols
                if (request.Url.AbsolutePath == "/symbols")
                {
                    string symbolList = null;
                    
                    BeginInvokeOnMainThread(() =>
                    {
                        try
                        {
                            var json = new StringBuilder();
                            json.Append("{\"symbols\":[");
                            
                            // Get symbols from account (available pairs)
                            bool first = true;
                            
                            // Try to get all symbols that have market data
                            string[] commonSymbols = {
                                "EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD",
                                "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "EURAUD", "EURNZD", "GBPAUD",
                                "GBPNZD", "AUDNZD", "AUDCAD", "NZDCAD", "EURCAD", "GBPCAD", "GBPCHF",
                                "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD",
                                "USOIL", "WTI", "BRENT", "UK OIL", "US OIL"
                            };
                            
                            foreach (var symbolName in commonSymbols)
                            {
                                try
                                {
                                    var symbol = Symbols.GetSymbol(symbolName);
                                    if (symbol != null)
                                    {
                                        if (!first) json.Append(",");
                                        json.Append("\"").Append(symbolName).Append("\"");
                                        first = false;
                                    }
                                }
                                catch { }
                            }
                            
                            json.Append("]}");
                            symbolList = json.ToString();
                        }
                        catch (Exception ex)
                        {
                            symbolList = "{\"error\":\"" + ex.Message + "\"}";
                        }
                    });
                    
                    // Wait for result
                    int waitCount = 0;
                    while (symbolList == null && waitCount < 50)
                    {
                        System.Threading.Thread.Sleep(20);
                        waitCount++;
                    }
                    
                    if (symbolList != null)
                    {
                        byte[] buffer = Encoding.UTF8.GetBytes(symbolList);
                        response.ContentType = "application/json";
                        response.ContentLength64 = buffer.Length;
                        response.OutputStream.Write(buffer, 0, buffer.Length);
                        response.Close();
                    }
                    
                    listener.BeginGetContext(HandleRequest, listener);
                    return;
                }
                
                // Execute trade
                if (request.Url.AbsolutePath == "/execute")
                {
                    string executeResult = null;
                    
                    BeginInvokeOnMainThread(() =>
                    {
                        try
                        {
                            var symbol = GetParam(request.Url.Query, "symbol");
                            var direction = GetParam(request.Url.Query, "direction"); // "buy" or "sell"
                            var volume = double.Parse(GetParam(request.Url.Query, "volume") ?? "0.01");
                            var sl = double.Parse(GetParam(request.Url.Query, "sl") ?? "0");
                            var tp = double.Parse(GetParam(request.Url.Query, "tp") ?? "0");
                            
                            var symbolObj = Symbols.GetSymbol(symbol);
                            if (symbolObj == null)
                            {
                                executeResult = "{\"error\":\"Symbol not found\"}";
                                return;
                            }
                            
                            var tradeType = direction.ToLower() == "buy" ? TradeType.Buy : TradeType.Sell;
                            var result = ExecuteMarketOrder(tradeType, symbolObj.Name, volume, "ForexGod", sl, tp);
                            
                            if (result.IsSuccessful)
                            {
                                executeResult = "{\"success\":true,\"positionId\":" + result.Position.Id + ",\"entryPrice\":" + result.Position.EntryPrice.ToString(System.Globalization.CultureInfo.InvariantCulture) + "}";
                            }
                            else
                            {
                                executeResult = "{\"error\":\"" + result.Error + "\"}";
                            }
                        }
                        catch (Exception ex)
                        {
                            executeResult = "{\"error\":\"" + ex.Message + "\"}";
                        }
                    });
                    
                    // Wait for execution
                    int waitCount2 = 0;
                    while (executeResult == null && waitCount2 < 50)
                    {
                        System.Threading.Thread.Sleep(20);
                        waitCount2++;
                    }
                    
                    if (executeResult != null)
                    {
                        byte[] buffer = Encoding.UTF8.GetBytes(executeResult);
                        response.ContentType = "application/json";
                        response.ContentLength64 = buffer.Length;
                        response.OutputStream.Write(buffer, 0, buffer.Length);
                        response.Close();
                    }
                    
                    listener.BeginGetContext(HandleRequest, listener);
                    return;
                }
                
                // Get trade history from TradeHistorySyncer2 JSON file
                if (request.Url.AbsolutePath == "/history")
                {
                    try
                    {
                        string jsonPath = "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/trade_history.json";
                        
                        if (System.IO.File.Exists(jsonPath))
                        {
                            string jsonContent = System.IO.File.ReadAllText(jsonPath);
                            byte[] buffer = Encoding.UTF8.GetBytes(jsonContent);
                            response.ContentType = "application/json";
                            response.ContentLength64 = buffer.Length;
                            response.OutputStream.Write(buffer, 0, buffer.Length);
                            response.Close();
                        }
                        else
                        {
                            byte[] buffer = Encoding.UTF8.GetBytes("{\"error\":\"Trade history file not found\"}");
                            response.StatusCode = 404;
                            response.ContentType = "application/json";
                            response.ContentLength64 = buffer.Length;
                            response.OutputStream.Write(buffer, 0, buffer.Length);
                            response.Close();
                        }
                    }
                    catch (Exception ex)
                    {
                        Print($"❌ Error reading trade history: {ex.Message}");
                        byte[] buffer = Encoding.UTF8.GetBytes("{\"error\":\"" + ex.Message + "\"}");
                        response.StatusCode = 500;
                        response.ContentType = "application/json";
                        response.ContentLength64 = buffer.Length;
                        response.OutputStream.Write(buffer, 0, buffer.Length);
                        response.Close();
                    }
                    
                    listener.BeginGetContext(HandleRequest, listener);
                    return;
                }
                
                // Handle /historical/{symbol}/{timeframe}/{bars} path format
                if (request.Url.AbsolutePath.StartsWith("/historical/"))
                {
                    var pathParts = request.Url.AbsolutePath.Split(new[] { '/' }, StringSplitOptions.RemoveEmptyEntries);
                    if (pathParts.Length >= 4)
                    {
                        var pathSymbol = pathParts[1];  // /historical/GBPJPY/D1/100 -> GBPJPY
                        var pathTimeframe = pathParts[2];  // D1
                        var pathBars = int.Parse(pathParts[3] ?? "100");  // 100
                        
                        Print($"📊 PATH FORMAT: Getting {pathBars} {pathTimeframe} bars for {pathSymbol}");
                        
                        // Process on main thread
                        string pathJsonResult = null;
                        Exception pathError = null;
                        
                        BeginInvokeOnMainThread(() =>
                        {
                            try
                            {
                                var symbolObj = Symbols.GetSymbol(pathSymbol);
                                if (symbolObj == null)
                                {
                                    pathError = new Exception($"Symbol {pathSymbol} not found");
                                    return;
                                }
                                
                                var tf = ParseTimeFrame(pathTimeframe);
                                var series = MarketData.GetBars(tf, symbolObj.Name);
                                
                                if (series == null || series.Count == 0)
                                {
                                    pathError = new Exception("No data");
                                    return;
                                }
                                
                                var json = new StringBuilder();
                                json.Append("{\"symbol\":\"").Append(pathSymbol).Append("\",\"bars\":[");
                                
                                int count = Math.Min(pathBars, series.Count);
                                int start = series.Count - count;
                                
                                for (int i = start; i < series.Count; i++)
                                {
                                    var bar = series[i];
                                    if (i > start) json.Append(",");
                                    
                                    json.Append("{\"time\":\"")
                                        .Append(bar.OpenTime.ToString("yyyy-MM-dd HH:mm:ss"))
                                        .Append("\",\"open\":").Append(bar.Open.ToString(System.Globalization.CultureInfo.InvariantCulture))
                                        .Append(",\"high\":").Append(bar.High.ToString(System.Globalization.CultureInfo.InvariantCulture))
                                        .Append(",\"low\":").Append(bar.Low.ToString(System.Globalization.CultureInfo.InvariantCulture))
                                        .Append(",\"close\":").Append(bar.Close.ToString(System.Globalization.CultureInfo.InvariantCulture))
                                        .Append(",\"volume\":").Append(bar.TickVolume)
                                        .Append("}");
                                }
                                
                                json.Append("]}");
                                pathJsonResult = json.ToString();
                            }
                            catch (Exception ex)
                            {
                                pathError = ex;
                            }
                        });
                        
                        // Wait for completion
                        int waitCount3 = 0;
                        while (pathJsonResult == null && pathError == null && waitCount3 < 50)
                        {
                            System.Threading.Thread.Sleep(20);
                            waitCount3++;
                        }
                        
                        if (pathError != null)
                        {
                            Print($"❌ Error: {pathError.Message}");
                            byte[] errorBuf = Encoding.UTF8.GetBytes($"{{\"error\":\"{pathError.Message}\"}}");
                            response.StatusCode = 500;
                            response.ContentType = "application/json";
                            response.ContentLength64 = errorBuf.Length;
                            response.OutputStream.Write(errorBuf, 0, errorBuf.Length);
                        }
                        else if (pathJsonResult != null)
                        {
                            byte[] buffer = Encoding.UTF8.GetBytes(pathJsonResult);
                            response.ContentType = "application/json";
                            response.ContentLength64 = buffer.Length;
                            response.OutputStream.Write(buffer, 0, buffer.Length);
                        }
                        
                        response.Close();
                        listener.BeginGetContext(HandleRequest, listener);
                        return;
                    }
                }
                
                // Get data (legacy query param format)
                var query = request.Url.Query;
                var symbol = GetParam(query, "symbol") ?? "GBPUSD";
                var timeframe = GetParam(query, "timeframe") ?? "Daily";
                var bars = int.Parse(GetParam(query, "bars") ?? "100");
                
                Print($"📊 Getting {bars} {timeframe} bars for {symbol}");
                
                // Must run on main thread
                string jsonResult = null;
                Exception error = null;
                
                BeginInvokeOnMainThread(() =>
                {
                    try
                    {
                        // Get symbol object first
                        var symbolObj = Symbols.GetSymbol(symbol);
                        if (symbolObj == null)
                        {
                            error = new Exception($"Symbol {symbol} not found");
                            return;
                        }
                        
                        var tf = ParseTimeFrame(timeframe);
                        var series = MarketData.GetBars(tf, symbolObj.Name);
                        
                        if (series == null || series.Count == 0)
                        {
                            error = new Exception("No data");
                            return;
                        }
                        
                        var json = new StringBuilder();
                        json.Append("{\"symbol\":\"").Append(symbol).Append("\",\"bars\":[");
                        
                        int count = Math.Min(bars, series.Count);
                        int start = series.Count - count;
                        
                        for (int i = start; i < series.Count; i++)
                        {
                            var bar = series[i];
                            if (i > start) json.Append(",");
                            
                            json.Append("{\"time\":\"")
                                .Append(bar.OpenTime.ToString("yyyy-MM-dd HH:mm:ss"))
                                .Append("\",\"open\":").Append(bar.Open.ToString(System.Globalization.CultureInfo.InvariantCulture))
                                .Append(",\"high\":").Append(bar.High.ToString(System.Globalization.CultureInfo.InvariantCulture))
                                .Append(",\"low\":").Append(bar.Low.ToString(System.Globalization.CultureInfo.InvariantCulture))
                                .Append(",\"close\":").Append(bar.Close.ToString(System.Globalization.CultureInfo.InvariantCulture))
                                .Append(",\"volume\":").Append(bar.TickVolume)
                                .Append("}");
                        }
                        
                        json.Append("]}");
                        jsonResult = json.ToString();
                    }
                    catch (Exception ex)
                    {
                        error = ex;
                    }
                });
                
                // Wait for main thread (increase timeout)
                int maxWait = 50; // 50 * 20ms = 1 second
                int waited = 0;
                while (jsonResult == null && error == null && waited < maxWait)
                {
                    System.Threading.Thread.Sleep(20);
                    waited++;
                }
                
                if (error != null)
                {
                    Print($"❌ Error: {error.Message}");
                    response.StatusCode = 500;
                    byte[] errorBuffer = Encoding.UTF8.GetBytes($"{{\"error\":\"{error.Message}\"}}");
                    response.OutputStream.Write(errorBuffer, 0, errorBuffer.Length);
                    response.Close();
                    listener.BeginGetContext(HandleRequest, listener);
                    return;
                }
                
                if (jsonResult == null)
                {
                    Print("❌ No data returned");
                    response.StatusCode = 500;
                    response.Close();
                    listener.BeginGetContext(HandleRequest, listener);
                    return;
                }
                
                byte[] data = Encoding.UTF8.GetBytes(jsonResult);
                response.ContentType = "application/json";
                response.ContentLength64 = data.Length;
                response.OutputStream.Write(data, 0, data.Length);
                response.Close();
                
                Print($"✅ Sent data");
            }
            catch (Exception ex)
            {
                Print($"❌ Error: {ex.Message}");
                try
                {
                    if (context != null)
                    {
                        context.Response.StatusCode = 500;
                        context.Response.Close();
                    }
                }
                catch { }
            }
            
            try
            {
                listener.BeginGetContext(HandleRequest, listener);
            }
            catch (Exception ex)
            {
                Print($"❌ BeginGetContext error: {ex.Message}");
            }
        }
        
        private string GetParam(string query, string param)
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
            try
            {
                listener?.Stop();
                Print("🛑 Server stopped");
            }
            catch { }
        }
    }
}
