"""
V41.1 — Dedup persistent alerte Telegram (Windows VPS + procese paralele).

O singura alerta EXECUTE NOW BLOCAT per simbol+directie in fereastra de cooldown.
Foloseste file lock ca 15 procese executor sa nu trimita 15 mesaje simultan.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

# 1 alerta / simbol / directie / ora — indiferent de motiv sau numar procese
EXECUTE_NOW_BLOCKED_COOLDOWN_SEC = 3600

_DEDUP_PATH = Path(__file__).resolve().parent / "data" / "telegram_execute_now_blocked.json"
_LOCK_PATH = _DEDUP_PATH.with_suffix(".lock")


def _acquire_lock(lock_path: Path, timeout_sec: float = 2.0) -> object | None:
    """Exclusive lock — None daca alt proces tine lock-ul."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            fh = open(lock_path, "a+b")
            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    fh.close()
                    time.sleep(0.05)
                    continue
            else:
                import fcntl

                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    fh.close()
                    time.sleep(0.05)
                    continue
            return fh
        except OSError:
            time.sleep(0.05)
    return None


def _release_lock(fh) -> None:
    if fh is None:
        return
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except Exception:
        pass
    try:
        fh.close()
    except Exception:
        pass


def claim_execute_now_blocked_alert(symbol: str, direction: str) -> bool:
    """
    True = primul apel in cooldown — trimite Telegram.
    False = duplicat (alt proces sau alerta recenta) — SKIP.
    """
    key = f"{symbol.upper()}|{str(direction).lower()}"
    now = time.time()
    fh = _acquire_lock(_LOCK_PATH)
    if fh is None:
        return False
    try:
        data: dict = {}
        if _DEDUP_PATH.exists():
            try:
                raw = json.loads(_DEDUP_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    data = raw
            except Exception:
                data = {}

        last = float(data.get(key, 0) or 0)
        if last and (now - last) < EXECUTE_NOW_BLOCKED_COOLDOWN_SEC:
            return False

        data[key] = now
        data = {k: v for k, v in data.items() if now - float(v) < 86400}
        _DEDUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = _DEDUP_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(_DEDUP_PATH)
        return True
    finally:
        _release_lock(fh)
