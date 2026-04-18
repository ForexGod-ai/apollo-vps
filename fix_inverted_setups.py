"""
fix_inverted_setups.py — V1.0 (18 Apr 2026)
============================================
Fixes 3 broken setups in monitoring_setups.json:

  1. GBPJPY BUY  — TP 206.905 BELOW entry 212.943 (inverted)
  2. GBPNZD SELL — TP 2.26099 ABOVE entry 2.25858 (inverted)
  3. XTIUSD BUY  — FVG at 98-104 is stale; correct FVG is ~60$

For each:
  - Fetches live D1 data from cTrader port 8010
  - Detects correct D1 swing target for TP
  - For XTIUSD: detects nearest D1 FVG to entry_price (~60.765)
  - Recalculates risk_reward
  - Patches monitoring_setups.json in-place
  - Removes _audit_warning flags

Run on VPS: python fix_inverted_setups.py
"""

import json
import os
import sys

# ── imports (same env as rest of project) ──────────────────────────────────────
try:
    from ctrader_cbot_client import CTraderCBotClient
    import pandas as pd
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

SETUPS_PATH = os.path.join(os.path.dirname(__file__), "monitoring_setups.json")
PORT = 8010

# ──────────────────────────────────────────────────────────────────────────────
def get_data(symbol: str, tf: str, bars: int) -> "pd.DataFrame | None":
    client = CTraderCBotClient()
    if not client.is_available():
        print(f"❌ cTrader port {PORT} not available. Start MarketDataProvider cBot.")
        return None
    df = client.get_historical_data(symbol, tf, bars)
    if df is None or df.empty:
        print(f"⚠️ No data for {symbol} {tf}")
        return None
    df = df.reset_index()
    return df


def detect_swing_highs(df: "pd.DataFrame", window: int = 10) -> list:
    """Return list of (idx, price) for swing highs."""
    highs = []
    for i in range(window, len(df) - window):
        local_max = df["high"].iloc[i - window:i + window + 1].max()
        if df["high"].iloc[i] == local_max:
            highs.append((i, float(df["high"].iloc[i])))
    return highs


def detect_swing_lows(df: "pd.DataFrame", window: int = 10) -> list:
    """Return list of (idx, price) for swing lows."""
    lows = []
    for i in range(window, len(df) - window):
        local_min = df["low"].iloc[i - window:i + window + 1].min()
        if df["low"].iloc[i] == local_min:
            lows.append((i, float(df["low"].iloc[i])))
    return lows


def detect_d1_fvgs(df: "pd.DataFrame") -> list:
    """
    Detect Fair Value Gaps on D1.
    Returns list of dicts: {top, bottom, direction, bar_idx}
    An FVG exists at bar i when:
      Bullish FVG: df.low[i+1] > df.high[i-1]  → gap between candle i-1 high and candle i+1 low
      Bearish FVG: df.high[i+1] < df.low[i-1]  → gap between candle i-1 low and candle i+1 high
    """
    fvgs = []
    for i in range(1, len(df) - 1):
        prev_high = df["high"].iloc[i - 1]
        prev_low  = df["low"].iloc[i - 1]
        next_high = df["high"].iloc[i + 1]
        next_low  = df["low"].iloc[i + 1]

        if next_low > prev_high:
            # Bullish FVG
            fvgs.append({
                "top": float(next_low),
                "bottom": float(prev_high),
                "direction": "bullish",
                "bar_idx": i,
            })
        elif next_high < prev_low:
            # Bearish FVG
            fvgs.append({
                "top": float(prev_low),
                "bottom": float(next_high),
                "direction": "bearish",
                "bar_idx": i,
            })
    return fvgs


# ──────────────────────────────────────────────────────────────────────────────
def fix_gbpjpy(setup: dict) -> dict:
    """
    GBPJPY BUY — recalculate TP as nearest D1 swing HIGH above entry.
    """
    symbol = "GBPJPY"
    entry  = setup["entry_price"]   # 212.943
    sl     = setup["stop_loss"]     # 211.680

    print(f"\n{'='*60}")
    print(f"🔧 Fixing {symbol} BUY — entry={entry}, SL={sl}")
    print(f"   Current (WRONG) TP = {setup['take_profit']} (below entry!)")

    df = get_data(symbol, "D1", 500)
    if df is None:
        print("   ❌ Cannot fix — no data")
        return setup

    current_price = float(df["close"].iloc[-1])
    print(f"   Current D1 close: {current_price:.3f}")

    swing_highs = detect_swing_highs(df, window=5)
    # Filter: swing highs ABOVE current price (viable upside targets)
    highs_above = [(idx, p) for idx, p in swing_highs if p > current_price]

    if highs_above:
        # Nearest swing high above price (smallest value above)
        nearest = min(highs_above, key=lambda x: x[1])
        tp = nearest[1]
        print(f"   ✅ Nearest D1 swing High above price: {tp:.3f} (bar {nearest[0]})")
    else:
        # Fallback: max D1 high in history excluding last bar
        tp = float(df["high"].iloc[:-1].max())
        print(f"   ⚠️ No swing High above price — fallback to D1 max high: {tp:.3f}")

    if tp <= entry:
        print(f"   ❌ TP {tp:.3f} still ≤ entry {entry:.3f} — GBPJPY has no D1 target above entry.")
        print("      Setup will be REMOVED (dead setup — price traded through all D1 highs above FVG).")
        return None   # Signal to remove setup

    sl_dist = abs(entry - sl)
    rr = abs(tp - entry) / sl_dist if sl_dist > 0 else 0

    print(f"   ✅ Fixed TP = {tp:.3f} | RR = 1:{rr:.2f}")
    setup["take_profit"] = round(tp, 5)
    setup["risk_reward"] = round(rr, 6)
    setup.pop("_audit_warning", None)
    return setup


