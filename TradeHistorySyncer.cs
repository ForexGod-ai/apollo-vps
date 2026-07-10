using System;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Linq;
using System.Globalization;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class TradeHistorySyncer : Robot
    {
        [Parameter("JSON File Path", DefaultValue = @"C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\trade_history.json")]
        public string JsonFilePath { get; set; }

        [Parameter("HTTP Port", DefaultValue = 8767)]
        public int HttpPort { get; set; }

        [Parameter("Update Interval (seconds)", DefaultValue = 10)]
        public int UpdateInterval { get; set; }

        private DateTime _lastUpdate = DateTime.MinValue;
        private DateTime _lastTickSyncAttempt = DateTime.MinValue;
        private HttpListener _httpListener;
        private Thread _httpThread;
        private string _lastJson = "{}";
        private readonly object _jsonLock = new object();
        private volatile bool _httpStopRequested;

        private bool IsDataStale()
        {
            if (_lastUpdate == DateTime.MinValue)
                return true;
            return (DateTime.Now - _lastUpdate).TotalSeconds > Math.Max(UpdateInterval * 3, 90);
        }

        protected override void OnStart()
        {
            Print("🔄 Trade History Syncer V3 Started");
            Print($"📁 Output: {JsonFilePath}");
            Print($"🌐 HTTP Port: {HttpPort}");
            Print($"⏱️ Update interval: {UpdateInterval}s");

            StartHttpServer();
            SyncTradeHistory();
            Timer.Start(UpdateInterval);
        }

        private void StartHttpServer()
        {
            try
            {
                _httpListener = new HttpListener();
                _httpListener.Prefixes.Add($"http://localhost:{HttpPort}/");
                _httpListener.Start();
                Print($"✅ HTTP server started: http://localhost:{HttpPort}/");

                _httpStopRequested = false;
                _httpThread = new Thread(HttpServeLoop);
                _httpThread.IsBackground = true;
                _httpThread.Start();
            }
            catch (Exception ex)
            {
                Print($"❌ HTTP server failed to start: {ex.Message}");
            }
        }

        private void HttpServeLoop()
        {
            while (_httpListener != null && _httpListener.IsListening && !_httpStopRequested)
            {
                try
                {
                    var ctx = _httpListener.GetContext();
                    if (IsDataStale())
                    {
                        Print($"⚠️ HTTP request with stale cache ({StaleAgeSeconds():F0}s) — forcing live sync");
                        ForceSyncOnMainThread();
                    }

                    string responseJson;
                    lock (_jsonLock)
                        responseJson = _lastJson;

                    var bytes = Encoding.UTF8.GetBytes(responseJson);
                    ctx.Response.ContentType = "application/json; charset=utf-8";
                    ctx.Response.ContentLength64 = bytes.Length;
                    ctx.Response.StatusCode = 200;
                    ctx.Response.OutputStream.Write(bytes, 0, bytes.Length);
                    ctx.Response.OutputStream.Close();
                }
                catch (HttpListenerException ex)
                {
                    if (!_httpStopRequested)
                        Print($"⚠️ HTTP listener hiccup: {ex.Message} — continuing");
                    Thread.Sleep(200);
                }
                catch (Exception ex)
                {
                    Print($"⚠️ HTTP response error: {ex.Message}");
                }
            }
        }

        private double StaleAgeSeconds()
        {
            if (_lastUpdate == DateTime.MinValue)
                return double.MaxValue;
            return (DateTime.Now - _lastUpdate).TotalSeconds;
        }

        private void ForceSyncOnMainThread()
        {
            try
            {
                var done = new ManualResetEventSlim(false);
                BeginInvokeOnMainThread(() =>
                {
                    try { SyncTradeHistory(); }
                    finally { done.Set(); }
                });
                done.Wait(TimeSpan.FromSeconds(8));
            }
            catch (Exception ex)
            {
                Print($"⚠️ ForceSyncOnMainThread failed: {ex.Message}");
            }
        }

        protected override void OnTimer()
        {
            SyncTradeHistory();
        }

        protected override void OnTick()
        {
            if (!IsDataStale())
                return;
            if ((DateTime.Now - _lastTickSyncAttempt).TotalSeconds < 10)
                return;
            _lastTickSyncAttempt = DateTime.Now;
            Print($"⚠️ OnTick stale recovery ({StaleAgeSeconds():F0}s since last sync)");
            SyncTradeHistory();
        }

        protected override void OnStop()
        {
            _httpStopRequested = true;
            try { _httpListener?.Stop(); } catch { }
            SyncTradeHistory();
            Print("🛑 Trade History Syncer Stopped");
        }

        private void SyncTradeHistory()
        {
            try
            {
                Print("═══════════════════════════════════════════════════════");
                Print($"🔍 SYNCING TRADE HISTORY + OPEN POSITIONS");
                Print($"   Account: {Account.Number}");
                Print($"   Closed Trades: {History?.Count ?? 0}");
                Print($"   Open Positions: {Positions?.Count ?? 0}");
                Print("═══════════════════════════════════════════════════════");

                var closedPositions = History?.OrderBy(x => x.EntryTime).ThenBy(x => x.PositionId).ToList() ?? new System.Collections.Generic.List<HistoricalTrade>();
                var openPositions = Positions?.ToList() ?? new System.Collections.Generic.List<Position>();

                Print($"🔢 Sorting by EntryTime → PositionId for accurate balance calculation");
                Print($"📊 Found {closedPositions.Count} closed + {openPositions.Count} open positions");

                double currentBalance = Account.Balance;
                double openPL = openPositions.Sum(p => p.NetProfit);
                double equity = Account.Equity;
                string lastUpdateStr = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss");

                var json = new StringBuilder();
                json.AppendLine("{");

                json.AppendLine("    \"account\": {");
                json.AppendLine($"        \"number\": \"{Account.Number}\",");
                json.AppendLine($"        \"balance\": {currentBalance.ToString("F2", CultureInfo.InvariantCulture)},");
                json.AppendLine($"        \"equity\": {equity.ToString("F2", CultureInfo.InvariantCulture)},");
                json.AppendLine($"        \"open_pl\": {openPL.ToString("F2", CultureInfo.InvariantCulture)},");
                json.AppendLine($"        \"currency\": \"USD\",");
                json.AppendLine($"        \"last_update\": \"{lastUpdateStr}\"");
                json.AppendLine("    },");

                json.AppendLine("    \"open_positions\": [");
                for (int i = 0; i < openPositions.Count; i++)
                {
                    var position = openPositions[i];
                    var symbol = Symbols.GetSymbol(position.SymbolName);
                    double lotSize = symbol != null
                        ? symbol.VolumeInUnitsToQuantity(position.VolumeInUnits)
                        : position.VolumeInUnits / 100000.0;

                    json.AppendLine("        {");
                    json.AppendLine($"            \"ticket\": {position.Id},");
                    json.AppendLine($"            \"symbol\": \"{position.SymbolName}\",");
                    json.AppendLine($"            \"direction\": \"{(position.TradeType == TradeType.Buy ? "BUY" : "SELL")}\",");
                    json.AppendLine($"            \"entry_price\": {position.EntryPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"current_price\": {(position.TradeType == TradeType.Buy ? position.Symbol.Bid : position.Symbol.Ask).ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"lot_size\": {lotSize.ToString("F2", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"volume\": {position.VolumeInUnits.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"open_time\": \"{position.EntryTime:yyyy-MM-ddTHH:mm:ss}\",");
                    json.AppendLine($"            \"profit\": {position.NetProfit.ToString("F2", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"pips\": {position.Pips.ToString("F1", CultureInfo.InvariantCulture)},");
                    if (position.StopLoss.HasValue)
                        json.AppendLine($"            \"stop_loss\": {position.StopLoss.Value.ToString(CultureInfo.InvariantCulture)},");
                    if (position.TakeProfit.HasValue)
                        json.AppendLine($"            \"take_profit\": {position.TakeProfit.Value.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"comment\": \"{position.Comment ?? ""}\"");

                    if (i < openPositions.Count - 1)
                        json.AppendLine("        },");
                    else
                        json.AppendLine("        }");
                }
                json.AppendLine("    ],");

                json.AppendLine("    \"closed_trades\": [");
                for (int i = 0; i < closedPositions.Count; i++)
                {
                    var position = closedPositions[i];
                    var symbol = Symbols.GetSymbol(position.SymbolName);
                    double lotSize = symbol != null
                        ? symbol.VolumeInUnitsToQuantity(position.VolumeInUnits)
                        : position.VolumeInUnits / 100000.0;

                    json.AppendLine("        {");
                    json.AppendLine($"            \"ticket\": {position.PositionId},");
                    json.AppendLine($"            \"symbol\": \"{position.SymbolName}\",");
                    json.AppendLine($"            \"direction\": \"{(position.TradeType == TradeType.Buy ? "BUY" : "SELL")}\",");
                    json.AppendLine($"            \"entry_price\": {position.EntryPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"closing_price\": {position.ClosingPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"lot_size\": {lotSize.ToString("F2", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"volume\": {position.VolumeInUnits.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"open_time\": \"{position.EntryTime:yyyy-MM-ddTHH:mm:ss}\",");
                    json.AppendLine($"            \"close_time\": \"{position.ClosingTime:yyyy-MM-ddTHH:mm:ss}\",");
                    json.AppendLine($"            \"profit\": {position.NetProfit.ToString("F2", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"pips\": {position.Pips.ToString("F1", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"comment\": \"{position.Comment ?? ""}\"");

                    if (i < closedPositions.Count - 1)
                        json.AppendLine("        },");
                    else
                        json.AppendLine("        }");
                }
                json.AppendLine("    ]");

                json.AppendLine("}");

                var jsonString = json.ToString();
                File.WriteAllText(JsonFilePath, jsonString);

                lock (_jsonLock)
                    _lastJson = jsonString;

                Print($"✅ Synced {closedPositions.Count} closed + {openPositions.Count} open to JSON");
                Print($"💰 Balance: ${currentBalance:F2} | Equity: ${equity:F2} | Open P/L: ${openPL:F2}");
                Print($"🕒 last_update: {lastUpdateStr}");
                Print($"🌐 HTTP: http://localhost:{HttpPort}/ — response updated");

                _lastUpdate = DateTime.Now;
            }
            catch (Exception ex)
            {
                Print($"❌ Sync error: {ex.Message}");
            }
        }
    }
}
