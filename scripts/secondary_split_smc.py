#!/usr/bin/env python3
"""Secondary split: keep each smc_detector module under 800 lines."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "smc_detector"

HEADER = """from __future__ import annotations

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


def read_module(name: str) -> list[str]:
    return (PKG / name).read_text(encoding="utf-8").splitlines(keepends=True)


def write_mixin(name: str, class_name: str, doc: str, method_blocks: list[str]) -> None:
    body = HEADER + f"\nclass {class_name}:\n    \"\"\"{doc}\"\"\"\n\n"
    body += "\n".join(method_blocks)
    if not body.endswith("\n"):
        body += "\n"
    (PKG / name).write_text(body, encoding="utf-8")


def extract_methods(lines: list[str], method_names: list[str]) -> list[str]:
    src = "".join(lines)
    tree = ast.parse(src)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    by_name = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    out = []
    for name in method_names:
        node = by_name[name]
        start = node.lineno - 1
        if node.decorator_list:
            start = node.decorator_list[0].lineno - 1
        out.append("".join(lines[start : node.end_lineno]))
    return out


def split_core() -> None:
    lines = read_module("core.py")
    swings = [
        "calculate_atr", "calculate_equilibrium_reversal", "calculate_equilibrium_continuity",
        "detect_liquidity_sweep", "detect_choch", "detect_swing_highs", "detect_swing_lows",
        "_body_close_below_after", "_body_close_above_after", "filter_major_swings",
        "_last_swing_before", "_swing_body_high", "_swing_body_low", "macro_trend_from_swings",
        "has_confirmation_swing",
    ]
    structure = [
        "detect_choch_and_bos", "compute_structural_range", "_range_signal_level",
        "_bar_body_close_above", "_bar_body_close_below", "_is_internal_range_signal",
        "filter_internal_range_signals",
    ]
    write_mixin("core_swings.py", "CoreSwingsMixin", "V67 C: swing + equilibrium detection.", extract_methods(lines, swings))
    write_mixin("core_structure.py", "CoreStructureMixin", "V67 C: CHoCH/BOS + structural range.", extract_methods(lines, structure))


def split_d1() -> None:
    lines = read_module("d1_authority.py")
    leg = [
        "_protected_hl_level_after_leg", "_protected_lh_level_after_leg",
        "_leg_invalidated_by_protected_breach", "_leg_superseded_by_opposite_major_flip",
        "_leg_choch_still_valid", "_dedupe_chochs_by_bar", "_true_choch_flips", "_post_leg_bos",
        "_strategy_from_leg_choch", "_classify_d1_strategy", "_d1_signal_for_strategy",
        "_demote_post_leg_choch_to_bos", "_find_leg_choch", "_expansion_bos_confirms_new_range",
        "resolve_structural_bias_fallback", "_resolve_historical_opposite_bias",
        "_resolve_post_leg_flip", "_is_major_structural_choch", "_major_reversal_confirmed",
    ]
    auth = [
        "build_d1_context", "resolve_authoritative_d1_bias", "macro_authority_supports_direction",
        "_resolve_v426_latest_flip", "_resolve_d1_leg",
    ]
    write_mixin("d1_leg.py", "D1LegMixin", "V67 C: D1 leg resolution helpers.", extract_methods(lines, leg))
    write_mixin("d1_authority.py", "D1AuthorityMixin", "V67 C: canonical D1 authority.", extract_methods(lines, auth))


def split_poi() -> None:
    lines = read_module("poi.py")
    fvg = [
        "store_fvg_magnet", "validate_fvg_zone", "get_fvg_magnets", "detect_order_block",
        "fvg_audit_entry", "detect_fvg", "calculate_fvg_quality_score",
    ]
    poi = [
        "build_active_dealing_range", "poi_conflicts_with_continuation", "should_preserve_stored_poi",
        "compute_structural_breach", "_fvg_within_adr", "_fvg_body_mitigated", "_scan_organic_fvgs",
        "_impulse_equilibrium", "_fvg_in_pd_zone", "_resolve_continuation_poi_cascade",
        "resolve_d1_poi", "calculate_premium_discount_zones", "is_price_in_fvg",
    ]
    write_mixin("fvg.py", "FvgMixin", "V67 C: FVG detection and scoring.", extract_methods(lines, fvg))
    write_mixin("poi.py", "PoiMixin", "V67 C: D1 POI resolution.", extract_methods(lines, poi))


def split_scan() -> None:
    lines = read_module("scan.py")
    entry = [
        "_get_asset_class", "_uses_macro_ceiling", "_compute_macro_ceiling_d1", "_get_pip_size",
        "_calculate_minimum_sl_distance", "calculate_entry_sl_tp",
    ]
    setup = ["scan_for_setup"]
    write_mixin("scan_entry.py", "ScanEntryMixin", "V67 C: entry / SL / TP calculation.", extract_methods(lines, entry))
    write_mixin("scan_setup.py", "ScanSetupMixin", "V67 C: scan_for_setup orchestrator.", extract_methods(lines, setup))


def patch_init() -> None:
    old = (PKG / "__init__.py").read_text(encoding="utf-8")
    tail = old[old.index("    def __init__") :]
    init = '''"""Glitch in Matrix SMC detector — V67 C modular package."""

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
from smc_detector.core_swings import CoreSwingsMixin
from smc_detector.core_structure import CoreStructureMixin
from smc_detector.d1_leg import D1LegMixin
from smc_detector.d1_authority import D1AuthorityMixin
from smc_detector.fvg import FvgMixin
from smc_detector.poi import PoiMixin
from smc_detector.w1 import W1Mixin
from smc_detector.scan_entry import ScanEntryMixin
from smc_detector.scan_setup import ScanSetupMixin


class SMCDetector(
    W1Mixin,
    D1LegMixin,
    D1AuthorityMixin,
    PoiMixin,
    FvgMixin,
    CoreStructureMixin,
    CoreSwingsMixin,
    ScanSetupMixin,
    ScanEntryMixin,
):
    """SMC detector facade — same public API as legacy monolith."""

'''
    (PKG / "__init__.py").write_text(init + tail, encoding="utf-8")


def fix_refs() -> None:
    d1 = PKG / "d1_leg.py"
    text = d1.read_text(encoding="utf-8")
    d1.write_text(text.replace("D1AuthorityMixin._post_leg_bos", "D1LegMixin._post_leg_bos"), encoding="utf-8")
    poi = PKG / "poi.py"
    pt = poi.read_text(encoding="utf-8")
    poi.write_text(pt.replace("POIMixin.poi_conflicts_with_continuation", "PoiMixin.poi_conflicts_with_continuation"), encoding="utf-8")


def cleanup() -> None:
    (PKG / "core.py").unlink(missing_ok=True)
    (PKG / "scan.py").unlink(missing_ok=True)


def main() -> None:
    split_core()
    split_d1()
    split_poi()
    split_scan()
    patch_init()
    fix_refs()
    cleanup()
    over = []
    for f in sorted(PKG.glob("*.py")):
        n = len(f.read_text(encoding="utf-8").splitlines())
        flag = " ⚠️" if n > 800 else ""
        if n > 800:
            over.append(f.name)
        print(f"  {f.name}: {n} lines{flag}")
    if over:
        print(f"Over 800 lines: {over}")


if __name__ == "__main__":
    main()
