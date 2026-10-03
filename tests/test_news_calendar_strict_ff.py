"""Strict FF loader — no manual merge when upcoming_news is FF-sourced."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import news_calendar_utils as ncu

FIXED_NOW = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)


def test_load_high_impact_skips_manual_when_ff_sourced(tmp_path, monkeypatch):
    upcoming = tmp_path / "upcoming_news.json"
    manual_path = tmp_path / "economic_calendar.json"
    upcoming.write_text(
        json.dumps({
            "source_provider": "forexfactory_html",
            "last_updated": FIXED_NOW.isoformat(),
            "events": [{
                "date": "2026-10-06",
                "time": "07:35",
                "datetime_utc": "2026-10-06T07:35:00+00:00",
                "currency": "JPY",
                "event": "BOJ Gov Ueda Speaks",
                "impact": "High",
                "forecast": "",
                "previous": "",
                "source": "forexfactory_html",
            }],
        }),
        encoding="utf-8",
    )
    manual_path.write_text(
        json.dumps({
            "custom_events_october_2026": [{
                "date": "2026-10-08",
                "time": "12:30",
                "datetime_utc": "2026-10-08T12:30:00+00:00",
                "currency": "USD",
                "event": "Unemployment Claims",
                "impact": "High",
                "forecast": "",
                "previous": "",
            }],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(ncu, "UPCOMING_NEWS_FILE", upcoming)
    monkeypatch.setattr(ncu, "CALENDAR_FILE", manual_path)

    events = ncu.load_high_impact_events(days_ahead=14)
    titles = {e["event"] for e in events}
    assert "BOJ Gov Ueda Speaks" in titles
    assert "Unemployment Claims" not in titles
