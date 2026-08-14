"""Faza B — setup identity lock in daily_scanner."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from daily_scanner import (
    _apply_setup_identity_lock,
    _structure_identity_breached,
    _live_contradicts_locked_identity,
)
from smc_detector import SMCDetector

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "historical_cache"


def _load_d1(symbol: str) -> pd.DataFrame:
    matches = sorted(CACHE.glob(f"{symbol}_D1_*.csv"), key=lambda p: p.stat().st_mtime)
    if not matches:
        pytest.skip(f"No D1 cache for {symbol}")
    df = pd.read_csv(matches[-1])
    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"])
        df = df.set_index("time")
    for col in ("open", "high", "low", "close"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.dropna(subset=["close"]).iloc[-300:]


def _locked_bullish() -> dict:
    return {
        'symbol': 'EURUSD',
        'direction': 'buy',
        'daily_bias': 'BULLISH',
        'strategy_type': 'continuation',
        'setup_identity_locked': True,
        'major_structure_floor': 1.1000,
        'major_structure_ceiling': 1.1200,
        'leg_choch_price': 1.1000,
        'entry_price': 1.1050,
        'stop_loss': 1.0980,
        'poi_top': 1.1060,
        'poi_bottom': 1.1040,
    }


def test_contradicts_locked_identity():
    old = _locked_bullish()
    new = {**old, 'direction': 'sell', 'daily_bias': 'BEARISH', 'strategy_type': 'reversal'}
    assert _live_contradicts_locked_identity(old, new) is True


def test_structure_breached_bullish():
    locked = _locked_bullish()
    df = pd.DataFrame({'close': [1.0950]})
    assert _structure_identity_breached(df, locked) is True


def test_structure_not_breached_bullish_pullback():
    locked = _locked_bullish()
    df = pd.DataFrame({'close': [1.1020]})
    assert _structure_identity_breached(df, locked) is False


def test_identity_lock_blocks_flip_without_breach():
    detector = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    old = _locked_bullish()
    new_live = {
        **old,
        'direction': 'sell',
        'daily_bias': 'BEARISH',
        'strategy_type': 'reversal',
        'entry_price': 1.1150,
        'stop_loss': 1.1180,
        'poi_top': 1.1160,
        'poi_bottom': 1.1140,
    }
    df = pd.DataFrame({'close': [1.1020]})
    merged = _apply_setup_identity_lock(old, new_live, df, detector, 'EURUSD')
    assert merged['direction'] == 'buy'
    assert merged['strategy_type'] == 'continuation'
    assert merged['entry_price'] == 1.1050
    assert merged['poi_top'] == 1.1060


def test_identity_lock_allows_new_identity_after_breach():
    detector = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    old = _locked_bullish()
    new_live = {
        **old,
        'direction': 'sell',
        'daily_bias': 'BEARISH',
        'strategy_type': 'reversal',
        'entry_price': 1.0900,
    }
    df = pd.DataFrame({'close': [1.0950]})
    merged = _apply_setup_identity_lock(old, new_live, df, detector, 'EURUSD')
    assert merged['direction'] == 'sell'
    assert merged['entry_price'] == 1.0900


def test_first_lock_stamps_from_empty_old():
    detector = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    df = _load_d1("EURUSD")
    auth = detector.resolve_authoritative_d1_bias(df, symbol="EURUSD")
    new_entry = {
        'symbol': 'EURUSD',
        'direction': auth.get('direction') or 'sell',
        'daily_bias': auth.get('daily_bias') or 'BEARISH',
        'strategy_type': auth.get('strategy_type') or 'continuation',
        'entry_price': float(df['close'].iloc[-1]),
    }
    merged = _apply_setup_identity_lock({}, new_entry, df, detector, 'EURUSD')
    if merged.get('setup_identity_locked'):
        assert merged.get('leg_choch_bar') is not None
        assert merged.get('major_structure_floor') is not None
    else:
        assert merged.get('direction') == auth.get('direction')


def test_identity_lock_allows_v62_macro_flip_gbpcad():
    """GBPCAD-class: locked SHORT, live scan LONG — macro authority allows flip."""
    detector = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    df = _load_d1("GBPCAD")
    auth = detector.resolve_authoritative_d1_bias(df, symbol='GBPCAD')
    if auth.get('trend') != 'bullish':
        pytest.skip(f"GBPCAD cache not bullish in this snapshot ({auth})")

    old = {
        'symbol': 'GBPCAD',
        'direction': 'sell',
        'daily_bias': 'BEARISH',
        'd1_bias_direction': 'bearish',
        'strategy_type': 'reversal',
        'setup_identity_locked': True,
        'major_structure_floor': float(df['low'].iloc[-60:].min()),
        'major_structure_ceiling': float(df['high'].iloc[-60:].max()),
        'leg_choch_price': float(df['close'].iloc[-1]),
        'entry_price': float(df['close'].iloc[-1]) + 0.01,
        'poi_top': float(df['high'].iloc[-1]),
        'poi_bottom': float(df['low'].iloc[-1]),
    }
    new_live = {
        **old,
        'direction': 'buy',
        'daily_bias': 'BULLISH',
        'd1_bias_direction': 'bullish',
        'strategy_type': 'continuation',
        'entry_price': float(df['close'].iloc[-1]),
    }
    merged = _apply_setup_identity_lock(old, new_live, df, detector, 'GBPCAD')
    assert merged['direction'] == 'buy'
    assert merged['strategy_type'] == 'continuation'


def test_rehydrate_stored_macro_bias_gbpcad():
    detector = SMCDetector(swing_lookback=5, atr_multiplier=0.5)
    df = _load_d1("GBPCAD")
    auth = detector.resolve_authoritative_d1_bias(df, symbol='GBPCAD')
    if auth.get('trend') != 'bullish':
        pytest.skip(f"GBPCAD cache not bullish ({auth})")

    from daily_scanner import _rehydrate_stored_macro_bias

    stored = {
        'symbol': 'GBPCAD',
        'direction': 'sell',
        'daily_bias': 'BEARISH',
        'strategy_type': 'reversal',
        'status': 'MONITORING',
        'radar_4h_choch_detected': True,
        'EXECUTE_NOW': True,
    }
    out = _rehydrate_stored_macro_bias(detector, df, stored, 'GBPCAD')
    assert out['direction'] == 'buy'
    assert out.get('EXECUTE_NOW') is None
    assert out.get('radar_4h_choch_detected') is None
