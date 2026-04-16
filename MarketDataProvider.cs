using System;
using System.Net;
using System.Text;
using System.Threading;
using System.Globalization;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    /// <summary>
    /// MarketDataProvider — HTTP Server for OHLCV bar data
    /// Port: 8000 (default)
    ///
    /// Endpoints:
    ///   GET /health                                          → {"status":"ok"}
    ///   GET /data?symbol=EURUSD&timeframe=Daily&bars=100     → {"symbol":..., "bars":[...]}
    ///   GET /price?symbol=EURUSD                            → {"symbol":..., "bid":..., "ask":...}
    ///   GET /swap_info?symbol=EURUSD                        → {"success":true, "swap_long":..., "swap_short":..., "swap_triple_day":...}
    ///
    /// by ФорексГод — Glitch in Matrix
    /// </summary>
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class MarketDataProvider : Robot
    {
        [Parameter("HTTP Port", DefaultValue = 8000)]
        public int HttpPort { get; set; }

        private HttpListener _httpListener;
        private Thread _httpThread;

        protected override void OnStart()
        {
            Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            Print("📡 MarketDataProvider — Glitch in Matrix");
            Print($"   Port: {HttpPort}");
            Print("   Endpoints: /health /data /price /swap_info");
            Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");

            try
            {
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add($"http://localhost:{HttpPort}/");
                _httpListener.Start();
                Print($"✅ HTTP server started on http://localhost:{HttpPort}/");

                _httpThread = new Thread(HandleRequests);
                _httpThread.IsBackground = true;
                _httpThread.Start();
            }
            catch (Exception ex)
            {
                Print($"❌ Failed to start HTTP server: {ex.Message}");
            }
        }

        private void HandleRequests()
        {
            while (_httpListener != null && _httpListener.IsListening)
            {
                try
                {
                    var ctx = _httpListener.GetContext();
                    ThreadPool.QueueUserWorkItem(_ => ProcessRequest(ctx));
                }
                catch (HttpListenerException) { break; }
                catch (Exception ex) { Print($"⚠️ Listener error: {ex.Message}"); }
            }
        }

        private void ProcessRequest(HttpListenerContext ctx)
        {
            try
            {
                var path = ctx.Request.Url.AbsolutePath.ToLower().TrimEnd('/');
                var query = ctx.Request.QueryString;
                string responseBody;

                if (path == "/health" || path == "")
                {
                    responseBody = "{\"status\":\"ok\",\"port\":" + HttpPort + ",\"bot\":\"MarketDataProvider\"}";
                }
                else if (path == "/data")
                {
                    responseBody = HandleData(query);
                }
                else if (path == "/price")
                {
                    responseBody = HandlePrice(query);
                }
                else if (path == "/swap_info")
                {
                    responseBody = HandleSwapInfo(query);
                }
                else
                {
                    responseBody = "{\"error\":\"Unknown endpoint. Available: /health /data /price /swap_info\"}";
                    ctx.Response.StatusCode = 404;
                }

                var bytes = Encoding.UTF8.GetBytes(responseBody);
                ctx.Response.ContentType = "application/json; charset=utf-8";
                ctx.Response.ContentLength64 = bytes.Length;
                if (ctx.Response.StatusCode == 200)
                    ctx.Response.StatusCode = 200;
                ctx.Response.OutputStream.Write(bytes, 0, bytes.Length);
                ctx.Response.OutputStream.Close();
            }
            catch (Exception ex)
            {
                Print($"⚠️ Request error: {ex.Message}");
                try { ctx.Response.OutputStream.Close(); } catch { }
            }
        }

        // ─── /data ────────────────────────────────────────────────────────────

        private string HandleData(System.Collections.Specialized.NameValueCollection q)
        {
            string symbolName = q["symbol"] ?? "EURUSD";
            string timeframeStr = q["timeframe"] ?? "Daily";
            int barsCount = 100;
            if (int.TryParse(q["bars"], out int parsed))
                barsCount = Math.Min(parsed, 1000);

            var symbol = Symbols.GetSymbol(symbolName);
            if (symbol == null)
                return $"{{\"error\":\"Symbol not found: {symbolName}\"}}";

            TimeFrame tf = ResolveTimeframe(timeframeStr);
            var series = MarketData.GetBars(tf, symbolName);

            if (series == null || series.Count == 0)
                return $"{{\"error\":\"No bars available for {symbolName} {timeframeStr}\"}}";

            int start = Math.Max(0, series.Count - barsCount);
            var sb = new StringBuilder();
            sb.Append("{");
            sb.Append($"\"symbol\":\"{symbolName}\",");
            sb.Append($"\"timeframe\":\"{timeframeStr}\",");
            sb.Append("\"bars\":[");

            bool first = true;
            for (int i = start; i < series.Count; i++)
            {
                if (!first) sb.Append(",");
                first = false;
                var bar = series[i];
                sb.Append("{");
                sb.Append($"\"time\":\"{bar.OpenTime:yyyy-MM-ddTHH:mm:ss}\",");
                sb.Append($"\"open\":{bar.Open.ToString(CultureInfo.InvariantCulture)},");
                sb.Append($"\"high\":{bar.High.ToString(CultureInfo.InvariantCulture)},");
                sb.Append($"\"low\":{bar.Low.ToString(CultureInfo.InvariantCulture)},");
                sb.Append($"\"close\":{bar.Close.ToString(CultureInfo.InvariantCulture)},");
                sb.Append($"\"volume\":{bar.TickVolume.ToString(CultureInfo.InvariantCulture)}");
                sb.Append("}");
            }

            sb.Append("]}");
            return sb.ToString();
        }

        // ─── /price ───────────────────────────────────────────────────────────

        private string HandlePrice(System.Collections.Specialized.NameValueCollection q)
        {
            string symbolName = q["symbol"] ?? "EURUSD";
            var symbol = Symbols.GetSymbol(symbolName);
            if (symbol == null)
                return $"{{\"error\":\"Symbol not found: {symbolName}\"}}";

            return "{" +
                $"\"symbol\":\"{symbolName}\"," +
                $"\"bid\":{symbol.Bid.ToString(CultureInfo.InvariantCulture)}," +
                $"\"ask\":{symbol.Ask.ToString(CultureInfo.InvariantCulture)}," +
                $"\"spread\":{symbol.Spread.ToString(CultureInfo.InvariantCulture)}," +
                $"\"time\":\"{Server.Time:yyyy-MM-ddTHH:mm:ss}\"" +
                "}";
        }

        // ─── /swap_info ───────────────────────────────────────────────────────

        private string HandleSwapInfo(System.Collections.Specialized.NameValueCollection q)
        {
            string symbolName = q["symbol"] ?? "EURUSD";
            var symbol = Symbols.GetSymbol(symbolName);
            if (symbol == null)
                return $"{{\"success\":false,\"error\":\"Symbol not found: {symbolName}\"}}";

            // Triple swap day: Wednesday is standard for most brokers (IC Markets included)
            string tripleDay = "Wednesday";

            return "{" +
                "\"success\":true," +
                $"\"symbol\":\"{symbolName}\"," +
                $"\"swap_long\":{symbol.SwapLong.ToString(CultureInfo.InvariantCulture)}," +
                $"\"swap_short\":{symbol.SwapShort.ToString(CultureInfo.InvariantCulture)}," +
                $"\"swap_triple_day\":\"{tripleDay}\"" +
                "}";
        }

        // ─── Timeframe resolver ───────────────────────────────────────────────

        private TimeFrame ResolveTimeframe(string tf)
        {
            switch (tf.ToUpper())
            {
                case "M1":     return TimeFrame.Minute;
                case "M5":     return TimeFrame.Minute5;
                case "M15":    return TimeFrame.Minute15;
                case "M30":    return TimeFrame.Minute30;
                case "H1":
                case "HOUR1":  return TimeFrame.Hour;
                case "H4":
                case "HOUR4":  return TimeFrame.Hour4;
                case "D1":
                case "DAILY":  return TimeFrame.Daily;
                case "W1":
                case "WEEKLY": return TimeFrame.Weekly;
                default:       return TimeFrame.Daily;
            }
        }

        protected override void OnStop()
        {
            try { _httpListener?.Stop(); } catch { }
            Print("🛑 MarketDataProvider stopped.");
        }
    }
}
