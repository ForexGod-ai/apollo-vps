#!/usr/bin/env python3.14
"""
cTrader Sync Daemon - Continuous synchronization from cTrader API to trade_history.json + SQLite

Sources data from MarketDataProvider API (localhost:8767) every 30 seconds
Updates trade_history.json automatically so dashboard and Telegram stay current
Saves to SQLite for permanent storage (Problem #2 Solution)

Usage:
    python3.14 ctrader_sync_daemon.py --loop    # Continuous mode
    python3.14 ctrader_sync_daemon.py          # One-time sync
"""

from typing import Optional
import argparse
import json
import sys
import time
import requests
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from loguru import logger

from broker_data_freshness import (
    MAX_BROKER_AGE_SECONDS,
    format_stale_reason,
    incoming_is_newer_or_equal,
    is_payload_fresh,
    load_local_trade_history,
)

# Configure logger
# Windows VPS fix: wrap stdout with UTF-8 to prevent UnicodeEncodeError on emoji
import io as _io
_safe_stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace') if hasattr(sys.stdout, 'buffer') else sys.stdout
logger.remove()
logger.add(
    _safe_stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="INFO",
    colorize=False
)
logger.add(
    "ctrader_sync.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="7 days",
    compression="zip"
)

CTRADER_API_URL = "http://localhost:8767/"  # TradeHistorySyncer — use localhost not 127.0.0.1
TRADE_HISTORY_FILE = Path(__file__).parent / "trade_history.json"
SYNC_INTERVAL = 30  # seconds
SQLITE_DB_PATH = "data/trades.db"
STALE_ALERT_AFTER_S = 300  # 5 min consecutive broker failures → Telegram
STALE_ALERT_COOLDOWN_S = 3600  # max one alert per hour

_last_fetch_failure: Optional[str] = None  # stale | offline | invalid | error


def convert_volume_to_lots(symbol: str, volume_units: float) -> float:
    """
    Convert cTrader VolumeInUnits to standard Lots
    
    ✅ FOREX (EURUSD, GBPUSD, etc.): 100,000 units = 1.0 lot
    ✅ GOLD (XAUUSD): 100 units = 1.0 lot  
    ✅ CRYPTO (BTCUSD): 1 unit = 1.0 lot (broker-specific)
    
    Returns: Lots (float with 2 decimals)
    """
    if not symbol or volume_units == 0:
        return 0.0
    
    symbol_upper = symbol.upper()
    
    # CRYPTO: 1 unit = 1 lot (special case for BTC, ETH, etc.)
    if any(crypto in symbol_upper for crypto in ['BTC', 'ETH', 'LTC', 'XRP']):
        return round(volume_units, 2)
    
    # GOLD: 100 units = 1 lot
    elif 'XAU' in symbol_upper or 'GOLD' in symbol_upper:
        return round(volume_units / 100, 2)
    
    # FOREX: 100,000 units = 1 lot (standard)
    else:
        return round(volume_units / 100000, 2)


