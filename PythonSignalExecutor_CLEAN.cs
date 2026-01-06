using System;
using System.IO;
using System.Collections.Generic;
using System.Text.Json;
using cAlgo.API;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class PythonSignalExecutor : Robot
    {
        [Parameter("Signal File Path", DefaultValue = "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/signals.json")]
        public string SignalFilePath { get; set; }

        [Parameter("Check Interval (seconds)", DefaultValue = 10)]
        public int CheckInterval { get; set; }

        [Parameter("Max Risk %", DefaultValue = 2.0)]
        public double MaxRiskPercent { get; set; }

        [Parameter("Auto Close at Profit (pips)", DefaultValue = 100.0)]
        public double AutoCloseProfitPips { get; set; }

        [Parameter("Move SL to Breakeven at (pips)", DefaultValue = 50.0)]
        public double BreakevenTriggerPips { get; set; }

        private DateTime _lastFileCheck = DateTime.MinValue;
        private string _lastProcessedSignal = "";
        private string _processedSignalsFile = "";

        protected override void OnStart()
        {
            Print("🤖 Python Signal Executor Started (Swing Trading Mode)");
            Print($"📁 Monitoring: {SignalFilePath}");
            Print($"⏱️ Check interval: {CheckInterval}s");
            Print($"💰 Max risk: {MaxRiskPercent}%");
            Print($"🎯 Auto-close at: +{AutoCloseProfitPips} pips");
            Print($"🔒 Breakeven trigger: +{BreakevenTriggerPips} pips");
            
            // Set processed signals file in same directory as signal file
            var signalDir = Path.GetDirectoryName(SignalFilePath);
            _processedSignalsFile = Path.Combine(signalDir, "processed_signals.txt");
            Print($"💾 Tracking file: {_processedSignalsFile}");
            
            // Load last processed signal from persistent storage
            LoadLastProcessedSignal();
            
            Timer.Start(CheckInterval);
        }
        
        private void LoadLastProcessedSignal()
        {
            try
            {
                if (File.Exists(_processedSignalsFile))
                {
                    var lines = File.ReadAllLines(_processedSignalsFile);
                    if (lines.Length > 0)
                    {
                        _lastProcessedSignal = lines[lines.Length - 1].Trim();
                        Print($"📖 Loaded last processed signal: {_lastProcessedSignal}");
                    }
                }
            }
            catch (Exception ex)
            {
                Print($"⚠️  Could not load processed signals: {ex.Message}");
            }
        }
        
        private void SaveProcessedSignal(string signalId)
        {
            try
            {
                // Append signal ID to file (keep history)
                File.AppendAllText(_processedSignalsFile, signalId + Environment.NewLine);
                Print($"💾 Saved processed signal: {signalId}");
            }
            catch (Exception ex)
            {
                Print($"⚠️  Could not save processed signal: {ex.Message}");
            }
        }

        protected override void OnTimer()
        {
            try
            {
                // FIRST: Manage existing positions
                ManageOpenPositions();
                
                // Export active positions for Telegram sync
                ExportActivePositions();
                
                // THEN: Check for new signals
                if (!File.Exists(SignalFilePath))
                    return;
                    
                var fileInfo = new FileInfo(SignalFilePath);
                if (fileInfo.LastWriteTime <= _lastFileCheck)
                    return;
                    
                _lastFileCheck = fileInfo.LastWriteTime;
                var json = File.ReadAllText(SignalFilePath);
                Print($"🔍 Raw JSON: {json}");
                
                var signal = JsonSerializer.Deserialize<TradeSignal>(json);
                
                if (signal == null)
                {
                    Print("❌ Failed to deserialize signal (NULL)");
                    return;
                }
                
                Print($"✅ Signal deserialized: {signal.SignalId}");
                
                if (signal.SignalId == _lastProcessedSignal)
                {
                    Print($"⏭️  Signal already processed: {signal.SignalId}");
                    return;
                }
                
                _lastProcessedSignal = signal.SignalId;
                SaveProcessedSignal(signal.SignalId); // Save to persistent storage
                
                Print($"📊 NEW SIGNAL RECEIVED: {signal.Symbol} {signal.Direction.ToUpper()}");
                Print($"   Strategy: {signal.StrategyType}");
                Print($"   Entry: {signal.EntryPrice}");
                Print($"   SL: {signal.StopLoss}");
                Print($"   TP: {signal.TakeProfit}");
                Print($"   R:R: 1:{signal.RiskReward}");
                
                ExecuteSignal(signal);
                
                // Clear signal file after processing
                try
                {
                    File.Delete(SignalFilePath);
                    Print($"🗑️  Signal file cleared");
                }
                catch (Exception deleteEx)
                {
                    Print($"⚠️  Could not delete signal file: {deleteEx.Message}");
                }
            }
            catch (Exception ex)
            {
                Print($"❌ ERROR: {ex.Message}");
            }
        }

        private void ExportActivePositions()
        {
            try
            {
                var positionsList = new List<object>();
                foreach (var position in Positions)
                {
                    var symbol = Symbols.GetSymbol(position.SymbolName);
                    if (symbol == null)
                        continue;

                    var exportObj = new {
                        symbol = position.SymbolName,
                        direction = position.TradeType.ToString().ToLower(),
                        entry_price = position.EntryPrice,
                        volume = position.VolumeInUnits,
                        opened_at = position.EntryTime,
                        stop_loss = position.StopLoss,
                        take_profit = position.TakeProfit
                    };
                    positionsList.Add(exportObj);
                }
                
                var exportPath = SignalFilePath.Replace("signals.json", "active_positions.json");
                var options = new JsonSerializerOptions { WriteIndented = true };
                File.WriteAllText(exportPath, JsonSerializer.Serialize(positionsList, options));
            }
            catch (Exception ex)
            {
                Print($"❌ Error exporting active positions: {ex.Message}");
            }
        }

        private string MapSymbolName(string pythonSymbol)
        {
            // Symbol mapping: Python scanner names → IC Markets cTrader names
            
            // Disabled symbols
            if (pythonSymbol == "PIUSDT") return null;
            
            // Oil mapping: USOIL → WTIUSD
            if (pythonSymbol == "USOIL") return "WTIUSD";
            
            // All other symbols work as-is
            return pythonSymbol;
        }

        private void ManageOpenPositions()
        {
            foreach (var position in Positions)
            {
                if (!position.Label.StartsWith("Glitch Matrix"))
                    continue;

                var symbol = Symbols.GetSymbol(position.SymbolName);
                if (symbol == null)
                    continue;

                var currentPrice = position.TradeType == TradeType.Buy ? symbol.Bid : symbol.Ask;
                var profitPips = (position.TradeType == TradeType.Buy 
                    ? currentPrice - position.EntryPrice 
                    : position.EntryPrice - currentPrice) / symbol.PipSize;

                // Just monitor - no auto-close or breakeven modifications
                if (profitPips >= AutoCloseProfitPips)
                {
                    Print($"🎯 Position {position.SymbolName} at +{profitPips:F1} pips profit");
                }
            }
        }

        private void LogTradeClosure(Position position, double profitPips, string reason)
        {
            try
            {
                var closurePath = SignalFilePath.Replace("signals.json", "trade_closures.json");
                
                var closure = new
                {
                    position_id = position.Id.ToString(),
                    symbol = position.SymbolName,
                    direction = position.TradeType.ToString().ToLower(),
                    entry_price = position.EntryPrice,
                    close_price = position.TradeType == TradeType.Buy 
                        ? Symbols.GetSymbol(position.SymbolName).Bid 
                        : Symbols.GetSymbol(position.SymbolName).Ask,
                    profit_pips = profitPips,
                    profit_usd = position.NetProfit,
                    reason = reason,
                    closed_at = DateTime.Now,
                    duration_hours = (DateTime.Now - position.EntryTime).TotalHours
                };
                
                var options = new JsonSerializerOptions { WriteIndented = true };
                File.WriteAllText(closurePath, JsonSerializer.Serialize(closure, options));
            }
            catch (Exception ex)
            {
                Print($"⚠️  Could not log closure: {ex.Message}");
            }
        }

        private void ExecuteSignal(TradeSignal signal)
        {
            // Map Python symbol names to IC Markets cTrader names
            var pythonSymbol = signal.Symbol.Replace("/", "");
            var symbolName = MapSymbolName(pythonSymbol);
            
            if (string.IsNullOrEmpty(symbolName))
            {
                Print($"❌ Symbol disabled or not available: {pythonSymbol}");
                return;
            }
            
            var symbol = Symbols.GetSymbol(symbolName);
            
            if (symbol == null)
            {
                Print($"❌ Symbol not found in cTrader: {symbolName} (from {pythonSymbol})");
                Print($"   💡 Check Market Watch and verify symbol name");
                return;
            }

            // ✅ CHECK IF POSITION ALREADY EXISTS FOR THIS SIGNAL
            foreach (var position in Positions)
            {
                if (position.Label.Contains(signal.SignalId) || 
                    (position.SymbolName == symbolName && 
                     position.Label.StartsWith("Glitch Matrix")))
                {
                    Print($"⏭️  SKIPPED: Position already exists for {symbolName}");
                    Print($"   Existing Position ID: {position.Id}");
                    Print($"   Signal ID: {signal.SignalId}");
                    return; // Don't execute duplicate
                }
            }

            var volume = CalculateVolume(signal, symbol);
            
            Print($"📈 Executing: {signal.Direction.ToUpper()} {volume} lots");

            var tradeType = signal.Direction.ToLower() == "bullish" || signal.Direction.ToLower() == "buy" 
                ? TradeType.Buy 
                : TradeType.Sell;

            var result = ExecuteMarketOrder(
                tradeType,
                symbolName,
                volume,
                $"Glitch Matrix - {signal.StrategyType} - {signal.SignalId}",
                signal.StopLossPips,
                signal.TakeProfitPips
            );

            if (result.IsSuccessful)
            {
                Print($"✅ ORDER EXECUTED: {result.Position.Id}");
                Print($"   Volume: {volume} lots");
                Print($"   Entry: {result.Position.EntryPrice}");
                
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
            var balance = Account.Balance;
            var riskAmount = balance * (MaxRiskPercent / 100.0);
            
            var slDistance = Math.Abs(signal.EntryPrice - signal.StopLoss);
            var slPips = slDistance / symbol.PipSize;
            
            var volumeInUnits = riskAmount / (slPips * symbol.PipValue);
            var volumeInLots = (long)symbol.NormalizeVolumeInUnits((long)volumeInUnits, RoundingMode.Down);
            
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
