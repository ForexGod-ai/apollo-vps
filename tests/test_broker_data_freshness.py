"""V56: broker_data_freshness unit tests."""
from datetime import datetime, timedelta, timezone

from broker_data_freshness import (
    incoming_is_newer_or_equal,
    is_payload_fresh,
    parse_last_update,
    payload_age_seconds,
)


def _payload(ts: str) -> dict:
    return {'account': {'last_update': ts, 'balance': 31.4, 'equity': 31.4}}


def test_parse_last_update_space_format():
    dt = parse_last_update('2026-06-24 12:00:00')
    assert dt is not None
    assert dt.tzinfo is not None


def test_fresh_payload():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    assert is_payload_fresh(_payload(now)) is True


def test_stale_payload():
    old = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    assert is_payload_fresh(_payload(old)) is False


def test_incoming_newer_or_equal():
    newer = _payload('2026-06-24 12:00:00')
    older = _payload('2026-06-24 11:00:00')
    assert incoming_is_newer_or_equal(newer, older) is True
    assert incoming_is_newer_or_equal(older, newer) is False


def test_payload_age_seconds_non_negative():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    age = payload_age_seconds(_payload(now))
    assert age is not None
    assert age >= 0
