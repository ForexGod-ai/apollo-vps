"""Weekly P&L aggregation — broker-first sync + SQLite fallback."""

import json
import sqlite3
from pathlib import Path

import pytest

from trade_manager import TradeManager


class TestCloseDateParsing:
    def test_iso_timestamp(self):
        assert TradeManager._close_date_yyyy_mm_dd('2026-06-29T09:48:00') == '2026-06-29'

    def test_display_format(self):
        assert TradeManager._close_date_yyyy_mm_dd('2026-06-29 09:48') == '2026-06-29'

    def test_ctrader_dd_mm_yyyy(self):
        assert TradeManager._close_date_yyyy_mm_dd('29/06/2026 09:48:00.419') == '2026-06-29'


class TestWeeklyStats:
    TRADES = [
        {'close_time': '2026-06-29T09:48:00', 'profit': -2.87},
        {'close_time': '2026-06-29T15:34:33', 'profit': -2.54},
        {'close_time': '2026-07-02T11:22:42', 'profit': 47.01},
        {'close_time': '2026-06-20T10:00:00', 'profit': 100.0},
    ]

    def test_filters_last_seven_days(self):
        tm = TradeManager()
        stats = tm._calc_weekly_stats(self.TRADES, '2026-06-26')
        assert stats['total'] == 3
        assert stats['wins'] == 1
        assert stats['losses'] == 2
        assert abs(stats['total_pnl'] - 41.60) < 0.01
        assert stats['best_trade'] == 47.01
        assert stats['worst_trade'] == -2.87


class TestWeeklyBrokerLive:
    TRADES = [
        {'close_time': '2026-06-29T09:48:00', 'profit': -2.87},
        {'close_time': '2026-06-29T15:34:33', 'profit': -2.54},
        {'close_time': '2026-07-02T11:22:42', 'profit': 47.01},
    ]

    def test_aggregates_from_live_broker_response(self, tmp_path, monkeypatch):
        script_dir = tmp_path / 'proj'
        script_dir.mkdir()
        tm = TradeManager(script_dir)

        broker_payload = {
            'account': {'balance': 99.71, 'equity': 99.71},
            'closed_trades': self.TRADES,
            'open_positions': [],
        }
        monkeypatch.setattr(tm, 'fetch_broker_live', lambda: broker_payload)

        stats = tm.get_weekly_pnl('2026-06-26')
        assert stats['total'] == 3
        assert abs(stats['total_pnl'] - 41.60) < 0.01
        assert stats['source'] == 'ctrader_broker:8767'
        assert stats['broker_synced'] is True
        assert stats['balance'] == 99.71


class TestWeeklySqliteFallback:
    def test_sqlite_used_when_json_empty(self, tmp_path, monkeypatch):
        script_dir = tmp_path / 'proj'
        script_dir.mkdir()
        (script_dir / 'data').mkdir()
        db_path = script_dir / 'data' / 'trades.db'

        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE closed_trades (
                ticket INTEGER PRIMARY KEY,
                symbol TEXT, direction TEXT, volume REAL,
                open_time TEXT, close_time TEXT,
                open_price REAL, close_price REAL,
                profit REAL, commission REAL, swap REAL,
                stop_loss REAL, take_profit REAL,
                comment TEXT, magic_number INTEGER,
                raw_data TEXT, updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO closed_trades (
                ticket, symbol, direction, volume, open_time, close_time,
                open_price, close_price, profit, commission, swap,
                stop_loss, take_profit, comment, magic_number, raw_data, updated_at
            ) VALUES (1, 'EURJPY', 'sell', 0.05, '2026-07-02T08:00:00',
                      '2026-07-02T11:22:42', 185.678, 184.110, 47.01,
                      0, 0, NULL, NULL, '', 0, '{}', '2026-07-02')
            """
        )
        conn.commit()
        conn.close()

        th_file = script_dir / 'trade_history.json'
        th_file.write_text(json.dumps({'account': {}, 'closed_trades': []}), encoding='utf-8')

        tm = TradeManager(script_dir)
        monkeypatch.setattr(tm, 'fetch_broker_live', lambda: None)

        stats = tm.get_weekly_pnl('2026-06-26')
        assert stats['total'] == 1
        assert stats['total_pnl'] == 47.01
        assert stats['source'] == 'trades.db(offline)'
        assert stats['broker_synced'] is False
