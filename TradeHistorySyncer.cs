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
                // ENHANCED DEBUG - Print EVERYTHING from History API
                Print("═══════════════════════════════════════════════════════");
                Print($"🔍 FULL HISTORY DEBUG");
                Print($"   Account: {Account.Number}");
                Print($"   History NULL? {History == null}");
                Print($"   History.Count = {History?.Count ?? 0}");
                Print("═══════════════════════════════════════════════════════");
                
                // Get all closed positions from History
                if (History == null || History.Count == 0)
                {
                    Print("⚠️ No history available");
                    return;
                }
                
                // Print EVERY trade in History
                int counter = 0;
                foreach (var trade in History)
                {
                    counter++;
                    Print($"  [{counter}] Ticket: {trade.PositionId} | {trade.SymbolName} | {trade.EntryTime:yyyy-MM-dd HH:mm} → {trade.ClosingTime:yyyy-MM-dd HH:mm} | P/L: ${trade.NetProfit:F2}");
                }
                
                Print($"📊 Total trades enumerated: {counter}");
                Print("═══════════════════════════════════════════════════════");
                
                var closedPositions = History.OrderBy(x => x.ClosingTime).ToList();
                
                Print($"📊 Found {closedPositions.Count} closed positions in history");

                var json = new StringBuilder();
                json.AppendLine("[");

                double runningBalance = 1000.0; // Initial balance

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
                    
                    if (i < closedPositions.Count - 1)
                        json.AppendLine("    },");
                    else
                        json.AppendLine("    }");
                }

                json.AppendLine("]");

                // Write to file
                File.WriteAllText(JsonFilePath, json.ToString());

                Print($"✅ Synced {closedPositions.Count} trades to JSON");
                Print($"💰 Current balance: ${runningBalance:F2}");
                
                _lastUpdate = DateTime.Now;
            }
            catch (Exception ex)
            {
                Print($"❌ Sync error: {ex.Message}");
            }
        }
    }
}
