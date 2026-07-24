"""Macro rates — live fetch, fallback chain, stale alert removal."""
from __future__ import annotations

import json
from unittest.mock import patch

import macro_rates as mr


SAMPLE_HTML = """
<table>
<tr><td>Central Bank</td><td>Current Rate</td></tr>
<tr><td>Federal Reserve (FED)</td><td>3.75%</td></tr>
<tr><td>European Central Bank (ECB)</td><td>2.40%</td></tr>
<tr><td>Bank of England (BOE)</td><td>3.75%</td></tr>
<tr><td>Swiss National Bank (SNB)</td><td>0.00%</td></tr>
<tr><td>Reserve Bank of Australia</td><td>4.35%</td></tr>
<tr><td>Bank of Canada</td><td>2.25%</td></tr>
<tr><td>Reserve Bank of New Zealand</td><td>2.50%</td></tr>
<tr><td>Bank of Japan</td><td>1.00%</td></tr>
</table>
"""


def test_parse_investing_cb_table():
    live = mr._parse_investing_cb_table(SAMPLE_HTML)
    assert len(live) >= 6
    assert live["USD"] == 3.75
    assert live["EUR"] == 2.40
    assert live["NZD"] == 2.50


def test_get_effective_rates_live_success():
    live = {"USD": 3.75, "EUR": 2.40, "GBP": 3.75, "CHF": 0.0, "AUD": 4.35, "CAD": 2.25, "NZD": 2.5, "JPY": 1.0}
    with patch.object(mr, "fetch_live_cb_rates", return_value=live), \
         patch.object(mr, "load_cache", return_value=None), \
         patch.object(mr, "save_cache") as mock_save:
        rates, source, fetched_at, changes = mr.get_effective_rates(force_refresh=True)
    assert source == "live"
    assert rates["USD"] == 3.75
    assert fetched_at
    mock_save.assert_called_once()


def test_get_effective_rates_live_fail_uses_old_cache(tmp_path):
    cache_file = tmp_path / "cb_rates_cache.json"
    cache_file.write_text(json.dumps({
        "rates": {"USD": 4.0, "EUR": 2.5, "GBP": 3.5, "JPY": 1.0, "AUD": 4.0, "CAD": 2.0, "CHF": 0.0, "NZD": 2.0},
        "fetched_at": "2026-06-18T01:42:27",
        "source": "investing.com",
    }), encoding="utf-8")
    with patch.object(mr, "CACHE_FILE", cache_file), \
         patch.object(mr, "fetch_live_cb_rates", return_value={}):
        rates, source, fetched_at, _ = mr.get_effective_rates(force_refresh=True)
    assert source == "cache_stale"
    assert rates["USD"] == 4.0
    assert "2026-06-18" in (fetched_at or "")


def test_get_effective_rates_fallback_only_when_no_cache():
    with patch.object(mr, "load_cache", return_value=None), \
         patch.object(mr, "fetch_live_cb_rates", return_value={}):
        rates, source, fetched_at, _ = mr.get_effective_rates(force_refresh=True)
    assert source == "fallback"
    assert fetched_at is None
    assert rates == mr.FALLBACK_RATES


def test_source_badge_live_and_cache_stale():
    assert mr._source_badge("live", "2026-07-24T10:00:00") == "🟢 LIVE"
    assert mr._source_badge("cache_stale", "2026-06-18T01:42:27").startswith("🟡 CACHE")
    assert mr._source_badge("fallback", None) == "🔴 OFFLINE"


def test_refresh_rates_daily_no_stale_or_change_on_fallback():
    with patch.object(mr, "get_effective_rates", return_value=(mr.FALLBACK_RATES, "fallback", None, [])), \
         patch.object(mr, "_write_refresh_meta"), \
         patch.object(mr, "_send_rate_change_alert") as mock_change:
        summary = mr.refresh_rates_daily(notify_telegram=True)
    mock_change.assert_not_called()
    assert summary["source"] == "fallback"
    assert summary["success"] is False


