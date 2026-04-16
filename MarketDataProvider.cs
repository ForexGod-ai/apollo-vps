using System;
using System.Net;
using System.Text;
using System.Threading;
using cAlgo.API;

namespace cAlgo.Robots
{
    /// <summary>
    /// MarketDataProvider — HTTP Server for OHLCV bar data
    /// Port: 8000 (default, configurable via Parameter)
    ///
    /// Endpoints:
    ///   GET /health
    ///   GET /symbols
    ///   GET /data?symbol=EURUSD&timeframe=Daily&bars=100
    ///   GET /historical/{symbol}/{timeframe}/{bars}
    ///   GET /price?symbol=EURUSD
    ///   GET /swap_info?symbol=EURUSD
    ///   GET /execute?symbol=EURUSD&direction=buy&volume=0.01&sl=0&tp=0
    ///
    /// by ФорексГод — Glitch in Matrix
    /// </summary>
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class MarketDataProvider : Robot
    {
        [Parameter("HTTP Port", DefaultValue = 8000)]
        public int HttpPort { get; set; }

        private HttpListener _listener;

        protected override void OnStart()
        {
            try
            {
                _listener = new HttpListener();
                _listener.Prefixes.Add($"http://localhost:{HttpPort}/");
                _listener.Start();

                Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                Print("📡 MarketDataProvider — Glitch in Matrix");
                Print($"✅ Server started on http://localhost:{HttpPort}/");
                Print("   /health  /symbols  /data  /historical  /price  /swap_info  /execute");
                Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

                _listener.BeginGetContext(HandleRequest, _listener);
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
                context = _listener.EndGetContext(result);
                var request  = context.Request;
                var response = context.Response;

                Print($"📥 {request.HttpMethod} {request.Url.PathAndQuery}");

                response.AddHeader("Access-Control-Allow-Origin", "*");

                if (request.HttpMethod == "OPTIONS")
                {
                    response.StatusCode = 200;
                    response.Close();
                    _listener.BeginGetContext(HandleRequest, _listener);
                    return;
                }

                var path = request.Url.AbsolutePath;

                // ── /health ──────────────────────────────────────────────────
                if (path == "/health")
                {
                    Send(response, 200, $"{{\"status\":\"ok\",\"port\":{HttpPort},\"bot\":\"MarketDataProvider\"}}");
                    _listener.BeginGetContext(HandleRequest, _listener);
                    return;
                }

                // ── /symbols ─────────────────────────────────────────────────
                if (path == "/symbols")
                {
                    string res = null;
                    BeginInvokeOnMainThread(() =>
                    {
                        try
                        {
                            string[] candidates = {
                                "EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD","USDCAD","NZDUSD",
                                "EURGBP","EURJPY","GBPJPY","AUDJPY","EURAUD","EURNZD","GBPAUD",
                                "GBPNZD","AUDNZD","AUDCAD","NZDCAD","EURCAD","GBPCAD","GBPCHF",
                                "XAUUSD","XAGUSD","BTCUSD","ETHUSD","WTIUSD"
                            };
                            var sb = new StringBuilder("{\"symbols\":[");
                            bool first = true;
                            foreach (var s in candidates)
                            {
                                try
                                {
                                    if (Symbols.GetSymbol(s) != null)
                                    {
                                        if (!first) sb.Append(",");
                                        sb.Append("\"").Append(s).Append("\"");
                                        first = false;
                                    }
                                }
                                catch { }
                            }
                            sb.Append("]}");
                            res = sb.ToString();
                        }
                        catch (Exception ex) { res = $"{{\"error\":\"{ex.Message}\"}}"; }
                    });
                    WaitFor(ref res, "{{\"error\":\"Timeout\"}}");
                    Send(response, 200, res);
                    _listener.BeginGetContext(HandleRequest, _listener);
                    return;
                }

                // ── /price ───────────────────────────────────────────────────
                if (path == "/price")
                {
                    string res = null;
                    var sym = GetParam(request.Url.Query, "symbol") ?? "EURUSD";
                    BeginInvokeOnMainThread(() =>
                    {
                        try
                        {
                            var s = Symbols.GetSymbol(sym);
                            if (s == null) { res = $"{{\"error\":\"Symbol not found: {sym}\"}}"; return; }
                            res = "{\"symbol\":\"" + sym + "\""
                                + ",\"bid\":"    + s.Bid.ToString(System.Globalization.CultureInfo.InvariantCulture)
                                + ",\"ask\":"    + s.Ask.ToString(System.Globalization.CultureInfo.InvariantCulture)
                                + ",\"spread\":" + s.Spread.ToString(System.Globalization.CultureInfo.InvariantCulture)
                                + ",\"time\":\"" + Server.Time.ToString("yyyy-MM-ddTHH:mm:ss") + "\"}";
                        }
                        catch (Exception ex) { res = $"{{\"error\":\"{ex.Message}\"}}"; }
                    });
                    WaitFor(ref res, "{\"error\":\"Timeout\"}");
                    Send(response, 200, res);
                    _listener.BeginGetContext(HandleRequest, _listener);
                    return;
                }

                // ── /swap_info ───────────────────────────────────────────────
                if (path == "/swap_info")
                {
                    string res = null;
                    var sym = GetParam(request.Url.Query, "symbol");
                    if (string.IsNullOrEmpty(sym))
                    {
                        Send(response, 400, "{\"error\":\"Missing symbol parameter\"}");
                        _listener.BeginGetContext(HandleRequest, _listener);
                        return;
                    }
                    BeginInvokeOnMainThread(() =>
                    {
                        try
                        {
                            var s = Symbols.GetSymbol(sym);
                            if (s == null) { res = $"{{\"success\":false,\"error\":\"Symbol not found: {sym}\"}}"; return; }
                            // Swap3DaysRollover is the correct cTrader API property
                            string tripleDay = s.Swap3DaysRollover.ToString();
                            res = "{\"success\":true"
                                + ",\"symbol\":\""       + sym + "\""
                                + ",\"swap_long\":"      + s.SwapLong.ToString(System.Globalization.CultureInfo.InvariantCulture)
                                + ",\"swap_short\":"     + s.SwapShort.ToString(System.Globalization.CultureInfo.InvariantCulture)
                                + ",\"swap_triple_day\":\"" + tripleDay + "\"}";
                        }
                        catch (Exception ex) { res = $"{{\"success\":false,\"error\":\"{ex.Message}\"}}"; }
                    });
                    WaitFor(ref res, "{\"success\":false,\"error\":\"Timeout\"}");
                    Send(response, 200, res);
                    _listener.BeginGetContext(HandleRequest, _listener);
                    return;
                }

                // ── /execute ─────────────────────────────────────────────────
                if (path == "/execute")
                {
                    string res = null;
                    BeginInvokeOnMainThread(() =>
                    {
                        try
                        {
                            var sym  = GetParam(request.Url.Query, "symbol");
                            var dir  = GetParam(request.Url.Query, "direction");
                            double vol = double.Parse(GetParam(request.Url.Query, "volume") ?? "0.01", System.Globalization.CultureInfo.InvariantCulture);
                            double sl  = double.Parse(GetParam(request.Url.Query, "sl")     ?? "0",    System.Globalization.CultureInfo.InvariantCulture);
                            double tp  = double.Parse(GetParam(request.Url.Query, "tp")     ?? "0",    System.Globalization.CultureInfo.InvariantCulture);

                            var s = Symbols.GetSymbol(sym);
                            if (s == null) { res = $"{{\"error\":\"Symbol not found: {sym}\"}}"; return; }

                            var tradeType = dir?.ToLower() == "buy" ? TradeType.Buy : TradeType.Sell;
                            var r = ExecuteMarketOrder(tradeType, s.Name, vol, "MarketDataProvider", sl, tp);
                            if (r.IsSuccessful)
                                res = "{\"success\":true,\"positionId\":" + r.Position.Id
                                    + ",\"entryPrice\":" + r.Position.EntryPrice.ToString(System.Globalization.CultureInfo.InvariantCulture) + "}";
                            else
                                res = $"{{\"error\":\"{r.Error}\"}}";
                        }
                        catch (Exception ex) { res = $"{{\"error\":\"{ex.Message}\"}}"; }
                    });
                    WaitFor(ref res, "{\"error\":\"Timeout\"}");
                    Send(response, 200, res);
                    _listener.BeginGetContext(HandleRequest, _listener);
                    return;
                }

                // ── /historical/{symbol}/{timeframe}/{bars} ──────────────────
                if (path.StartsWith("/historical/"))
                {
                    var parts = path.Split(new[] { '/' }, StringSplitOptions.RemoveEmptyEntries);
                    if (parts.Length >= 4)
                    {
                        var sym  = parts[1];
                        var tf   = parts[2];
                        int bars = int.Parse(parts[3]);
                        string res = null;
                        BeginInvokeOnMainThread(() => { res = FetchBars(sym, tf, bars); });
                        WaitFor(ref res, "{\"error\":\"Timeout\"}");
                        Send(response, res.Contains("\"error\"") ? 500 : 200, res);
                        _listener.BeginGetContext(HandleRequest, _listener);
                        return;
                    }
                }

                // ── /data?symbol=&timeframe=&bars= (default) ─────────────────
                {
                    var sym  = GetParam(request.Url.Query, "symbol")    ?? "GBPUSD";
                    var tf   = GetParam(request.Url.Query, "timeframe") ?? "Daily";
                    int bars = int.Parse(GetParam(request.Url.Query, "bars") ?? "100");
                    string res = null;
                    BeginInvokeOnMainThread(() => { res = FetchBars(sym, tf, bars); });
                    WaitFor(ref res, "{\"error\":\"Timeout\"}");
                    Send(response, res.Contains("\"error\"") ? 500 : 200, res);
                }
            }
            catch (Exception ex)
            {
                Print($"❌ HandleRequest error: {ex.Message}");
                try { context?.Response.Close(); } catch { }
            }

            try { _listener.BeginGetContext(HandleRequest, _listener); }
            catch (Exception ex) { Print($"❌ BeginGetContext error: {ex.Message}"); }
        }

        // ── Helpers ──────────────────────────────────────────────────────────

        private string FetchBars(string symbolName, string timeframeStr, int barsCount)
        {
            try
            {
                var s = Symbols.GetSymbol(symbolName);
                if (s == null) return $"{{\"error\":\"Symbol not found: {symbolName}\"}}";

                var series = MarketData.GetBars(ParseTimeFrame(timeframeStr), s.Name);
                if (series == null || series.Count == 0)
                    return $"{{\"error\":\"No data for {symbolName} {timeframeStr}\"}}";

                int count = Math.Min(barsCount, series.Count);
                int start = series.Count - count;

                var sb = new StringBuilder();
                sb.Append("{\"symbol\":\"").Append(symbolName).Append("\",");
                sb.Append("\"timeframe\":\"").Append(timeframeStr).Append("\",");
                sb.Append("\"bars\":[");

                for (int i = start; i < series.Count; i++)
                {
                    var bar = series[i];
                    if (i > start) sb.Append(",");
                    sb.Append("{\"time\":\"").Append(bar.OpenTime.ToString("yyyy-MM-dd HH:mm:ss")).Append("\"")
                      .Append(",\"open\":")   .Append(bar.Open.ToString(System.Globalization.CultureInfo.InvariantCulture))
                      .Append(",\"high\":")   .Append(bar.High.ToString(System.Globalization.CultureInfo.InvariantCulture))
                      .Append(",\"low\":")    .Append(bar.Low.ToString(System.Globalization.CultureInfo.InvariantCulture))
                      .Append(",\"close\":")  .Append(bar.Close.ToString(System.Globalization.CultureInfo.InvariantCulture))
                      .Append(",\"volume\":") .Append(bar.TickVolume)
                      .Append("}");
                }
                sb.Append("]}");
                return sb.ToString();
            }
            catch (Exception ex)
            {
                return $"{{\"error\":\"{ex.Message}\"}}";
            }
        }

        private void Send(HttpListenerResponse response, int statusCode, string body)
        {
            try
            {
                var bytes = Encoding.UTF8.GetBytes(body);
                response.ContentType = "application/json; charset=utf-8";
                response.ContentLength64 = bytes.Length;
                response.StatusCode = statusCode;
                response.OutputStream.Write(bytes, 0, bytes.Length);
                response.Close();
            }
            catch { }
        }

        private void WaitFor(ref string result, string timeoutValue, int maxMs = 1000)
        {
            int waited = 0;
            while (result == null && waited < maxMs)
            {
                Thread.Sleep(20);
                waited += 20;
            }
            if (result == null) result = timeoutValue;
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
                case "M1":  case "MINUTE":   return TimeFrame.Minute;
                case "M5":  case "MINUTE5":  return TimeFrame.Minute5;
                case "M15": case "MINUTE15": return TimeFrame.Minute15;
                case "M30": case "MINUTE30": return TimeFrame.Minute30;
                case "H1":  case "HOUR":     return TimeFrame.Hour;
                case "H4":  case "HOUR4":    return TimeFrame.Hour4;
                case "D1":  case "DAILY": case "D": return TimeFrame.Daily;
                case "W1":  case "WEEKLY":   return TimeFrame.Weekly;
                default:                     return TimeFrame.Daily;
            }
        }

        protected override void OnStop()
        {
            try { _listener?.Stop(); } catch { }
            Print("🛑 MarketDataProvider stopped.");
        }
    }
}
