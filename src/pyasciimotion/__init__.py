from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from .models import Animation, AnimationMeta, Cell, Frame
from .parser import load, loads
from .player import Player, State, play_interactive
from .renderer import init_terminal, render_frame, render_frame_plain


class AsciiMotion:
    def __init__(self, animation: Animation):
        self._animation = animation
        self._player: Optional[Player] = None

    @classmethod
    def load(cls, path: Union[str, Path]) -> AsciiMotion:
        return cls(load(path))

    @classmethod
    def from_string(cls, data: str, name: str = "untitled") -> AsciiMotion:
        return cls(loads(data, name))

    @property
    def animation(self) -> Animation:
        return self._animation

    @property
    def meta(self) -> AnimationMeta:
        return self._animation.meta

    @property
    def frames(self) -> list[Frame]:
        return self._animation.frames

    @property
    def frame_count(self) -> int:
        return self._animation.frame_count

    @property
    def width(self) -> int:
        return self._animation.meta.width

    @property
    def height(self) -> int:
        return self._animation.meta.height

    def get_frame(self, index: int) -> Frame:
        return self._animation.get_frame(index)

    def frame_text(self, index: int, trim: bool = True) -> str:
        return self.get_frame(index).to_plain_text(trim=trim)

    def play(
        self,
        fps: Optional[int] = None,
        loop: bool = True,
        color: bool = True,
    ) -> None:
        play_interactive(self._animation, fps=fps, loop=loop, color=color)

    def player(
        self,
        fps: Optional[int] = None,
        loop: Optional[bool] = None,
        color: bool = True,
    ) -> Player:
        return Player(self._animation, fps=fps, loop=loop, color=color)

    def render(self, index: int = 0, color: bool = True) -> None:
        frame = self.get_frame(index)
        if color:
            render_frame(frame)
        else:
            render_frame_plain(frame)

    def __repr__(self) -> str:
        name = self.meta.name or "untitled"
        return f"AsciiMotion({name!r}, {self.frame_count} frames, {self.width}x{self.height})"

    def __len__(self) -> int:
        return self.frame_count

    def __getitem__(self, index: int) -> Frame:
        return self.get_frame(index)

    def __iter__(self):
        return iter(self._animation.frames)


__all__ = [
    "AsciiMotion",
    "Animation",
    "AnimationMeta",
    "Cell",
    "Frame",
    "Player",
    "State",
    "init_terminal",
    "load",
    "loads",
    "render_frame",
    "render_frame_plain",
    "play_interactive",
]
