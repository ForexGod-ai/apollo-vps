#!/usr/bin/env python3
"""
Audit post-mortem cont LIVE — Aprilie → prezent
Rulează pe VPS unde trade_history.json + data/trades.db sunt populate.

Usage:
    python scripts/audit_live_postmortem.py
    python scripts/audit_live_postmortem.py --start-balance 930
    python scripts/audit_live_postmortem.py --json-out data/postmortem_report.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
TRADE_JSON = ROOT / "trade_history.json"
SQLITE_DB = ROOT / "data" / "trades.db"

# Repere arhitectură (calibrare vs producție)
PHASES = [
    ("2026-04-01", "2026-04-15", "FAZA 0 — Pre-VPS / setup inițial"),
    ("2026-04-16", "2026-04-30", "FAZA 1 — VPS migration + calibrare"),
    ("2026-05-01", "2026-05-31", "FAZA 2 — Tuning Radar/Executor"),
    ("2026-06-01", "2026-06-10", "FAZA 3 — Pre-V37 (V36.x)"),
    ("2026-06-11", "2099-12-31", "FAZA 4 — Post-V37 hardening"),
]


def _parse_dt(val: Any) -> Optional[datetime]:
    if not val:
        return None
    s = str(val).replace("Z", "+00:00").replace(" ", "T")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s[:26], fmt.replace("%z", ""))
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _phase_for(dt: Optional[datetime]) -> str:
    if not dt:
        return "UNKNOWN"
    d = dt.date().isoformat()
    for start, end, label in PHASES:
        if start <= d <= end:
            return label
    return "OUT_OF_RANGE"


def _classify_comment(comment: str) -> str:
    c = (comment or "").upper()
    if "EXECUTE_NOW" in c or "D1_EXECUTE_NOW" in c:
        return "EXECUTE_NOW (Radar)"
    if "FORCED" in c or "READY" in c:
        return "FORCED/READY (legacy)"
    if "SCALE" in c or "ENTRY2" in c or "E2" in c:
        return "Entry 2 scale-in (dezactivat V37)"
    if "V8" in c or "NOMATH" in c:
        return "V8 bypass / sizing fix"
    if "D1_" in c and "4H" in c:
        return "Tagged D1_4H_SYNC"
    if c.strip():
        return f"Other: {comment[:40]}"
    return "Fără comment (manual/broker?)"


def _load_trades_from_json() -> Tuple[Dict, List[Dict]]:
    if not TRADE_JSON.exists():
        return {}, []
    with open(TRADE_JSON, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {}, data
    account = data.get("account", {})
    trades = data.get("closed_trades", [])
    return account, trades


def _load_trades_from_sqlite() -> List[Dict]:
    if not SQLITE_DB.exists():
        return []
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT ticket, symbol, direction, volume, open_time, close_time,
                   open_price, close_price, profit, commission, swap,
                   stop_loss, take_profit, comment
            FROM closed_trades
            ORDER BY close_time ASC
            """
        )
        rows = [dict(r) for r in cur.fetchall()]
    except sqlite3.Error:
        rows = []
    conn.close()
    return rows


def _net_profit(t: Dict) -> float:
    p = float(t.get("profit") or 0)
    comm = float(t.get("commission") or 0)
    swap = float(t.get("swap") or 0)
    return p + comm + swap


def _normalize_trade(t: Dict) -> Dict:
    return {
        "ticket": t.get("ticket"),
        "symbol": (t.get("symbol") or "?").upper(),
        "direction": (t.get("direction") or t.get("type") or "?").upper(),
        "volume": float(t.get("volume") or t.get("lot_size") or t.get("lots") or 0),
        "open_time": t.get("open_time") or t.get("openTime"),
        "close_time": t.get("close_time") or t.get("closeTime"),
        "open_price": t.get("open_price") or t.get("openPrice"),
        "close_price": t.get("close_price") or t.get("closePrice"),
        "profit": _net_profit(t),
        "comment": t.get("comment") or "",
        "path": _classify_comment(t.get("comment") or ""),
        "phase": _phase_for(_parse_dt(t.get("close_time") or t.get("closeTime"))),
    }


