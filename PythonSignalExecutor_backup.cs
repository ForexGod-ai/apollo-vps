using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class PythonSignalExecutor : Robot
    {
        [Parameter("Signal File Path", DefaultValue = "/Users/forexgod/Desktop/trading-ai-agent/signals.json")]
        public string SignalFilePath { get; set; }

        [Parameter("Check Interval (seconds)", DefaultValue = 10)]
        public int CheckInterval { get; set; }

        [Parameter("Max Risk %", DefaultValue = 2.0)]
        public double MaxRiskPercent { get; set; }

        private DateTime _lastFileCheck = DateTime.MinValue;
        private string _lastProcessedSignal = "";

        protected override void OnStart()
        {
            Print("🤖 Python Signal Executor Started");
            Print($"📁 Monitoring: {SignalFilePath}");
            Print($"⏱️ Check interval: {CheckInterval}s");
            Print($"💰 Max risk: {MaxRiskPercent}%");
            
            Timer.Start(CheckInterval);
        }

        protected override void OnTimer()
        {
            try
            {
                if (!File.Exists(SignalFilePath))
                {
                    return;
                }

                // Read signal file
                var fileInfo = new FileInfo(SignalFilePath);
                if (fileInfo.LastWriteTime <= _lastFileCheck)
                {
                    return; // No new signals
                }

                _lastFileCheck = fileInfo.LastWriteTime;
                
                var json = File.ReadAllText(SignalFilePath);
                var signal = JsonSerializer.Deserialize<TradeSignal>(json);

                if (signal == null || signal.SignalId == _lastProcessedSignal)
                {
                    return; // Already processed
                }

                Print($"📊 NEW SIGNAL RECEIVED: {signal.Symbol} {signal.Direction.ToUpper()}");
                Print($"   Strategy: {signal.StrategyType}");
                Print($"   Entry: {signal.EntryPrice}");
                Print($"   SL: {signal.StopLoss}");
                Print($"   TP: {signal.TakeProfit}");
                Print($"   R:R: 1:{signal.RiskReward}");

                // Execute trade
                ExecuteSignal(signal);
                
                _lastProcessedSignal = signal.SignalId;
            }
            catch (Exception ex)
            {
                Print($"❌ ERROR: {ex.Message}");
            }
        }

        private void ExecuteSignal(TradeSignal signal)
        {
            var symbolName = signal.Symbol.Replace("/", "");
            var symbol = Symbols.GetSymbol(symbolName);
            
            if (symbol == null)
            {
                Print($"❌ Symbol not found: {symbolName}");
                return;
            }

            // Calculate volume based on risk
            var volume = CalculateVolume(signal, symbol);
            
            Print($"📈 Executing: {signal.Direction.ToUpper()} {volume} lots");

            var tradeType = signal.Direction.ToLower() == "bullish" || signal.Direction.ToLower() == "buy" 
                ? TradeType.Buy 
                : TradeType.Sell;

            var result = ExecuteMarketOrder(
                tradeType,
                symbolName,
                volume,
                $"Glitch Matrix - {signal.StrategyType}",
                signal.StopLossPips,
                signal.TakeProfitPips
            );

            if (result.IsSuccessful)
            {
                Print($"✅ ORDER EXECUTED: {result.Position.Id}");
                Print($"   Volume: {volume} lots");
                Print($"   Entry: {result.Position.EntryPrice}");
                
                // Send confirmation to Python (write to log file)
                var confirmationPath = SignalFilePath.Replace("signals.json", "trade_confirmations.json");
                var confirmation = new
                {
                    signal_id = signal.SignalId,
                    position_id = result.Position.Id.ToString(),
                    symbol = signal.Symbol,
                    direction = signal.Direction,
                    volume = volume,
                    entry_price = result.Position.EntryPrice,
                    sl = result.Position.StopLoss,
                    tp = result.Position.TakeProfit,
                    executed_at = DateTime.Now,
                    status = "executed"
                };
                
                var options = new JsonSerializerOptions { WriteIndented = true };
                File.WriteAllText(confirmationPath, JsonSerializer.Serialize(confirmation, options));
            }
            else
            {
                Print($"❌ ORDER FAILED: {result.Error}");
            }
        }

        private long CalculateVolume(TradeSignal signal, Symbol symbol)
        {
            // Calculate volume based on max risk
            var balance = Account.Balance;
            var riskAmount = balance * (MaxRiskPercent / 100.0);
            
            var slDistance = Math.Abs(signal.EntryPrice - signal.StopLoss);
            var slPips = slDistance / symbol.PipSize;
            
            var volumeInUnits = riskAmount / (slPips * symbol.PipValue);
            var volumeInLots = (long)symbol.NormalizeVolumeInUnits((long)volumeInUnits, RoundingMode.Down);
            
            // Min/Max volume check
            if (volumeInLots < (long)symbol.VolumeInUnitsMin)
                volumeInLots = (long)symbol.VolumeInUnitsMin;
            if (volumeInLots > (long)symbol.VolumeInUnitsMax)
                volumeInLots = (long)symbol.VolumeInUnitsMax;
            
            Print($"💰 Risk: {MaxRiskPercent}% = ${riskAmount:F2}");
            Print($"📊 Volume calculated: {symbol.VolumeInUnitsToQuantity(volumeInLots)} lots");
            
            return volumeInLots;
        }

        protected override void OnStop()
        {
            Print("🛑 Python Signal Executor Stopped");
        }
    }

    // Signal data class
    public class TradeSignal
    {
        public string SignalId { get; set; }
        public string Symbol { get; set; }
        public string Direction { get; set; }
        public string StrategyType { get; set; }
        public double EntryPrice { get; set; }
        public double StopLoss { get; set; }
        public double TakeProfit { get; set; }
        public double StopLossPips { get; set; }
        public double TakeProfitPips { get; set; }
        public double RiskReward { get; set; }
        public DateTime Timestamp { get; set; }
    }
}