class TradeDatabase:
    """SQLite database handler for permanent trade storage"""
    
    def __init__(self, db_path=SQLITE_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure database tables exist (lightweight check)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Quick check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            
            if 'closed_trades' not in tables or 'open_positions' not in tables:
                logger.warning("⚠️  Database tables missing - run migrate_to_sqlite.py first!")
            
            conn.close()
        except Exception as e:
            logger.error(f"❌ Database check failed: {e}")
    
    def save_closed_trade(self, trade):
        """Save closed trade to SQLite (INSERT OR REPLACE to avoid duplicates)"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO closed_trades (
                    ticket, symbol, direction, volume,
                    open_time, close_time, open_price, close_price,
                    profit, commission, swap, stop_loss, take_profit,
                    comment, magic_number, raw_data, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade.get('ticket'),
                trade.get('symbol'),
                trade.get('direction', trade.get('type', 'buy')),
                trade.get('volume', trade.get('lots', 0)),
                trade.get('open_time', trade.get('openTime')),
                trade.get('close_time', trade.get('closeTime')),
                trade.get('open_price', trade.get('openPrice', trade.get('entry_price', 0))),
                trade.get('close_price', trade.get('closePrice', trade.get('closing_price', 0))),
                trade.get('profit', 0),
                trade.get('commission', 0),
                trade.get('swap', 0),
                trade.get('stop_loss', trade.get('stopLoss')),
                trade.get('take_profit', trade.get('takeProfit')),
                trade.get('comment', ''),
                trade.get('magic_number', 0),
                json.dumps(trade),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save trade {trade.get('ticket')} to SQLite: {e}")
            return False
    
    def save_open_position(self, position):
        """Save open position to SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO open_positions (
                    ticket, symbol, direction, volume,
                    open_time, open_price, current_price, profit,
                    commission, swap, stop_loss, take_profit,
                    comment, magic_number, raw_data, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                position.get('ticket'),
                position.get('symbol'),
                position.get('direction', position.get('type', 'buy')),
                position.get('volume', position.get('lots', 0)),
                position.get('open_time', position.get('openTime')),
                position.get('open_price', position.get('openPrice', 0)),
                position.get('current_price', position.get('currentPrice', 0)),
                position.get('profit', 0),
                position.get('commission', 0),
                position.get('swap', 0),
                position.get('stop_loss', position.get('stopLoss')),
                position.get('take_profit', position.get('takeProfit')),
                position.get('comment', ''),
                position.get('magic_number', 0),
                json.dumps(position),
                datetime.now().isoformat()
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save position {position.get('ticket')} to SQLite: {e}")
            return False
    
    def save_account_snapshot(self, account_data, open_count):
        """Save account snapshot to SQLite"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO account_snapshots (
                    timestamp, balance, equity, margin, free_margin,
                    margin_level, open_positions_count, raw_data
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                account_data.get('balance', 0),
                account_data.get('equity', 0),
                account_data.get('margin', 0),
                account_data.get('freeMargin', 0),
                account_data.get('marginLevel', 0),
                open_count,
                json.dumps(account_data)
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to save account snapshot to SQLite: {e}")
            return False


def fetch_ctrader_data():
    """Fetch live account data from TradeHistorySyncer HTTP server on localhost:8767.

    TradeHistorySyncer.cs runs an HTTP server on port 8767 and serves:
      { "account": { "balance", "equity", ... }, "open_positions": [...], "closed_trades": [...] }

    Port 8000 = MarketDataProvider (OHLCV bars only — different bot, different port).
    """
    global _last_fetch_failure
    try:
        logger.debug(f"📡 Fetching from {CTRADER_API_URL}")
        response = requests.get(CTRADER_API_URL, timeout=10)
        response.raise_for_status()

        data = response.json()

        account = data.get('account', {})
        balance = account.get('balance')
        equity = account.get('equity')

        if balance is None or equity is None:
            _last_fetch_failure = 'invalid'
            logger.error("❌ Response missing account.balance/equity — TradeHistorySyncer may not be synced yet")
            return None

        if not is_payload_fresh(data):
            _last_fetch_failure = 'stale'
            logger.error(
                f"❌ STALE broker payload rejected — {format_stale_reason(data)} "
                f"(restart TradeHistorySyncer cBot in cTrader)"
            )
            return None

        _last_fetch_failure = None
        logger.success(
            f"✅ API Response: Balance ${balance:.2f}, Equity ${equity:.2f} "
            f"(last_update={(account.get('last_update'))})"
        )
        return data

    except requests.exceptions.ConnectionError:
        _last_fetch_failure = 'offline'
        logger.error("❌ Cannot connect to TradeHistorySyncer (localhost:8767) — is the cBot running in cTrader?")
        return None
    except requests.exceptions.Timeout:
        _last_fetch_failure = 'offline'
        logger.error("⏱️ Request timeout after 10 seconds")
        return None
    except requests.exceptions.RequestException as e:
        _last_fetch_failure = 'error'
        logger.error(f"❌ HTTP request failed: {e}")
        return None
    except json.JSONDecodeError:
        _last_fetch_failure = 'invalid'
        logger.error("❌ Invalid JSON response from TradeHistorySyncer")
        return None


def _send_broker_stale_telegram(failure_kind: str, consecutive_failures: int) -> None:
    """V56: one Telegram alert when broker 8767 unavailable/stale >5 min."""
    kind_note = {
        'stale': 'TradeHistorySyncer răspunde dar datele sunt STALE (last_update vechi)',
        'offline': 'TradeHistorySyncer offline — port 8767 inaccesibil',
        'invalid': 'Răspuns JSON invalid sau fără balance/equity',
        'error': 'Eroare HTTP la citirea brokerului',
    }.get(failure_kind, failure_kind or 'necunoscut')
    try:
        from telegram_notifier import TelegramNotifier
        tn = TelegramNotifier()
        msg = (
            "⚠️ <b>cTRADER SYNC STALE</b>\n"
            "────────────────\n"
            f"Broker feed <code>localhost:8767</code> indisponibil "
            f"<b>{STALE_ALERT_AFTER_S // 60} min</b> consecutive.\n"
            f"Cauză: {kind_note}\n"
            f"Eșecuri consecutive: <code>{consecutive_failures}</code>\n"
            "────────────────\n"
            "<b>Acțiune:</b> în cTrader → Stop + Start <b>TradeHistorySyncer</b>, "
            "apoi verifică:\n"
            "<code>Invoke-RestMethod http://localhost:8767/</code>"
        )
        if tn.send_message(msg, parse_mode='HTML'):
            logger.warning("[V56] Broker stale Telegram alert sent")
        else:
            logger.warning("[V56] Broker stale Telegram alert failed to send")
    except Exception as exc:
        logger.warning(f"[V56] Broker stale Telegram alert error: {exc}")


def write_trade_history(data, db: TradeDatabase):
    """Write fetched data to trade_history.json AND SQLite"""
    try:
        local = load_local_trade_history(TRADE_HISTORY_FILE)
        if not incoming_is_newer_or_equal(data, local):
            lu_inc = (data.get('account') or {}).get('last_update')
            lu_loc = (local.get('account') or {}).get('last_update') if local else None
            logger.warning(
                f"⚠️ Skip write — incoming data older than local file "
                f"(incoming={lu_inc} local={lu_loc}); keeping trade_history.json"
            )
            return False

        # ✅ V10.0 FIX: Convert volume from UNITS to LOTS for all positions
        open_positions = data.get('open_positions', [])
        for pos in open_positions:
            volume_units = pos.get('volume', 0)
            symbol = pos.get('symbol', '')
            pos['lot_size'] = convert_volume_to_lots(symbol, volume_units)
            logger.debug(f"📊 {symbol}: {volume_units} units → {pos['lot_size']:.2f} lots")
        
        # ✅ V10.0 FIX: Convert volume for closed trades too
        closed_trades = data.get('closed_trades', [])
        for trade in closed_trades:
            volume_units = trade.get('volume', 0)
            symbol = trade.get('symbol', '')
            trade['lot_size'] = convert_volume_to_lots(symbol, volume_units)
        
        # Sort closed trades chronologically before writing (critical for dashboard charts)
        closed_trades.sort(key=lambda t: t.get('close_time', ''), reverse=False)
        data['closed_trades'] = closed_trades
        
        # Write to JSON atomically (prevents dashboard reading partial file mid-write)
        tmp_path = TRADE_HISTORY_FILE.with_suffix('.json.tmp')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        tmp_path.replace(TRADE_HISTORY_FILE)
        
        # Extract data
        account = data.get('account', {})
        open_positions = data.get('open_positions', [])
        
        logger.info("📝 trade_history.json updated:")
        logger.info(f"   Balance: ${account.get('balance', 0):.2f}")
        logger.info(f"   Equity: ${account.get('equity', 0):.2f}")
        logger.info(f"   Open Positions: {len(open_positions)}")
        logger.info(f"   Closed Trades: {len(closed_trades)}")
        
        # Save to SQLite (permanent storage)
        sqlite_success = True
        
        # Save closed trades
        for trade in closed_trades:
            if not db.save_closed_trade(trade):
                sqlite_success = False
        
        # Save open positions
        for position in open_positions:
            if not db.save_open_position(position):
                sqlite_success = False
        
        # Save account snapshot (every sync)
        db.save_account_snapshot(account, len(open_positions))
        
        if sqlite_success:
            logger.success("💾 SQLite: Data saved permanently")
        else:
            logger.warning("⚠️  SQLite: Some records failed to save")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to write trade_history.json: {e}")
        return False


def sync_once(db: TradeDatabase):
    """Perform single sync operation"""
    logger.info("🔄 Starting sync from cTrader API...")
    
    data = fetch_ctrader_data()
    if not data:
        logger.error("❌ Sync failed - no data received")
        return False
    
    success = write_trade_history(data, db)
    if success:
        logger.success("✅ Sync complete - trade_history.json is current")
        return True
    else:
        return False


def sync_loop(interval=SYNC_INTERVAL):
    """Continuous sync loop every interval seconds"""
    logger.info("="*70)
    logger.info("🚀 cTrader Sync Daemon STARTED")
    logger.info(f"   API: {CTRADER_API_URL}")
    logger.info(f"   Output: {TRADE_HISTORY_FILE}")
    logger.info(f"   SQLite: {SQLITE_DB_PATH}")
    logger.info(f"   Interval: {interval}s")
    logger.info("="*70)
    
    # Initialize SQLite database
    db = TradeDatabase()
    
    consecutive_failures = 0
    failure_started_at: Optional[float] = None
    last_stale_alert_at: Optional[float] = None
    
    while True:
        try:
            success = sync_once(db)
            
            if success:
                consecutive_failures = 0
                failure_started_at = None
            else:
                consecutive_failures += 1
                now = time.time()
                if failure_started_at is None:
                    failure_started_at = now
                elapsed = now - failure_started_at
                logger.warning(
                    f"⚠️ Sync skipped/failed ({consecutive_failures} consecutive, "
                    f"{elapsed:.0f}s) — daemon stays alive (max age {MAX_BROKER_AGE_SECONDS:.0f}s)"
                )
                if (
                    elapsed >= STALE_ALERT_AFTER_S
                    and (
                        last_stale_alert_at is None
                        or (now - last_stale_alert_at) >= STALE_ALERT_COOLDOWN_S
                    )
                ):
                    _send_broker_stale_telegram(_last_fetch_failure or 'error', consecutive_failures)
                    last_stale_alert_at = now
            
            logger.debug(f"💤 Sleeping {interval}s until next sync...")
            time.sleep(interval)
            
        except KeyboardInterrupt:
            logger.info("\n⚠️ Keyboard interrupt received - stopping daemon")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error in sync loop: {e}")
            consecutive_failures += 1
            time.sleep(interval)
    
    logger.info("="*70)
    logger.info("🛑 cTrader Sync Daemon STOPPED")
    logger.info("="*70)


def main():
    """Main entry point"""
    import sys as _sys
    from pathlib import Path as _Path

    # 🔒 SINGLE INSTANCE LOCK — prevent 2 sync daemons writing trade_history.json simultaneously
    _lock_path = _Path(__file__).parent / "process_ctrader_sync_daemon.lock"
    _lock_fd = open(_lock_path, 'w', encoding='utf-8')
    try:
        if _sys.platform == 'win32':
            import msvcrt as _msvcrt
            _msvcrt.locking(_lock_fd.fileno(), _msvcrt.LK_NBLCK, 1)
        else:
            import fcntl as _fcntl
            _fcntl.flock(_lock_fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
        _lock_fd.write(str(__import__('os').getpid()))
        _lock_fd.flush()
    except (BlockingIOError, OSError):
        print("[WARN] ctrader_sync_daemon already running - exiting duplicate instance")
        _sys.exit(1)
    parser = argparse.ArgumentParser(
        description="cTrader Sync Daemon - Automatic cTrader → trade_history.json + SQLite synchronization"
    )
    parser.add_argument(
        '--loop',
        action='store_true',
        help='Run in continuous loop mode (default: one-time sync)'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=SYNC_INTERVAL,
        help=f'Sync interval in seconds (default: {SYNC_INTERVAL}s)'
    )
    
    args = parser.parse_args()
    
    # Run in loop or one-time mode
    if args.loop:
        sync_loop(args.interval)
    else:
        db = TradeDatabase()
        success = sync_once(db)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