def build_report(start_balance: float, since: Optional[str] = None, until: Optional[str] = None) -> Dict:
    account, json_trades = _load_trades_from_json()
    sqlite_trades = _load_trades_from_sqlite()
    raw = json_trades if json_trades else sqlite_trades
    trades = [_normalize_trade(t) for t in raw]

    since_dt = _parse_dt(since + "T00:00:00") if since else None
    until_dt = _parse_dt(until + "T23:59:59") if until else None

    def _in_range(t: Dict) -> bool:
        dt = _parse_dt(t.get("close_time"))
        if not dt:
            return since_dt is None and until_dt is None
        if since_dt and dt < since_dt:
            return False
        if until_dt and dt > until_dt:
            return False
        return True

    trades = [t for t in trades if _in_range(t)]
    trades.sort(key=lambda x: x.get("close_time") or "")

    current_balance = float(account.get("balance") or 0)
    if current_balance <= 0 and trades:
        current_balance = start_balance + sum(t["profit"] for t in trades)

    total_pnl = sum(t["profit"] for t in trades)
    wins = [t for t in trades if t["profit"] > 0]
    losses = [t for t in trades if t["profit"] < 0]

    by_phase: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "pnl": 0.0, "wins": 0})
    by_symbol: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    by_path: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "pnl": 0.0})
    by_month: Dict[str, Dict] = defaultdict(lambda: {"count": 0, "pnl": 0.0})

    equity = start_balance
    equity_curve: List[Dict] = [{"date": "START", "equity": equity}]
    max_equity = equity
    max_dd_pct = 0.0

    for t in trades:
        equity += t["profit"]
        equity_curve.append({
            "date": t.get("close_time"),
            "equity": round(equity, 2),
            "symbol": t["symbol"],
            "pnl": round(t["profit"], 2),
        })
        max_equity = max(max_equity, equity)
        if max_equity > 0:
            dd = (max_equity - equity) / max_equity * 100
            max_dd_pct = max(max_dd_pct, dd)

        ph = t["phase"]
        by_phase[ph]["count"] += 1
        by_phase[ph]["pnl"] += t["profit"]
        if t["profit"] > 0:
            by_phase[ph]["wins"] += 1

        sym = t["symbol"]
        by_symbol[sym]["count"] += 1
        by_symbol[sym]["pnl"] += t["profit"]

        path = t["path"]
        by_path[path]["count"] += 1
        by_path[path]["pnl"] += t["profit"]

        dt = _parse_dt(t.get("close_time"))
        month = dt.strftime("%Y-%m") if dt else "unknown"
        by_month[month]["count"] += 1
        by_month[month]["pnl"] += t["profit"]

    gross_win = sum(t["profit"] for t in wins)
    gross_loss = abs(sum(t["profit"] for t in losses))
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")

    worst = sorted(trades, key=lambda x: x["profit"])[:10]
    best = sorted(trades, key=lambda x: x["profit"], reverse=True)[:5]

    return {
        "generated_at": datetime.now().isoformat(),
        "source": "trade_history.json" if json_trades else ("data/trades.db" if sqlite_trades else "NONE"),
        "filter_since": since,
        "filter_until": until,
        "account_meta": account,
        "start_balance_assumed": start_balance,
        "current_balance_reported": current_balance,
        "computed_end_equity": round(start_balance + total_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "drawdown_pct_from_peak": round(max_dd_pct, 1),
        "loss_from_start_pct": round((start_balance - (start_balance + total_pnl)) / start_balance * 100, 1)
        if start_balance > 0 else 0,
        "trade_count": len(trades),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else 0,
        "profit_factor": round(pf, 2) if pf != float("inf") else None,
        "avg_win": round(gross_win / len(wins), 2) if wins else 0,
        "avg_loss": round(-gross_loss / len(losses), 2) if losses else 0,
        "by_phase": dict(by_phase),
        "by_symbol": dict(sorted(by_symbol.items(), key=lambda x: x[1]["pnl"])),
        "by_path": dict(by_path),
        "by_month": dict(sorted(by_month.items())),
        "worst_trades": worst,
        "best_trades": best,
        "equity_curve_tail": equity_curve[-15:],
        "calibration_note": (
            "Apr–Mai 2026 = perioadă calibrare VPS + bug-uri cunoscute (scale-in, RR XTI, "
            "READY forced, dual executor paths). V37 (11 Jun) le adresează — separă PnL pe faze."
        ),
    }


def print_report(r: Dict) -> None:
    sep = "=" * 72
    print(sep)
    print("APOLLO LIVE POST-MORTEM — Aprilie 2026 → prezent")
    print(sep)
    print(f"Sursa date     : {r['source']}")
    if r.get("filter_since") or r.get("filter_until"):
        print(f"Filtru         : {r.get('filter_since') or '...'} → {r.get('filter_until') or '...'}")
    if r["trade_count"] == 0:
        print("\n[!] ZERO trade-uri in trade_history.json / trades.db")
        print("    Ruleaza pe VPS dupa: python ctrader_sync_daemon.py (port 8767 activ)")
        print(f"    Cale asteptata: {TRADE_JSON}")
        return

    print(f"Start presupus   : ${r['start_balance_assumed']:,.2f}")
    print(f"Equity calculata : ${r['computed_end_equity']:,.2f}  (PnL total ${r['total_pnl']:+,.2f})")
    if r.get("current_balance_reported"):
        print(f"Balance JSON     : ${r['current_balance_reported']:,.2f}")
    print(f"Pierdere vs start: {r['loss_from_start_pct']:.1f}%  |  Max DD peak: {r['drawdown_pct_from_peak']:.1f}%")
    print(f"Trades           : {r['trade_count']}  |  Win rate: {r['win_rate_pct']:.1f}%  |  PF: {r['profit_factor']}")
    print(f"Avg win/loss     : ${r['avg_win']:+.2f} / ${r['avg_loss']:+.2f}")

    print(f"\n{sep}\nPE FAZA (calibrare vs productie)\n{sep}")
    for phase, stats in sorted(r["by_phase"].items()):
        wr = stats["wins"] / stats["count"] * 100 if stats["count"] else 0
        print(f"  {phase}")
        print(f"    trades={stats['count']}  PnL=${stats['pnl']:+,.2f}  WR={wr:.0f}%")

    print(f"\n{sep}\nPE LUNA\n{sep}")
    for month, stats in r["by_month"].items():
        print(f"  {month}: {stats['count']} trades  PnL=${stats['pnl']:+,.2f}")

    print(f"\n{sep}\nPE CALEA DE EXECUTIE (comment tag)\n{sep}")
    for path, stats in sorted(r["by_path"].items(), key=lambda x: -abs(x[1]["pnl"])):
        print(f"  {path}")
        print(f"    n={stats['count']}  PnL=${stats['pnl']:+,.2f}")

    print(f"\n{sep}\nTOP PIERDERI SIMBOL\n{sep}")
    sym_sorted = sorted(r["by_symbol"].items(), key=lambda x: x[1]["pnl"])
    for sym, stats in sym_sorted[:8]:
        print(f"  {sym:10} {stats['count']:3} trades  PnL=${stats['pnl']:+,.2f}")

    print(f"\n{sep}\nTOP 5 WORST TRADES\n{sep}")
    for t in r["worst_trades"][:5]:
        print(
            f"  {t.get('close_time','?')[:16]}  {t['symbol']:8} {t['direction']:4} "
            f"vol={t['volume']:.2f}  ${t['profit']:+.2f}  [{t['path']}]"
        )

    print(f"\n{sep}\nNOTA\n{sep}")
    print(f"  {r['calibration_note']}")
    print(sep)


def main() -> int:
    p = argparse.ArgumentParser(description="Apollo live post-mortem audit")
    p.add_argument("--start-balance", type=float, default=930.0, help="Balanta initiala live ($)")
    p.add_argument("--since", type=str, default="2026-04-01", help="Include doar trade-uri de la data (YYYY-MM-DD)")
    p.add_argument("--until", type=str, default="", help="Include doar trade-uri pana la data (YYYY-MM-DD)")
    p.add_argument("--json-out", type=str, default="", help="Salveaza raport JSON")
    args = p.parse_args()

    report = build_report(
        args.start_balance,
        since=args.since or None,
        until=args.until or None,
    )
    print_report(report)

    if args.json_out:
        out = Path(args.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nJSON salvat: {out}")

    return 0 if report["trade_count"] > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