def test_refresh_rates_daily_sends_change_alert_on_live():
    changes = [("USD", 3.50, 3.75)]
    rates = dict(mr.FALLBACK_RATES)
    rates["USD"] = 3.75
    with patch.object(mr, "get_effective_rates", return_value=(rates, "live", "2026-07-24T10:00:00", changes)), \
         patch.object(mr, "load_cache", return_value=None), \
         patch.object(mr, "_write_refresh_meta"), \
         patch.object(mr, "_should_send_alert", return_value=True), \
         patch.object(mr, "_send_rate_change_alert") as mock_change, \
         patch.object(mr, "_mark_alert_sent") as mock_mark:
        mr.refresh_rates_daily(notify_telegram=True)
    mock_change.assert_called_once()
    mock_mark.assert_called_once()


def test_weekly_report_skips_table_on_fallback():
    with patch.object(mr, "get_effective_rates", return_value=(mr.FALLBACK_RATES, "fallback", None, [])):
        msg = mr.format_weekly_macro_report()
    assert "MACRO WEEKLY TABLE" in msg
    assert "Live indisponibil" in msg
    assert "DOBÂNZI BĂNCI CENTRALE" not in msg


def test_weekly_report_includes_table_on_live():
    rates = dict(mr.FALLBACK_RATES)
    with patch.object(mr, "get_effective_rates", return_value=(rates, "live", "2026-07-24T10:00:00", [])):
        msg = mr.format_weekly_macro_report()
    assert "DOBÂNZI BĂNCI CENTRALE" in msg
    assert "🟢 LIVE" in msg


MOCK_SWAPS = [
    {"symbol": "GBPJPY", "swap_long": 1.21, "swap_short": -2.38, "triple_day": "Wed"},
    {"symbol": "XAUUSD", "swap_long": -53.76, "swap_short": 36.93, "triple_day": "Wed"},
    {"symbol": "EURUSD", "swap_long": -0.82, "swap_short": 0.15, "triple_day": "Wed"},
    {"symbol": "USDCAD", "swap_long": 0.24, "swap_short": -0.99, "triple_day": "Wed"},
    {"symbol": "AUDJPY", "swap_long": 0.85, "swap_short": -1.36, "triple_day": "Wed"},
]


def test_top_swap_credits_sorts_long_and_short():
    long_top = mr._top_swap_credits(MOCK_SWAPS, "long", 3)
    short_top = mr._top_swap_credits(MOCK_SWAPS, "short", 3)
    assert long_top[0]["symbol"] == "GBPJPY"
    assert long_top[0]["swap_long"] == 1.21
    assert short_top[0]["symbol"] == "XAUUSD"
    assert short_top[0]["swap_short"] == 36.93


def test_format_rates_v64_elite_sections():
    rates = dict(mr.FALLBACK_RATES)
    with patch.object(mr, "get_effective_rates", return_value=(rates, "live", "2026-07-24T16:01:00", [])), \
         patch.object(mr, "_write_refresh_meta"), \
         patch.object(mr, "fetch_ic_markets_swaps", return_value=MOCK_SWAPS):
        msg = mr.format_rates_telegram_message(
            force_refresh=False,
            notify_on_change=False,
        )
    assert "DOBÂNZI BĂNCI CENTRALE" in msg
    assert "CARRY POLICY (teoretic)" in msg
    assert "Spread rate BC — nu e swap broker" in msg
    assert "TOP SWAP IC MARKETS" in msg
    assert "cTrader live" in msg
    assert "SWAP GRID" in msg
    assert "HIGH" in msg or "LOW" in msg
    assert "▰" in msg


def test_format_rates_fallback_warning_unchanged():
    with patch.object(mr, "get_effective_rates", return_value=(mr.FALLBACK_RATES, "fallback", None, [])), \
         patch.object(mr, "_write_refresh_meta"), \
         patch.object(mr, "fetch_ic_markets_swaps", return_value=[]):
        msg = mr.format_rates_telegram_message(force_refresh=False, notify_on_change=False)
    assert "Live indisponibil" in msg
    assert "DOBÂNZI BĂNCI CENTRALE" in msg
