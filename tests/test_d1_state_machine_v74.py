"""V74/V77 sequential SMC state machine — bias on historical cache."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"

# V80: fractal swing anchors — cache golden table (closed D1 authority).
EXPECTED = {
    "USDCAD": "bearish",
    "USDCHF": "bearish",
    "BTCUSD": "bearish",
    "XAUUSD": "bullish",
    "EURGBP": "bearish",
    "EURJPY": "bullish",
}


def _load_d1(symbol: str, tail: int = 400) -> pd.DataFrame:
    matches = list(CACHE.glob(f"{symbol}_D1_*.csv"))
    if not matches:
        pytest.skip(f"No D1 cache for {symbol}")
    best = max(matches, key=lambda p: p.stat().st_size)
    df = pd.read_csv(best)
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    elif "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-tail:]


@pytest.mark.parametrize("symbol,expected", list(EXPECTED.items()))
def test_v74_state_machine_bias(symbol: str, expected: str):
    det = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    df = _load_d1(symbol)
    ctx = det.build_d1_context(df, symbol=symbol)
    assert ctx.trend in ("bullish", "bearish", "neutral")
    assert ctx.trend == expected, (
            f"{symbol}: got {ctx.trend}, expected {expected}, "
            f"latest={type(ctx.latest_signal).__name__ if ctx.latest_signal else None}"
        )


def test_v74_bias_table(capsys):
    """Print verification table (also runs assertions via parametrize)."""
    det = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    rows = []
    for symbol, expected in EXPECTED.items():
        df = _load_d1(symbol)
        ctx = det.build_d1_context(df, symbol=symbol)
        ok = ctx.trend == expected
        rows.append((symbol, expected, ctx.trend, "OK" if ok else "FAIL"))
    print("\n| Symbol | Expected | Actual | Status |")
    print("|--------|----------|--------|--------|")
    for sym, exp, act, st in rows:
        print(f"| {sym} | {exp.upper()} | {act.upper()} | {st} |")
    assert all(st == "OK" for _, _, _, st in rows), rows


def test_v77_protected_low_advances_after_bos_not_global_wick_floor():
    """V80: protected low trails major/fractal HL on BOS (not ancient wick floor)."""
    det = SMCDetector()
    n = 45
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = []
    for i in range(n):
        close.append(1.34 + 0.003 * i + 0.01 * (1 if (i // 6) % 2 else -1))
    df = pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.005 for c in close],
            "low": [c - 0.005 for c in close],
            "close": close,
        },
        index=idx,
    )
    df.loc[df.index[0], "low"] = 1.330
    sm = det.run_d1_smc_state_machine(df)
    assert sm["trend"] == "bullish"
    assert sm["protected_low"] is not None
    assert sm["protected_low"] >= 1.36, (
        f"protected_low should reflect recent fractal HL, got {sm['protected_low']}"
    )
