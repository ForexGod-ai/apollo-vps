#!/usr/bin/env python3
"""
SQLite Database Migration Script - Glitch In Matrix v3.2
=========================================================
Migrează datele de trading din JSON în SQLite pentru stocare permanentă.

Autor: ФорексГод
Data: 2026-02-03
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime
from loguru import logger
import sys

# Configure logging
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    level="INFO"
)

class DatabaseMigration:
    """Handles migration from JSON to SQLite"""
    
    def __init__(self, db_path: str = "data/trades.db", json_path: str = "trade_history.json"):
        self.db_path = Path(db_path)
        self.json_path = Path(json_path)
        
        # Ensure data directory exists
        self.db_path.parent.mkdir(exist_ok=True)
        
        logger.info(f"🗄️  Database path: {self.db_path}")
        logger.info(f"📄 JSON source: {self.json_path}")
    
    def create_database_schema(self):
        """Create SQLite tables with proper schema"""
        logger.info("🔧 Creating database schema...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table 1: Closed Trades (historical trades)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS closed_trades (
                ticket INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                volume REAL NOT NULL,
                open_time TEXT NOT NULL,
                close_time TEXT NOT NULL,
                open_price REAL NOT NULL,
                close_price REAL NOT NULL,
                profit REAL NOT NULL,
                commission REAL DEFAULT 0,
                swap REAL DEFAULT 0,
                stop_loss REAL,
                take_profit REAL,
                comment TEXT,
                magic_number INTEGER,
                raw_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table 2: Open Positions (current active trades)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS open_positions (
                ticket INTEGER PRIMARY KEY,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                volume REAL NOT NULL,
                open_time TEXT NOT NULL,
                open_price REAL NOT NULL,
                current_price REAL NOT NULL,
                profit REAL NOT NULL,
                commission REAL DEFAULT 0,
                swap REAL DEFAULT 0,
                stop_loss REAL,
                take_profit REAL,
                comment TEXT,
                magic_number INTEGER,
                raw_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table 3: Account Snapshots (balance tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                balance REAL NOT NULL,
                equity REAL NOT NULL,
                margin REAL,
                free_margin REAL,
                margin_level REAL,
                open_positions_count INTEGER,
                total_profit REAL,
                raw_data TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_closed_symbol ON closed_trades(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_closed_time ON closed_trades(close_time)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_open_symbol ON open_positions(symbol)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_time ON account_snapshots(timestamp)")
        
        conn.commit()
        conn.close()
        
        logger.success("✅ Database schema created successfully!")
    
    def migrate_json_to_sqlite(self):
        """Migrate existing trade_history.json data to SQLite"""
        logger.info("📦 Starting migration from JSON to SQLite...")
        
        if not self.json_path.exists():
            logger.warning("⚠️  trade_history.json not found - skipping migration")
            return
        
        # Load JSON data
        with open(self.json_path, 'r') as f:
            data = json.load(f)
        
        logger.info(f"📊 Loaded JSON with {len(data.get('closed_trades', []))} closed trades")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Migrate closed trades
        closed_count = 0
        for trade in data.get('closed_trades', []):
            try:
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
                    trade.get('open_price', trade.get('openPrice', 0)),
                    trade.get('close_price', trade.get('closePrice', 0)),
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
                closed_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to migrate trade {trade.get('ticket')}: {e}")
        
        # Migrate open positions
        open_count = 0
        for position in data.get('open_positions', []):
            try:
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
                open_count += 1
            except Exception as e:
                logger.error(f"❌ Failed to migrate position {position.get('ticket')}: {e}")
        
        # Create initial account snapshot
        if 'balance' in data or 'equity' in data:
            cursor.execute("""
                INSERT INTO account_snapshots (
                    timestamp, balance, equity, open_positions_count, raw_data
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                data.get('balance', 0),
                data.get('equity', 0),
                len(data.get('open_positions', [])),
                json.dumps(data)
            ))
        
        conn.commit()
        conn.close()
        
        logger.success(f"✅ Migration complete!")
        logger.success(f"   📊 Migrated {closed_count} closed trades")
        logger.success(f"   📈 Migrated {open_count} open positions")
    
    def verify_migration(self):
        """Verify data was migrated correctly"""
        logger.info("🔍 Verifying migration...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM closed_trades")
        closed_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM open_positions")
        open_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM account_snapshots")
        snapshots_count = cursor.fetchone()[0]
        
        # Get sample data
        cursor.execute("SELECT ticket, symbol, profit FROM closed_trades ORDER BY close_time DESC LIMIT 3")
        recent_trades = cursor.fetchall()
        
        conn.close()
        
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info("📊 DATABASE VERIFICATION RESULTS")
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        logger.info(f"   🔒 Closed Trades:     {closed_count:,} records")
        logger.info(f"   📈 Open Positions:    {open_count:,} records")
        logger.info(f"   📸 Account Snapshots: {snapshots_count:,} records")
        logger.info("")
        
        if recent_trades:
            logger.info("   🔥 Recent Trades:")
            for ticket, symbol, profit in recent_trades:
                profit_emoji = "💰" if profit > 0 else "💸"
                logger.info(f"      {profit_emoji} #{ticket} {symbol} | Profit: ${profit:.2f}")
        
        logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        return closed_count, open_count, snapshots_count
    
    def run_full_migration(self):
        """Execute complete migration process"""
        logger.info("╔════════════════════════════════════════════════════════╗")
        logger.info("║  🗄️  SQLITE MIGRATION - Glitch In Matrix v3.2         ║")
        logger.info("║  Problem #2: Data Loss → Solution 2A & 2B              ║")
        logger.info("╚════════════════════════════════════════════════════════╝")
        logger.info("")
        
        try:
            # Step 1: Create schema
            self.create_database_schema()
            logger.info("")
            
            # Step 2: Migrate data
            self.migrate_json_to_sqlite()
            logger.info("")
            
            # Step 3: Verify
            self.verify_migration()
            logger.info("")
            
            logger.success("🎉 MIGRATION COMPLETED SUCCESSFULLY!")
            logger.success("   📁 Database: data/trades.db")
            logger.success("   🔒 Data is now permanently stored in SQLite")
            logger.success("   💾 JSON compatibility maintained for dashboard")
            logger.info("")
            logger.info("🚀 Next steps:")
            logger.info("   1. Restart ctrader_sync_daemon.py to enable SQLite writes")
            logger.info("   2. Monitor logs to ensure data is being saved")
            logger.info("   3. Query database anytime: sqlite3 data/trades.db")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            raise

def main():
    """Main migration entry point"""
    migration = DatabaseMigration()
    migration.run_full_migration()

if __name__ == '__main__':
    main()
