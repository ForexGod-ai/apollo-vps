"""V52.2: POI touch anchor — retroactive first touch + post-POI filter."""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from poi_utils import (
    find_first_poi_touch_time,
    resolve_poi_touch_anchor,
)
from multi_tf_radar import _filter_structural_post_poi, _parse_radar_dt, _structural_event_dt


class _FakeCHoCH:
    def __init__(self, index: int, direction: str, candle_time: str):
        self.index = index
        self.direction = direction
        self.candle_time = candle_time
        self.break_price = 185.0
        self.swing_broken = type('S', (), {'price': 186.0})()


def _make_ohlc(rows):
    """rows: list of (time_iso, high, low)."""
    return pd.DataFrame(
        {
            'time': [r[0] for r in rows],
            'high': [r[1] for r in rows],
            'low': [r[2] for r in rows],
            'open': [r[2] for r in rows],
            'close': [r[1] for r in rows],
        }
    )


def test_find_first_poi_touch_time_d1():
    df_d1 = _make_ohlc([
        ('2026-07-01T00:00:00+00:00', 184.0, 183.5),
        ('2026-07-03T00:00:00+00:00', 185.5, 184.6),  # intersects POI
        ('2026-07-08T00:00:00+00:00', 186.0, 185.0),
    ])
    ts = find_first_poi_touch_time(df_d1, None, 184.54460, 184.84240)
    assert ts == '2026-07-03T00:00:00+00:00'


def test_resolve_poi_touch_anchor_picks_earliest():
    historical = '2026-07-03T00:00:00+00:00'
    d1_today = '2026-07-08T00:00:00+00:00'
    now_ts = '2026-07-08T10:00:00+00:00'
    anchor = resolve_poi_touch_anchor(
        d1_touch_time=d1_today,
        now_ts=now_ts,
        historical_touch=historical,
        existing=None,
    )
    assert anchor == historical


def test_resolve_poi_touch_anchor_never_advances_existing():
    existing = '2026-07-03T00:00:00+00:00'
    d1_today = '2026-07-08T00:00:00+00:00'
    anchor = resolve_poi_touch_anchor(
        d1_touch_time=d1_today,
        now_ts='2026-07-08T10:00:00+00:00',
        historical_touch='2026-07-05T00:00:00+00:00',
        existing=existing,
    )
    assert anchor == existing


def test_bearish_choch_passes_post_poi_after_retroactive_anchor():
    """EURJPY-style: CHoCH bearish T-2d, POI touch T-3d, bad anchor = today → fix passes."""
    poi_touch = datetime(2026, 7, 3, tzinfo=timezone.utc)
    choch_time = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    bad_anchor = datetime(2026, 7, 8, 0, 0, tzinfo=timezone.utc)

    choch = _FakeCHoCH(10, 'bearish', choch_time.isoformat())
    filtered_bad = _filter_structural_post_poi([choch], bad_anchor)
    assert len(filtered_bad) == 0

    filtered_good = _filter_structural_post_poi([choch], poi_touch)
    assert len(filtered_good) == 1
    assert _structural_event_dt(filtered_good[0]) == choch_time


def test_retroactive_anchor_corrects_stored_json_anchor():
    """Simulate backfill: stored anchor today, historical touch 3 days ago."""
    stored = '2026-07-08T00:00:00+00:00'
    historical = '2026-07-03T00:00:00+00:00'
    corrected = resolve_poi_touch_anchor(
        d1_touch_time='2026-07-08T00:00:00+00:00',
        now_ts='2026-07-08T13:50:00+00:00',
        historical_touch=historical,
        existing=stored,
    )
    assert _parse_radar_dt(corrected) == _parse_radar_dt(historical)


def test_v55_structural_dt_int_candle_time_df_fallback():
    """V55 B2: int candle_time (RangeIndex SMC) → fallback df.iloc[index]['time']."""
    df = _make_ohlc([
        ('2026-07-06T12:00:00+00:00', 185.0, 184.0),
        ('2026-07-07T12:00:00+00:00', 186.0, 185.0),
    ])
    ev = type('E', (), {'index': 0, 'candle_time': 999})()
    dt = _structural_event_dt(ev, df)
    assert dt == _parse_radar_dt('2026-07-06T12:00:00+00:00')


def test_v55_same_bar_post_poi_inclusive():
    """V55 B8: CHoCH pe aceeași lumânărică ca POI touch → post_poi valid (>=)."""
    anchor = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)
    choch = _FakeCHoCH(0, 'bearish', anchor.isoformat())
    df = _make_ohlc([
        (anchor.isoformat(), 185.0, 184.0),
    ])
    filtered = _filter_structural_post_poi([choch], anchor, df)
    assert len(filtered) == 1
