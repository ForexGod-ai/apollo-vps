using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Globalization;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class TradeHistorySyncer : Robot
    {
        [Parameter("JSON File Path", DefaultValue = "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/trade_history.json")]
        public string JsonFilePath { get; set; }

        [Parameter("Update Interval (seconds)", DefaultValue = 10)]
        public int UpdateInterval { get; set; }

        private DateTime _lastUpdate = DateTime.MinValue;

        protected override void OnStart()
        {
            Print("🔄 Trade History Syncer Started");
            Print($"📁 Output: {JsonFilePath}");
            Print($"⏱️ Update interval: {UpdateInterval}s");
            
            // Sync immediately on start
            SyncTradeHistory();
            
            // Setup timer for periodic sync
            Timer.Start(UpdateInterval);
        }

        protected override void OnTimer()
        {
            SyncTradeHistory();
        }

        protected override void OnStop()
        {
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
                    json.AppendLine("        {");
                    json.AppendLine($"            \"ticket\": {position.Id},");
                    json.AppendLine($"            \"symbol\": \"{position.SymbolName}\",");
                    json.AppendLine($"            \"direction\": \"{(position.TradeType == TradeType.Buy ? "BUY" : "SELL")}\",");
                    json.AppendLine($"            \"entry_price\": {position.EntryPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"current_price\": {(position.TradeType == TradeType.Buy ? position.Symbol.Bid : position.Symbol.Ask).ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"lot_size\": {(position.VolumeInUnits / 100000.0).ToString("F2", CultureInfo.InvariantCulture)},");
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
                    
                    json.AppendLine("        {");
                    json.AppendLine($"            \"ticket\": {position.PositionId},");
                    json.AppendLine($"            \"symbol\": \"{position.SymbolName}\",");
                    json.AppendLine($"            \"direction\": \"{(position.TradeType == TradeType.Buy ? "BUY" : "SELL")}\",");
                    json.AppendLine($"            \"entry_price\": {position.EntryPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"closing_price\": {position.ClosingPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"            \"lot_size\": {(position.VolumeInUnits / 100000.0).ToString("F2", CultureInfo.InvariantCulture)},");
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

                // Write to file
                File.WriteAllText(JsonFilePath, json.ToString());

                Print($"✅ Synced {closedPositions.Count} closed + {openPositions.Count} open to JSON");
                Print($"💰 Balance: ${currentBalance:F2} | Open P/L: ${openPositions.Sum(p => p.NetProfit):F2}");
                
                _lastUpdate = DateTime.Now;
            }
            catch (Exception ex)
            {
                Print($"❌ Sync error: {ex.Message}");
            }
        }
    }
}
