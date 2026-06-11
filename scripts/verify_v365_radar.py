#!/usr/bin/env python3
"""Static verification: V36.5 Radar Always-On H4/H1 (no P/D early return)."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
RADAR = ROOT / "multi_tf_radar.py"


def main() -> int:
    if not RADAR.exists():
        print(f"FAIL: missing {RADAR}")
        return 1

    text = RADAR.read_text(encoding="utf-8")
    errors: list[str] = []

    required = [
        "V36.5 ALWAYS-ON H4/H1",
        "def _evaluate_pd_guard(",
        "def _log_scan_done(",
        "[V36.5 SCAN DONE]",
        "[V36.5 P/D BLOCK EXECUTE]",
        "pd_guard_passed",
        "pd_guard_reason",
    ]
    for marker in required:
        if marker not in text:
            errors.append(f"missing marker: {marker!r}")

    # P/D must not return None inside analyze_setup (only direction/price fatal paths)
    setup_match = re.search(
        r"def analyze_setup\(.*?(?=\n    def |\Z)",
        text,
        re.DOTALL,
    )
    if not setup_match:
        errors.append("could not parse analyze_setup()")
    else:
        body = setup_match.group(0)
        if "P/D GUARD SHORT" in body and "return None" in body:
            # Old V31 pattern: skip entire scan on P/D
            pd_block = body.split("_evaluate_pd_guard")[0] if "_evaluate_pd_guard" in body else body
            if re.search(r"P/D GUARD.*return None", pd_block, re.DOTALL):
                errors.append("analyze_setup still has P/D return None before H4/H1 scan")
        if "_evaluate_pd_guard" not in body:
            errors.append("analyze_setup does not call _evaluate_pd_guard")
        if body.find("analyze_timeframe") > body.find("_evaluate_pd_guard"):
            errors.append("P/D guard runs BEFORE analyze_timeframe — should be AFTER (V36.5)")

    if errors:
        print("V36.5 VERIFICATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("V36.5 VERIFICATION PASSED")
    print("  - _evaluate_pd_guard extracted")
    print("  - H4/H1 scan before P/D execution gate")
    print("  - pd_guard_passed/reason in JSON path")
    print("  - Log tokens: SCAN DONE, P/D BLOCK EXECUTE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
