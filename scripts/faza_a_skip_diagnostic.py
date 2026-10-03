#!/usr/bin/env python3
"""Faza A — read-only diagnostic: Deep Sleep, logs, monitoring_setups skip patterns."""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOGS = ROOT / "logs"
MONITORING = DATA / "monitoring_setups.json"
DEEP_SLEEP = DATA / "deep_sleep_state.json"

LOG_PATTERNS = re.compile(
    r"DEEP SLEEP|V42\.3|V49 POI|W\+D|EXECUTE_NOW ABORT|EXEC SKIP|RADAR SKIP|"
    r"last_radar_skip|RR SHIELD|V40\.9",
    re.I,
)


def _load_json(path: Path):
    if not path.exists():
        return None, f"missing: {path.relative_to(ROOT)}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def main() -> int:
    print("=== Faza A — skip / block diagnostic ===\n")

    ds, ds_err = _load_json(DEEP_SLEEP)
    if ds_err:
        print(f"deep_sleep_state.json: {ds_err}")
    else:
        active = ds.get("active") or ds.get("deep_sleep_active")
        print(f"deep_sleep_state.json: active={active!r} keys={list(ds.keys())[:8]}")

    setups: list = []
    if MONITORING.exists():
        from monitoring_json_io import load_monitoring_json

        _, setups, _ = load_monitoring_json(MONITORING)
        print(f"\nmonitoring_setups.json: {len(setups)} setup(s)")
    else:
        print(f"\nmonitoring_setups.json: missing ({MONITORING})")

    counters: Counter = Counter()
    choch_no_execute = 0
    for s in setups:
        if not isinstance(s, dict):
            continue
        sym = s.get("symbol", "?")
        if s.get("radar_4h_choch_detected") and s.get("EXECUTE_NOW") is not True:
            choch_no_execute += 1
        if s.get("status") == "WAITING_W_D_SYNC" or s.get("w_d_aligned") is False:
            counters["W+D misaligned / WAITING_W_D_SYNC"] += 1
        if s.get("last_radar_skip_reason"):
            counters[f"radar skip: {s['last_radar_skip_reason'][:80]}"] += 1
        if s.get("last_rejection_reason"):
            counters[f"executor reject: {s['last_rejection_reason'][:80]}"] += 1
        if s.get("v42_3_alignment_block"):
            counters["V42.3 alignment block flag"] += 1
        if s.get("execute_now_blocked_at") and not s.get("EXECUTE_NOW"):
            counters["execute_now_blocked_at set (cooldown candidate)"] += 1

    if choch_no_execute:
        counters["CHoCH 4H fără EXECUTE_NOW"] += choch_no_execute

    print("\n--- Setup-derived signals ---")
    if not counters:
        print("(no setups or no skip flags in JSON)")
    else:
        for reason, count in counters.most_common(10):
            print(f"  {count:3d}  {reason}")

    print("\n--- Log tail (matching patterns) ---")
    if not LOGS.is_dir():
        print(f"logs/: missing ({LOGS})")
    else:
        hits: list[str] = []
        for log_path in sorted(LOGS.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                if LOG_PATTERNS.search(line):
                    hits.append(f"{log_path.name}: {line[:200]}")
            if len(hits) >= 80:
                break
        if not hits:
            print("(no matching log lines)")
        else:
            for line in hits[-80:]:
                print(line)

    print("\n--- Top 3 probable blockers (heuristic) ---")
    top3 = [r for r, _ in counters.most_common(3)]
    if not top3:
        top3 = [
            "1) Verifică Deep Sleep + executor logs pe VPS",
            "2) CHoCH fără Pas 3 (retrace / FVG) — vezi last_radar_skip_reason",
            "3) V42.3 / cooldown / infra 8010 — grep logs",
        ]
    for i, item in enumerate(top3, 1):
        print(f"  {i}. {item}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
