"""
Resilient read/write for monitoring_setups.json — shared by radar, executor, Telegram.

- Tolerant load (Extra data / concatenated JSON)
- Atomic save via per-writer temp files + os.replace
- Cross-process lock file (Windows VPS + Unix)
"""
from __future__ import annotations

import json
import math
import os
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from loguru import logger

DEFAULT_LOCK_TIMEOUT_SEC = 10.0
DEFAULT_LOCK_POLL_SEC = 0.05


def monitoring_json_default(obj: Any) -> Any:
    """json.dump default: numpy scalars/arrays + str fallback."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    try:
        import numpy as np
        if isinstance(obj, (np.bool_,)):
            return bool(obj)
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            val = float(obj)
            if math.isnan(val) or math.isinf(val):
                return None
            return val
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


@contextmanager
def monitoring_json_lock(path: Path, timeout: float = DEFAULT_LOCK_TIMEOUT_SEC):
    """Exclusive lock via atomic O_EXCL create — works on Windows VPS."""
    path = Path(path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    fd: Optional[int] = None
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"monitoring_setups lock timeout ({timeout}s): {lock_path.name}"
                    )
                time.sleep(DEFAULT_LOCK_POLL_SEC)
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            lock_path.unlink(missing_ok=True)
        except OSError:
            pass


def load_monitoring_json(
    path: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], bool]:
    """
    Load monitoring_setups.json resiliently.

    Returns:
        (data_dict, setups_list, had_trailing_junk)
        had_trailing_junk=True when Extra data was stripped (caller may rewrite clean file).
    """
    path = Path(path)
    if not path.exists():
        return {}, [], False
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.error(f"Cannot read {path}: {exc}")
        return {}, [], False
    if not raw:
        return {}, [], False

    had_trailing_junk = False
    data: Any = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            decoder = json.JSONDecoder()
            data, end = decoder.raw_decode(raw)
            if end < len(raw):
                had_trailing_junk = True
                logger.warning(
                    f"[monitoring_json_io] {path.name}: extra data after char {end} "
                    f"(using first valid JSON object)"
                )
        except json.JSONDecodeError as exc:
            logger.error(f"[monitoring_json_io] {path.name} unreadable: {exc}")
            return {}, [], False

    if isinstance(data, list):
        return {"setups": data}, data, had_trailing_junk
    if isinstance(data, dict):
        setups = data.get("setups", [])
        if not isinstance(setups, list):
            setups = []
        return data, setups, had_trailing_junk
    return {}, [], had_trailing_junk


def save_monitoring_json(
    path: Path,
    data: Dict[str, Any],
    *,
    tmp_tag: str = "",
    json_default: Optional[Callable[[Any], Any]] = None,
    locked: bool = False,
) -> None:
    """Atomic write with optional cross-process lock and per-writer temp suffix."""
    path = Path(path)
    payload = dict(data)
    if "setups" not in payload:
        payload["setups"] = []
    payload.setdefault("last_updated", datetime.now().isoformat())

    tmp_path = path.with_suffix(f"{path.suffix}.tmp{tmp_tag}")
    default_fn = json_default or monitoring_json_default

    def _write() -> None:
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, default=default_fn)
        os.replace(tmp_path, path)

    if locked:
        _write()
    else:
        with monitoring_json_lock(path):
            _write()


def repair_monitoring_json_if_needed(path: Path, tmp_tag: str = ".repair") -> bool:
    """Rewrite file when trailing junk was detected. Returns True if repaired."""
    path = Path(path)
    data, setups, had_junk = load_monitoring_json(path)
    if not had_junk or not setups:
        return False
    with monitoring_json_lock(path):
        save_monitoring_json(path, data, tmp_tag=tmp_tag, locked=True)
    logger.warning(
        f"[monitoring_json_io] Repaired {path.name} — {len(setups)} setup(s) preserved"
    )
    return True
