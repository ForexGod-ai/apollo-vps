"""Legacy 1H multi_entry_plan normalization at load."""
from monitoring_json_io import normalize_setup_legacy_1h, normalize_setups_legacy_1h


def test_normalize_multi_entry_plan_strips_1h():
    s = {"symbol": "EURUSD", "multi_entry_plan": ["1H", "4H"]}
    assert normalize_setup_legacy_1h(s) is True
    assert s["multi_entry_plan"] == ["4H"]


def test_normalize_idempotent_4h_only():
    s = {"symbol": "EURUSD", "multi_entry_plan": ["4H"]}
    assert normalize_setup_legacy_1h(s) is False


def test_normalize_batch():
    setups = [
        {"multi_entry_plan": "1H"},
        {"multi_entry_plan": ["4H"]},
    ]
    assert normalize_setups_legacy_1h(setups) == 1
    assert setups[0]["multi_entry_plan"] == ["4H"]
