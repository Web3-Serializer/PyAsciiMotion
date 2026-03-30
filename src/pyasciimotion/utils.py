from __future__ import annotations

import os
import shutil


def terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.columns, size.lines


def fits_terminal(width: int, height: int) -> bool:
    cols, rows = terminal_size()
    return width <= cols and height <= rows


def supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    term = os.environ.get("TERM", "")
    if "color" in term or "256" in term or "xterm" in term:
        return True
    if os.name == "nt":
        return True
    try:
        import sys
        return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    except Exception:
        return False


def format_duration(ms: float) -> str:
    seconds = ms / 1000.0
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"
