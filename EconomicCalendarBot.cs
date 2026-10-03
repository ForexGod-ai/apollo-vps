using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Globalization;
using cAlgo.API;

namespace cAlgo.Robots
{
    /// <summary>
    /// HTTP :8768 — serves economic events for news_fetcher.py and /news.
    /// cAlgo does NOT expose Application.EconomicCalendar (Spotware policy).
    /// Reads data/upcoming_news.json (ForexFactory High via news_fetcher HTML/mirror) on the VPS.
    /// </summary>
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class EconomicCalendarBot : Robot
    {
        [Parameter("HTTP Port", DefaultValue = 8768)]
        public int HttpPort { get; set; }

        [Parameter("Days Ahead", DefaultValue = 14)]
        public int DaysAhead { get; set; }

        [Parameter("Events JSON Path", DefaultValue = @"C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\data\upcoming_news.json")]
        public string EventsJsonPath { get; set; }

        private HttpListener _httpListener;
        private Thread _listenerThread;

        protected override void OnStart()
        {
            Print("🚀 Economic Calendar Bot starting...");
            Print($"📡 HTTP port: {HttpPort}");
            Print($"📁 Events file: {EventsJsonPath}");
            Print("ℹ️ cAlgo has no EconomicCalendar API — serving upcoming_news.json from news_fetcher.py");

            try
            {
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add($"http://localhost:{HttpPort}/");
                _httpListener.Start();

                _listenerThread = new Thread(HandleRequests);
                _listenerThread.Start();

                Print($"✅ HTTP server: http://localhost:{HttpPort}/calendar");
            }
            catch (Exception ex)
            {
                Print($"❌ Failed to start HTTP server: {ex.Message}");
            }
        }

        protected override void OnStop()
        {
            if (_httpListener != null && _httpListener.IsListening)
            {
                _httpListener.Stop();
                _httpListener.Close();
            }

            if (_listenerThread != null && _listenerThread.IsAlive)
            {
                _listenerThread.Join(TimeSpan.FromSeconds(2));
            }

            Print("✅ Economic Calendar Bot stopped");
        }

        private void HandleRequests()
        {
            while (_httpListener != null && _httpListener.IsListening)
            {
                try
                {
                    var context = _httpListener.GetContext();
                    var request = context.Request;
                    var response = context.Response;

                    response.AddHeader("Access-Control-Allow-Origin", "*");
                    response.AddHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
                    response.AddHeader("Access-Control-Allow-Headers", "Content-Type");

                    if (request.HttpMethod == "OPTIONS")
                    {
                        response.StatusCode = 200;
                        response.Close();
                        continue;
                    }

                    string responseString;
                    if (request.Url.AbsolutePath == "/calendar")
                    {
                        responseString = BuildCalendarJson();
                        response.StatusCode = 200;
                    }
                    else if (request.Url.AbsolutePath == "/health")
                    {
                        responseString = string.Format(
                            "{{\"status\":\"ok\",\"timestamp\":\"{0}\",\"service\":\"EconomicCalendarBot\"}}",
                            Server.Time.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture));
                        response.StatusCode = 200;
                    }
                    else
                    {
                        responseString = "{\"error\":\"Not Found\",\"message\":\"Use /calendar or /health\"}";
                        response.StatusCode = 404;
                    }

                    byte[] buffer = Encoding.UTF8.GetBytes(responseString);
                    response.ContentType = "application/json; charset=utf-8";
                    response.ContentLength64 = buffer.Length;
                    response.OutputStream.Write(buffer, 0, buffer.Length);
                    response.Close();
                }
                catch (HttpListenerException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    if (_httpListener != null && _httpListener.IsListening)
                        Print($"⚠️ HTTP error: {ex.Message}");
                }
            }
        }

