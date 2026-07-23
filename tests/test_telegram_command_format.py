"""V63 — Telegram Command Center format helpers + footer."""
from __future__ import annotations

import json
from pathlib import Path

from telegram_command_format import (
    SLIM_FOOTER_BRAND,
    SLIM_FOOTER_SEP,
    append_slim_footer,
    format_btcusd_card,
    format_slim_footer,
    format_two_column_grid,
    load_monitoring_json,
    save_monitoring_json,
)


def test_slim_footer_separator_matches_brand_width():
    assert len(SLIM_FOOTER_SEP) == len(SLIM_FOOTER_BRAND)
    assert SLIM_FOOTER_BRAND in format_slim_footer()
    assert SLIM_FOOTER_SEP in format_slim_footer()


def test_append_slim_footer():
    body = append_slim_footer("Hello")
    assert body.startswith("Hello")
    assert SLIM_FOOTER_BRAND in body
    assert "AUTHORED BY" not in body


def test_load_monitoring_json_concatenated(tmp_path: Path):
    path = tmp_path / "monitoring_setups.json"
    first = {"setups": [{"symbol": "EURUSD", "status": "MONITORING"}]}
    second = {"setups": [{"symbol": "GBPUSD", "status": "READY"}]}
    path.write_text(json.dumps(first) + json.dumps(second), encoding="utf-8")
    data, setups = load_monitoring_json(path)
    assert len(setups) == 1
    assert setups[0]["symbol"] == "EURUSD"
    assert "setups" in data


def test_save_monitoring_json_atomic(tmp_path: Path):
    path = tmp_path / "monitoring_setups.json"
    payload = {"setups": [{"symbol": "BTCUSD", "status": "MONITORING"}]}
    save_monitoring_json(path, payload)
    data, setups = load_monitoring_json(path)
    assert setups[0]["symbol"] == "BTCUSD"
    assert data == payload


def test_format_two_column_grid():
    grid = format_two_column_grid(["A ✅", "B ❌", "C ✅"], cols=2)
    assert "A ✅" in grid
    assert "B ❌" in grid
    assert "C ✅" in grid


def test_format_btcusd_card_hybrid_ro():
    card = format_btcusd_card({
        "symbol": "BTCUSD",
        "direction": "buy",
        "status": "MONITORING",
        "strategy_type": "continuation",
        "fvg_bottom": 72000,
        "fvg_top": 78000,
        "radar_4h_choch_detected": True,
        "live_price": 75000,
    })
    assert "BTCUSD" in card
    assert "Preț cTrader" in card
    assert "POI Daily" in card
    assert "Radar" in card
