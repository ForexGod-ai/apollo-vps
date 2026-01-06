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
    public class EconomicCalendarHTTP : Robot
    {
        [Parameter("HTTP Port", DefaultValue = 8768)]
        public int HttpPort { get; set; }

        [Parameter("Days Ahead", DefaultValue = 14)]
        public int DaysAhead { get; set; }

        private HttpListener _httpListener;
        private Thread _listenerThread;

        protected override void OnStart()
        {
            Print("🚀 Economic Calendar HTTP Server starting...");
            Print($"📡 Port: {HttpPort}");

            try
            {
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add($"http://localhost:{HttpPort}/");
                _httpListener.Start();

                _listenerThread = new Thread(HandleRequests);
                _listenerThread.Start();

                Print($"✅ Server started: http://localhost:{HttpPort}/calendar");
                Print($"📅 Exposing {DaysAhead} days of economic events");
            }
            catch (Exception ex)
            {
                Print($"❌ Server failed: {ex.Message}");
            }
        }

        protected override void OnStop()
        {
            Print("🛑 Stopping server...");

            if (_httpListener != null && _httpListener.IsListening)
            {
                _httpListener.Stop();
                _httpListener.Close();
            }

            if (_listenerThread != null && _listenerThread.IsAlive)
            {
                _listenerThread.Join(TimeSpan.FromSeconds(2));
            }

            Print("✅ Server stopped");
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

                    // CORS headers
                    response.AddHeader("Access-Control-Allow-Origin", "*");
                    response.AddHeader("Access-Control-Allow-Methods", "GET, OPTIONS");
                    response.AddHeader("Content-Type", "application/json");

                    if (request.HttpMethod == "OPTIONS")
                    {
                        response.StatusCode = 200;
                        response.Close();
                        continue;
                    }

                    if (request.Url.AbsolutePath == "/calendar" || request.Url.AbsolutePath == "/")
                    {
                        string jsonResponse = GetCalendarJSON();
                        byte[] buffer = Encoding.UTF8.GetBytes(jsonResponse);
                        
                        response.StatusCode = 200;
                        response.ContentLength64 = buffer.Length;
                        response.OutputStream.Write(buffer, 0, buffer.Length);
                        response.OutputStream.Close();
                        
                        Print($"✅ Served {request.RemoteEndPoint}");
                    }
                    else
                    {
                        response.StatusCode = 404;
                        response.Close();
                    }
                }
                catch (HttpListenerException)
                {
                    // Listener stopped
                    break;
                }
                catch (Exception ex)
                {
                    Print($"⚠️ Request error: {ex.Message}");
                }
            }
        }

        private string GetCalendarJSON()
        {
            try
            {
                // cTrader API limitations: EconomicCalendar not accessible in all versions
                // Bot serves as health check endpoint
                // Python will fetch LIVE data from Trading Economics API
                
                var now = Server.Time;
                
                string result = string.Format("{{\"status\":\"active\",\"bot_version\":\"1.0\",\"timestamp\":\"{0}\",\"message\":\"Bot running. Python fetches live data from API.\",\"events\":[]}}",
                    now.ToString("yyyy-MM-ddTHH:mm:ssZ"));

                Print($"✅ Health check - Bot active at {now}");
                return result;
            }
            catch (Exception ex)
            {
                Print($"❌ Error: {ex.Message}");
                return string.Format("{{\"status\":\"error\",\"message\":\"{0}\",\"events\":[]}}", EscapeJson(ex.Message));
            }
        }

        private string EscapeJson(string text)
        {
            if (string.IsNullOrEmpty(text))
                return "";
            
            return text.Replace("\\", "\\\\")
                      .Replace("\"", "\\\"")
                      .Replace("\n", "\\n")
                      .Replace("\r", "\\r")
                      .Replace("\t", "\\t");
        }
    }
}
