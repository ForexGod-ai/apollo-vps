"""Tests for news_fetcher V67.3 merge, horizon, cache, and save guards."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import news_fetcher as nf


FIXTURE = Path(__file__).parent / "fixtures" / "ff_mirror_oct2026_sample.json"
FIXED_NOW = datetime(2026, 10, 3, 13, 0, tzinfo=timezone.utc)


def test_horizon_includes_late_day_14():
    end = nf.horizon_end(FIXED_NOW, 14)
    assert end.date() == datetime(2026, 10, 18, tzinfo=timezone.utc).date()
    late = datetime(2026, 10, 17, 22, 30, tzinfo=timezone.utc)
    assert nf.event_in_horizon(late, FIXED_NOW, 14)


def test_parse_ff_mirror_oct_fixture():
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    events = nf.parse_ff_mirror_items(raw, days_ahead=14, now=FIXED_NOW)
    titles = {e["event"] for e in events}
    assert "BOJ Gov Ueda Speaks" in titles
    assert "FOMC Meeting Minutes" in titles
    assert "Employment Change" in titles
    assert all(e["impact"] in ("High", "Medium") for e in events)
    assert not any("Low Impact" in e["event"] for e in events)


def test_ff_cache_rejected_when_too_old(tmp_path, monkeypatch):
    cache_dir = tmp_path / "ff_mirror_cache"
    cache_dir.mkdir()
    cache_file = cache_dir / "thisweek.json"
    old = FIXED_NOW - timedelta(hours=72)
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cache_file.write_text(
        json.dumps({"cached_at": old.isoformat(), "events": raw}),
        encoding="utf-8",
    )
    monkeypatch.setattr(nf, "FF_MIRROR_CACHE_DIR", cache_dir)
    monkeypatch.setattr(nf, "_ff_mirror_cache_path", lambda label: cache_dir / f"{label}.json")

    loaded = nf._load_ff_mirror_cache("thisweek", days_ahead=14)
    assert loaded == []


def test_save_events_refuses_empty(tmp_path, monkeypatch):
    out = tmp_path / "upcoming_news.json"
    out.write_text('{"events": [{"event": "keep"}]}', encoding="utf-8")
    monkeypatch.setattr(nf, "OUTPUT_FILE", out)

    assert nf.save_events([]) is False
    assert "keep" in out.read_text(encoding="utf-8")


def test_fetch_ctrader_calendar_parses_high():
    payload = {
        "success": True,
        "events": [
            {
                "time": "2026-10-07 18:00:00",
                "currency": "USD",
                "impact": "High",
                "event": "FOMC Meeting Minutes",
                "forecast": None,
                "previous": None,
            },
        ],
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload

    with patch.object(nf, "datetime") as mock_dt:
        mock_dt.now.return_value = FIXED_NOW
        mock_dt.strptime = datetime.strptime
        with patch("news_fetcher.requests.get", return_value=mock_resp):
            events = nf.fetch_ctrader_calendar(days_ahead=14)

    assert len(events) == 1
    assert events[0]["event"] == "FOMC Meeting Minutes"
    assert events[0]["source"] == "ctrader_calendar"


def test_fetch_all_merged_html_primary_no_manual_ctrader():
    html_event = {
        "date": "2026-10-06",
        "time": "07:35",
        "datetime_utc": "2026-10-06T07:35:00+00:00",
        "currency": "JPY",
        "event": "BOJ Gov Ueda Speaks",
        "impact": "High",
        "forecast": "",
        "previous": "",
        "source": "forexfactory_html",
    }
    with patch.object(
        nf,
        "fetch_forexfactory_high_impact",
        return_value=([html_event], "forexfactory_html", 2),
    ):
        with patch.object(nf, "fetch_forexfactory_mirror") as mock_mirror:
            with patch.object(nf, "fetch_ctrader_calendar") as mock_ct:
                with patch.object(nf, "fetch_from_manual_calendar") as mock_man:
                    merged = nf.fetch_all_merged(days_ahead=14)

    assert len(merged) == 1
    assert merged[0]["source"] == "forexfactory_html"
    mock_mirror.assert_not_called()
    mock_ct.assert_not_called()
    mock_man.assert_not_called()
    assert nf.LAST_SOURCE_PROVIDER == "forexfactory_html"


def test_fetch_all_merged_mirror_fallback_high_only():
    mirror_events = [
        {
            "date": "2026-10-06",
            "time": "07:35",
            "datetime_utc": "2026-10-06T07:35:00+00:00",
            "currency": "JPY",
            "event": "BOJ Gov Ueda Speaks",
            "impact": "High",
            "forecast": "",
            "previous": "",
            "source": "forexfactory_mirror",
        },
        {
            "date": "2026-10-07",
            "time": "12:00",
            "datetime_utc": "2026-10-07T12:00:00+00:00",
            "currency": "USD",
            "event": "Low tier",
            "impact": "Medium",
            "forecast": "",
            "previous": "",
            "source": "forexfactory_mirror",
        },
    ]
    with patch.object(nf, "fetch_forexfactory_high_impact", return_value=([], "scrape failed", 0)):
        with patch.object(nf, "fetch_forexfactory_mirror", return_value=(mirror_events, True)):
            with patch.object(nf, "fetch_ctrader_calendar") as mock_ct:
                with patch.object(nf, "fetch_from_manual_calendar") as mock_man:
                    merged = nf.fetch_all_merged(days_ahead=14)

    assert len(merged) == 1
    assert merged[0]["impact"] == "High"
    mock_ct.assert_not_called()
    mock_man.assert_not_called()
    assert nf.LAST_SOURCE_PROVIDER == "forexfactory_mirror"


def test_save_events_allow_empty_clears_stale(tmp_path, monkeypatch):
    out = tmp_path / "upcoming_news.json"
    out.write_text('{"events": [{"event": "stale manual"}]}', encoding="utf-8")
    monkeypatch.setattr(nf, "OUTPUT_FILE", out)
    assert nf.save_events([], source_provider="forexfactory_html", allow_empty=True)
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["events"] == []
    assert payload["source_provider"] == "forexfactory_html"


def test_save_events_writes_source_provider(tmp_path, monkeypatch):
    out = tmp_path / "upcoming_news.json"
    monkeypatch.setattr(nf, "OUTPUT_FILE", out)
    nf.LAST_SOURCE_PROVIDER = "forexfactory_html"
    ok = nf.save_events([{
        "date": "2026-10-06",
        "time": "07:35",
        "datetime_utc": "2026-10-06T07:35:00+00:00",
        "currency": "JPY",
        "event": "BOJ Gov Ueda Speaks",
        "impact": "High",
        "forecast": "",
        "previous": "",
        "source": "forexfactory_html",
    }])
    assert ok
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["source_provider"] == "forexfactory_html"
    assert payload["high_count"] == 1
    assert payload["medium_count"] == 0
