from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True, slots=True)
class Cell:
    char: str = " "
    fg: Optional[str] = None
    bg: Optional[str] = None

    @property
    def is_empty(self) -> bool:
        return self.char == " " and self.fg is None and self.bg is None


@dataclass(slots=True)
class Frame:
    width: int
    height: int
    cells: dict[tuple[int, int], Cell] = field(default_factory=dict)
    duration_ms: Optional[float] = None

    def cell_at(self, x: int, y: int) -> Cell:
        return self.cells.get((x, y), Cell())

    def row(self, y: int) -> list[Cell]:
        return [self.cell_at(x, y) for x in range(self.width)]

    def to_plain_text(self, trim: bool = True) -> str:
        lines = []
        for y in range(self.height):
            line = "".join(self.cell_at(x, y).char for x in range(self.width))
            if trim:
                line = line.rstrip()
            lines.append(line)
        if trim:
            while lines and not lines[-1]:
                lines.pop()
            while lines and not lines[0]:
                lines.pop(0)
        return "\n".join(lines)


@dataclass(slots=True)
class AnimationMeta:
    name: str = ""
    version: str = ""
    app_version: str = ""
    frame_rate: int = 12
    loop: bool = True
    width: int = 80
    height: int = 24
    background_color: Optional[str] = None
    created_at: Optional[str] = None


@dataclass(slots=True)
class Animation:
    meta: AnimationMeta
    frames: list[Frame]

    @property
    def frame_count(self) -> int:
        return len(self.frames)

    @property
    def duration_ms(self) -> float:
        per_frame = 1000.0 / self.meta.frame_rate
        return sum(f.duration_ms or per_frame for f in self.frames)

    def get_frame(self, index: int) -> Frame:
        if not 0 <= index < len(self.frames):
            raise IndexError(f"Frame index {index} out of range [0, {len(self.frames)})")
        return self.frames[index]
