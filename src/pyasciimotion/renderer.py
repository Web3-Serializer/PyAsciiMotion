from __future__ import annotations

import os
import shutil
import sys
from typing import Optional, TextIO

from .models import Cell, Frame


_CSI = "\033["
_RESET = f"{_CSI}0m"
_HIDE_CURSOR = f"{_CSI}?25l"
_SHOW_CURSOR = f"{_CSI}?25h"
_CLEAR_SCREEN = f"{_CSI}2J"
_HOME = f"{_CSI}H"

_vt_initialized = False


def init_terminal() -> None:
    global _vt_initialized
    if _vt_initialized:
        return
    _vt_initialized = True

    if os.name == "nt":
        _enable_windows_vt()


def _enable_windows_vt() -> None:
    try:
        import ctypes
        import ctypes.wintypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        STD_OUTPUT_HANDLE = ctypes.wintypes.DWORD(-11)
        STD_ERROR_HANDLE = ctypes.wintypes.DWORD(-12)
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        ENABLE_PROCESSED_OUTPUT = 0x0001

        for handle_id in (STD_OUTPUT_HANDLE, STD_ERROR_HANDLE):
            handle = kernel32.GetStdHandle(handle_id)
            if handle == -1:
                continue
            mode = ctypes.wintypes.DWORD()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                continue
            new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING | ENABLE_PROCESSED_OUTPUT
            kernel32.SetConsoleMode(handle, new_mode)
    except (AttributeError, OSError, ValueError):
        pass


def hide_cursor(out: TextIO = sys.stdout) -> None:
    init_terminal()
    out.write(_HIDE_CURSOR)
    out.flush()


def show_cursor(out: TextIO = sys.stdout) -> None:
    out.write(_SHOW_CURSOR)
    out.flush()


def clear(out: TextIO = sys.stdout) -> None:
    out.write(_CLEAR_SCREEN + _HOME)
    out.flush()


def move_to(row: int, col: int, out: TextIO = sys.stdout) -> None:
    out.write(f"{_CSI}{row};{col}H")


def terminal_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(fallback=(80, 24))
    return size.columns, size.lines


def try_resize_terminal(cols: int, rows: int, out: TextIO = sys.stdout) -> None:
    if os.name == "nt":
        _resize_windows_console(cols, rows)
    else:
        out.write(f"{_CSI}8;{rows};{cols}t")
        out.flush()


def _resize_windows_console(cols: int, rows: int) -> None:
    try:
        os.system(f"mode con: cols={cols} lines={rows}")
    except OSError:
        pass


def fill_background(
    bg_color: str,
    width: int,
    height: int,
    out: TextIO = sys.stdout,
    offset_row: int = 1,
    offset_col: int = 1,
) -> None:
    init_terminal()
    bg_code = _hex_to_ansi_bg(bg_color)
    if not bg_code:
        return
    blank = " " * width
    buf = [f"{_CSI}{bg_code}m"]
    for y in range(height):
        buf.append(f"{_CSI}{offset_row + y};{offset_col}H")
        buf.append(blank)
    buf.append(_RESET)
    out.write("".join(buf))
    out.flush()


def render_frame(
    frame: Frame,
    out: TextIO = sys.stdout,
    color: bool = True,
    offset_row: int = 1,
    offset_col: int = 1,
    bg_color: Optional[str] = None,
    clip_cols: Optional[int] = None,
    clip_rows: Optional[int] = None,
) -> None:
    if color:
        init_terminal()
    draw_h = min(frame.height, clip_rows) if clip_rows else frame.height
    draw_w = min(frame.width, clip_cols) if clip_cols else frame.width

    default_bg = _hex_to_ansi_bg(bg_color) if bg_color else None

    buf: list[str] = []
    prev_fg: Optional[str] = None
    prev_bg: Optional[str] = None

    for y in range(draw_h):
        buf.append(f"{_CSI}{offset_row + y};{offset_col}H")
        prev_fg = None
        prev_bg = None

        for x in range(draw_w):
            cell = frame.cell_at(x, y)

            if color:
                want_fg = _hex_to_ansi_fg(cell.fg) if cell.fg else None
                want_bg = _hex_to_ansi_bg(cell.bg) if cell.bg else default_bg
            else:
                want_fg = None
                want_bg = None

            if want_fg != prev_fg or want_bg != prev_bg:
                if want_fg is None and want_bg is None:
                    if prev_fg is not None or prev_bg is not None:
                        buf.append(_RESET)
                else:
                    parts: list[str] = ["0"]
                    if want_fg:
                        parts.append(want_fg)
                    if want_bg:
                        parts.append(want_bg)
                    buf.append(f"{_CSI}{';'.join(parts)}m")
                prev_fg = want_fg
                prev_bg = want_bg

            buf.append(cell.char)

        if prev_fg is not None or prev_bg is not None:
            buf.append(_RESET)

    out.write("".join(buf))
    out.flush()


def render_frame_plain(frame: Frame, out: TextIO = sys.stdout) -> None:
    out.write(frame.to_plain_text(trim=True))
    out.write("\n")
    out.flush()


def _hex_to_ansi_fg(color: str) -> Optional[str]:
    rgb = _parse_hex(color)
    if rgb is None:
        return None
    r, g, b = rgb
    return f"38;2;{r};{g};{b}"


def _hex_to_ansi_bg(color: str) -> Optional[str]:
    rgb = _parse_hex(color)
    if rgb is None:
        return None
    r, g, b = rgb
    return f"48;2;{r};{g};{b}"


def _parse_hex(color: str) -> tuple[int, int, int] | None:
    color = color.strip().lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    if len(color) != 6:
        return None
    try:
        r = int(color[0:2], 16)
        g = int(color[2:4], 16)
        b = int(color[4:6], 16)
        return r, g, b
    except ValueError:
        return None
