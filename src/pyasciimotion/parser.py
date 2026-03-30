from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Union

from .models import Animation, AnimationMeta, Cell, Frame


def load(source: Union[str, Path]) -> Animation:
    path = Path(source)
    raw = path.read_text(encoding="utf-8")

    if path.suffix in (".json", ".asciimtn"):
        return _parse_json(raw, path.name)

    if path.suffix == ".txt":
        return _parse_plain_text(raw, path.name)

    try:
        return _parse_json(raw, path.name)
    except (json.JSONDecodeError, KeyError):
        return _parse_plain_text(raw, path.name)


def loads(data: str, name: str = "untitled") -> Animation:
    try:
        return _parse_json(data, name)
    except (json.JSONDecodeError, KeyError):
        return _parse_plain_text(data, name)


def _parse_json(raw: str, name: str) -> Animation:
    doc = json.loads(raw)

    if "version" in doc and "animation" in doc:
        return _parse_session(doc, name)

    if "frames" in doc:
        return _parse_export_json(doc, name)

    if isinstance(doc, list):
        return _parse_frame_array(doc, name)

    raise KeyError("Unrecognized JSON structure")


def _parse_session(doc: dict[str, Any], name: str) -> Animation:
    metadata = doc.get("metadata", {})
    anim_data = doc.get("animation", {})
    canvas = doc.get("canvas", {})

    width = canvas.get("width", 80)
    height = canvas.get("height", 24)
    frame_rate = anim_data.get("frameRate", 12)

    meta = AnimationMeta(
        name=metadata.get("name", name),
        version=doc.get("version", ""),
        app_version=metadata.get("appVersion", ""),
        frame_rate=frame_rate,
        loop=anim_data.get("looping", True),
        width=width,
        height=height,
        background_color=canvas.get("backgroundColor"),
        created_at=metadata.get("createdAt"),
    )

    raw_frames = anim_data.get("frames", [])
    if not raw_frames:
        raw_frames = _extract_v2_frames(doc, width, height)

    frames = [_parse_session_frame(f, width, height) for f in raw_frames]
    if not frames:
        frames = [Frame(width=width, height=height)]

    return Animation(meta=meta, frames=frames)


def _extract_v2_frames(doc: dict[str, Any], width: int, height: int) -> list[dict]:
    layers = doc.get("layers", doc.get("animation", {}).get("layers", []))
    if not layers:
        return []

    frames_out = []
    for layer in layers:
        content_frames = layer.get("contentFrames", layer.get("frames", []))
        for cf in content_frames:
            frames_out.append(cf)

    return frames_out


def _parse_session_frame(raw: dict[str, Any], width: int, height: int) -> Frame:
    cells: dict[tuple[int, int], Cell] = {}
    duration_ms = raw.get("durationMs") or raw.get("duration")

    cell_data = raw.get("cells", raw.get("data", {}))

    if isinstance(cell_data, dict):
        for key, val in cell_data.items():
            coords = _parse_cell_key(key)
            if coords is None:
                continue
            cells[coords] = _build_cell(val)

    elif isinstance(cell_data, list):
        for entry in cell_data:
            if isinstance(entry, list) and len(entry) >= 3:
                x, y = int(entry[0]), int(entry[1])
                char = str(entry[2])
                fg = entry[3] if len(entry) > 3 else None
                bg = entry[4] if len(entry) > 4 else None
                cells[(x, y)] = Cell(char=char, fg=fg, bg=bg)

    rows = raw.get("rows", raw.get("content", None))
    if rows and isinstance(rows, list):
        colors = raw.get("colors", raw.get("colorDict", {}))
        cells = _parse_content_rows(rows, colors, width)

    return Frame(width=width, height=height, cells=cells, duration_ms=duration_ms)


def _parse_cell_key(key: str) -> tuple[int, int] | None:
    if "," in key:
        parts = key.split(",", 1)
    elif ":" in key:
        parts = key.split(":", 1)
    else:
        return None
    try:
        return int(parts[0].strip()), int(parts[1].strip())
    except (ValueError, IndexError):
        return None


def _build_cell(val: Any) -> Cell:
    if isinstance(val, str):
        return Cell(char=val[0] if val else " ")
    if isinstance(val, dict):
        return Cell(
            char=val.get("char", val.get("character", val.get("c", " "))),
            fg=val.get("fg", val.get("foreground", val.get("color"))),
            bg=val.get("bg", val.get("background", val.get("bgColor"))),
        )
    return Cell()


def _parse_content_rows(
    rows: list[str], colors: dict[str, Any], width: int
) -> dict[tuple[int, int], Cell]:
    cells: dict[tuple[int, int], Cell] = {}
    color_map = _resolve_color_dict(colors)

    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch == " ":
                continue
            fg = color_map.get((x, y, "fg"))
            bg = color_map.get((x, y, "bg"))
            cells[(x, y)] = Cell(char=ch, fg=fg, bg=bg)

    return cells


