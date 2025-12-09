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
        [Parameter("JSON File Path", DefaultValue = "/Users/forexgod/Desktop/trading-ai-agent apollo/trade_history.json")]
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
                
                var closedPositions = History?.OrderBy(x => x.ClosingTime).ToList() ?? new System.Collections.Generic.List<HistoricalTrade>();
                var openPositions = Positions?.ToList() ?? new System.Collections.Generic.List<Position>();
                
                Print($"📊 Found {closedPositions.Count} closed + {openPositions.Count} open positions");

                var json = new StringBuilder();
                json.AppendLine("[");

                double runningBalance = 1000.0; // Initial balance
                int totalCount = closedPositions.Count + openPositions.Count;
                int currentIndex = 0;

                // Add CLOSED positions first
                for (int i = 0; i < closedPositions.Count; i++)
                {
                    var position = closedPositions[i];
                    
                    runningBalance += position.NetProfit;

                    json.AppendLine("    {");
                    json.AppendLine($"        \"ticket\": {position.PositionId},");
                    json.AppendLine($"        \"symbol\": \"{position.SymbolName}\",");
                    json.AppendLine($"        \"direction\": \"{(position.TradeType == TradeType.Buy ? "BUY" : "SELL")}\",");
                    json.AppendLine($"        \"entry_price\": {position.EntryPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"        \"closing_price\": {position.ClosingPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"        \"lot_size\": {(position.VolumeInUnits / 100000.0).ToString("F2", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"        \"open_time\": \"{position.EntryTime:yyyy-MM-ddTHH:mm:ss}\",");
                    json.AppendLine($"        \"close_time\": \"{position.ClosingTime:yyyy-MM-ddTHH:mm:ss}\",");
                    json.AppendLine($"        \"status\": \"CLOSED\",");
                    json.AppendLine($"        \"profit\": {position.NetProfit.ToString("F2", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"        \"pips\": {position.Pips.ToString("F1", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"        \"balance_after\": {runningBalance.ToString("F2", CultureInfo.InvariantCulture)}");
                    
                    currentIndex++;
                    if (currentIndex < totalCount)
                        json.AppendLine("    },");
                    else
                        json.AppendLine("    }");
                }
                
                // Add OPEN positions
                for (int i = 0; i < openPositions.Count; i++)
                {
                    var position = openPositions[i];
                    
                    // Calculate current P/L for open position
                    double currentPnL = position.NetProfit;

                    json.AppendLine("    {");
                    json.AppendLine($"        \"ticket\": {position.Id},");
                    json.AppendLine($"        \"symbol\": \"{position.SymbolName}\",");
                    json.AppendLine($"        \"direction\": \"{(position.TradeType == TradeType.Buy ? "BUY" : "SELL")}\",");
                    json.AppendLine($"        \"entry_price\": {position.EntryPrice.ToString(CultureInfo.InvariantCulture)},");
                    json.AppendLine($"        \"lot_size\": {(position.VolumeInUnits / 100000.0).ToString("F2", CultureInfo.InvariantCulture)},");
                    json.AppendLine($"        \"open_time\": \"{position.EntryTime:yyyy-MM-ddTHH:mm:ss}\",");
                    json.AppendLine($"        \"status\": \"OPEN\",");
                    json.AppendLine($"        \"profit\": {currentPnL.ToString("F2", CultureInfo.InvariantCulture)},");
                    
                    // Add SL/TP if set
                    if (position.StopLoss.HasValue)
                        json.AppendLine($"        \"stop_loss\": {position.StopLoss.Value.ToString(CultureInfo.InvariantCulture)},");
                    if (position.TakeProfit.HasValue)
                        json.AppendLine($"        \"take_profit\": {position.TakeProfit.Value.ToString(CultureInfo.InvariantCulture)},");
                    
                    json.AppendLine($"        \"balance_after\": {runningBalance.ToString("F2", CultureInfo.InvariantCulture)}");
                    
                    currentIndex++;
                    if (currentIndex < totalCount)
                        json.AppendLine("    },");
                    else
                        json.AppendLine("    }");
                }

                json.AppendLine("]");

                // Write to file
                File.WriteAllText(JsonFilePath, json.ToString());

                Print($"✅ Synced {closedPositions.Count} closed + {openPositions.Count} open to JSON");
                Print($"💰 Balance: ${runningBalance:F2} | Open P/L: ${openPositions.Sum(p => p.NetProfit):F2}");
                
                _lastUpdate = DateTime.Now;
            }
            catch (Exception ex)
            {
                Print($"❌ Sync error: {ex.Message}");
            }
        }
    }
}
