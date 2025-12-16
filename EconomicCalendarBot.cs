using System;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Globalization;
using cAlgo.API;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class EconomicCalendarBot : Robot
    {
        [Parameter("HTTP Port", DefaultValue = 8768)]
        public int HttpPort { get; set; }

        private HttpListener _httpListener;
        private Thread _listenerThread;

        protected override void OnStart()
        {
            Print("🚀 Economic Calendar Bot starting...");
            Print($"📡 Starting HTTP server on port {HttpPort}");

            try
            {
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add($"http://localhost:{HttpPort}/");
                _httpListener.Start();

                _listenerThread = new Thread(HandleRequests);
                _listenerThread.Start();

                Print($"✅ HTTP server started successfully on http://localhost:{HttpPort}/");
                Print("📅 Economic Calendar data available at /calendar");
                Print("💡 Python can now fetch calendar events from this endpoint");
            }
            catch (Exception ex)
            {
                Print($"❌ Failed to start HTTP server: {ex.Message}");
            }
        }

        protected override void OnStop()
        {
            Print("🛑 Stopping Economic Calendar Bot...");

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
            while (_httpListener.IsListening)
            {
                try
                {
                    var context = _httpListener.GetContext();
                    var request = context.Request;
                    var response = context.Response;

                    // Enable CORS
                    response.AddHeader("Access-Control-Allow-Origin", "*");
                    response.AddHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
                    response.AddHeader("Access-Control-Allow-Headers", "Content-Type");

                    if (request.HttpMethod == "OPTIONS")
                    {
                        response.StatusCode = 200;
                        response.Close();
                        continue;
                    }

                    string responseString = "";

                    if (request.Url.AbsolutePath == "/calendar")
                    {
                        responseString = GetEconomicCalendar();
                        response.StatusCode = 200;
                    }
                    else if (request.Url.AbsolutePath == "/health")
                    {
                        responseString = $@"{{
    ""status"": ""ok"",
    ""timestamp"": ""{Server.Time:yyyy-MM-dd HH:mm:ss}"",
    ""service"": ""EconomicCalendarBot""
}}";
                        response.StatusCode = 200;
                    }
                    else
                    {
                        responseString = $@"{{
    ""error"": ""Not Found"",
    ""message"": ""Available endpoints: /calendar, /health""
}}";
                        response.StatusCode = 404;
                    }

                    byte[] buffer = Encoding.UTF8.GetBytes(responseString);
                    response.ContentType = "application/json";
                    response.ContentLength64 = buffer.Length;
                    response.OutputStream.Write(buffer, 0, buffer.Length);
                    response.Close();
                }
                catch (Exception ex)
                {
                    if (_httpListener.IsListening)
                    {
                        Print($"⚠️ Error handling request: {ex.Message}");
                    }
                }
            }
        }

        private string GetEconomicCalendar()
        {
            try
            {
                // Get calendar events from cTrader
                var calendarEvents = Application.EconomicCalendar.Events;
                
                if (calendarEvents == null || calendarEvents.Count == 0)
                {
                    return @"{
    ""success"": true,
    ""events"": [],
    ""count"": 0,
    ""message"": ""No calendar events available""
}";
                }

                // Get events for next 7 days
                var now = Server.Time;
                var endDate = now.AddDays(7);

                var upcomingEvents = calendarEvents
                    .Where(e => e.DateTime >= now && e.DateTime <= endDate)
                    .OrderBy(e => e.DateTime)
                    .ToList();

                // Build JSON manually
                var json = new StringBuilder();
                json.AppendLine("{");
                json.AppendLine("    \"success\": true,");
                json.AppendLine("    \"events\": [");

                for (int i = 0; i < upcomingEvents.Count; i++)
                {
                    var e = upcomingEvents[i];
                    var timestamp = new DateTimeOffset(e.DateTime).ToUnixTimeSeconds();
                    var isHighImpact = e.Impact == CalendarImpact.High;
                    
                    // Escape strings for JSON
                    var eventName = EscapeJsonString(e.EventName);
                    var actual = e.ActualValue.HasValue ? e.ActualValue.Value.ToString(CultureInfo.InvariantCulture) : "null";
                    var forecast = e.ForecastValue.HasValue ? e.ForecastValue.Value.ToString(CultureInfo.InvariantCulture) : "null";
                    var previous = e.PreviousValue.HasValue ? e.PreviousValue.Value.ToString(CultureInfo.InvariantCulture) : "null";

                    json.AppendLine("        {");
                    json.AppendLine($"            \"time\": \"{e.DateTime:yyyy-MM-dd HH:mm:ss}\",");
                    json.AppendLine($"            \"timestamp\": {timestamp},");
                    json.AppendLine($"            \"currency\": \"{e.CurrencyCode}\",");
                    json.AppendLine($"            \"impact\": \"{e.Impact}\",");
                    json.AppendLine($"            \"event\": \"{eventName}\",");
                    json.AppendLine($"            \"actual\": {actual},");
                    json.AppendLine($"            \"forecast\": {forecast},");
                    json.AppendLine($"            \"previous\": {previous},");
                    json.AppendLine($"            \"is_high_impact\": {isHighImpact.ToString().ToLower()},");
                    json.AppendLine($"            \"country\": \"{e.CountryCode}\"");
                    
                    if (i < upcomingEvents.Count - 1)
                        json.AppendLine("        },");
                    else
                        json.AppendLine("        }");
                }

                json.AppendLine("    ],");
                json.AppendLine($"    \"count\": {upcomingEvents.Count},");
                json.AppendLine($"    \"fetched_at\": \"{now:yyyy-MM-dd HH:mm:ss}\",");
                json.AppendLine("    \"period\": {");
                json.AppendLine($"        \"start\": \"{now:yyyy-MM-dd}\",");
                json.AppendLine($"        \"end\": \"{endDate:yyyy-MM-dd}\",");
                json.AppendLine("        \"days\": 7");
                json.AppendLine("    }");
                json.AppendLine("}");

                return json.ToString();
            }
            catch (Exception ex)
            {
                Print($"❌ Error getting calendar: {ex.Message}");
                return $@"{{
    ""success"": false,
    ""error"": ""{EscapeJsonString(ex.Message)}"",
    ""events"": []
}}";
            }
        }

        private string EscapeJsonString(string str)
        {
            if (string.IsNullOrEmpty(str))
                return str;
            
            return str
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\n", "\\n")
                .Replace("\r", "\\r")
                .Replace("\t", "\\t");
        }
    }
}