# ──────────────────────────────────────────────────────────────────────────────
def fix_gbpnzd(setup: dict) -> dict:
    """
    GBPNZD SELL — recalculate TP as nearest D1 swing LOW below entry.
    entry1 already filled at 2.30018 — keep the position managed.
    """
    symbol = "GBPNZD"
    entry  = setup["entry_price"]   # 2.25858
    sl     = setup["stop_loss"]     # 2.26255

    print(f"\n{'='*60}")
    print(f"🔧 Fixing {symbol} SELL — entry={entry}, SL={sl}")
    print(f"   Current (WRONG) TP = {setup['take_profit']} (above entry!)")
    print(f"   entry1 already filled at {setup.get('entry1_price','?')} — keeping position open")

    df = get_data(symbol, "D1", 500)
    if df is None:
        print("   ❌ Cannot fix — no data")
        return setup

    current_price = float(df["close"].iloc[-1])
    print(f"   Current D1 close: {current_price:.5f}")

    swing_lows = detect_swing_lows(df, window=5)
    # Filter: swing lows BELOW current price (viable downside targets for SELL)
    lows_below = [(idx, p) for idx, p in swing_lows if p < current_price]

    if lows_below:
        # Nearest swing low below price (largest value below = closest)
        nearest = max(lows_below, key=lambda x: x[1])
        tp = nearest[1]
        print(f"   ✅ Nearest D1 swing Low below price: {tp:.5f} (bar {nearest[0]})")
    else:
        # Fallback: min D1 low in history
        tp = float(df["low"].iloc[:-1].min())
        print(f"   ⚠️ No swing Low below price — fallback to D1 min low: {tp:.5f}")

    if tp >= entry:
        # Try second nearest
        lows_below_entry = [(idx, p) for idx, p in swing_lows if p < entry]
        if lows_below_entry:
            nearest = max(lows_below_entry, key=lambda x: x[1])
            tp = nearest[1]
            print(f"   ↩️ Retry with lows below entry zone: {tp:.5f}")
        else:
            tp = float(df["low"].iloc[:-1].min())
            print(f"   ↩️ Absolute min D1 low fallback: {tp:.5f}")

    if tp >= entry:
        print(f"   ❌ Cannot find valid TP below entry {entry:.5f} for SELL.")
        return None

    sl_dist = abs(sl - entry)
    rr = abs(entry - tp) / sl_dist if sl_dist > 0 else 0

    # Enforce minimum RR 1:4
    min_tp = entry - 4.0 * sl_dist
    if tp > min_tp:
        print(f"   ⚠️ RR {rr:.2f} too low (< 1:4) — using 1:4 floor TP = {min_tp:.5f}")
        tp = min_tp
        rr = 4.0

    print(f"   ✅ Fixed TP = {tp:.5f} | RR = 1:{rr:.2f}")
    setup["take_profit"] = round(tp, 7)
    setup["risk_reward"] = round(rr, 6)
    setup.pop("_audit_warning", None)
    return setup


