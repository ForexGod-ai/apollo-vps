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
        private HttpListener _httpListener;
        private Thread _httpThread;
        private string _lastJson = "{}";
        private readonly object _jsonLock = new object();

        protected override void OnStart()
        {
            Print("🔄 Trade History Syncer V2 Started");
            Print($"📁 Output: {JsonFilePath}");
            Print($"🌐 HTTP Port: {HttpPort}");
            Print($"⏱️ Update interval: {UpdateInterval}s");

            // Start HTTP server
            StartHttpServer();

            // Sync immediately on start
            SyncTradeHistory();

            // Setup timer for periodic sync
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

                _httpThread = new Thread(() =>
                {
                    while (_httpListener.IsListening)
                    {
                        try
                        {
                            var ctx = _httpListener.GetContext();
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
                        catch (HttpListenerException) { break; }
                        catch (Exception ex) { Print($"⚠️ HTTP response error: {ex.Message}"); }
                    }
                });
                _httpThread.IsBackground = true;
                _httpThread.Start();
            }
            catch (Exception ex)
            {
                Print($"❌ HTTP server failed to start: {ex.Message}");
            }
        }

        protected override void OnTimer()
        {
            SyncTradeHistory();
        }

        protected override void OnStop()
        {
            // Stop HTTP server
            try { _httpListener?.Stop(); } catch { }

            // Final sync on stop
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
                
                // Sort by EntryTime first (when trade opened), then PositionId for chronological order
                var closedPositions = History?.OrderBy(x => x.EntryTime).ThenBy(x => x.PositionId).ToList() ?? new System.Collections.Generic.List<HistoricalTrade>();
                var openPositions = Positions?.ToList() ?? new System.Collections.Generic.List<Position>();
                
                Print($"🔢 Sorting by EntryTime → PositionId for accurate balance calculation");
                
                Print($"📊 Found {closedPositions.Count} closed + {openPositions.Count} open positions");

                // Calculate account metrics
                double currentBalance = Account.Balance;
                double openPL = openPositions.Sum(p => p.NetProfit);
                double equity = Account.Equity;

                var json = new StringBuilder();
                json.AppendLine("{");
                
                // ========== ACCOUNT SECTION ==========
                json.AppendLine("    \"account\": {");
                json.AppendLine($"        \"number\": \"{Account.Number}\",");
                json.AppendLine($"        \"balance\": {currentBalance.ToString("F2", CultureInfo.InvariantCulture)},");
                json.AppendLine($"        \"equity\": {equity.ToString("F2", CultureInfo.InvariantCulture)},");
                json.AppendLine($"        \"open_pl\": {openPL.ToString("F2", CultureInfo.InvariantCulture)},");
                json.AppendLine($"        \"currency\": \"USD\",");
                json.AppendLine($"        \"last_update\": \"{DateTime.Now:yyyy-MM-dd HH:mm:ss}\"");
                json.AppendLine("    },");

                // ========== OPEN POSITIONS SECTION ==========
                json.AppendLine("    \"open_positions\": [");
                for (int i = 0; i < openPositions.Count; i++)
                {
                    var position = openPositions[i];
                    
                    // ✅ V10.1 FIX: Use broker-specific volume conversion (fixes BTCUSD 0.0 bug)
                    var symbol = Symbols.GetSymbol(position.SymbolName);
                    double lotSize = symbol != null 
                        ? symbol.VolumeInUnitsToQuantity(position.VolumeInUnits) 
                        : position.VolumeInUnits / 100000.0; // Fallback for missing symbols
                    
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

                // ========== CLOSED TRADES SECTION ==========
                json.AppendLine("    \"closed_trades\": [");
                for (int i = 0; i < closedPositions.Count; i++)
                {
                    var position = closedPositions[i];
                    
                    // ✅ V10.1 FIX: Use broker-specific volume conversion (fixes BTCUSD 0.0 bug)
                    var symbol = Symbols.GetSymbol(position.SymbolName);
                    double lotSize = symbol != null 
                        ? symbol.VolumeInUnitsToQuantity(position.VolumeInUnits) 
                        : position.VolumeInUnits / 100000.0; // Fallback for missing symbols
                    
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

                // Write to file
                File.WriteAllText(JsonFilePath, jsonString);

                // Update in-memory JSON served via HTTP on port 8767
                lock (_jsonLock)
                    _lastJson = jsonString;

                Print($"✅ Synced {closedPositions.Count} closed + {openPositions.Count} open to JSON");
                Print($"💰 Balance: ${currentBalance:F2} | Open P/L: ${openPositions.Sum(p => p.NetProfit):F2}");
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
