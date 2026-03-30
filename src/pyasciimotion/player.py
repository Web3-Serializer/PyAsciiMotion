from __future__ import annotations

import sys
import time
import threading
from enum import Enum, auto
from typing import Callable, Optional, TextIO

from .models import Animation
from .renderer import (
    clear,
    fill_background,
    hide_cursor,
    render_frame,
    show_cursor,
    terminal_size,
    try_resize_terminal,
)


class State(Enum):
    IDLE = auto()
    PLAYING = auto()
    PAUSED = auto()
    STOPPED = auto()


class Player:
    def __init__(
        self,
        animation: Animation,
        fps: Optional[int] = None,
        loop: Optional[bool] = None,
        color: bool = True,
        out: TextIO = sys.stdout,
        on_frame: Optional[Callable[[int], None]] = None,
        auto_fit: bool = True,
    ):
        self._anim = animation
        self._fps = fps or animation.meta.frame_rate
        self._loop = loop if loop is not None else animation.meta.loop
        self._color = color
        self._out = out
        self._on_frame = on_frame
        self._auto_fit = auto_fit
        self._bg_color = animation.meta.background_color

        self._clip_cols: Optional[int] = None
        self._clip_rows: Optional[int] = None

        self._state = State.IDLE
        self._current = 0
        self._lock = threading.Lock()
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def state(self) -> State:
        with self._lock:
            return self._state

    @property
    def current_frame(self) -> int:
        with self._lock:
            return self._current

    @property
    def fps(self) -> int:
        return self._fps

    @fps.setter
    def fps(self, value: int) -> None:
        self._fps = max(1, min(value, 120))

    def play(self, blocking: bool = True) -> None:
        with self._lock:
            if self._state == State.PLAYING:
                return
            self._state = State.PLAYING
            self._stop_event.clear()
            self._pause_event.set()

        if blocking:
            self._run_loop()
        else:
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def pause(self) -> None:
        with self._lock:
            if self._state != State.PLAYING:
                return
            self._state = State.PAUSED
            self._pause_event.clear()

    def resume(self) -> None:
        with self._lock:
            if self._state != State.PAUSED:
                return
            self._state = State.PLAYING
            self._pause_event.set()

    def toggle_pause(self) -> None:
        with self._lock:
            if self._state == State.PLAYING:
                self._state = State.PAUSED
                self._pause_event.clear()
            elif self._state == State.PAUSED:
                self._state = State.PLAYING
                self._pause_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        with self._lock:
            self._state = State.STOPPED
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def seek(self, index: int) -> None:
        total = self._anim.frame_count
        with self._lock:
            self._current = max(0, min(index, total - 1))
        self._draw_current()

    def step(self, delta: int = 1) -> None:
        total = self._anim.frame_count
        with self._lock:
            self._current = max(0, min(self._current + delta, total - 1))
        self._draw_current()

    def _run_loop(self) -> None:
        try:
            hide_cursor(self._out)

            w = self._anim.meta.width
            h = self._anim.meta.height

            if self._auto_fit:
                try_resize_terminal(w, h + 1, self._out)
                import time as _t
                _t.sleep(0.05)

            term_cols, term_rows = terminal_size()
            if w > term_cols or h > term_rows:
                self._clip_cols = term_cols
                self._clip_rows = term_rows

            clear(self._out)

            draw_w = min(w, self._clip_cols) if self._clip_cols else w
            draw_h = min(h, self._clip_rows) if self._clip_rows else h

            if self._color and self._bg_color:
                fill_background(self._bg_color, draw_w, draw_h, self._out)

            self._playback_loop()
        except KeyboardInterrupt:
            pass
        finally:
            show_cursor(self._out)
            with self._lock:
                self._state = State.STOPPED

    def _playback_loop(self) -> None:
        total = self._anim.frame_count
        if total == 0:
            return

        while not self._stop_event.is_set():
            self._pause_event.wait()
            if self._stop_event.is_set():
                break

            with self._lock:
                idx = self._current

            frame = self._anim.get_frame(idx)
            per_frame = frame.duration_ms or (1000.0 / self._fps)
            deadline = time.monotonic() + per_frame / 1000.0

            render_frame(
                frame,
                out=self._out,
                color=self._color,
                bg_color=self._bg_color,
                clip_cols=self._clip_cols,
                clip_rows=self._clip_rows,
            )

            if self._on_frame:
                self._on_frame(idx)

            with self._lock:
                next_idx = self._current + 1
                if next_idx >= total:
                    if self._loop:
                        self._current = 0
                    else:
                        self._state = State.STOPPED
                        break
                else:
                    self._current = next_idx

            remaining = deadline - time.monotonic()
            if remaining > 0:
                self._stop_event.wait(timeout=remaining)

    def _draw_current(self) -> None:
        with self._lock:
            idx = self._current
        frame = self._anim.get_frame(idx)
        render_frame(
            frame,
            out=self._out,
            color=self._color,
            bg_color=self._bg_color,
            clip_cols=self._clip_cols,
            clip_rows=self._clip_rows,
        )


def play_interactive(animation: Animation, fps: int | None = None, loop: bool = True, color: bool = True) -> None:
    orig_cols, orig_rows = terminal_size()
    player = Player(animation, fps=fps, loop=loop, color=color, auto_fit=True)

    running = True

    def _handle_input() -> None:
        nonlocal running
        try:
            fd = sys.stdin.fileno()
            _with_raw_terminal(fd, player, lambda: not running)
        except (OSError, ValueError, ImportError):
            _fallback_input(player, lambda: not running)

    input_thread = threading.Thread(target=_handle_input, daemon=True)
    input_thread.start()

    try:
        player.play(blocking=True)
    except KeyboardInterrupt:
        player.stop()
    finally:
        running = False
        show_cursor()
        clear()
        try_resize_terminal(orig_cols, orig_rows)


def _with_raw_terminal(fd: int, player: Player, should_stop: Callable[[], bool]) -> None:
    import termios
    import tty

    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while not should_stop() and player.state in (State.PLAYING, State.PAUSED):
            ch = sys.stdin.read(1)
            if not ch:
                break
            _dispatch_key(ch, player)
            if ch in ("q", "Q", "\x03"):
                break
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _fallback_input(player: Player, should_stop: Callable[[], bool]) -> None:
    try:
        import msvcrt
        while not should_stop() and player.state in (State.PLAYING, State.PAUSED):
            if msvcrt.kbhit():
                ch = msvcrt.getch().decode("utf-8", errors="ignore")
                _dispatch_key(ch, player)
                if ch in ("q", "Q"):
                    break
            else:
                time.sleep(0.05)
    except ImportError:
        while not should_stop() and player.state in (State.PLAYING, State.PAUSED):
            time.sleep(0.1)


def _dispatch_key(ch: str, player: Player) -> None:
    if ch in ("q", "Q", "\x03"):
        player.stop()
    elif ch == " ":
        player.toggle_pause()
    elif ch in (".", "]"):
        player.step(1)
    elif ch in (",", "["):
        player.step(-1)
    elif ch == "0":
        player.seek(0)
    elif ch == "+":
        player.fps = player.fps + 1
    elif ch == "-":
        player.fps = max(1, player.fps - 1)