        private string BuildCalendarJson()
        {
            var now = Server.Time;
            var horizonDays = Math.Max(1, DaysAhead);
            var endDate = now.AddDays(horizonDays);

            var events = LoadEventsFromJson(now, endDate);
            var json = new StringBuilder();
            json.AppendLine("{");
            json.AppendLine("    \"success\": true,");
            json.AppendLine("    \"events\": [");

            for (int i = 0; i < events.Count; i++)
            {
                var e = events[i];
                json.AppendLine("        {");
                json.AppendLine(string.Format("            \"time\": \"{0}\",", e.Time));
                json.AppendLine(string.Format("            \"currency\": \"{0}\",", EscapeJson(e.Currency)));
                json.AppendLine(string.Format("            \"impact\": \"{0}\",", EscapeJson(e.Impact)));
                json.AppendLine(string.Format("            \"event\": \"{0}\",", EscapeJson(e.Event)));
                json.AppendLine(string.Format("            \"forecast\": \"{0}\",", EscapeJson(e.Forecast)));
                json.AppendLine(string.Format("            \"previous\": \"{0}\",", EscapeJson(e.Previous)));
                json.AppendLine(string.Format("            \"is_high_impact\": {0}", e.IsHighImpact ? "true" : "false"));
                if (i < events.Count - 1)
                    json.AppendLine("        },");
                else
                    json.AppendLine("        }");
            }

            json.AppendLine("    ],");
            json.AppendLine(string.Format("    \"count\": {0},", events.Count));
            json.AppendLine(string.Format("    \"fetched_at\": \"{0}\",", now.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture)));
            json.AppendLine("    \"period\": {");
            json.AppendLine(string.Format("        \"start\": \"{0}\",", now.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture)));
            json.AppendLine(string.Format("        \"end\": \"{0}\",", endDate.ToString("yyyy-MM-dd", CultureInfo.InvariantCulture)));
            json.AppendLine(string.Format("        \"days\": {0}", horizonDays));
            json.AppendLine("    },");
            json.AppendLine("    \"source\": \"upcoming_news.json\"");
            json.AppendLine("}");

            return json.ToString();
        }

        private List<CalendarRow> LoadEventsFromJson(DateTime now, DateTime endDate)
        {
            var result = new List<CalendarRow>();
            if (string.IsNullOrWhiteSpace(EventsJsonPath) || !System.IO.File.Exists(EventsJsonPath))
            {
                Print($"⚠️ Events file missing: {EventsJsonPath} — run news_fetcher.py on VPS");
                return result;
            }

            try
            {
                var text = System.IO.File.ReadAllText(EventsJsonPath);
                var events = ExtractEventsArray(text);
                foreach (var block in events)
                {
                    var row = ParseEventBlock(block, now, endDate);
                    if (row != null)
                        result.Add(row);
                }

                Print($"📅 Served {result.Count} events from JSON (horizon {DaysAhead}d)");
            }
            catch (Exception ex)
            {
                Print($"❌ Read JSON failed: {ex.Message}");
            }

            return result.OrderBy(r => r.Time).ToList();
        }

        private static List<string> ExtractEventsArray(string json)
        {
            var list = new List<string>();
            int keyIdx = json.IndexOf("\"events\"", StringComparison.Ordinal);
            if (keyIdx < 0)
                return list;

            int arrStart = json.IndexOf('[', keyIdx);
            if (arrStart < 0)
                return list;

            int depth = 0;
            int objStart = -1;
            for (int i = arrStart; i < json.Length; i++)
            {
                char c = json[i];
                if (c == '{')
                {
                    if (depth == 0)
                        objStart = i;
                    depth++;
                }
                else if (c == '}')
                {
                    depth--;
                    if (depth == 0 && objStart >= 0)
                    {
                        list.Add(json.Substring(objStart, i - objStart + 1));
                        objStart = -1;
                    }
                }
                else if (c == ']' && depth == 0)
                    break;
            }

            return list;
        }

        private CalendarRow ParseEventBlock(string block, DateTime now, DateTime endDate)
        {
            var impact = GetJsonString(block, "impact");
            if (impact != "High" && impact != "Medium")
                return null;

            var currency = GetJsonString(block, "currency");
            if (string.IsNullOrEmpty(currency))
                return null;

            var eventName = GetJsonString(block, "event");
            if (string.IsNullOrEmpty(eventName))
                return null;

            var dateStr = GetJsonString(block, "date");
            var timeStr = GetJsonString(block, "time");
            if (string.IsNullOrEmpty(dateStr))
                return null;
            if (string.IsNullOrEmpty(timeStr))
                timeStr = "12:00";

            DateTime eventTime;
            if (!DateTime.TryParseExact(
                    dateStr + " " + timeStr,
                    new[] { "yyyy-MM-dd HH:mm", "yyyy-MM-dd H:mm" },
                    CultureInfo.InvariantCulture,
                    DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal,
                    out eventTime))
                return null;

            if (eventTime < now || eventTime > endDate)
                return null;

            return new CalendarRow
            {
                Time = eventTime.ToString("yyyy-MM-dd HH:mm:ss", CultureInfo.InvariantCulture),
                Currency = currency,
                Impact = impact,
                Event = eventName,
                Forecast = GetJsonString(block, "forecast"),
                Previous = GetJsonString(block, "previous"),
                IsHighImpact = impact == "High",
            };
        }

        private static string GetJsonString(string block, string key)
        {
            var pattern = "\"" + key + "\"";
            int idx = block.IndexOf(pattern, StringComparison.Ordinal);
            if (idx < 0)
                return "";
            idx = block.IndexOf(':', idx);
            if (idx < 0)
                return "";
            idx++;
            while (idx < block.Length && char.IsWhiteSpace(block[idx]))
                idx++;
            if (idx >= block.Length)
                return "";
            if (block[idx] == '"')
            {
                idx++;
                var sb = new StringBuilder();
                while (idx < block.Length && block[idx] != '"')
                {
                    if (block[idx] == '\\' && idx + 1 < block.Length)
                    {
                        idx++;
                        sb.Append(block[idx]);
                    }
                    else
                        sb.Append(block[idx]);
                    idx++;
                }
                return sb.ToString();
            }
            return "";
        }

        private static string EscapeJson(string str)
        {
            if (string.IsNullOrEmpty(str))
                return "";
            return str
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\n", "\\n")
                .Replace("\r", "\\r")
                .Replace("\t", "\\t");
        }

        private class CalendarRow
        {
            public string Time { get; set; }
            public string Currency { get; set; }
            public string Impact { get; set; }
            public string Event { get; set; }
            public string Forecast { get; set; }
            public string Previous { get; set; }
            public bool IsHighImpact { get; set; }
        }
    }
}
