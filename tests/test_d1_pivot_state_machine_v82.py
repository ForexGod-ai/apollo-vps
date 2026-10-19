"""V82 — explicit bias / protected_pivot / target_pivot transitions."""
from __future__ import annotations

import pandas as pd

from smc_detector import SMCDetector


def test_bullish_pullback_zone_does_not_change_bias():
    """Same synthetic as V80 — two red dailies must not flip bullish bias."""
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
    assert sm["trend"] == "bullish"
    assert sm["structural_hl"] is not None
    assert sm["structural_hh"] is not None


def test_bearish_pullback_zone_does_not_change_bias():
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
    assert sm["trend"] == "bearish"
