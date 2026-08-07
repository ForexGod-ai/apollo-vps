#!/usr/bin/env python3
"""One-shot splitter: smc_detector.py -> smc_detector/ package (V67 Faza C)."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "smc_detector.py"

METHOD_MAP = {
    "w1": {
        "_normalize_macro_bias_label",
        "daily_poi_inside_weekly_zone",
        "_resolve_w1_leg_pipeline",
        "calculate_w1_bias",
        "resolve_w1_poi",
        "evaluate_w_d_sync",
        "resolve_status_after_w_d_sync",
        "apply_w_d_sync_gate",
        "apply_w1_gate",
    },
    "core": {
        "calculate_atr",
        "calculate_equilibrium_reversal",
        "calculate_equilibrium_continuity",
        "detect_liquidity_sweep",
        "detect_swing_highs",
        "detect_swing_lows",
        "_body_close_below_after",
        "_body_close_above_after",
        "filter_major_swings",
        "_last_swing_before",
        "detect_choch_and_bos",
        "detect_choch",
        "_swing_body_high",
        "_swing_body_low",
        "compute_structural_range",
        "_range_signal_level",
        "_bar_body_close_above",
        "_bar_body_close_below",
        "_is_internal_range_signal",
        "macro_trend_from_swings",
        "has_confirmation_swing",
        "filter_internal_range_signals",
    },
    "d1_authority": {
        "_protected_hl_level_after_leg",
        "_protected_lh_level_after_leg",
        "_leg_invalidated_by_protected_breach",
        "_leg_superseded_by_opposite_major_flip",
        "_leg_choch_still_valid",
        "_dedupe_chochs_by_bar",
        "_true_choch_flips",
        "_post_leg_bos",
        "_strategy_from_leg_choch",
        "_classify_d1_strategy",
        "_d1_signal_for_strategy",
        "_demote_post_leg_choch_to_bos",
        "_find_leg_choch",
        "_expansion_bos_confirms_new_range",
        "resolve_structural_bias_fallback",
        "_resolve_historical_opposite_bias",
        "_resolve_post_leg_flip",
        "_is_major_structural_choch",
        "_major_reversal_confirmed",
        "build_d1_context",
        "resolve_authoritative_d1_bias",
        "macro_authority_supports_direction",
        "_resolve_v426_latest_flip",
        "_resolve_d1_leg",
    },
    "poi": {
        "store_fvg_magnet",
        "get_fvg_magnets",
        "validate_fvg_zone",
        "detect_order_block",
        "fvg_audit_entry",
        "detect_fvg",
        "build_active_dealing_range",
        "poi_conflicts_with_continuation",
        "should_preserve_stored_poi",
        "compute_structural_breach",
        "_fvg_within_adr",
        "_fvg_body_mitigated",
        "_scan_organic_fvgs",
        "_impulse_equilibrium",
        "_fvg_in_pd_zone",
        "_resolve_continuation_poi_cascade",
        "resolve_d1_poi",
        "calculate_premium_discount_zones",
        "is_price_in_fvg",
        "calculate_fvg_quality_score",
    },
    "scan": {
        "_get_asset_class",
        "_uses_macro_ceiling",
        "_compute_macro_ceiling_d1",
        "_get_pip_size",
        "_calculate_minimum_sl_distance",
        "calculate_entry_sl_tp",
        "scan_for_setup",
    },
}

MIXIN_NAMES = {
    "w1": "W1Mixin",
    "core": "CoreMixin",
    "d1_authority": "D1AuthorityMixin",
    "poi": "POIMixin",
    "scan": "ScanMixin",
}

MODULE_IMPORTS = """from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from smc_detector.models import (
    ActiveDealingRange,
    BOS,
    CHoCH,
    D1AuthContext,
    FVG,
    OrderBlock,
    POIResolution,
    StructuralRangeState,
    SwingPoint,
    TradeSetup,
    CRYPTO_MACRO_CEILING_LOOKBACK,
    CRYPTO_MACRO_CEILING_MIN_BARS,
)

"""


def main() -> None:
    source = SRC.read_text(encoding="utf-8")
    tree = ast.parse(source)
    smc_cls = next(
        n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SMCDetector"
    )
    methods = [n for n in smc_cls.body if isinstance(n, ast.FunctionDef)]
    method_names = {m.name for m in methods}

    all_mapped = set().union(*METHOD_MAP.values())
    unmapped = method_names - all_mapped - {"__init__"}
    if unmapped:
        raise SystemExit(f"Unmapped methods: {sorted(unmapped)}")
    missing = all_mapped - method_names
    if missing:
        raise SystemExit(f"Mapped but missing: {sorted(missing)}")

    lines = source.splitlines(keepends=True)
    models_body = "".join(lines[6 : smc_cls.lineno - 1]).rstrip() + "\n"

    def extract(node: ast.FunctionDef) -> str:
        start = node.lineno - 1
        if node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        return "".join(lines[start : node.end_lineno])

    init_src = extract(next(m for m in methods if m.name == "__init__"))

    pkg = ROOT / "smc_detector"
    pkg.mkdir(exist_ok=True)

    models_imports = """from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

"""
    (pkg / "models.py").write_text(models_imports + models_body, encoding="utf-8")

    for mod, names in METHOD_MAP.items():
        parts = [extract(m) for m in methods if m.name in names]
        body = MODULE_IMPORTS + f"\nclass {MIXIN_NAMES[mod]}:\n    pass\n\n"
        # replace empty pass with methods
        body = MODULE_IMPORTS + f"\nclass {MIXIN_NAMES[mod]}:\n    \"\"\"V67 C: {mod} mixin.\"\"\"\n\n"
        body += "\n".join(parts)
        if not body.endswith("\n"):
            body += "\n"
        (pkg / f"{mod}.py").write_text(body, encoding="utf-8")

    init_py = '''"""Glitch in Matrix SMC detector — V67 C modular package."""

from smc_detector.models import (
    ActiveDealingRange,
    BOS,
    CHoCH,
    CRYPTO_MACRO_CEILING_LOOKBACK,
    CRYPTO_MACRO_CEILING_MIN_BARS,
    D1AuthContext,
    FVG,
    OrderBlock,
    POIResolution,
    StructuralRangeState,
    SwingPoint,
    TradeSetup,
)
from smc_detector.core import CoreMixin
from smc_detector.d1_authority import D1AuthorityMixin
from smc_detector.poi import POIMixin
from smc_detector.w1 import W1Mixin
from smc_detector.scan import ScanMixin


class SMCDetector(W1Mixin, D1AuthorityMixin, POIMixin, CoreMixin, ScanMixin):
    """SMC detector facade — same public API as legacy monolith."""

''' + init_src + "\n"
    (pkg / "__init__.py").write_text(init_py, encoding="utf-8")

    backup = ROOT / "smc_detector.py.bak"
    if not backup.exists():
        SRC.rename(backup)

    print(f"Created package at {pkg}")
    for f in sorted(pkg.glob("*.py")):
        n = len(f.read_text(encoding="utf-8").splitlines())
        print(f"  {f.name}: {n} lines")
    print(f"Backup: {backup}")


if __name__ == "__main__":
    main()
