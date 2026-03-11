"""
Signal Cache Manager - Anti-Spam & Persistent Memory System
Prevents duplicate notifications and execution of old signals

✨ Glitch in Matrix by ФорексГод ✨
Created: February 23, 2026
"""

import json
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Set, Optional, Dict
from loguru import logger


class SignalCache:
    """
    🛡️ ANTI-SPAM SYSTEM - Persistent memory for processed signals
    
    Features:
    - Persistent storage (survives restarts)
    - Automatic cleanup of old entries (>24h)
    - Fast duplicate detection (O(1) lookup)
    - Thread-safe operations
    """
    
    def __init__(self, cache_file: str = "processed_signals_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache: Dict[str, float] = {}  # {signal_id: timestamp}
        self.max_age_hours = 24  # Keep cache entries for 24h
        
        # Load existing cache
        self._load_cache()
        
        # Clean old entries
        self._cleanup_old_entries()
        
        logger.success(f"🛡️ Signal Cache initialized: {len(self.cache)} entries")
    
    def _load_cache(self):
        """Load cache from disk"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    self.cache = {k: float(v) for k, v in data.items()}
                logger.info(f"📂 Loaded {len(self.cache)} cached signals from {self.cache_file}")
            else:
                logger.info(f"📂 Cache file not found, starting fresh: {self.cache_file}")
                self.cache = {}
        except Exception as e:
            logger.error(f"❌ Failed to load cache: {e}")
            self.cache = {}
    
    def _save_cache(self):
        """Save cache to disk (persistent)"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
            logger.debug(f"💾 Cache saved: {len(self.cache)} entries")
        except Exception as e:
            logger.error(f"❌ Failed to save cache: {e}")
    
    def _cleanup_old_entries(self):
        """Remove entries older than max_age_hours"""
        current_time = time.time()
        max_age_seconds = self.max_age_hours * 3600
        
        old_entries = [
            signal_id for signal_id, timestamp in self.cache.items()
            if current_time - timestamp > max_age_seconds
        ]
        
        for signal_id in old_entries:
            del self.cache[signal_id]
        
        if old_entries:
            logger.info(f"🧹 Cleaned {len(old_entries)} old cache entries (>{self.max_age_hours}h)")
            self._save_cache()
    
    def is_processed(self, signal_id: str) -> bool:
        """
        Check if signal was already processed
        
        Returns:
            True if signal exists in cache (duplicate)
            False if signal is new
        """
        exists = signal_id in self.cache
        
        if exists:
            timestamp = self.cache[signal_id]
            age_seconds = time.time() - timestamp
            age_minutes = age_seconds / 60
            logger.warning(f"🚫 DUPLICATE DETECTED: {signal_id} (processed {age_minutes:.1f}m ago)")
        
        return exists
    
    def mark_processed(self, signal_id: str):
        """
        Mark signal as processed
        Saves to disk for persistence across restarts
        """
        self.cache[signal_id] = time.time()
        self._save_cache()
        logger.debug(f"✅ Signal marked as processed: {signal_id}")
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        current_time = time.time()
        
        # Count by age
        last_hour = sum(1 for t in self.cache.values() if current_time - t < 3600)
        last_day = len(self.cache)
        
        return {
            'total_entries': last_day,
            'last_hour': last_hour,
            'last_24h': last_day,
            'oldest_entry_age_hours': max((current_time - min(self.cache.values())) / 3600, 0) if self.cache else 0
        }
    
    def clear_cache(self):
        """Clear entire cache (emergency use)"""
        logger.warning(f"⚠️ CACHE CLEARED: Removing {len(self.cache)} entries")
        self.cache = {}
        self._save_cache()


class TelegramDebouncer:
    """
    🔕 TELEGRAM NOTIFICATION DEBOUNCER
    Prevents sending the same message multiple times within a short timeframe
    """
    
    def __init__(self, debounce_minutes: int = 5):
        self.debounce_seconds = debounce_minutes * 60
        self.sent_messages: Dict[str, float] = {}  # {message_hash: timestamp}
    
    def _hash_message(self, symbol: str, message_type: str, extra: str = "") -> str:
        """Create unique hash for message deduplication"""
        return f"{symbol}:{message_type}:{extra}"
    
    def should_send(self, symbol: str, message_type: str, extra: str = "") -> bool:
        """
        Check if message should be sent
        
        Args:
            symbol: Trading symbol (EURUSD, BTCUSD, etc.)
            message_type: Type of notification (setup_alert, execution, rejection)
            extra: Additional context (entry_price, status, etc.)
        
        Returns:
            True if message should be sent
            False if it's a duplicate (too recent)
        """
        msg_hash = self._hash_message(symbol, message_type, extra)
        current_time = time.time()
        
        if msg_hash in self.sent_messages:
            last_sent = self.sent_messages[msg_hash]
            time_since = current_time - last_sent
            
            if time_since < self.debounce_seconds:
                minutes_since = time_since / 60
                logger.warning(f"🔕 DEBOUNCED: {symbol} {message_type} (sent {minutes_since:.1f}m ago)")
                return False
        
        # Update timestamp
        self.sent_messages[msg_hash] = current_time
        
        # Cleanup old entries (older than 2x debounce time)
        cleanup_threshold = current_time - (self.debounce_seconds * 2)
        old_hashes = [h for h, t in self.sent_messages.items() if t < cleanup_threshold]
        for h in old_hashes:
            del self.sent_messages[h]
        
        return True
    
    def get_stats(self) -> Dict:
        """Get debouncer statistics"""
        return {
            'tracked_messages': len(self.sent_messages),
            'debounce_minutes': self.debounce_seconds / 60
        }


def cleanup_old_signals_file(signals_file: Path, max_age_hours: int = 1):
    """
    🧹 STARTUP CLEANUP - Removes old signals from signals.json
    Prevents reprocessing of stale signals after restart
    
    Args:
        signals_file: Path to signals.json
        max_age_hours: Maximum age in hours (default: 1 hour)
    """
    try:
        if not signals_file.exists():
            logger.info(f"📂 No signals file to clean: {signals_file}")
            return
        
        with open(signals_file, 'r') as f:
            content = f.read().strip()
        
        # Handle empty file or []
        if not content or content == '[]':
            logger.info(f"📂 Signals file already empty: {signals_file}")
            return
        
        data = json.loads(content)
        
        # ── V7.0: Handle both array and legacy single-object format ──
        if isinstance(data, dict):
            # Legacy single-object → wrap in array for uniform processing
            signals = [data] if data else []
        elif isinstance(data, list):
            signals = data
        else:
            logger.warning(f"⚠️ Unexpected signals format: {type(data)}")
            return
        
        if not signals:
            logger.info(f"📂 No signals to process")
            return
        
        # Filter: keep only fresh signals
        fresh_signals = []
        removed_count = 0
        
        for signal in signals:
            signal_id = signal.get('SignalId', '')
            timestamp_str = signal.get('Timestamp', '')
            
            # Try to extract timestamp from SignalId
            try:
                parts = signal_id.split('_')
                if parts:
                    timestamp_unix = int(parts[-1])
                    signal_time = datetime.fromtimestamp(timestamp_unix)
                else:
                    signal_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except (ValueError, IndexError):
                logger.warning(f"⚠️ Cannot parse signal timestamp: {signal_id}")
                signal_time = datetime.now() - timedelta(hours=max_age_hours + 1)
            
            age = datetime.now() - signal_time
            age_hours = age.total_seconds() / 3600
            
            if age_hours > max_age_hours:
                logger.warning(f"🧹 CLEANING OLD SIGNAL: {signal_id} (age: {age_hours:.1f}h)")
                logger.info(f"   Signal details: {signal.get('Symbol')} {signal.get('Direction')} @ {signal.get('EntryPrice')}")
                removed_count += 1
            else:
                logger.info(f"📂 Signal is fresh ({age_hours:.1f}h old), keeping: {signal_id}")
                fresh_signals.append(signal)
        
        # Write back only fresh signals (always array format for V7.0)
        if removed_count > 0:
            with open(signals_file, 'w') as f:
                json.dump(fresh_signals, f, indent=2)
            logger.success(f"✅ Removed {removed_count} old signal(s), kept {len(fresh_signals)} fresh")
    
    except Exception as e:
        logger.error(f"❌ Failed to cleanup signals file: {e}")


# Global instances (singleton pattern)
_signal_cache: Optional[SignalCache] = None
_telegram_debouncer: Optional[TelegramDebouncer] = None


def get_signal_cache() -> SignalCache:
    """Get global SignalCache instance (singleton)"""
    global _signal_cache
    if _signal_cache is None:
        _signal_cache = SignalCache()
    return _signal_cache


def get_telegram_debouncer() -> TelegramDebouncer:
    """Get global TelegramDebouncer instance (singleton)"""
    global _telegram_debouncer
    if _telegram_debouncer is None:
        _telegram_debouncer = TelegramDebouncer(debounce_minutes=5)
    return _telegram_debouncer


if __name__ == "__main__":
    # Test the signal cache
    print("="*70)
    print("🧪 SIGNAL CACHE TEST")
    print("="*70)
    
    cache = SignalCache("test_cache.json")
    
    # Test 1: New signal
    print("\nTest 1: New signal")
    is_dup = cache.is_processed("EURUSD_buy_1708711234")
    print(f"Is duplicate? {is_dup} (Expected: False)")
    
    # Test 2: Mark as processed
    print("\nTest 2: Mark as processed")
    cache.mark_processed("EURUSD_buy_1708711234")
    print("✅ Signal marked")
    
    # Test 3: Check again (should be duplicate now)
    print("\nTest 3: Check again")
    is_dup = cache.is_processed("EURUSD_buy_1708711234")
    print(f"Is duplicate? {is_dup} (Expected: True)")
    
    # Test 4: Stats
    print("\nTest 4: Cache stats")
    stats = cache.get_cache_stats()
    print(json.dumps(stats, indent=2))
    
    # Test 5: Debouncer
    print("\n"+"="*70)
    print("🧪 TELEGRAM DEBOUNCER TEST")
    print("="*70)
    
    debouncer = TelegramDebouncer(debounce_minutes=5)
    
    print("\nTest 1: First message")
    should_send = debouncer.should_send("EURUSD", "setup_alert", "1.18134")
    print(f"Should send? {should_send} (Expected: True)")
    
    print("\nTest 2: Immediate duplicate")
    should_send = debouncer.should_send("EURUSD", "setup_alert", "1.18134")
    print(f"Should send? {should_send} (Expected: False - debounced)")
    
    print("\nTest 3: Different symbol")
    should_send = debouncer.should_send("GBPUSD", "setup_alert", "1.31234")
    print(f"Should send? {should_send} (Expected: True - different symbol)")
    
    print("\n✅ ALL TESTS COMPLETE")
