using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Collections.Generic;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace cAlgo.Robots
{
    /// <summary>
    /// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    /// 🛡️ Python Signal Executor V3.1 - Unified Risk Management
    /// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    /// 
    /// NEW IN V3.1:
    /// - Reads SUPER_CONFIG.json (shared with Python)
    /// - Checks kill switch (trading_disabled.flag)
    /// - Enforces max position limits
    /// - Validates daily loss limits
    /// - Sends branded rejection alerts to Telegram
    /// 
    /// ✨ Glitch in Matrix by ФорексГод ✨
    /// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    /// </summary>
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class PythonSignalExecutorV31 : Robot
    {
        [Parameter("Signal File Path", DefaultValue = "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/signals.json")]
        public string SignalFilePath { get; set; }

        [Parameter("Config File Path", DefaultValue = "/Users/forexgod/Desktop/Glitch in Matrix/trading-ai-agent apollo/SUPER_CONFIG.json")]
        public string ConfigFilePath { get; set; }

        [Parameter("Check Interval (seconds)", DefaultValue = 10)]
        public int CheckInterval { get; set; }

        private DateTime _lastFileCheck = DateTime.MinValue;
        private string _lastProcessedSignal = "";
        private SuperConfig _config;
        private DateTime _dailyResetTime = DateTime.UtcNow.Date;
        private double _dailyStartBalance = 0;

        protected override void OnStart()
        {
            Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            Print("🤖 Python Signal Executor V3.1 - Unified Risk");
            Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            Print($"📁 Signals: {SignalFilePath}");
            Print($"⚙️  Config: {ConfigFilePath}");
            Print($"⏱️ Check interval: {CheckInterval}s");
            
            // Load SUPER_CONFIG.json
            LoadConfiguration();
            
            // Initialize daily balance
            _dailyStartBalance = Account.Balance;
            
            Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            Print("✨ Glitch in Matrix by ФорексГод ✨");
            Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            
            Timer.Start(CheckInterval);
        }

        protected override void OnTimer()
        {
            try
            {
                // CRITICAL: Check kill switch FIRST
                if (IsKillSwitchActive())
                {
                    Print("🔴 KILL SWITCH ACTIVE - Trading disabled");
                    return;
                }
                
                // Reset daily balance at midnight UTC
                if (DateTime.UtcNow.Date > _dailyResetTime)
                {
                    _dailyResetTime = DateTime.UtcNow.Date;
                    _dailyStartBalance = Account.Balance;
                    Print($"📅 Daily reset - New balance: ${_dailyStartBalance:F2}");
                }
                
                // Check daily loss limit
                if (!ValidateDailyLoss())
                {
                    return;  // Daily loss limit reached
                }
                
                // Manage existing positions
                ManageOpenPositions();
                
                // Export active positions for Telegram sync
                ExportActivePositions();
                
                // Check for new signals
                if (!File.Exists(SignalFilePath))
                    return;
                
                var fileInfo = new FileInfo(SignalFilePath);
                if (fileInfo.LastWriteTime <= _lastFileCheck)
                    return;
                
                _lastFileCheck = fileInfo.LastWriteTime;
                
                var json = File.ReadAllText(SignalFilePath);
                var signal = JsonSerializer.Deserialize<TradeSignal>(json);
                
                if (signal == null)
                {
                    Print("❌ Failed to deserialize signal");
                    return;
                }
                
                // Check if already processed
                string processedSignalsFile = Path.Combine(Path.GetDirectoryName(SignalFilePath), "processed_signals.txt");
                if (File.Exists(processedSignalsFile))
                {
                    string[] processedSignals = File.ReadAllLines(processedSignalsFile);
                    if (processedSignals.Contains(signal.SignalId))
                    {
                        return;  // Already processed
                    }
                }
                
                if (signal.SignalId == _lastProcessedSignal)
                {
                    return;  // Already processed in this session
                }
                
                _lastProcessedSignal = signal.SignalId;
                Print($"\n📊 NEW SIGNAL RECEIVED: {signal.Symbol} {signal.Direction.ToUpper()}");
                
                // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                // V3.1 UNIFIED RISK VALIDATION
                // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                
                if (!ValidateNewTrade(signal))
                {
                    Print("🛑 TRADE REJECTED by Unified Risk Manager");
                    MarkSignalAsProcessed(signal.SignalId);
                    return;
                }
                
                // All validations passed - execute trade
                ExecuteSignal(signal);
                MarkSignalAsProcessed(signal.SignalId);
                
            }
            catch (Exception ex)
            {
                Print($"❌ Error in OnTimer: {ex.Message}");
            }
        }

        private void LoadConfiguration()
        {
            try
            {
                if (!File.Exists(ConfigFilePath))
                {
                    Print($"⚠️  Config file not found: {ConfigFilePath}");
                    Print("   Using default parameters");
                    _config = GetDefaultConfig();
                    return;
                }
                
                var json = File.ReadAllText(ConfigFilePath);
                _config = JsonSerializer.Deserialize<SuperConfig>(json);
                
                if (_config == null)
                {
                    Print("❌ Failed to deserialize config");
                    _config = GetDefaultConfig();
                    return;
                }
                
                Print("✅ SUPER_CONFIG.json loaded:");
                Print($"   Risk per trade: {_config.RiskManagement.RiskPerTradePercent}%");
                Print($"   Max positions: {_config.PositionLimits.MaxOpenPositions}");
                Print($"   Daily loss limit: {_config.DailyLimits.MaxDailyLossPercent}%");
                Print($"   Kill switch: {(_config.KillSwitch.Enabled ? "ENABLED" : "DISABLED")}");
            }
            catch (Exception ex)
            {
                Print($"❌ Error loading config: {ex.Message}");
                _config = GetDefaultConfig();
            }
        }

        private SuperConfig GetDefaultConfig()
        {
            return new SuperConfig
            {
                RiskManagement = new RiskManagement { RiskPerTradePercent = 5.0 },
                PositionLimits = new PositionLimits { MaxOpenPositions = 15 },
                DailyLimits = new DailyLimits { MaxDailyLossPercent = 10.0 },
                KillSwitch = new KillSwitch { Enabled = true, TriggerDailyLossPercent = 10.0, FlagFile = "trading_disabled.flag" }
            };
        }

        private bool IsKillSwitchActive()
        {
            if (!_config.KillSwitch.Enabled)
                return false;
            
            string killSwitchPath = Path.Combine(Path.GetDirectoryName(SignalFilePath), _config.KillSwitch.FlagFile);
            
            if (File.Exists(killSwitchPath))
            {
                Print($"🔴 KILL SWITCH DETECTED: {killSwitchPath}");
                return true;
            }
            
            return false;
        }

        private bool ValidateDailyLoss()
        {
            double currentBalance = Account.Balance;
            double dailyPnL = currentBalance - _dailyStartBalance;
            double dailyLossPct = (dailyPnL / _dailyStartBalance) * 100;
            
            if (dailyLossPct <= -_config.DailyLimits.MaxDailyLossPercent)
            {
                Print($"🛑 DAILY LOSS LIMIT REACHED");
                Print($"   Current: {dailyLossPct:F2}%");
                Print($"   Limit: {_config.DailyLimits.MaxDailyLossPercent}%");
                
                // Activate kill switch
                ActivateKillSwitch($"Daily loss {dailyLossPct:F2}% >= {_config.DailyLimits.MaxDailyLossPercent}%");
                
                return false;
            }
            
            return true;
        }

        private bool ValidateNewTrade(TradeSignal signal)
        {
            // 1. Check position count
            int openPositions = Positions.Count(p => p.Label.StartsWith("Glitch Matrix"));
            
            if (openPositions >= _config.PositionLimits.MaxOpenPositions)
            {
                Print($"⛔ MAX POSITIONS REACHED: {openPositions}/{_config.PositionLimits.MaxOpenPositions}");
                SendRejectionAlert(signal.Symbol, signal.Direction, $"Max positions reached ({openPositions}/{_config.PositionLimits.MaxOpenPositions})");
                return false;
            }
            
            // 2. Check daily loss warning level
            double currentBalance = Account.Balance;
            double dailyPnL = currentBalance - _dailyStartBalance;
            double dailyLossPct = (dailyPnL / _dailyStartBalance) * 100;
            
            if (dailyLossPct <= -7.0)  // Warning threshold
            {
                Print($"⚠️  WARNING: Daily loss at {dailyLossPct:F2}%");
                Print($"   Close to limit ({_config.DailyLimits.MaxDailyLossPercent}%)");
            }
            
            // 3. All checks passed
            Print($"✅ RISK VALIDATION PASSED:");
            Print($"   Positions: {openPositions}/{_config.PositionLimits.MaxOpenPositions}");
            Print($"   Daily P&L: {dailyLossPct:F2}%");
            
            return true;
        }

        private void ActivateKillSwitch(string reason)
        {
            try
            {
                string killSwitchPath = Path.Combine(Path.GetDirectoryName(SignalFilePath), _config.KillSwitch.FlagFile);
                
                File.WriteAllText(killSwitchPath, $"ACTIVATED: {DateTime.UtcNow}\nReason: {reason}");
                
                Print($"🔴 KILL SWITCH ACTIVATED");
                Print($"   Reason: {reason}");
                Print($"   File: {killSwitchPath}");
                
                // TODO: Send Telegram alert (would need HTTP implementation)
            }
            catch (Exception ex)
            {
                Print($"❌ Error activating kill switch: {ex.Message}");
            }
        }

        private void SendRejectionAlert(string symbol, string direction, string reason)
        {
            Print($"⛔ TRADE REJECTED");
            Print($"   Symbol: {symbol} {direction}");
            Print($"   Reason: {reason}");
            Print($"   ━━━━━━━━━━━━━━━━━━━━");
            Print($"   ✨ Glitch in Matrix by ФорексГод ✨");
            Print($"   🧠 AI-Powered • 💎 Smart Money");
            
            // TODO: Implement Telegram notification
            // Would require HTTP POST to Telegram API
        }

        private void ExecuteSignal(TradeSignal signal)
        {
            var symbol = Symbols.GetSymbol(signal.Symbol);
            if (symbol == null)
            {
                Print($"❌ Symbol not found: {signal.Symbol}");
                return;
            }
            
            var volume = CalculateVolume(signal, symbol);
            
            Print($"📈 Executing: {signal.Direction.ToUpper()} {volume} lots");
            Print($"   Entry: {signal.EntryPrice}");
            Print($"   SL: {signal.StopLoss} ({signal.StopLossPips:F1} pips)");
            Print($"   TP: {signal.TakeProfit} ({signal.TakeProfitPips:F1} pips)");
            Print($"   Risk: {_config.RiskManagement.RiskPerTradePercent}%");
            
            var tradeType = signal.Direction.ToLower() == "buy" ? TradeType.Buy : TradeType.Sell;
            
            var result = ExecuteMarketOrder(
                tradeType,
                symbol.Name,
                volume,
                "Glitch Matrix v3.1",
                signal.StopLossPips,
                signal.TakeProfitPips
            );
            
            if (result.IsSuccessful)
            {
                Print($"✅ TRADE EXECUTED SUCCESSFULLY");
                Print($"   Ticket: {result.Position.Id}");
                Print($"   Volume: {symbol.VolumeInUnitsToQuantity(volume)} lots");
                Print($"   Entry: {result.Position.EntryPrice}");
                Print($"   ✨ Glitch in Matrix by ФорексГод ✨");
            }
            else
            {
                Print($"❌ TRADE FAILED: {result.Error}");
            }
        }

        private long CalculateVolume(TradeSignal signal, Symbol symbol)
        {
            // Use risk percentage from SUPER_CONFIG.json
            var balance = Account.Balance;
            var riskAmount = balance * (_config.RiskManagement.RiskPerTradePercent / 100.0);
            
            var slDistance = Math.Abs(signal.EntryPrice - signal.StopLoss);
            var slPips = slDistance / symbol.PipSize;
            
            var volumeInUnits = riskAmount / (slPips * symbol.PipValue);
            var volumeInLots = (long)symbol.NormalizeVolumeInUnits((long)volumeInUnits, RoundingMode.Down);
            
            if (volumeInLots < (long)symbol.VolumeInUnitsMin)
                volumeInLots = (long)symbol.VolumeInUnitsMin;
            if (volumeInLots > (long)symbol.VolumeInUnitsMax)
                volumeInLots = (long)symbol.VolumeInUnitsMax;
            
            Print($"💰 Risk: {_config.RiskManagement.RiskPerTradePercent}% = ${riskAmount:F2}");
            Print($"📊 Volume calculated: {symbol.VolumeInUnitsToQuantity(volumeInLots)} lots");
            
            return volumeInLots;
        }

        private void ManageOpenPositions()
        {
            foreach (var position in Positions)
            {
                if (!position.Label.StartsWith("Glitch Matrix"))
                    continue;
                
                var symbol = Symbols.GetSymbol(position.SymbolName);
                if (symbol == null) continue;
                
                double profitPips = position.Pips;
                
                // Auto close at +100 pips profit
                if (profitPips >= 100.0)
                {
                    Print($"🎯 AUTO-CLOSE TRIGGERED: {position.SymbolName} at +{profitPips:F1} pips");
                    ClosePosition(position);
                    Print($"✅ POSITION CLOSED: ${position.NetProfit:F2} profit");
                }
            }
        }

        private void ExportActivePositions()
        {
            try
            {
                var positionsList = new List<object>();
                foreach (var position in Positions)
                {
                    if (!position.Label.StartsWith("Glitch Matrix"))
                        continue;
                    
                    positionsList.Add(new
                    {
                        ticket = position.Id,
                        symbol = position.SymbolName,
                        direction = position.TradeType.ToString().ToLower(),
                        volume = position.VolumeInUnits,
                        entry_price = position.EntryPrice,
                        current_price = position.TradeType == TradeType.Buy ? Symbol.Bid : Symbol.Ask,
                        unrealized_profit = position.NetProfit,
                        pips = position.Pips,
                        open_time = position.EntryTime.ToString("o")
                    });
                }
                
                string outputPath = Path.Combine(Path.GetDirectoryName(SignalFilePath), "active_positions.json");
                var json = JsonSerializer.Serialize(positionsList, new JsonSerializerOptions { WriteIndented = true });
                File.WriteAllText(outputPath, json);
            }
            catch (Exception ex)
            {
                Print($"⚠️  Error exporting positions: {ex.Message}");
            }
        }

        private void MarkSignalAsProcessed(string signalId)
        {
            try
            {
                string processedFile = Path.Combine(Path.GetDirectoryName(SignalFilePath), "processed_signals.txt");
                File.AppendAllText(processedFile, signalId + Environment.NewLine);
            }
            catch (Exception ex)
            {
                Print($"⚠️  Error marking signal as processed: {ex.Message}");
            }
        }
    }

    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    // Data Models (matching SUPER_CONFIG.json structure)
    // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    
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
        public string Timestamp { get; set; }
    }

    public class SuperConfig
    {
        public RiskManagement RiskManagement { get; set; }
        public PositionLimits PositionLimits { get; set; }
        public DailyLimits DailyLimits { get; set; }
        public KillSwitch KillSwitch { get; set; }
    }

    public class RiskManagement
    {
        public double RiskPerTradePercent { get; set; }
    }

    public class PositionLimits
    {
        public int MaxOpenPositions { get; set; }
    }

    public class DailyLimits
    {
        public double MaxDailyLossPercent { get; set; }
    }

    public class KillSwitch
    {
        public bool Enabled { get; set; }
        public double TriggerDailyLossPercent { get; set; }
        public string FlagFile { get; set; }
    }
}
