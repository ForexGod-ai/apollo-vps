#!/usr/bin/env python3
"""Print V74 D1 state-machine bias table for scanner verification."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from smc_detector import SMCDetector

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"

SYMBOLS = ("USDCAD", "USDCHF", "BTCUSD", "XAUUSD", "EURGBP", "EURJPY")
EXPECTED = {
    "USDCAD": "bullish",
    "USDCHF": "bullish",
    "BTCUSD": "bullish",
    "XAUUSD": "bullish",
    "EURGBP": "bearish",
    "EURJPY": "bearish",
}


def load_d1(symbol: str, tail: int = 400) -> pd.DataFrame:
    matches = list(CACHE.glob(f"{symbol}_D1_*.csv"))
    if not matches:
        raise SystemExit(f"No cache for {symbol}")
    path = max(matches, key=lambda p: p.stat().st_size)
    df = pd.read_csv(path)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-tail:]


def main() -> None:
    det = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    print("| Symbol | Expected | V74 Actual | Match |")
    print("|--------|----------|------------|-------|")
    for symbol in SYMBOLS:
        ctx = det.build_d1_context(load_d1(symbol), symbol=symbol)
        exp = EXPECTED[symbol].upper()
        act = (ctx.trend or "neutral").upper()
        ok = "OK" if ctx.trend == EXPECTED[symbol] else "—"
        print(f"| {symbol} | {exp} | {act} | {ok} |")


if __name__ == "__main__":
    main()