# ──────────────────────────────────────────────────────────────────────────────
def fix_xtiusd(setup: dict) -> dict:
    """
    XTIUSD BUY — FVG at 98-104 is stale (price at ~60$).
    Find nearest D1 bullish FVG to entry_price (~60.765).
    Recalculate TP as nearest D1 swing High above current price.
    """
    symbol   = "XTIUSD"
    entry    = setup["entry_price"]   # 60.765
    sl       = setup["stop_loss"]     # 60.390

    print(f"\n{'='*60}")
    print(f"🔧 Fixing {symbol} BUY — entry={entry}, SL={sl}")
    print(f"   Current (WRONG) FVG = {setup['fvg_bottom']:.3f} - {setup['fvg_top']:.3f}")
    print(f"   Current (WRONG) TP  = {setup['take_profit']:.3f}")

    df = get_data(symbol, "D1", 500)
    if df is None:
        print("   ❌ Cannot fix — no data")
        return setup

    current_price = float(df["close"].iloc[-1])
    print(f"   Current D1 close: {current_price:.3f}")

    # Find nearest BULLISH FVG to entry_price
    fvgs = detect_d1_fvgs(df)
    bullish_fvgs = [f for f in fvgs if f["direction"] == "bullish"]

    if bullish_fvgs:
        # Sort by proximity of zone midpoint to entry
        def midpoint_dist(f):
            mid = (f["top"] + f["bottom"]) / 2
            return abs(mid - entry)

        nearest_fvg = min(bullish_fvgs, key=midpoint_dist)
        fvg_top    = nearest_fvg["top"]
        fvg_bottom = nearest_fvg["bottom"]
        print(f"   ✅ Nearest bullish D1 FVG: {fvg_bottom:.3f} - {fvg_top:.3f} (bar {nearest_fvg['bar_idx']})")
    else:
        # Fallback: use a zone around entry ±1 ATR
        atr = float((df["high"] - df["low"]).tail(14).mean())
        fvg_bottom = entry - atr * 0.5
        fvg_top    = entry + atr * 0.5
        print(f"   ⚠️ No bullish FVG found — using ATR zone: {fvg_bottom:.3f} - {fvg_top:.3f}")

    # Recalculate TP: nearest D1 swing High above current price
    swing_highs = detect_swing_highs(df, window=5)
    highs_above = [(idx, p) for idx, p in swing_highs if p > current_price]

    if highs_above:
        nearest_h = min(highs_above, key=lambda x: x[1])
        tp = nearest_h[1]
        print(f"   ✅ Nearest D1 swing High above price: {tp:.3f} (bar {nearest_h[0]})")
    else:
        tp = float(df["high"].iloc[:-1].max())
        print(f"   ⚠️ Fallback to D1 max high: {tp:.3f}")

    if tp <= entry:
        print(f"   ❌ XTIUSD TP {tp:.3f} ≤ entry {entry:.3f} — no upside target. Removing setup.")
        return None

    sl_dist = abs(entry - sl)
    rr = abs(tp - entry) / sl_dist if sl_dist > 0 else 0

    if rr < 4.0:
        print(f"   ⚠️ RR {rr:.2f} < 1:4 minimum. XTIUSD setup rejected — removing.")
        return None

    print(f"   ✅ Fixed FVG = {fvg_bottom:.3f} - {fvg_top:.3f}")
    print(f"   ✅ Fixed TP  = {tp:.3f} | RR = 1:{rr:.2f}")
    setup["fvg_top"]    = round(fvg_top, 5)
    setup["fvg_bottom"] = round(fvg_bottom, 5)
    setup["take_profit"] = round(tp, 5)
    setup["risk_reward"] = round(rr, 6)
    return setup


# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  fix_inverted_setups.py — V1.0 (18 Apr 2026)")
    print("=" * 60)

    # Load monitoring_setups.json
    if not os.path.exists(SETUPS_PATH):
        print(f"❌ File not found: {SETUPS_PATH}")
        sys.exit(1)

    with open(SETUPS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    setups = data.get("setups", [])
    print(f"\n📋 Loaded {len(setups)} setups from monitoring_setups.json")

    fixed_setups = []
    removed = []

    for setup in setups:
        symbol = setup.get("symbol", "")

        if symbol == "GBPJPY":
            result = fix_gbpjpy(setup)
            if result is None:
                removed.append(symbol)
                print(f"   🗑️  GBPJPY removed (no valid TP found)")
            else:
                fixed_setups.append(result)

        elif symbol == "GBPNZD":
            result = fix_gbpnzd(setup)
            if result is None:
                removed.append(symbol)
                print(f"   🗑️  GBPNZD removed (no valid TP found)")
            else:
                fixed_setups.append(result)

        elif symbol == "XTIUSD":
            result = fix_xtiusd(setup)
            if result is None:
                removed.append(symbol)
                print(f"   🗑️  XTIUSD removed (invalid RR after FVG fix)")
            else:
                fixed_setups.append(result)

        else:
            # Keep all other setups unchanged
            fixed_setups.append(setup)

    # Write back
    data["setups"] = fixed_setups
    from datetime import datetime
    data["last_update"] = datetime.utcnow().isoformat()

    with open(SETUPS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"✅ monitoring_setups.json updated")
    print(f"   Setups kept: {len(fixed_setups)}")
    if removed:
        print(f"   Setups removed: {', '.join(removed)}")
    print(f"{'='*60}\n")

    # Summary of changes
    for s in fixed_setups:
        sym = s.get("symbol", "?")
        if sym in ["GBPJPY", "GBPNZD", "XTIUSD"]:
            tp  = s.get("take_profit", "?")
            rr  = s.get("risk_reward", "?")
            fvg = f"FVG {s.get('fvg_bottom','?'):.3f}-{s.get('fvg_top','?'):.3f}" if sym == "XTIUSD" else ""
            print(f"  ✅ {sym}: TP={tp}  RR=1:{rr:.2f}  {fvg}")


if __name__ == "__main__":
    main()
