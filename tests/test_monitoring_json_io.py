"""monitoring_setups.json resilient I/O — Extra data + lock + per-writer temp files."""
from __future__ import annotations

import json
from pathlib import Path

from monitoring_json_io import (
    load_monitoring_json,
    repair_monitoring_json_if_needed,
    save_monitoring_json,
)


def test_load_concatenated_json_uses_first_object(tmp_path: Path):
    path = tmp_path / "monitoring_setups.json"
    first = {"setups": [{"symbol": "EURUSD", "status": "MONITORING"}]}
    second = {"setups": [{"symbol": "GBPUSD", "status": "READY"}]}
    path.write_text(json.dumps(first) + json.dumps(second), encoding="utf-8")

    data, setups, had_junk = load_monitoring_json(path)
    assert had_junk is True
    assert len(setups) == 1
    assert setups[0]["symbol"] == "EURUSD"
    assert "setups" in data


def test_repair_writes_clean_file(tmp_path: Path):
    path = tmp_path / "monitoring_setups.json"
    first = {"setups": [{"symbol": "XAUUSD", "status": "WAITING_D1_PULLBACK"}]}
    junk = {"setups": []}
    path.write_text(json.dumps(first) + json.dumps(junk), encoding="utf-8")

    assert repair_monitoring_json_if_needed(path) is True
    repaired = json.loads(path.read_text(encoding="utf-8"))
    assert len(repaired["setups"]) == 1
    assert repaired["setups"][0]["symbol"] == "XAUUSD"


def test_save_uses_distinct_temp_suffix(tmp_path: Path):
    path = tmp_path / "monitoring_setups.json"
    payload = {"setups": [{"symbol": "BTCUSD", "status": "MONITORING"}]}
    save_monitoring_json(path, payload, tmp_tag=".radar")
    save_monitoring_json(path, payload, tmp_tag=".executor")
    data, setups, had_junk = load_monitoring_json(path)
    assert had_junk is False
    assert setups[0]["symbol"] == "BTCUSD"
