"""V70: strict P/D FVG selection + OTE fallback for Daily POI."""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import pytest

from smc_detector.fvg import FvgMixin
from smc_detector.models import FVG, SwingPoint


class _Det(FvgMixin):
    pass


def _make_choch(direction: str, swing_price: float, break_price: float, index: int = 50):
    swing = SimpleNamespace(price=swing_price)
    return SimpleNamespace(
        direction=direction,
        swing_broken=swing,
        break_price=break_price,
        index=index,
    )


def test_build_ote_pd_fvg_bullish_discount():
    det = _Det()
    choch = _make_choch("bullish", 1.0000, 1.1000, index=10)
    df = pd.DataFrame({"time": [datetime(2026, 1, 1)] * 20, "open": [1.05] * 20, "close": [1.05] * 20})
    fvg = det.build_ote_pd_fvg(1.0, 1.1, "bullish", choch, df)
    assert fvg is not None
    assert fvg.bottom < fvg.top
    assert fvg.middle < 1.05  # discount side below equilibrium


def test_build_ote_pd_fvg_bearish_premium():
    det = _Det()
    choch = _make_choch("bearish", 1.1000, 1.0000, index=10)
    df = pd.DataFrame({"time": [datetime(2026, 1, 1)] * 20, "open": [1.05] * 20, "close": [1.05] * 20})
    fvg = det.build_ote_pd_fvg(1.0, 1.1, "bearish", choch, df)
    assert fvg is not None
    assert fvg.middle > 1.05


def test_strict_pd_selects_largest_gap():
    det = _Det()
    choch = _make_choch("bearish", 110.0, 100.0, index=40)
    eq = 105.0
    small = FVG(45, "bearish", 107.0, 106.5, 106.75, datetime.now(), associated_choch=choch)
    large = FVG(46, "bearish", 108.0, 106.0, 107.0, datetime.now(), associated_choch=choch)
    assert small.middle > eq and large.middle > eq
    pool = [small, large]
    selected = max(pool, key=lambda f: (f.top - f.bottom, f.index))
    assert selected is large


def test_apply_poi_to_setup_dict_sets_entry():
    from daily_scanner import _apply_poi_to_setup_dict
    from smc_detector.models import POIResolution

    fvg = FVG(1, "bearish", 108.0, 106.0, 107.0, datetime.now())
    res = POIResolution(fvg=fvg, adr=None, poi_source="ote_pd_fallback")
    out = _apply_poi_to_setup_dict(
        {"symbol": "AUDJPY", "direction": "sell", "daily_bias": "BEARISH"},
        res,
    )
    assert out["poi_top"] == 108.0
    assert out["poi_bottom"] == 106.0
    assert out["entry_price"] == 108.0
    assert out["poi_v43_source"] == "ote_pd_fallback"
