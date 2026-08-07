#!/usr/bin/env python3
"""Restore/build scan_setup / scan_finalize / scan split."""
from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "smc_detector"


def main() -> None:
    header = (PKG / "scan_entry.py").read_text(encoding="utf-8").split("class ScanEntryMixin")[0]
    bak = (Path(__file__).resolve().parents[1] / "smc_detector.py.bak").read_text(encoding="utf-8").splitlines(
        keepends=True
    )
    tree = ast.parse("".join(bak))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "SMCDetector")
    scan = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "scan_for_setup")
    body = bak[scan.lineno - 1 : scan.end_lineno]
    split_i = next(i for i, ln in enumerate(body) if "Step 7: Calculate entry, SL, TP" in ln)
    doc_end = next(
        i
        for i, ln in enumerate(body)
        if i > 5 and '"""' in ln and "Return complete setup" in "".join(body[max(0, i - 5) : i + 1])
    )
    sig_doc = body[: doc_end + 1]
    part1 = body[doc_end + 1 : split_i]
    part2 = body[split_i:]

    assigned_p1: set[str] = set()
    for node in ast.walk(ast.parse("def _p1():\n" + "".join(part1))):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    assigned_p1.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            assigned_p1.add(node.target.id)

    loaded_p2 = {
        n.id
        for n in ast.walk(ast.parse("def _p2():\n" + "".join(part2)))
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
    }
    params = [
        "symbol", "df_daily", "df_4h", "priority", "require_4h_choch",
        "skip_fvg_quality", "debug", "stored_poi_top", "stored_poi_bottom", "d1_ctx",
    ]
    needed = sorted((loaded_p2 & assigned_p1) | set(params))

    phase1 = (
        [
            "    def _scan_through_poi_validation(",
            "        self,",
            "        symbol: str,",
            "        df_daily: pd.DataFrame,",
            "        df_4h: pd.DataFrame,",
            "        priority: int,",
            "        require_4h_choch: bool,",
            "        skip_fvg_quality: bool,",
            "        debug: bool,",
            "        stored_poi_top: Optional[float],",
            "        stored_poi_bottom: Optional[float],",
            "        d1_ctx: Optional[D1AuthContext],",
            "    ):",
        ]
        + part1
        + ["        return self._scan_finalize_trade_setup(locals())\n"]
    )

    finalize = (
        [
            "    def _scan_finalize_trade_setup(self, _scan: dict) -> Optional[TradeSetup]:\n",
            "        l = _scan\n",
        ]
        + [f"        {n} = l[{n!r}]\n" for n in needed]
        + part2
    )

    orchestrator = sig_doc + [
        "        return self._scan_through_poi_validation(",
        "            symbol, df_daily, df_4h, priority, require_4h_choch,",
        "            skip_fvg_quality, debug, stored_poi_top, stored_poi_bottom, d1_ctx,",
        "        )\n",
    ]

    (PKG / "scan_setup.py").write_text(
        header + '\nclass ScanSetupMixin:\n    """V67 C: scan D1/FVG/POI phase."""\n\n' + "".join(phase1),
        encoding="utf-8",
    )
    (PKG / "scan_finalize.py").write_text(
        header + '\nclass ScanFinalizeMixin:\n    """V67 C: scan finalize/build phase."""\n\n' + "".join(finalize),
        encoding="utf-8",
    )
    (PKG / "scan.py").write_text(
        header + '\nclass ScanOrchestratorMixin:\n    """V67 C: scan_for_setup entry."""\n\n' + "".join(orchestrator),
        encoding="utf-8",
    )
    (PKG / "scan_build.py").unlink(missing_ok=True)

    init_tail = (PKG / "__init__.py").read_text(encoding="utf-8").split("def __init__", 1)[1]
    init_head = '''"""Glitch in Matrix SMC detector — V67 C modular package."""

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
from smc_detector.scan_finalize import ScanFinalizeMixin
from smc_detector.scan import ScanOrchestratorMixin


class SMCDetector(
    W1Mixin,
    D1LegMixin,
    D1AuthorityMixin,
    PoiMixin,
    FvgMixin,
    CoreStructureMixin,
    CoreSwingsMixin,
    ScanFinalizeMixin,
    ScanSetupMixin,
    ScanOrchestratorMixin,
    ScanEntryMixin,
):
    """SMC detector facade — same public API as legacy monolith."""

    def __init__'''
    (PKG / "__init__.py").write_text(init_head + init_tail, encoding="utf-8")

    for f in sorted(PKG.glob("*.py")):
        n = len(f.read_text(encoding="utf-8").splitlines())
        print(f"{f.name}: {n}" + (" ⚠️" if n > 800 else ""))


if __name__ == "__main__":
    main()
