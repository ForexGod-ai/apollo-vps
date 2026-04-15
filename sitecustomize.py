"""
sitecustomize.py — Windows VPS UTF-8 fix
Loaded automatically by Python at startup (before any user code).
Forces sys.stdout and sys.stderr to UTF-8 on Windows CMD (cp1252 default).
This prevents UnicodeEncodeError on emoji/Cyrillic in all loguru/logging output.
"""
import sys
import io
import os

# Force PYTHONUTF8 mode
os.environ.setdefault('PYTHONUTF8', '1')

# Re-wrap stdout/stderr with UTF-8 if running on Windows with a non-UTF-8 console
if sys.platform == 'win32':
    if hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )
    if hasattr(sys.stderr, 'buffer'):
        sys.stderr = io.TextIOWrapper(
            sys.stderr.buffer,
            encoding='utf-8',
            errors='replace',
            line_buffering=True
        )