def _resolve_color_dict(colors: dict[str, Any]) -> dict[tuple[int, int, str], str]:
    result: dict[tuple[int, int, str], str] = {}
    if not colors:
        return result

    fg_map = colors.get("foreground")
    bg_map = colors.get("background")

    if fg_map and isinstance(fg_map, dict):
        for key, val in fg_map.items():
            coords = _parse_cell_key(key)
            if coords is None:
                continue
            if isinstance(val, str):
                result[(*coords, "fg")] = val
        if bg_map and isinstance(bg_map, dict):
            for key, val in bg_map.items():
                coords = _parse_cell_key(key)
                if coords is None:
                    continue
                if isinstance(val, str):
                    result[(*coords, "bg")] = val
        return result

    for key, val in colors.items():
        coords = _parse_cell_key(key)
        if coords is None:
            continue
        x, y = coords
        if isinstance(val, dict):
            if "fg" in val:
                result[(x, y, "fg")] = val["fg"]
            if "bg" in val:
                result[(x, y, "bg")] = val["bg"]
        elif isinstance(val, str):
            result[(x, y, "fg")] = val

    return result


def _parse_export_json(doc: dict[str, Any], name: str) -> Animation:
    canvas = doc.get("canvas", {})
    anim_cfg = doc.get("animation", {})

    width = canvas.get("width", doc.get("width", 80))
    height = canvas.get("height", doc.get("height", 24))
    frame_rate = anim_cfg.get("frameRate", doc.get("frameRate", doc.get("fps", 12)))
    loop = anim_cfg.get("looping", doc.get("loop", True))

    meta = AnimationMeta(
        name=doc.get("name", name),
        frame_rate=frame_rate,
        loop=loop,
        width=width,
        height=height,
        background_color=canvas.get("backgroundColor"),
    )

    color_dict = doc.get("colorDict", doc.get("colors", {}))
    frames = []

    for raw_frame in doc["frames"]:
        content = raw_frame.get("content")
        rows = raw_frame.get("rows")

        if content is not None or rows is not None:
            if isinstance(content, str):
                row_data = content.split("\n")
            elif isinstance(content, list):
                row_data = content
            elif isinstance(rows, list):
                row_data = rows
            else:
                row_data = []
            cells = _parse_content_rows(
                row_data,
                raw_frame.get("colors", color_dict),
                width,
            )
        elif "cells" in raw_frame:
            cells = {}
            cell_data = raw_frame["cells"]
            if isinstance(cell_data, dict):
                for key, val in cell_data.items():
                    coords = _parse_cell_key(key)
                    if coords is None:
                        continue
                    cells[coords] = _build_cell(val)
            elif isinstance(cell_data, list):
                for entry in cell_data:
                    if isinstance(entry, list) and len(entry) >= 3:
                        x, y = int(entry[0]), int(entry[1])
                        char = str(entry[2])
                        fg_idx = entry[3] if len(entry) > 3 else None
                        bg_idx = entry[4] if len(entry) > 4 else None
                        fg = _resolve_indexed_color(fg_idx, color_dict)
                        bg = _resolve_indexed_color(bg_idx, color_dict)
                        cells[(x, y)] = Cell(char=char, fg=fg, bg=bg)
        else:
            cells = {}

        duration = raw_frame.get("durationMs", raw_frame.get("duration"))
        frames.append(Frame(width=width, height=height, cells=cells, duration_ms=duration))

    return Animation(meta=meta, frames=frames)


def _resolve_indexed_color(idx: Any, color_dict: dict) -> str | None:
    if idx is None:
        return None
    if isinstance(idx, str) and idx.startswith("#"):
        return idx
    color_list = color_dict.get("palette", color_dict.get("list", []))
    if isinstance(color_list, list):
        try:
            return color_list[int(idx)]
        except (IndexError, ValueError, TypeError):
            pass
    if isinstance(idx, (int, str)):
        return color_dict.get(str(idx))
    return None


def _parse_frame_array(doc: list, name: str) -> Animation:
    if not doc:
        raise ValueError("Empty frame array")

    first = doc[0]
    if isinstance(first, str):
        frame = _text_to_frame(doc)
        meta = AnimationMeta(name=name, width=frame.width, height=frame.height)
        return Animation(meta=meta, frames=[frame])

    if isinstance(first, list):
        frames = []
        max_w = 0
        max_h = 0
        for item in doc:
            if isinstance(item, list) and all(isinstance(r, str) for r in item):
                f = _text_to_frame(item)
                max_w = max(max_w, f.width)
                max_h = max(max_h, f.height)
                frames.append(f)
        for f in frames:
            f.width = max_w
            f.height = max_h
        meta = AnimationMeta(name=name, width=max_w, height=max_h)
        return Animation(meta=meta, frames=frames)

    raise KeyError("Unrecognized array structure")


def _text_to_frame(lines: list[str]) -> Frame:
    cells: dict[tuple[int, int], Cell] = {}
    width = max((len(line) for line in lines), default=0)
    height = len(lines)
    for y, line in enumerate(lines):
        for x, ch in enumerate(line):
            if ch != " ":
                cells[(x, y)] = Cell(char=ch)
    return Frame(width=width, height=height, cells=cells)


def _parse_plain_text(raw: str, name: str) -> Animation:
    separator = "\n---\n"
    if separator in raw:
        chunks = raw.split(separator)
    else:
        chunks = [raw]

    frames = []
    max_w = 0
    max_h = 0

    for chunk in chunks:
        lines = chunk.split("\n")
        f = _text_to_frame(lines)
        max_w = max(max_w, f.width)
        max_h = max(max_h, f.height)
        frames.append(f)

    for f in frames:
        f.width = max_w
        f.height = max_h

    meta = AnimationMeta(name=name, width=max_w, height=max_h)
    return Animation(meta=meta, frames=frames)
