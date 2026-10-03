"""Tests for ForexFactory HTML scraper (High impact CSS only)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import ff_calendar_scraper as ffs
import news_fetcher as nf

FIXTURE = Path(__file__).parent / "fixtures" / "ff_calendar_week_oct2026.html"
FIXED_NOW = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)
TZ = ZoneInfo("Europe/Bucharest")


def test_parse_high_impact_fixture_excludes_medium():
    html = FIXTURE.read_text(encoding="utf-8")
    events = ffs.parse_high_impact_rows(
        html,
        TZ,
        now=FIXED_NOW,
        days_ahead=14,
        event_in_horizon=nf.event_in_horizon,
    )
    titles = {e["event"] for e in events}
    assert "BOJ Gov Ueda Speaks" in titles
    assert "FOMC Meeting Minutes" in titles
    assert "Employment Change" in titles
    assert "Unemployment Rate" in titles
    assert "CPI m/m" in titles
    assert "GDP m/m" in titles
    assert "Unemployment Claims" not in titles
    assert "ISM Services PMI" not in titles
    assert "Import Prices m/m" not in titles
    assert all(e["impact"] == "High" for e in events)
    assert all(e["source"] == "forexfactory_html" for e in events)


def test_build_week_urls_covers_horizon():
    urls = ffs.build_week_urls(FIXED_NOW, days_ahead=14)
    assert any("week=oct" in u for u in urls)
    assert len(urls) >= 2


def test_ff_week_slug():
    sunday = datetime(2026, 10, 4, tzinfo=timezone.utc)
    assert ffs.ff_week_slug(sunday) == "oct4.2026"
