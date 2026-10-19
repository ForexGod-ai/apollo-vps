"""V80 — fractal swing anchors + CHoCH cooldown (no 1–2 bar flip)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from smc_detector import SMCDetector

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"

V80_LIVE_TARGETS = {
    "USDCAD": "bullish",
    "USDCHF": "bullish",
    "GBPJPY": "bearish",
    "EURJPY": "bearish",
    "GBPUSD": "bearish",
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
    for col in ("open", "high", "low", "close"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-tail:]


def test_v80_two_red_bars_do_not_flip_bullish_leg():
    """Pullback of two bearish dailies must not CHoCH a bullish leg."""
    det = SMCDetector()
    n = 45
    idx = pd.date_range("2024-06-01", periods=n, freq="D")
    close = []
    for i in range(n):
        base = 1.30 + 0.004 * i
        wave = 0.015 * (1 if (i // 5) % 2 == 0 else -1)
        close.append(base + wave)
    close[-1] = close[-2] - 0.008
    close[-2] = close[-3] - 0.006
    df = pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.004 for c in close],
            "low": [c - 0.004 for c in close],
            "close": close,
        },
        index=idx,
    )
    sm = det.run_d1_smc_state_machine(df)
    assert sm["trend"] == "bullish", f"expected bullish after 2-bar pullback, got {sm['trend']}"


def test_v80_two_green_bars_do_not_flip_bearish_leg():
    """Two bullish dailies in a bearish leg are pullback only."""
    det = SMCDetector()
    n = 45
    idx = pd.date_range("2024-06-01", periods=n, freq="D")
    close = []
    for i in range(n):
        base = 1.50 - 0.004 * i
        wave = 0.015 * (1 if (i // 5) % 2 == 0 else -1)
        close.append(base + wave)
    close[-1] = close[-2] + 0.008
    close[-2] = close[-3] + 0.006
    df = pd.DataFrame(
        {
            "open": close,
            "high": [c + 0.004 for c in close],
            "low": [c - 0.004 for c in close],
            "close": close,
        },
        index=idx,
    )
    sm = det.run_d1_smc_state_machine(df)
    assert sm["trend"] == "bearish", f"expected bearish after 2-bar bounce, got {sm['trend']}"


def test_v80_bias_table(capsys):
    """Print V80 verification table (live targets vs cache)."""
    det = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    print("\n| Symbol | Target | Cache D1 | Status |")
    print("|--------|--------|----------|--------|")
    for symbol, target in V80_LIVE_TARGETS.items():
        df = _load_d1(symbol)
        df = df.reset_index()
        if "time" not in df.columns:
            df.rename(columns={df.columns[0]: "time"}, inplace=True)
        ctx = det.build_d1_context(df, symbol=symbol)
        act = (ctx.trend or "neutral").lower()
        st = "OK" if act == target else "CACHE≠LIVE"
        print(f"| {symbol} | {target.upper()} | {act.upper()} | {st} |")
