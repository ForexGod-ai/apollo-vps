#!/usr/bin/env python3
"""
Audit V57 — CONTINUATION vs REVERSAL + D1 lookback + leg validity.

Usage:
  python scripts/audit_structural_classification.py
  python scripts/audit_structural_classification.py --symbol BTCUSD EURUSD
  python scripts/audit_structural_classification.py --symbol EURUSD --cache
  python scripts/audit_structural_classification.py --symbol BTCUSD --debug
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from smc_detector import SMCDetector, CHoCH, BOS  # noqa: E402


def _load_daily_from_cache(symbol: str, bars: int) -> pd.DataFrame | None:
    cache_dir = ROOT / "data" / "historical_cache"
    if not cache_dir.exists():
        return None
    matches = sorted(cache_dir.glob(f"{symbol}_D1_*.csv"), key=lambda p: p.stat().st_mtime)
    if not matches:
        return None
    df = pd.read_csv(matches[-1])
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    elif "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"])
        df = df.set_index("datetime")
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close"])
    if bars and len(df) > bars:
        df = df.iloc[-bars:]
    return df


def _load_daily(symbol: str, bars: int, use_cache: bool):
    if use_cache:
        df = _load_daily_from_cache(symbol, bars)
        if df is not None and not df.empty:
            return df
    from daily_scanner import CTraderDataProvider

    dp = CTraderDataProvider()
    if not dp.connect():
        df = _load_daily_from_cache(symbol, bars)
        if df is not None and not df.empty:
            return df
        return None
    return dp.get_historical_data(symbol, "D1", bars)


def _macro_trend_swings(detector: SMCDetector, df: pd.DataFrame) -> str:
    sh = detector.detect_swing_highs(df)
    sl = detector.detect_swing_lows(df)
    if len(sh) < 3 or len(sl) < 3:
        return "neutral"
    recent_highs = sh[-3:]
    recent_lows = sl[-3:]
    hh = sum(
        1 for i in range(1, len(recent_highs))
        if recent_highs[i].price > recent_highs[i - 1].price
    )
    lh = sum(
        1 for i in range(1, len(recent_highs))
        if recent_highs[i].price < recent_highs[i - 1].price
    )
    hl = sum(
        1 for i in range(1, len(recent_lows))
        if recent_lows[i].price > recent_lows[i - 1].price
    )
    ll = sum(
        1 for i in range(1, len(recent_lows))
        if recent_lows[i].price < recent_lows[i - 1].price
    )
    if hh >= 2 and hl >= 2:
        return "bullish"
    if ll >= 2 and lh >= 2:
        return "bearish"
    return "neutral"


def _v45_v40_diagnostics(
    detector: SMCDetector,
    df: pd.DataFrame,
    chochs: list,
    rs,
) -> dict:
    close = float(df["close"].iloc[-1])
    out = {
        "v40_breakdown_eligible": False,
        "v45_would_supersede": False,
        "v40_breakdown_blocked_by_v58": False,
        "below_ll": False,
    }
    if rs is None or not rs.locked or rs.locked_bias != "bearish":
        return out
    _ll = float(rs.macro_range_low)
    out["below_ll"] = close <= _ll
    if not out["below_ll"]:
        return out
    out["v40_breakdown_eligible"] = True
    _last = chochs[-1] if chochs else None
    if _last is None:
        return out
    old_v45 = (
        _last.direction == "bullish"
        and _last.index >= rs.macro_range_low_bar
    )
    new_v45 = (
        _last.direction == "bullish"
        and close > _ll
        and detector._bar_body_close_above(df, _last.index, _ll)
    )
    out["v45_would_supersede"] = old_v45
    out["v40_breakdown_blocked_by_v58"] = old_v45 and not new_v45
    return out


def audit_symbol(
    detector: SMCDetector, symbol: str, d1_bars: int, debug: bool, use_cache: bool,
) -> dict:
    df = _load_daily(symbol, d1_bars, use_cache)
    if df is None or df.empty:
        return {"symbol": symbol, "error": "no_d1_data", "bars": 0}

    n = len(df)
    close = float(df["close"].iloc[-1])
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

    leg_still_valid = None
    leg_break_price = None
    if leg is not None:
        leg_still_valid = detector._leg_choch_still_valid(df, leg, bos_list)
        leg_break_price = float(leg.break_price)

    bearish_after_leg = []
    v434_would_trigger = False
    if leg is not None and leg.direction == "bullish":
        bearish_after_leg = [
            c for c in chochs
            if c.index > leg.index and c.direction == "bearish"
        ]
        drop_pct = 0.0
        if rs and rs.macro_range_high:
            drop_pct = (float(rs.macro_range_high) - close) / float(rs.macro_range_high) * 100.0
        leg_invalid = leg_still_valid is False
        if leg_invalid and len(bearish_after_leg) >= 1:
            v434_would_trigger = True
        elif rs and rs.locked and rs.locked_bias == "bearish":
            v434_would_trigger = drop_pct >= 5.0 or len(bearish_after_leg) > 2
        elif drop_pct >= 10.0 and len(bearish_after_leg) > 2:
            v434_would_trigger = True

    signal_kind = None
    if latest is not None:
        signal_kind = "CHoCH" if isinstance(latest, CHoCH) else "BOS"

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

    return {
        "symbol": symbol,
        "d1_bars_loaded": n,
        "d1_lookback_ok": n >= 200,
        "data_source": "cache" if use_cache else "live_or_cache_fallback",
        "daily_bias": bias,
        "strategy_type": strategy,
        "current_trend": trend,
        "classify_reason": reason,
        "latest_signal": signal_kind,
        "latest_signal_bar": getattr(latest, "index", None),
        "leg_choch_bar": getattr(leg, "index", None) if leg else None,
        "leg_still_valid": leg_still_valid,
        "leg_break_price": leg_break_price,
        "close": close,
        "macro_trend_swings": detector.macro_trend_from_swings(df),
        "structural_fallback_bias": detector.resolve_structural_bias_fallback(
            df, chochs, bos_list, rs,
        ),
        "bearish_choch_post_leg": len(bearish_after_leg),
        "v434_would_trigger": v434_would_trigger,
        **(_v45_v40_diagnostics(detector, df, chochs, rs)),
        "choch_count": len(chochs),
        "bos_count": len(bos_list),
        "json_snapshot": json_row,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit structural classification V58")
    parser.add_argument("--symbol", nargs="+", default=["BTCUSD", "EURUSD"])
    parser.add_argument("--d1-bars", type=int, default=300)
    parser.add_argument("--cache", action="store_true", help="Use local historical_cache CSV")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    detector = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    print("=" * 70)
    print("  V58 STRUCTURAL CLASSIFICATION AUDIT")
    print("=" * 70)

    for sym in args.symbol:
        print(f"\n--- {sym} ---")
        r = audit_symbol(detector, sym, args.d1_bars, args.debug, args.cache)
        if r.get("error"):
            print(f"  ERROR: {r['error']}")
            continue
        print(f"  D1 bars: {r['d1_bars_loaded']} (lookback OK: {r['d1_lookback_ok']})")
        print(f"  daily_bias: {r['daily_bias']}")
        print(f"  strategy_type: {r['strategy_type'].upper()} ({r['classify_reason']})")
        print(f"  current_trend: {r['current_trend']}")
        print(f"  latest: {r['latest_signal']} @ bar {r['latest_signal_bar']}")
        print(f"  leg CHoCH @ bar {r['leg_choch_bar']} | valid={r['leg_still_valid']} "
              f"break={r['leg_break_price']} close={r['close']:.5f}")
        print(f"  macro_swings: {r['macro_trend_swings']} | bearish post-leg: {r['bearish_choch_post_leg']}")
        print(f"  structural_fallback: {r['structural_fallback_bias']}")
        print(f"  v434_would_trigger: {r['v434_would_trigger']}")
        print(f"  v40_breakdown: eligible={r['v40_breakdown_eligible']} "
              f"v58_blocked={r['v40_breakdown_blocked_by_v58']} below_ll={r['below_ll']}")
        print(f"  CHoCH={r['choch_count']} BOS={r['bos_count']}")
        if r["json_snapshot"]:
            print(f"  JSON: {json.dumps(r['json_snapshot'], default=str)}")
        else:
            print("  JSON: (symbol not in monitoring_setups.json)")


if __name__ == "__main__":
    main()
