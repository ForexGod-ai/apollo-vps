#!/usr/bin/env python3
"""V46 sanity: EURJPY SELL impulse anchor + Premium/Discount 60–80% band."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from multi_tf_radar import (
    PullbackStatus,
    _RETRACE_ENTRY_MAX,
    _RETRACE_ENTRY_MIN,
    _choch_impulse_retrace_pct,
    _choch_premium_discount_zone,
    _v46_entry_status_and_note,
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def main() -> None:
    # EURJPY bearish impulse from plan (console anchor)
    swing_broken = 184.773
    break_px = 183.253
    direction = "bearish"

    retrace_at_70, impulse = _choch_impulse_retrace_pct(
        break_px, swing_broken, 184.32, direction,
    )
    lo, hi, mid = _choch_premium_discount_zone(break_px, impulse, direction)

    print(f"Impulse anchor: swing_broken {swing_broken} -> break {break_px} ({impulse:.3f})")
    print(f"Zone 60-80%: [{lo:.3f} - {hi:.3f}] midpoint={mid:.3f}")

    _assert(abs(lo - 184.165) < 0.02, f"zone bottom expected ~184.165 got {lo}")
    _assert(abs(hi - 184.469) < 0.02, f"zone top expected ~184.469 got {hi}")
    _assert(_RETRACE_ENTRY_MIN <= retrace_at_70 <= _RETRACE_ENTRY_MAX, "70% price should be in band")

    status_ok, _ = _v46_entry_status_and_note(
        "4H", "EURJPY", "bearish", in_poi_entry=True,
        retrace_pct=retrace_at_70, choch_bars_ago=26,
    )
    _assert(status_ok == PullbackStatus.EXECUTE_NOW_4H, "POI+65-70% retrace must EXECUTE at -26b CHoCH")

    retrace_deep, _ = _choch_impulse_retrace_pct(break_px, swing_broken, 185.70, direction)
    status_wait, _ = _v46_entry_status_and_note(
        "4H", "EURJPY", "bearish", in_poi_entry=False,
        retrace_pct=retrace_deep, choch_bars_ago=26,
    )
    _assert(retrace_deep > _RETRACE_ENTRY_MAX, f"185.70 should be >80% retrace, got {retrace_deep*100:.1f}%")
    _assert(status_wait == PullbackStatus.WAITING_4H_PULLBACK, "deep retrace must WAIT")

    # BUY mirror: zone below break
    buy_lo, buy_hi, _ = _choch_premium_discount_zone(100.0, 10.0, "bullish")
    _assert(buy_hi == 94.0 and buy_lo == 92.0, f"bullish zone wrong: {buy_lo}-{buy_hi}")

    print("OK — V46 EURJPY entry scenarios passed")


if __name__ == "__main__":
    main()
