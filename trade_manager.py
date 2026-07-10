"""
V40.4 — PNL synchronization: cTrader broker feed as source of truth.

Wraps TradeHistorySyncer (localhost:8767) and keeps trade_history.json + SQLite
aligned with closed deals from the broker.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from loguru import logger

from broker_data_freshness import format_stale_reason, is_payload_fresh

CTRADER_API_URL = "http://localhost:8767/"
DESYNC_THRESHOLD_USD = 5.0


class AccountClient:
    """HTTP client for TradeHistorySyncer cBot (port 8767)."""

    def __init__(self, api_url: str = CTRADER_API_URL, timeout: float = 10.0):
        self.api_url = api_url
        self.timeout = timeout

    def get_history_deals(self) -> Optional[Dict[str, Any]]:
        """
        Fetch account + closed_trades + open_positions from cTrader API.
        Equivalent to broker history_deals feed.
        """
        try:
            response = requests.get(self.api_url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            account = data.get('account', {})
            if account.get('balance') is None and account.get('equity') is None:
                logger.warning("[V40.4] API response missing account balance/equity")
                return None
            if not is_payload_fresh(data):
                logger.warning(
                    f"[V56] STALE broker payload rejected — {format_stale_reason(data)}"
                )
                return None
            return data
        except requests.exceptions.ConnectionError:
            logger.warning("[V40.4] cTrader API offline (8767)")
            return None
        except Exception as exc:
            logger.error(f"[V40.4] get_history_deals failed: {exc}")
            return None


class TradeManager:
    """Broker-first PNL sync for Telegram /status and /resume state recovery."""

    def __init__(self, script_dir: Optional[Path] = None):
        self.script_dir = Path(script_dir or Path(__file__).parent.resolve())
        self.client = AccountClient()
        self.trade_history_file = self.script_dir / 'trade_history.json'
        self.db_path = self.script_dir / 'data' / 'trades.db'
        self.debug_log = self.script_dir / 'system_debug.log'

    def _log_debug(self, message: str) -> None:
        try:
            ts = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            with open(self.debug_log, 'a', encoding='utf-8') as f:
                f.write(f"{ts} | {message}\n")
        except Exception as exc:
            logger.warning(f"[V40.4] system_debug.log write failed: {exc}")

    def _calc_closed_pnl(
        self,
        closed_trades: List[dict],
        today: str,
        reset_cutoff: Optional[str] = None,
        calendar_day_only: bool = False,
    ) -> Tuple[float, int]:
        """Sum profit for trades closed on `today` (YYYY-MM-DD)."""
        total = 0.0
        count = 0
        for trade in closed_trades:
            close_time = trade.get('close_time') or trade.get('closeTime') or ''
            if not close_time or close_time[:10] != today:
                continue
            if not calendar_day_only and reset_cutoff and close_time < reset_cutoff:
                continue
            total += float(trade.get('profit', 0) or 0)
            count += 1
        return total, count

    def _read_local_closed_trades(self) -> List[dict]:
        if not self.trade_history_file.exists():
            return []
        try:
            with open(self.trade_history_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('closed_trades', []) or []
        except Exception:
            return []

    @staticmethod
    def _close_date_yyyy_mm_dd(close_time: str) -> Optional[str]:
        """Normalize close_time to YYYY-MM-DD for window filters (ISO, display, DD/MM)."""
        if not close_time:
            return None
        raw = str(close_time).strip()
        if len(raw) >= 10 and raw[4] == '-' and raw[7] == '-':
            return raw[:10]
        if len(raw) >= 10 and raw[2] == '/' and raw[5] == '/':
            try:
                return datetime.strptime(raw[:10], '%d/%m/%Y').strftime('%Y-%m-%d')
            except ValueError:
                pass
        try:
            from dashboard_time_utils import _parse_utc
            utc_dt = _parse_utc(raw)
            if utc_dt is not None:
                return utc_dt.strftime('%Y-%m-%d')
        except Exception:
            pass
        return None

    def _calc_weekly_stats(self, closed_trades: List[dict], week_ago: str) -> Dict[str, Any]:
        """Aggregate closed trades since week_ago (YYYY-MM-DD, inclusive)."""
        total = wins = losses = 0
        total_pnl = 0.0
        best_trade: Optional[float] = None
        worst_trade: Optional[float] = None
        for trade in closed_trades:
            close_date = self._close_date_yyyy_mm_dd(
                trade.get('close_time') or trade.get('closeTime') or ''
            )
            if not close_date or close_date < week_ago:
                continue
            profit = float(trade.get('profit', 0) or 0)
            total += 1
            total_pnl += profit
            if profit > 0:
                wins += 1
            else:
                losses += 1
            if best_trade is None or profit > best_trade:
                best_trade = profit
            if worst_trade is None or profit < worst_trade:
                worst_trade = profit
        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'total_pnl': total_pnl,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
        }

    def _read_sqlite_weekly_stats(self, week_ago: str) -> Dict[str, Any]:
        empty = {
            'total': 0, 'wins': 0, 'losses': 0, 'total_pnl': 0.0,
            'best_trade': None, 'worst_trade': None,
        }
        if not self.db_path.exists():
            return empty
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END),
                    SUM(profit),
                    MAX(profit),
                    MIN(profit)
                FROM closed_trades
                WHERE DATE(close_time, 'localtime') >= ?
                """,
                (week_ago,),
            )
            row = cursor.fetchone()
            conn.close()
            if not row or not row[0]:
                return empty
            return {
                'total': int(row[0] or 0),
                'wins': int(row[1] or 0),
                'losses': int(row[2] or 0),
                'total_pnl': float(row[3] or 0.0),
                'best_trade': row[4],
                'worst_trade': row[5],
            }
        except Exception as exc:
            logger.warning(f"[V40.4] SQLite weekly read failed: {exc}")
            return empty

    def _persist_broker_payload(self, data: Dict[str, Any]) -> bool:
        """Write broker snapshot to trade_history.json + SQLite (cache only)."""
        try:
            from ctrader_sync_daemon import TradeDatabase, write_trade_history
            db = TradeDatabase(str(self.db_path))
            return bool(write_trade_history(data, db))
        except Exception as exc:
            logger.error(f"[V40.4] persist broker payload failed: {exc}")
            return False

    def fetch_broker_live(self) -> Optional[Dict[str, Any]]:
        """
        Live IC Markets feed via TradeHistorySyncer (localhost:8767).

        Returns in-memory broker payload; persists locally as side-effect cache.
        """
        data = self.client.get_history_deals()
        if not data:
            return None
        self._persist_broker_payload(data)
        return data

    def refresh_account_balance(self) -> bool:
        """
        State Recovery: pull fresh deals from cTrader and persist locally.
        Returns True if trade_history.json was updated.
        """
        data = self.fetch_broker_live()
        if data:
            logger.info("[V40.4] refresh_account_balance — broker → local sync OK")
            return True
        return False

    def get_weekly_pnl(self, week_ago: str) -> Dict[str, Any]:
        """
        Weekly stats from live cTrader broker (8767).

        Aggregates closed_trades directly from the HTTP response — not from stale JSON.
        Local JSON/SQLite used only when cBot is offline.
        """
        broker_data = self.fetch_broker_live()

        if broker_data:
            broker_trades = broker_data.get('closed_trades', []) or []
            stats = self._calc_weekly_stats(broker_trades, week_ago)
            balance = float(broker_data.get('account', {}).get('balance', 0) or 0)
            return {
                **stats,
                'broker_synced': True,
                'source': 'ctrader_broker:8767',
                'balance': balance,
                'week_ago': week_ago,
            }

        logger.warning("[V40.4] cTrader offline — weekly report using local cache")
        local_stats = self._calc_weekly_stats(self._read_local_closed_trades(), week_ago)
        source = 'trade_history.json(offline)'
        stats = local_stats

        if stats['total'] == 0:
            sqlite_stats = self._read_sqlite_weekly_stats(week_ago)
            if sqlite_stats['total'] > 0:
                stats = sqlite_stats
                source = 'trades.db(offline)'

        return {
            **stats,
            'broker_synced': False,
            'source': source,
            'balance': 0.0,
            'week_ago': week_ago,
        }

    def _read_sqlite_closed_trades(self, today: str, reset_cutoff: Optional[str]) -> Tuple[float, int]:
        if not self.db_path.exists():
            return 0.0, 0
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            if reset_cutoff:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(profit), 0), COUNT(*)
                    FROM closed_trades
                    WHERE DATE(close_time, 'localtime') = ?
                      AND close_time >= ?
                    """,
                    (today, reset_cutoff),
                )
            else:
                cursor.execute(
                    """
                    SELECT COALESCE(SUM(profit), 0), COUNT(*)
                    FROM closed_trades
                    WHERE DATE(close_time, 'localtime') = ?
                    """,
                    (today,),
                )
            row = cursor.fetchone()
            conn.close()
            return float(row[0] or 0), int(row[1] or 0)
        except Exception as exc:
            logger.warning(f"[V40.4] SQLite read failed: {exc}")
            return 0.0, 0

    def get_today_pnl(
        self,
        today: str,
        reset_cutoff: Optional[str] = None,
        starting_balance: float = 0.0,
        calendar_day_pnl: bool = True,
    ) -> Dict[str, Any]:
        """
        V40.4: Broker-first today's P/L.

        calendar_day_pnl=True → sum ALL closed deals today (00:00–now), ignore session cutoff.
        Used for /status display so /resume does not hide morning losses.
        """
        local_trades = self._read_local_closed_trades()
        local_pnl, local_count = self._calc_closed_pnl(
            local_trades, today, reset_cutoff=None, calendar_day_only=True
        )

        broker_data = self.fetch_broker_live()
        synced = broker_data is not None

        if broker_data:
            broker_trades = broker_data.get('closed_trades', []) or []
            balance = float(broker_data.get('account', {}).get('balance', 0) or 0)
        else:
            broker_trades = []
            balance = 0.0

        if calendar_day_pnl:
            closed_pnl, trade_count = self._calc_closed_pnl(
                broker_trades, today, reset_cutoff=None, calendar_day_only=True
            )
        else:
            closed_pnl, trade_count = self._calc_closed_pnl(
                broker_trades, today, reset_cutoff=reset_cutoff, calendar_day_only=False
            )

        if synced and abs(local_pnl - closed_pnl) > DESYNC_THRESHOLD_USD:
            msg = (
                f"[ALERT] PNL Desync Detected: Local: {local_pnl:+.2f}, "
                f"Real: {closed_pnl:+.2f}. Syncing..."
            )
            self._log_debug(msg)
            logger.warning(msg)

        if not broker_trades and local_trades and not synced:
            closed_pnl, trade_count = local_pnl, local_count

        if closed_pnl == 0.0 and trade_count == 0 and self.db_path.exists():
            sq_pnl, sq_count = self._read_sqlite_closed_trades(
                today, None if calendar_day_pnl else reset_cutoff
            )
            if sq_count > 0:
                closed_pnl, trade_count = sq_pnl, sq_count

        base = starting_balance if starting_balance > 0 else balance
        pnl_pct = (closed_pnl / base * 100) if base > 0 else 0.0

        return {
            'closed_pnl': closed_pnl,
            'trade_count': trade_count,
            'pnl_pct': pnl_pct,
            'balance': balance,
            'broker_synced': synced,
            'local_pnl_before_sync': local_pnl,
        }

    def recover_state_since_midnight(self, today: str) -> Dict[str, Any]:
        """
        /resume State Recovery: sync broker deals from calendar day start.
        Returns summary for logging/Telegram.
        """
        before = self._read_local_closed_trades()
        before_pnl, before_count = self._calc_closed_pnl(
            before, today, reset_cutoff=None, calendar_day_only=True
        )
        ok = self.refresh_account_balance()
        after = self._read_local_closed_trades()
        after_pnl, after_count = self._calc_closed_pnl(
            after, today, reset_cutoff=None, calendar_day_only=True
        )
        if ok and abs(before_pnl - after_pnl) > DESYNC_THRESHOLD_USD:
            self._log_debug(
                f"[ALERT] PNL Desync Detected: Local: {before_pnl:+.2f}, "
                f"Real: {after_pnl:+.2f}. Syncing..."
            )
        return {
            'sync_ok': ok,
            'today_pnl': after_pnl,
            'trade_count': after_count,
            'before_pnl': before_pnl,
        }
