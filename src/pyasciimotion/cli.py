from __future__ import annotations

import argparse
import sys

from .parser import load
from .player import Player, play_interactive
from .renderer import render_frame_plain, render_frame, clear, show_cursor
from .utils import format_duration, supports_color


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="pyasciimotion",
        description="Play ASCII animations from ascii-motion.app in your terminal.",
    )
    sub = parser.add_subparsers(dest="command")

    play_p = sub.add_parser("play", help="Play an animation file")
    play_p.add_argument("file", help="Path to animation file (.json, .asciimtn, .txt)")
    play_p.add_argument("--fps", type=int, default=None, help="Override frame rate")
    play_p.add_argument("--no-loop", action="store_true", help="Disable looping")
    play_p.add_argument("--no-color", action="store_true", help="Disable color output")

    info_p = sub.add_parser("info", help="Show animation metadata")
    info_p.add_argument("file", help="Path to animation file")

    frame_p = sub.add_parser("frame", help="Render a single frame")
    frame_p.add_argument("file", help="Path to animation file")
    frame_p.add_argument("--index", type=int, default=0, help="Frame index (default: 0)")
    frame_p.add_argument("--plain", action="store_true", help="Plain text, no color")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        if args.command == "play":
            return _cmd_play(args)
        elif args.command == "info":
            return _cmd_info(args)
        elif args.command == "frame":
            return _cmd_frame(args)
    except FileNotFoundError:
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


def _cmd_play(args: argparse.Namespace) -> int:
    anim = load(args.file)
    use_color = supports_color() and not args.no_color
    loop = not args.no_loop

    play_interactive(anim, fps=args.fps, loop=loop, color=use_color)
    return 0


def _cmd_info(args: argparse.Namespace) -> int:
    anim = load(args.file)
    m = anim.meta

    print(f"Name:        {m.name or '(untitled)'}")
    print(f"Dimensions:  {m.width}x{m.height}")
    print(f"Frames:      {anim.frame_count}")
    print(f"Frame rate:  {m.frame_rate} fps")
    print(f"Duration:    {format_duration(anim.duration_ms)}")
    print(f"Loop:        {'yes' if m.loop else 'no'}")
    if m.version:
        print(f"Format:      v{m.version}")
    if m.app_version:
        print(f"App version: {m.app_version}")
    if m.background_color:
        print(f"Background:  {m.background_color}")
    if m.created_at:
        print(f"Created:     {m.created_at}")

    return 0


def _cmd_frame(args: argparse.Namespace) -> int:
    anim = load(args.file)

    if args.index < 0 or args.index >= anim.frame_count:
        print(
            f"Error: frame index {args.index} out of range [0, {anim.frame_count})",
            file=sys.stderr,
        )
        return 1

    frame = anim.get_frame(args.index)

    if args.plain or not supports_color():
        render_frame_plain(frame)
    else:
        render_frame(frame, color=True)
        print()

    return 0


def entry() -> None:
    raise SystemExit(main())
