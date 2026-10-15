"""Windows-safe console: UTF-8, colorama, optional ANSI strip for broken CMD."""
from __future__ import annotations

import os
import re
import sys

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*m')

# V76: initialize colorama on first import (PowerShell / CMD ANSI → no raw ^[32m)
if sys.platform == 'win32':
    try:
        import colorama
        colorama.init(autoreset=True, strip=False, convert=True)
    except ImportError:
        pass


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)


class _AnsiStripWriter:
    """Wrap stdout/stderr when TERM does not interpret ANSI (raw ^[32m)."""

    def __init__(self, stream):
        self._stream = stream

    def write(self, data):
        if isinstance(data, bytes):
            data = data.decode('utf-8', errors='replace')
        return self._stream.write(strip_ansi(data))

    def flush(self):
        return self._stream.flush()

    def isatty(self):
        return self._stream.isatty()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def init_console() -> None:
    """Call once at process start (daily_scanner, radar, etc.)."""
    if sys.platform == 'win32':
        try:
            import colorama
            colorama.init(autoreset=True, strip=False, convert=True)
        except ImportError:
            pass
        if os.getenv('STRIP_ANSI', '0') == '1':
            if not isinstance(sys.stdout, _AnsiStripWriter):
                sys.stdout = _AnsiStripWriter(sys.stdout)
            if not isinstance(sys.stderr, _AnsiStripWriter):
                sys.stderr = _AnsiStripWriter(sys.stderr)


def loguru_colorize() -> bool:
    """Use loguru colorize when TTY and STRIP_ANSI is off (Windows: colorama convert)."""
    if os.getenv('STRIP_ANSI', '0') == '1':
        return False
    try:
        return sys.stderr.isatty()
    except Exception:
        return False
