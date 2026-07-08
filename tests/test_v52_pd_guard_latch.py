"""V52: P/D guard allows sequential entry after POI latch (EURJPY-style)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from multi_tf_radar import _compute_pd_guard_for_execute


def test_pd_guard_latched_outside_poi_passes_when_pd_ok():
    v43 = {
        'equilibrium': 184.0,
        'pd_passed': True,
        'in_poi': False,
        'reason': 'Premium OK',
    }
    passed, reason = _compute_pd_guard_for_execute(
        v43, {'passed': True, 'skipped': False}, daily_zone_validated=False, poi_sequential_active=True,
    )
    assert passed is True
    assert reason == ''


def test_pd_guard_no_latch_requires_in_poi():
    v43 = {
        'equilibrium': 184.0,
        'pd_passed': True,
        'in_poi': False,
        'reason': 'Premium OK',
    }
    passed, _ = _compute_pd_guard_for_execute(
        v43, {'passed': True, 'skipped': False}, daily_zone_validated=False, poi_sequential_active=False,
    )
    assert passed is False


def test_pd_guard_latched_fails_when_pd_wrong_zone():
    v43 = {
        'equilibrium': 184.0,
        'pd_passed': False,
        'in_poi': False,
        'reason': 'SHORT in Discount',
    }
    passed, reason = _compute_pd_guard_for_execute(
        v43, {'passed': False, 'skipped': False}, daily_zone_validated=False, poi_sequential_active=True,
    )
    assert passed is False
    assert 'Discount' in reason
