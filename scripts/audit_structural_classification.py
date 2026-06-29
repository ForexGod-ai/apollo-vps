#!/usr/bin/env python3
"""
Audit V44.2 — CONTINUATION vs REVERSAL + D1 lookback + body-close CHoCH/BOS.

Module map (fișierele din brief → cod real):
  structural_analyzer / daily_bias → smc_detector.py (_resolve_d1_leg)
  h4_radar                         → multi_tf_radar.py (4H/1H structure + JSON merge)

Usage:
  python scripts/audit_structural_classification.py
  python scripts/audit_structural_classification.py --symbol BTCUSD EURUSD
  python scripts/audit_structural_classification.py --symbol BTCUSD --debug
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from smc_detector import SMCDetector, CHoCH, BOS  # noqa: E402


def _load_daily(symbol: str, bars: int):
    from daily_scanner import CTraderDataProvider

    dp = CTraderDataProvider()
    if not dp.connect():
        print("WARN: cBot offline — skip live audit or use cache CSV")
        return None
    return dp.get_historical_data(symbol, "D1", bars)


def audit_symbol(detector: SMCDetector, symbol: str, d1_bars: int, debug: bool) -> dict:
    df = _load_daily(symbol, d1_bars)
    if df is None or df.empty:
        return {"symbol": symbol, "error": "no_d1_data", "bars": 0}

    n = len(df)
    chochs, bos_list = detector.detect_choch_and_bos(df)
    sh = detector.detect_swing_highs(df)
    sl = detector.detect_swing_lows(df)
    rs = detector.compute_structural_range(df, sh, sl, symbol=symbol)
    chochs, bos_list, rs = detector.filter_internal_range_signals(
        symbol, df, chochs, bos_list, rs
    )
    latest, strategy, trend, leg = detector._resolve_d1_leg(
        df, chochs, bos_list, debug=debug, range_state=rs
    )
    reason = f"{strategy}_via_resolve_d1_leg"
    bias = detector.determine_daily_trend(df, debug=debug, symbol=symbol)

    signal_kind = None
    if latest is not None:
        signal_kind = "CHoCH" if isinstance(latest, CHoCH) else "BOS"

    # JSON radar fields (stale check)
    json_path = ROOT / "monitoring_setups.json"
    json_row = {}
    if json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        setups = data.get("setups", data if isinstance(data, list) else [])
        for s in setups:
            if s.get("symbol") == symbol:
                json_row = {
                    k: s.get(k)
                    for k in (
                        "strategy_type", "direction", "status",
                        "h4_structure_locked", "radar_h4_choch_direction",
                        "radar_verdict", "EXECUTE_NOW",
                    )
                }
                break

    report = {
        "symbol": symbol,
        "d1_bars_loaded": n,
        "d1_lookback_ok": n >= 200,
        "daily_bias": bias,
        "strategy_type": strategy,
        "current_trend": trend,
        "classify_reason": reason,
        "latest_signal": signal_kind,
        "latest_signal_bar": getattr(latest, "index", None),
        "leg_choch_bar": getattr(leg, "index", None) if leg else None,
        "choch_count": len(chochs),
        "bos_count": len(bos_list),
        "json_snapshot": json_row,
    }
    return report


def main():
    parser = argparse.ArgumentParser(description="Audit structural classification V44.2")
    parser.add_argument("--symbol", nargs="+", default=["BTCUSD", "EURUSD"])
    parser.add_argument("--d1-bars", type=int, default=300)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    detector = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    print("=" * 70)
    print("  V44.2 STRUCTURAL CLASSIFICATION AUDIT")
    print("=" * 70)

    for sym in args.symbol:
        print(f"\n--- {sym} ---")
        r = audit_symbol(detector, sym, args.d1_bars, args.debug)
        if r.get("error"):
            print(f"  ERROR: {r['error']}")
            continue
        print(f"  D1 bars: {r['d1_bars_loaded']} (lookback OK: {r['d1_lookback_ok']})")
        print(f"  daily_bias: {r['daily_bias']}")
        print(f"  strategy_type: {r['strategy_type'].upper()} ({r['classify_reason']})")
        print(f"  latest: {r['latest_signal']} @ bar {r['latest_signal_bar']}")
        print(f"  leg CHoCH @ bar {r['leg_choch_bar']} | CHoCH={r['choch_count']} BOS={r['bos_count']}")
        if r["json_snapshot"]:
            print(f"  JSON: {json.dumps(r['json_snapshot'], default=str)}")
        else:
            print("  JSON: (symbol not in monitoring_setups.json)")


if __name__ == "__main__":
    main()
