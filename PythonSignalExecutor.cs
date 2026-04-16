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
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.FullAccess)]
    public class PythonSignalExecutor : Robot
    {
        [Parameter("Signal File Path", DefaultValue = @"C:\Users\Administrator\Desktop\Glitch in Matrix\trading-ai-agent apollo\signals.json")]
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
        private HashSet<string> _sessionProcessedSignals = new HashSet<string>();

        protected override void OnStart()
        {
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            Print("╔═══════════════════════════════════════════════════╗");
            Print("║                                                   ║");
            Print("║     🔱 ФорексГод — POCOVNICU TERMINAL 🔱    ║");
            Print("║     🏛️ Institutional Grade • MTF Perfection      ║");
            Print("║                                                   ║");
            Print("║     Python Signal Executor V10.4 ARRAY PROTOCOL ║");
            Print("║     D1 Bias → 4H Sync → 1H Entry                ║");
            Print("║                                                   ║");
            Print("╚═══════════════════════════════════════════════════╝");
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            Print("");
            Print("📋 CONFIGURATION:");
            Print($"   📁 Signal File: {SignalFilePath}");
            Print($"   ⏱️  Check Interval: {CheckInterval}s");
            Print($"   💰 Max Risk: {MaxRiskPercent}%");
            Print($"   🎯 Auto-Close: +{AutoCloseProfitPips} pips");
            Print($"   🔒 Breakeven: +{BreakevenTriggerPips} pips");
            Print($"   📦 Protocol: V7.0 ARRAY (List<TradeSignal>)");
            Print("");
            
            // 🚨 AUDIT: Validate signal file path
            var signalDir = Path.GetDirectoryName(SignalFilePath);
            if (!Directory.Exists(signalDir))
            {
                Print($"❌ ERROR: Signal directory does not exist: {signalDir}");
                Print($"⚠️  Bot will NOT receive signals! Check path configuration.");
            }
            else
            {
                Print($"✅ Signal directory validated: {signalDir}");
            }
            
            Print("🔗 MATRIX SYNC: Connected to Python V7.0 Array Protocol");
            Print("✅ System initialized - Ready for signals (ARRAY FORMAT)");
            Print("");
            
            Timer.Start(CheckInterval);
        }

        protected override void OnTimer()
        {
            try
            {
                // ✅ V10.2 LIVE SYNC: Write account status FIRST (before anything else)
                WriteAccountStatus();
                
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
                
                string json;
                try
                {
                    json = File.ReadAllText(SignalFilePath);
                }
                catch (IOException ioEx)
                {
                    // File might be locked by Python writing — skip this cycle, retry next
                    Print($"⚠️  File locked (Python writing?), retry next cycle: {ioEx.Message}");
                    return;
                }
                
                if (string.IsNullOrWhiteSpace(json))
                {
                    Print("⚠️  Signal file is empty, skipping");
                    return;
                }
                
                Print($"🔍 Raw JSON ({json.Length} chars): {json.Substring(0, Math.Min(json.Length, 200))}...");
                
                // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                // ✅ V7.0 ARRAY PROTOCOL: Deserialize as List<TradeSignal>
                // Python writes: [{signal1}, {signal2}, ...]
                // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                
                List<TradeSignal> signals = null;
                
                json = json.Trim();
                
                if (json.StartsWith("["))
                {
                    // ✅ V7.0 ARRAY FORMAT: [{...}, {...}, ...]
                    try
                    {
                        signals = JsonSerializer.Deserialize<List<TradeSignal>>(json);
                    }
                    catch (JsonException arrayEx)
                    {
                        Print($"❌ Array JSON parse error: {arrayEx.Message}");
                        Print($"⚠️  Attempting individual signal recovery...");
                        signals = TryRecoverSignalsFromArray(json);
                    }
                }
                else if (json.StartsWith("{"))
                {
                    // 🔄 BACKWARDS COMPATIBLE: Single object format (legacy)
                    try
                    {
                        var singleSignal = JsonSerializer.Deserialize<TradeSignal>(json);
                        if (singleSignal != null)
                        {
                            signals = new List<TradeSignal> { singleSignal };
                            Print($"🔄 Legacy single-object format detected, wrapped in array");
                        }
                    }
                    catch (JsonException singleEx)
                    {
                        Print($"❌ Single JSON parse error: {singleEx.Message}");
                    }
                }
                else
                {
                    Print($"❌ Unknown JSON format (first char: '{json[0]}')");
                    return;
                }
                
                if (signals == null || signals.Count == 0)
                {
                    Print("⚠️  No valid signals found in file (empty array or parse failure)");
                    // Delete empty/corrupt file to prevent re-processing
                    TryDeleteSignalFile();
                    return;
                }
                
                Print($"📦 V7.0 ARRAY: {signals.Count} signal(s) received");
                
                // ━━━ LOAD PERSISTENT PROCESSED LIST ━━━
                string processedSignalsFile = Path.Combine(Path.GetDirectoryName(SignalFilePath), "processed_signals.txt");
                HashSet<string> persistentProcessed = new HashSet<string>();
                if (File.Exists(processedSignalsFile))
                {
                    try
                    {
                        var lines = File.ReadAllLines(processedSignalsFile);
                        foreach (var line in lines)
                        {
                            if (!string.IsNullOrWhiteSpace(line))
                                persistentProcessed.Add(line.Trim());
                        }
                    }
                    catch { /* ignore read errors */ }
                }
                
                // ━━━ FOREACH: Process each signal individually ━━━
                int executed = 0;
                int skipped = 0;
                int failed = 0;
                
                foreach (var signal in signals)
                {
                    try
                    {
                        if (signal == null || string.IsNullOrEmpty(signal.SignalId))
                        {
                            Print($"⚠️  Skipping NULL/invalid signal in array");
                            skipped++;
                            continue;
                        }
                        
                        // Check persistent processed
                        if (persistentProcessed.Contains(signal.SignalId))
                        {
                            Print($"⏭️  Already processed (persistent): {signal.SignalId}");
                            skipped++;
                            continue;
                        }
                        
                        // Check session processed
                        if (_sessionProcessedSignals.Contains(signal.SignalId))
                        {
                            Print($"⏭️  Already processed (session): {signal.SignalId}");
                            skipped++;
                            continue;
                        }
                        
                        Print("");
                        Print($"━━━ PROCESSING SIGNAL {executed + skipped + failed + 1}/{signals.Count} ━━━");
                        Print($"📊 SIGNAL: {signal.Symbol} {signal.Direction?.ToUpper()} | ID: {signal.SignalId}");
                        Print($"   Strategy: {signal.StrategyType}");
                        Print($"   Entry: {signal.EntryPrice}");
                        Print($"   SL: {signal.StopLoss}");
                        Print($"   TP: {signal.TakeProfit}");
                        Print($"   R:R: 1:{signal.RiskReward}");
                        
                        // ━━━ V4.0 SMC INTELLIGENCE DISPLAY ━━━
                        if (signal.LiquiditySweep)
                            Print($"   💧 LIQUIDITY SWEEP: {signal.SweepType} detected (+{signal.ConfidenceBoost} conf)");
                        if (signal.OrderBlockUsed)
                            Print($"   📦 ORDER BLOCK: Entry refined (score {signal.OrderBlockScore}/10)");
                        
                        // ━━━ EXECUTE THE SIGNAL ━━━
                        ExecuteSignal(signal);
                        
                        // ━━━ Mark as processed (both session + persistent) ━━━
                        _sessionProcessedSignals.Add(signal.SignalId);
                        try
                        {
                            File.AppendAllText(processedSignalsFile, signal.SignalId + Environment.NewLine);
                        }
                        catch (Exception markEx)
                        {
                            Print($"⚠️  Could not mark as processed: {markEx.Message}");
                        }
                        
                        executed++;
                        Print($"✅ Signal {signal.SignalId} processed successfully");
                    }
                    catch (Exception signalEx)
                    {
                        // 🛡️ ERROR HANDLING: Skip corrupt signal, don't crash the bot!
                        Print($"❌ ERROR processing signal {signal?.SignalId ?? "UNKNOWN"}: {signalEx.Message}");
                        failed++;
                        // Continue to next signal — DON'T crash!
                    }
                }
                
                Print("");
                Print($"📊 BATCH RESULT: {executed} executed, {skipped} skipped, {failed} failed (of {signals.Count} total)");
                
                // ━━━ ATOMIC DELETE: Only AFTER processing entire array ━━━
                TryDeleteSignalFile();
            }
            catch (Exception ex)
            {
                Print($"❌ CRITICAL ERROR in OnTimer: {ex.Message}");
            }
        }
        
        /// <summary>
        /// V7.0: Try to recover individual signals from a corrupt array
        /// Splits by "},{" and tries to parse each one
        /// </summary>
        private List<TradeSignal> TryRecoverSignalsFromArray(string json)
        {
            var recovered = new List<TradeSignal>();
            try
            {
                // Remove outer brackets
                var inner = json.Trim().TrimStart('[').TrimEnd(']').Trim();
                if (string.IsNullOrEmpty(inner))
                    return recovered;
                
                // Split on "},{" boundary
                var parts = inner.Split(new[] { "},{" }, StringSplitOptions.RemoveEmptyEntries);
                
                for (int i = 0; i < parts.Length; i++)
                {
                    var part = parts[i].Trim();
                    // Re-add braces that were consumed by split
                    if (!part.StartsWith("{")) part = "{" + part;
                    if (!part.EndsWith("}")) part = part + "}";
                    
                    try
                    {
                        var signal = JsonSerializer.Deserialize<TradeSignal>(part);
                        if (signal != null && !string.IsNullOrEmpty(signal.SignalId))
                        {
                            recovered.Add(signal);
                            Print($"🔧 Recovered signal: {signal.SignalId}");
                        }
                    }
                    catch
                    {
                        Print($"⚠️  Could not recover signal part #{i + 1}");
                    }
                }
            }
            catch (Exception ex)
            {
                Print($"❌ Recovery failed: {ex.Message}");
            }
            
            Print($"🔧 Recovery result: {recovered.Count} signal(s) salvaged");
            return recovered;
        }
        
        /// <summary>
        /// Safely delete the signal file after processing
        /// </summary>
        private void TryDeleteSignalFile()
        {
            try
            {
                if (File.Exists(SignalFilePath))
                {
                    File.Delete(SignalFilePath);
                    Print($"🗑️  Signal file deleted (atomic cleanup)");
                }
            }
            catch (Exception deleteEx)
            {
                Print($"⚠️  Could not delete signal file: {deleteEx.Message}");
            }
        }

        private string MapSymbolName(string pythonSymbol)
        {
            // Symbol mapping: Python scanner names → IC Markets cTrader names
            // Verified with actual IC Markets cTrader account
            
            // Disabled symbols
            if (pythonSymbol == "PIUSDT") return null; // Not available in IC Markets
            
            // Oil mapping: USOIL → WTIUSD (verified)
            if (pythonSymbol == "USOIL") return "WTIUSD";
            
            // All other symbols work as-is:
            // - Forex pairs: GBPUSD, EURUSD, etc. ✓
            // - Gold: XAUUSD ✓
            // - Silver: XAGUSD ✓
            // - Bitcoin: BTCUSD ✓
            
            return pythonSymbol;
        }

        private void ManageOpenPositions()
        {
            foreach (var position in Positions)
            {
                // Skip positions not from this bot
                if (!position.Label.StartsWith("Glitch Matrix"))
                    continue;
                
                var symbol = Symbols.GetSymbol(position.SymbolName);
                if (symbol == null)
                    continue;
                
                double profitPips = position.Pips;
                
                // AUTO CLOSE at 100 pips profit
                if (profitPips >= AutoCloseProfitPips)
                {
                    Print($"🎯 AUTO-CLOSE TRIGGERED: {position.SymbolName} at +{profitPips:F1} pips");
                    ClosePosition(position);
                    Print($"✅ POSITION CLOSED: ${position.NetProfit:F2} profit");
                    LogTradeClosure(position, profitPips, "auto_close_100pips");
                    continue;
                }

                // TODO: BREAKEVEN FEATURE DISABLED (cTrader API deprecation)
                // Will be re-implemented later with new ProtectionType parameter
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
        
        private void WriteAccountStatus()
        {
            // ✅ V10.2 LIVE SYNC: Write real-time account status for Python Risk Manager
            // Eliminates desync (Python thinks 18 positions, cTrader has 2)
            try
            {
                var accountInfoPath = SignalFilePath.Replace("signals.json", "account_info.json");
                
                // Count only positions from this bot (not manual trades)
                int glitchPositionsCount = 0;
                foreach (var pos in Positions)
                {
                    if (pos.Label != null && pos.Label.StartsWith("Glitch Matrix"))
                        glitchPositionsCount++;
                }
                
                var accountStatus = new
                {
                    Status = "Running",
                    OpenPositionsCount = glitchPositionsCount,  // CRITICAL: Real count from cTrader
                    TotalPositions = Positions.Count,  // All positions (including manual)
                    Balance = Account.Balance,
                    Equity = Account.Equity,
                    FreeMargin = Account.FreeMargin,
                    MarginLevel = Account.MarginLevel,
                    UnrealizedPnL = Account.UnrealizedNetProfit,
                    Timestamp = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                    LastUpdate = DateTime.Now.ToString("HH:mm:ss")
                };
                
                var options = new JsonSerializerOptions { WriteIndented = true };
                File.WriteAllText(accountInfoPath, JsonSerializer.Serialize(accountStatus, options));
            }
            catch (Exception ex)
            {
                Print($"⚠️  Could not write account status: {ex.Message}");
            }
        }

        private void ExecuteSignal(TradeSignal signal)
        {
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            // 🛡️ V7.1 DUPLICATE POSITION GUARD — LAST LINE OF DEFENSE
            // Prevents opening multiple positions on the same symbol
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            var guardSymbol = signal.Symbol.Replace("/", "").Replace(" ", "");
            var guardMapped = MapSymbolName(guardSymbol);
            if (string.IsNullOrEmpty(guardMapped)) guardMapped = guardSymbol;
            
            bool alreadyHasPosition = false;
            foreach (var pos in Positions)
            {
                if (pos.SymbolName == guardMapped && pos.Label != null &&
                    (pos.Label.StartsWith("Glitch Matrix") || pos.Label.StartsWith("BTC_NUCLEAR")))
                {
                    alreadyHasPosition = true;
                    Print($"🛡️ DUPLICATE GUARD: Found existing {pos.TradeType} {pos.SymbolName} @ {pos.EntryPrice} (Label: {pos.Label})");
                    break;
                }
            }
            
            if (alreadyHasPosition)
            {
                // Allow CLOSE signals through even if position exists (that's the point!)
                if (string.IsNullOrEmpty(signal.Action) || signal.Action.ToUpper() != "CLOSE")
                {
                    Print($"⚠️ SKIP: Already have Glitch Matrix position on {guardMapped} — signal {signal.SignalId} rejected");
                    WriteExecutionConfirmation(signal, null, "REJECTED", $"Duplicate position guard: already have position on {guardMapped}");
                    return;
                }
            }
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            // 🔴 V8.0 CLOSE POSITION HANDLER
            // Python sends Action="CLOSE" → find matching position → ClosePosition()
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            if (!string.IsNullOrEmpty(signal.Action) && signal.Action.ToUpper() == "CLOSE")
            {
                Print("");
                Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                Print($"🔴 V8.0 CLOSE POSITION: {signal.Symbol} {signal.Direction}");
                Print($"   Reason: {signal.CloseReason ?? "N/A"}");
                Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                
                var closeSymbol = signal.Symbol.Replace("/", "").Replace(" ", "");
                var closeMapped = MapSymbolName(closeSymbol);
                if (string.IsNullOrEmpty(closeMapped)) closeMapped = closeSymbol;
                
                var closeDir = signal.Direction?.ToLower().Trim();
                TradeType? closeTradeType = null;
                if (closeDir == "sell" || closeDir == "short")
                    closeTradeType = TradeType.Sell;
                else if (closeDir == "buy" || closeDir == "long")
                    closeTradeType = TradeType.Buy;
                
                int closedCount = 0;
                foreach (var pos in Positions)
                {
                    if (pos.SymbolName != closeMapped)
                        continue;
                    if (pos.Label == null || (!pos.Label.StartsWith("Glitch Matrix") && !pos.Label.StartsWith("BTC_NUCLEAR")))
                        continue;
                    
                    // If direction specified, match it; otherwise close ALL positions on symbol
                    if (closeTradeType.HasValue && pos.TradeType != closeTradeType.Value)
                        continue;
                    
                    Print($"   🔴 Closing: {pos.TradeType} {pos.SymbolName} @ {pos.EntryPrice} (P&L: ${pos.NetProfit:F2})");
                    var closeResult = ClosePosition(pos);
                    if (closeResult.IsSuccessful)
                    {
                        Print($"   ✅ CLOSED: Position #{pos.Id} | P&L: ${pos.NetProfit:F2}");
                        closedCount++;
                    }
                    else
                    {
                        Print($"   ❌ CLOSE FAILED: {closeResult.Error}");
                    }
                }
                
                Print($"📊 CLOSE RESULT: {closedCount} position(s) closed for {closeMapped}");
                Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                
                WriteExecutionConfirmation(signal, null, closedCount > 0 ? "CLOSED" : "NO_POSITION",
                    closedCount > 0 ? $"Closed {closedCount} position(s) for {closeMapped}" : $"No matching position found for {closeMapped}");
                
                return; // EXIT — don't process as new order!
            }
            
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            // 🛡️ V8.0 SL/TP ZERO GUARD — Reject naked orders!
            // ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            string guardCleanSymbol = signal.Symbol.ToUpper().Replace(" ", "").Replace("/", "");
            bool isCryptoGuard = guardCleanSymbol.Contains("BTC") || guardCleanSymbol.Contains("ETH");
            
            if (!isCryptoGuard)
            {
                // Non-crypto: SL/TP are in pips
                if (signal.StopLossPips <= 0 || signal.TakeProfitPips <= 0)
                {
                    Print($"🚨 SL/TP ZERO GUARD: REJECTED {signal.Symbol} — SL_Pips={signal.StopLossPips}, TP_Pips={signal.TakeProfitPips}");
                    Print($"   Cannot execute naked order without valid SL/TP!");
                    WriteExecutionConfirmation(signal, null, "REJECTED", $"SL/TP zero guard: SL_pips={signal.StopLossPips}, TP_pips={signal.TakeProfitPips}");
                    return;
                }
            }
            else
            {
                // Crypto: SL/TP are absolute prices
                if (signal.StopLoss <= 0 || signal.TakeProfit <= 0)
                {
                    Print($"🚨 SL/TP ZERO GUARD (CRYPTO): REJECTED {signal.Symbol} — SL={signal.StopLoss}, TP={signal.TakeProfit}");
                    Print($"   Cannot execute naked crypto order without valid SL/TP!");
                    WriteExecutionConfirmation(signal, null, "REJECTED", $"SL/TP zero guard: SL={signal.StopLoss}, TP={signal.TakeProfit}");
                    return;
                }
            }
            
            // 🚨🚨🚨 V9.3 BULLETPROOF NUCLEAR OPTION: BTC EXECUTES FIRST - NO CALCULATIONS! 🚨🚨🚨
            // BULLETPROOF: Case-insensitive, ignores spaces/slashes (synced with Python V5.6)
            // V9.2 FIX: Use broker-native volume conversion (1 lot BTC = 1 unit, not 100k!)
            // V9.3 FIX: Use DOUBLE for volume (prevent truncation: 0.50 → 0 on long cast!)
            string cleanSymbol = signal.Symbol.ToUpper().Replace(" ", "").Replace("/", "");
            if (cleanSymbol.Contains("BTC"))
            {
                Print("");
                Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                Print("🚨 V9.3 DOUBLE TYPE FIX: BTC FORCE EXECUTION");
                Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                Print($"   Signal ID: {signal.SignalId}");
                Print($"   Original Symbol: {signal.Symbol}");
                Print($"   Detected as: BTC (cleanSymbol={cleanSymbol})");
                Print($"   SL: {signal.StopLoss} | TP: {signal.TakeProfit}");
                Print($"   ⚠️  BYPASSED: ALL calculations, validations, risk checks");
                Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                
                var btcSymbol = Symbols.GetSymbol("BTCUSD");
                if (btcSymbol == null)
                {
                    Print($"❌ CRITICAL: BTCUSD symbol not found in cTrader!");
                    WriteExecutionConfirmation(signal, null, "REJECTED", "Symbol not found");
                    return;
                }
                
                // 🚨 V9.3 CRITICAL FIX: Use DOUBLE (not long!) to preserve decimals
                // WRONG V9.2: long forcedVolume = (long)QuantityToVolumeInUnits(0.50)
                //             Result: 0.50 → 0 (truncated by long cast!)
                // RIGHT V9.3: double forcedVolume = QuantityToVolumeInUnits(0.50)
                //             Result: 0.50 → 0.50 (preserved!)
                double lotSize = signal.LotSize > 0 ? signal.LotSize : 0.50;
                double forcedVolume = btcSymbol.QuantityToVolumeInUnits(lotSize);
                
                // Normalize to broker step (respects min/max/step)
                forcedVolume = btcSymbol.NormalizeVolumeInUnits(forcedVolume, RoundingMode.Down);
                
                Print($"   Volume Calculation (V9.3 DOUBLE FIX):");
                Print($"      Requested: {lotSize} lots");
                Print($"      Raw conversion: {btcSymbol.QuantityToVolumeInUnits(lotSize):F8} units");
                Print($"      After normalization: {forcedVolume:F8} units");
                Print($"      Min/Max allowed: {btcSymbol.VolumeInUnitsMin} - {btcSymbol.VolumeInUnitsMax} units");
                Print($"      Volume step: {btcSymbol.VolumeInUnitsStep}");
                
                // ✅ V9.4 DIRECTION FIX: Accept synonyms (SHORT, SELL, PUT → Sell)
                var dir = signal.Direction.ToLower().Trim();
                TradeType tradeType;
                if (dir == "sell" || dir == "short" || dir == "put")
                {
                    tradeType = TradeType.Sell;
                }
                else
                {
                    tradeType = TradeType.Buy;
                }
                
                Print($"⚖️ DIRECTION CHECK: Input='{signal.Direction}' -> Interpreted as {tradeType}");
                Print($"🚀 Executing: {tradeType} BTCUSD {lotSize} lots ({forcedVolume:F8} broker units)");
                
                // Execute WITHOUT SL/TP first
                // NOTE: ExecuteMarketOrder accepts double for volume parameter
                var result = ExecuteMarketOrder(
                    tradeType,
                    "BTCUSD",
                    forcedVolume,  // ✅ DOUBLE (preserves 0.50, not truncated to 0)
                    $"BTC_NUCLEAR_{signal.SignalId}"
                );
                
                if (result.IsSuccessful)
                {
                    Print($"✅ ORDER EXECUTED: Position #{result.Position.Id}");
                    Print($"   Entry Price: {result.Position.EntryPrice}");
                    Print($"   Volume: {btcSymbol.VolumeInUnitsToQuantity(forcedVolume):F8} lots ({forcedVolume:F8} units)");
                    Print($"   V9.3 SUCCESS: Double type preserved decimals!");
                    
                    // V9.4 FIX: Convert to double? (nullable) + NEW API with ProtectionType
                    Print($"   Setting SL/TP...");
                    double? absoluteSl = signal.StopLoss > 0 ? signal.StopLoss : (double?)null;
                    double? absoluteTp = signal.TakeProfit > 0 ? signal.TakeProfit : (double?)null;
                    
                    Print($"   SL: {absoluteSl} | TP: {absoluteTp}");
                    
                    // Use NEW API (with ProtectionType.Absolute for price-based SL/TP)
                    var modifyResult = ModifyPosition(result.Position, absoluteSl, absoluteTp, ProtectionType.Absolute);
                    
                    if (modifyResult.IsSuccessful)
                        Print($"   ✅ SL/TP SET SUCCESS: SL: {absoluteSl} | TP: {absoluteTp}");
                    else
                        Print($"   ❌ SL/TP FAILED: {modifyResult.Error}");
                    
                    Print($"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                    
                    WriteExecutionConfirmation(signal, result.Position, "EXECUTED", "");
                }
                else
                {
                    Print($"❌ EXECUTION FAILED!");
                    Print($"   Error Code: {result.Error}");
                    Print($"   Error Details: {result.Error.ToString()}");
                    
                    // DETAILED ERROR LOGGING
                    if (result.Error == ErrorCode.BadVolume)
                    {
                        Print($"   🔍 BADVOLUME DIAGNOSIS:");
                        Print($"      Min Volume: {btcSymbol.VolumeInUnitsMin}");
                        Print($"      Max Volume: {btcSymbol.VolumeInUnitsMax}");
                        Print($"      Volume Step: {btcSymbol.VolumeInUnitsStep}");
                        Print($"      Attempted Volume: {forcedVolume}");
                        Print($"      Account Balance: ${Account.Balance:F2}");
                        Print($"      Free Margin: ${Account.FreeMargin:F2}");
                    }
                    
                    Print($"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                    
                    WriteExecutionConfirmation(signal, null, "REJECTED", result.Error.ToString());
                }
                
                return; // EXIT FUNCTION - Don't process any more code!
            }
            
            // Map Python symbol names to IC Markets cTrader names
            var pythonSymbol = signal.Symbol.Replace("/", "");
            var symbolName = MapSymbolName(pythonSymbol);
            
            if (string.IsNullOrEmpty(symbolName))
            {
                Print($"❌ Symbol disabled or not available: {pythonSymbol}");
                WriteExecutionConfirmation(signal, null, "REJECTED", $"Symbol not available: {pythonSymbol}");
                return;
            }
            
            var symbol = Symbols.GetSymbol(symbolName);
            
            if (symbol == null)
            {
                Print($"❌ Symbol not found in cTrader: {symbolName} (from {pythonSymbol})");
                WriteExecutionConfirmation(signal, null, "REJECTED", $"Symbol not found: {symbolName}");
                return;
            }

            // Calculate volume for NON-BTCUSD symbols
            long volume = CalculateVolume(signal, symbol);
            
            // ✅ V9.4 DIRECTION FIX: Accept synonyms (SHORT, SELL, PUT → Sell)
            var dir2 = signal.Direction.ToLower().Trim();
            TradeType tradeType2;
            if (dir2 == "sell" || dir2 == "short" || dir2 == "put" || dir2 == "bearish")
            {
                tradeType2 = TradeType.Sell;
            }
            else
            {
                tradeType2 = TradeType.Buy;
            }
            
            Print($"⚖️ DIRECTION CHECK: Input='{signal.Direction}' -> Interpreted as {tradeType2}");

            // Normal execution for non-BTCUSD symbols
            Print($"📈 Executing: {signal.Direction.ToUpper()} {symbol.VolumeInUnitsToQuantity(volume)} lots");
            
            // V10.3: Include StrategyTag in Label for trade identification
            var tradeLabel = !string.IsNullOrEmpty(signal.StrategyTag) 
                ? $"Glitch Matrix - {signal.StrategyTag}"
                : $"Glitch Matrix - {signal.StrategyType}";
            
            TradeResult result2 = ExecuteMarketOrder(
                tradeType2,
                symbolName,
                volume,
                tradeLabel,
                signal.StopLossPips,
                signal.TakeProfitPips
            );

            if (result2.IsSuccessful)
            {
                Print($"✅ ORDER EXECUTED: {result2.Position.Id}");
                Print($"   Volume: {symbol.VolumeInUnitsToQuantity(volume)} lots");
                Print($"   Entry: {result2.Position.EntryPrice}");
                
                WriteExecutionConfirmation(signal, result2.Position, "EXECUTED", "");
            }
            else
            {
                Print($"❌ ORDER FAILED: {result2.Error}");
                Print($"   Symbol: {symbolName}");
                Print($"   Volume: {symbol.VolumeInUnitsToQuantity(volume)} lots ({volume} units)");
                Print($"   Error Details: {result2.Error.ToString()}");
                
                WriteExecutionConfirmation(signal, null, "REJECTED", result2.Error.ToString());
            }
        }
        
        private void WriteExecutionConfirmation(TradeSignal signal, Position position, string status, string reason)
        {
            // ✅ TWO-WAY HANDSHAKE: Write execution report for Python to verify
            // Python will wait up to 15-30 seconds for this file before assuming failure
            try
            {
                // Write to BOTH locations for compatibility
                var confirmationPath = SignalFilePath.Replace("signals.json", "trade_confirmations.json");
                var executionReportPath = SignalFilePath.Replace("signals.json", "execution_report.json");
                
                // ✅ V9.3 FIX: Convert VolumeInUnits to LOTS for display
                double volumeInLots = 0.0;
                if (position != null)
                {
                    var symbol = Symbols.GetSymbol(position.SymbolName);
                    if (symbol != null)
                    {
                        volumeInLots = symbol.VolumeInUnitsToQuantity(position.VolumeInUnits);
                    }
                }
                
                var confirmation = new
                {
                    SignalId = signal.SignalId,
                    Status = status,  // "EXECUTED" or "REJECTED"
                    OrderId = position?.Id.ToString() ?? "N/A",
                    Volume = volumeInLots,  // ✅ V9.3 FIX: Volume in LOTS (not units!)
                    VolumeInUnits = position?.VolumeInUnits ?? 0.0,  // Keep units for reference
                    EntryPrice = position?.EntryPrice ?? 0.0,
                    StopLoss = position?.StopLoss ?? 0.0,
                    TakeProfit = position?.TakeProfit ?? 0.0,
                    Reason = reason,
                    Timestamp = DateTime.UtcNow,
                    
                    // Additional metadata
                    Symbol = signal.Symbol,
                    Direction = signal.Direction,
                    Account = Account.Number,
                    Balance = Account.Balance,
                    
                    // ✅ Message for easy Python parsing (include volume in LOTS)
                    Message = status == "EXECUTED" 
                        ? $"Filled at {position?.EntryPrice:F5} | Volume: {volumeInLots:F2} lots" 
                        : reason
                };
                
                var options = new JsonSerializerOptions { WriteIndented = true };
                var json = JsonSerializer.Serialize(confirmation, options);
                
                // Write to BOTH files (legacy + new protocol)
                File.WriteAllText(confirmationPath, json);
                File.WriteAllText(executionReportPath, json);
                
                Print($"✅ Execution report written: {status}");
                Print($"   Volume: {volumeInLots:F2} lots ({position?.VolumeInUnits ?? 0:F2} units)");
                Print($"   Primary: {confirmationPath}");
                Print($"   Mirror: {executionReportPath}");
            }
            catch (Exception ex)
            {
                Print($"⚠️  Could not write confirmation: {ex.Message}");
                
                // ✅ CRITICAL: Try to write minimal error report even if JSON fails
                try
                {
                    var errorPath = SignalFilePath.Replace("signals.json", "execution_report.json");
                    var errorData = $"{{\"SignalId\":\"{signal.SignalId}\",\"Status\":\"ERROR\",\"Message\":\"{ex.Message.Replace("\"", "'")}\",\"Timestamp\":\"{DateTime.UtcNow:O}\"}}";
                    File.WriteAllText(errorPath, errorData);
                    Print($"✅ Error report written (fallback)");
                }
                catch
                {
                    Print($"❌ CRITICAL: Cannot write ANY confirmation file!");
                }
            }
        }

        private long CalculateVolume(TradeSignal signal, Symbol symbol)
        {
            Print($"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            Print($"🔍 VOLUME CALCULATION START");
            Print($"   Symbol: {signal.Symbol}");
            Print($"   LotSize from JSON: {signal.LotSize}");
            Print($"   RawUnits from JSON: {signal.RawUnits}");
            Print($"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            
            // 🚨 V5.5 BULLETPROOF NUCLEAR: BTC gets ABSOLUTE PRIORITY - ZERO calculations!
            // BULLETPROOF: Case-insensitive, ignores spaces/slashes (synced with Python V5.6)
            string cleanSymbol = signal.Symbol.ToUpper().Replace(" ", "").Replace("/", "");
            if (cleanSymbol.Contains("BTC"))
            {
                // Use RawUnits if available (most direct)
                if (signal.RawUnits.HasValue && signal.RawUnits.Value > 0)
                {
                    Print($"🚀 BTC NUCLEAR ({signal.Symbol}): Using RawUnits={signal.RawUnits.Value} DIRECTLY");
                    Print($"   Detected as: BTC (cleanSymbol={cleanSymbol})");
                    Print($"⚠️  NO NORMALIZATION, NO CHECKS - DIRECT EXECUTION!");
                    return signal.RawUnits.Value;
                }
                
                // Fallback: Use LotSize and convert
                if (signal.LotSize > 0)
                {
                    long volumeInUnits = (long)symbol.QuantityToVolumeInUnits(signal.LotSize);
                    Print($"🚀 BTC NUCLEAR ({signal.Symbol}): Converted {signal.LotSize} lots → {volumeInUnits} units");
                    Print($"   Detected as: BTC (cleanSymbol={cleanSymbol})");
                    Print($"⚠️  DIRECT EXECUTION WITHOUT NORMALIZATION!");
                    return volumeInUnits;
                }
                
                // Emergency: Force 50000 units (0.50 lots)
                Print($"⚠️  BTC EMERGENCY ({signal.Symbol}): No valid volume in JSON!");
                Print($"   Detected as: BTC (cleanSymbol={cleanSymbol})");
                Print($"🚨 FORCING 50000 units (0.50 lots) as LAST RESORT");
                return 50000;
            }
            
            // For all other symbols: Use RawUnits with normalization
            if (signal.RawUnits.HasValue && signal.RawUnits.Value > 0)
            {
                long volumeInUnits = signal.RawUnits.Value;
                volumeInUnits = (long)symbol.NormalizeVolumeInUnits(volumeInUnits, RoundingMode.Down);
                
                if (volumeInUnits < (long)symbol.VolumeInUnitsMin)
                    volumeInUnits = (long)symbol.VolumeInUnitsMin;
                if (volumeInUnits > (long)symbol.VolumeInUnitsMax)
                    volumeInUnits = (long)symbol.VolumeInUnitsMax;
                
                Print($"✅ Using RawUnits: {volumeInUnits} units");
                return volumeInUnits;
            }
            
            // Use LotSize with normalization
            if (signal.LotSize > 0)
            {
                long volumeInUnits = (long)symbol.QuantityToVolumeInUnits(signal.LotSize);
                volumeInUnits = (long)symbol.NormalizeVolumeInUnits(volumeInUnits, RoundingMode.Down);
                
                if (volumeInUnits < (long)symbol.VolumeInUnitsMin)
                    volumeInUnits = (long)symbol.VolumeInUnitsMin;
                if (volumeInUnits > (long)symbol.VolumeInUnitsMax)
                    volumeInUnits = (long)symbol.VolumeInUnitsMax;
                
                Print($"✅ Using LotSize: {signal.LotSize} lots ({volumeInUnits} units)");
                return volumeInUnits;
            }
            
            // Fallback: Calculate volume from risk (old method)
            var balance = Account.Balance;
            var riskAmount = balance * (MaxRiskPercent / 100.0);
            
            var slDistance = Math.Abs(signal.EntryPrice - signal.StopLoss);
            var slPips = slDistance / symbol.PipSize;
            
            var volumeCalc = riskAmount / (slPips * symbol.PipValue);
            var volumeInLots = (long)symbol.NormalizeVolumeInUnits((long)volumeCalc, RoundingMode.Down);
            
            if (volumeInLots < (long)symbol.VolumeInUnitsMin)
                volumeInLots = (long)symbol.VolumeInUnitsMin;
            if (volumeInLots > (long)symbol.VolumeInUnitsMax)
                volumeInLots = (long)symbol.VolumeInUnitsMax;
            
            Print($"💰 Risk: {MaxRiskPercent}% = ${riskAmount:F2}");
            Print($"📊 Volume calculated: {symbol.VolumeInUnitsToQuantity(volumeInLots)} lots");
            
            return volumeInLots;
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

                    // V10.3: Extract strategy tag from Label
                    var label = position.Label ?? "";
                    var strategyTag = label.StartsWith("Glitch Matrix - ") 
                        ? label.Substring("Glitch Matrix - ".Length) 
                        : label;
                    
                    var exportObj = new
                    {
                        symbol = position.SymbolName,
                        direction = position.TradeType.ToString().ToLower(),
                        entry_price = position.EntryPrice,
                        volume = position.VolumeInUnits,
                        opened_at = position.EntryTime,
                        stop_loss = position.StopLoss,
                        take_profit = position.TakeProfit,
                        net_profit = position.NetProfit,
                        pips = position.Pips,
                        strategy_tag = strategyTag  // V10.3: D1_4H_REVERSAL_SNIPER_E1
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

        protected override void OnStop()
        {
            Print("");
            Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
            Print("🛑 ФорексГод — Executor Stopped");
            Print("🏛️ POCOVNICU TERMINAL • V10.4 MTF Perfection");
            Print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
        }
    }

    public class TradeSignal
    {
        // ━━━ V1.0 ORIGINAL FIELDS ━━━
        public string SignalId { get; set; }
        public string Symbol { get; set; }
        public string Direction { get; set; }
        public string Action { get; set; }  // V8.0: "CLOSE" = close position, null/empty = normal open
        public string CloseReason { get; set; }  // V8.0: Reason for closing (CLOSE_ENTRY1, timeout, etc.)
        public string StrategyType { get; set; }
        public double EntryPrice { get; set; }
        public double StopLoss { get; set; }
        public double TakeProfit { get; set; }
        public double StopLossPips { get; set; }
        public double TakeProfitPips { get; set; }
        public double RiskReward { get; set; }
        public DateTime Timestamp { get; set; }
        public double LotSize { get; set; }  // 🚨 V5.1 FIX: Lot size from Python (prevents BadVolume)
        public int? RawUnits { get; set; }  // 🪙 V5.1 CRYPTO: Raw volume units for BTC/ETH
        
        // ━━━ V4.0 SMC LEVEL UP - NEW FIELDS ━━━
        // 💧 Liquidity Sweep Detection
        public bool LiquiditySweep { get; set; }  // True if sweep detected
        public string SweepType { get; set; }  // "SSL" (Sell Side) or "BSL" (Buy Side)
        public int ConfidenceBoost { get; set; }  // +20 if sweep confirmed, 0 otherwise
        
        // 📦 Order Block Activation
        public bool OrderBlockUsed { get; set; }  // True if OB score ≥7 (refined entry)
        public int OrderBlockScore { get; set; }  // 1-10 (0 if not used)
        
        // V9.0: Daily Range fields REMOVED (caused UNKNOWN errors and 0 volume cascade)
        
        // ━━━ V10.3 STRATEGY TAGGING ━━━
        public string Comment { get; set; }  // D1_4H_REVERSAL_SNIPER_E1
        public string StrategyTag { get; set; }  // Same as Comment — human-readable strategy label
    }
}
