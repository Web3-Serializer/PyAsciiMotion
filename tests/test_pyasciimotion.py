import io
import json
import tempfile
from pathlib import Path

import pytest

from pyasciimotion import AsciiMotion, Cell, Frame, Animation, AnimationMeta, load, loads
from pyasciimotion.parser import _parse_plain_text, _parse_json
from pyasciimotion.renderer import render_frame, render_frame_plain, _parse_hex
from pyasciimotion.player import Player, State
from pyasciimotion.utils import format_duration
from pyasciimotion.cli import main


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


class TestCell:
    def test_defaults(self):
        c = Cell()
        assert c.char == " "
        assert c.fg is None
        assert c.bg is None
        assert c.is_empty

    def test_non_empty(self):
        c = Cell(char="X", fg="#ff0000")
        assert not c.is_empty
        assert c.char == "X"

    def test_frozen(self):
        c = Cell(char="A")
        with pytest.raises(AttributeError):
            c.char = "B"


class TestFrame:
    def test_cell_at_default(self):
        f = Frame(width=10, height=5)
        cell = f.cell_at(0, 0)
        assert cell.char == " "
        assert cell.is_empty

    def test_cell_at_populated(self):
        f = Frame(width=10, height=5, cells={(2, 3): Cell(char="@")})
        assert f.cell_at(2, 3).char == "@"
        assert f.cell_at(0, 0).is_empty

    def test_row(self):
        f = Frame(width=3, height=1, cells={(1, 0): Cell(char="X")})
        row = f.row(0)
        assert len(row) == 3
        assert row[1].char == "X"

    def test_to_plain_text(self):
        cells = {(0, 0): Cell(char="H"), (1, 0): Cell(char="i")}
        f = Frame(width=5, height=2, cells=cells)
        text = f.to_plain_text(trim=True)
        assert text == "Hi"

    def test_to_plain_text_no_trim(self):
        cells = {(0, 0): Cell(char="A")}
        f = Frame(width=3, height=2, cells=cells)
        text = f.to_plain_text(trim=False)
        assert text == "A  \n   "


class TestAnimation:
    def test_frame_count(self):
        meta = AnimationMeta()
        frames = [Frame(width=10, height=5) for _ in range(3)]
        anim = Animation(meta=meta, frames=frames)
        assert anim.frame_count == 3

    def test_get_frame_bounds(self):
        meta = AnimationMeta()
        frames = [Frame(width=10, height=5)]
        anim = Animation(meta=meta, frames=frames)
        anim.get_frame(0)
        with pytest.raises(IndexError):
            anim.get_frame(1)
        with pytest.raises(IndexError):
            anim.get_frame(-1)

    def test_duration(self):
        meta = AnimationMeta(frame_rate=10)
        frames = [Frame(width=1, height=1) for _ in range(10)]
        anim = Animation(meta=meta, frames=frames)
        assert anim.duration_ms == pytest.approx(1000.0)


class TestParserSession:
    def test_load_session_file(self):
        path = EXAMPLES / "spinner.json"
        if not path.exists():
            pytest.skip("spinner.json not found")
        anim = load(path)
        assert anim.frame_count == 4
        assert anim.meta.width == 9
        assert anim.meta.height == 5
        assert anim.meta.frame_rate == 8
        assert anim.meta.name == "Spinner Demo"

    def test_session_cells(self):
        path = EXAMPLES / "spinner.json"
        if not path.exists():
            pytest.skip("spinner.json not found")
        anim = load(path)
        frame = anim.get_frame(0)
        cell = frame.cell_at(3, 1)
        assert cell.char == "/"
        assert cell.fg == "#00ff88"


class TestParserExportJson:
    def test_load_export_json(self):
        path = EXAMPLES / "wave.json"
        if not path.exists():
            pytest.skip("wave.json not found")
        anim = load(path)
        assert anim.frame_count == 3
        assert anim.meta.width == 20

    def test_content_rows_with_colors(self):
        path = EXAMPLES / "wave.json"
        if not path.exists():
            pytest.skip("wave.json not found")
        anim = load(path)
        frame = anim.get_frame(0)
        cell = frame.cell_at(2, 1)
        assert cell.char == "~"
        assert cell.fg == "#4488ff"


class TestParserPlainText:
    def test_single_frame(self):
        anim = loads("Hello\nWorld")
        assert anim.frame_count == 1
        assert anim.meta.width == 5
        frame = anim.get_frame(0)
        assert frame.cell_at(0, 0).char == "H"

    def test_multi_frame(self):
        text = "AB\nCD\n---\nEF\nGH"
        anim = loads(text)
        assert anim.frame_count == 2
        assert anim.get_frame(0).cell_at(0, 0).char == "A"
        assert anim.get_frame(1).cell_at(0, 0).char == "E"

    def test_load_txt_file(self):
        path = EXAMPLES / "dance.txt"
        if not path.exists():
            pytest.skip("dance.txt not found")
        anim = load(path)
        assert anim.frame_count == 4

    def test_json_array_of_strings(self):
        data = json.dumps(["Hello", "World"])
        anim = loads(data)
        assert anim.frame_count == 1
        assert anim.get_frame(0).cell_at(0, 0).char == "H"

    def test_json_array_of_arrays(self):
        data = json.dumps([["AB", "CD"], ["EF", "GH"]])
        anim = loads(data)
        assert anim.frame_count == 2


class TestParserCellFormats:
    def test_cell_as_string(self):
        doc = {
            "version": "1.0.0",
            "metadata": {},
            "animation": {
                "frames": [{"cells": {"0,0": "X"}}],
                "frameRate": 12,
                "looping": True,
            },
            "canvas": {"width": 5, "height": 3},
        }
        anim = loads(json.dumps(doc))
        assert anim.get_frame(0).cell_at(0, 0).char == "X"

    def test_cell_compact_array(self):
        doc = {
            "name": "test",
            "width": 5,
            "height": 3,
            "frames": [{"cells": [[0, 0, "A", "#ff0000"], [1, 0, "B"]]}],
        }
        anim = loads(json.dumps(doc))
        frame = anim.get_frame(0)
        assert frame.cell_at(0, 0).char == "A"
        assert frame.cell_at(0, 0).fg == "#ff0000"
        assert frame.cell_at(1, 0).char == "B"

    def test_colon_key_separator(self):
        doc = {
            "version": "1.0.0",
            "metadata": {},
            "animation": {
                "frames": [{"cells": {"2:3": {"char": "Z"}}}],
                "frameRate": 12,
                "looping": True,
            },
            "canvas": {"width": 10, "height": 10},
        }
        anim = loads(json.dumps(doc))
        assert anim.get_frame(0).cell_at(2, 3).char == "Z"


class TestRenderer:
    def test_init_terminal_idempotent(self):
        from pyasciimotion.renderer import init_terminal, _vt_initialized
        init_terminal()
        init_terminal()
        from pyasciimotion import renderer
        assert renderer._vt_initialized is True

    def test_parse_hex_6(self):
        assert _parse_hex("#ff8800") == (255, 136, 0)

    def test_parse_hex_3(self):
        assert _parse_hex("#f80") == (255, 136, 0)

    def test_parse_hex_invalid(self):
        assert _parse_hex("notacolor") is None

    def test_render_plain(self):
        cells = {(0, 0): Cell(char="X"), (1, 0): Cell(char="Y")}
        frame = Frame(width=5, height=2, cells=cells)
        buf = io.StringIO()
        render_frame_plain(frame, out=buf)
        assert "XY" in buf.getvalue()

    def test_render_ansi(self):
        cells = {(0, 0): Cell(char="@", fg="#ff0000")}
        frame = Frame(width=3, height=1, cells=cells)
        buf = io.StringIO()
        render_frame(frame, out=buf, color=True)
        output = buf.getvalue()
        assert "@" in output
        assert "38;2;255;0;0" in output

    def test_render_with_bg_color(self):
        cells = {(0, 0): Cell(char=".", fg="#aaaaaa")}
        frame = Frame(width=3, height=1, cells=cells)
        buf = io.StringIO()
        render_frame(frame, out=buf, color=True, bg_color="#000000")
        output = buf.getvalue()
        assert "48;2;0;0;0" in output
        assert "38;2;170;170;170" in output

    def test_render_cell_bg_overrides_default(self):
        cells = {(0, 0): Cell(char="X", fg="#ffffff", bg="#ff0000")}
        frame = Frame(width=2, height=1, cells=cells)
        buf = io.StringIO()
        render_frame(frame, out=buf, color=True, bg_color="#000000")
        output = buf.getvalue()
        assert "48;2;255;0;0" in output

    def test_render_clip_cols(self):
        cells = {(0, 0): Cell(char="A"), (5, 0): Cell(char="B")}
        frame = Frame(width=10, height=1, cells=cells)
        buf = io.StringIO()
        render_frame(frame, out=buf, color=False, clip_cols=3)
        output = buf.getvalue()
        assert "A" in output
        assert "B" not in output

    def test_render_clip_rows(self):
        cells = {(0, 0): Cell(char="A"), (0, 5): Cell(char="B")}
        frame = Frame(width=1, height=10, cells=cells)
        buf = io.StringIO()
        render_frame(frame, out=buf, color=False, clip_rows=2)
        output = buf.getvalue()
        assert "A" in output
        assert "B" not in output

    def test_fill_background(self):
        buf = io.StringIO()
        from pyasciimotion.renderer import fill_background
        fill_background("#112233", 5, 2, out=buf)
        output = buf.getvalue()
        assert "48;2;17;34;51" in output
        assert "     " in output


class TestPlayer:
    def test_initial_state(self):
        meta = AnimationMeta(frame_rate=10)
        frames = [Frame(width=1, height=1) for _ in range(3)]
        anim = Animation(meta=meta, frames=frames)
        p = Player(anim, out=io.StringIO())
        assert p.state == State.IDLE
        assert p.current_frame == 0

    def test_play_no_loop_stops(self):
        meta = AnimationMeta(frame_rate=100)
        frames = [Frame(width=1, height=1) for _ in range(2)]
        anim = Animation(meta=meta, frames=frames)
        buf = io.StringIO()
        p = Player(anim, fps=100, loop=False, color=False, out=buf)
        p.play(blocking=True)
        assert p.state == State.STOPPED

    def test_seek(self):
        meta = AnimationMeta(frame_rate=10)
        frames = [Frame(width=1, height=1) for _ in range(5)]
        anim = Animation(meta=meta, frames=frames)
        buf = io.StringIO()
        p = Player(anim, out=buf, color=False)
        p.seek(3)
        assert p.current_frame == 3

    def test_seek_clamps(self):
        meta = AnimationMeta(frame_rate=10)
        frames = [Frame(width=1, height=1) for _ in range(5)]
        anim = Animation(meta=meta, frames=frames)
        buf = io.StringIO()
        p = Player(anim, out=buf, color=False)
        p.seek(100)
        assert p.current_frame == 4
        p.seek(-5)
        assert p.current_frame == 0

    def test_fps_setter(self):
        meta = AnimationMeta(frame_rate=10)
        anim = Animation(meta=meta, frames=[Frame(width=1, height=1)])
        p = Player(anim, out=io.StringIO())
        p.fps = 30
        assert p.fps == 30
        p.fps = -5
        assert p.fps == 1
        p.fps = 200
        assert p.fps == 120

    def test_on_frame_callback(self):
        meta = AnimationMeta(frame_rate=100)
        frames = [Frame(width=1, height=1) for _ in range(3)]
        anim = Animation(meta=meta, frames=frames)
        seen = []
        p = Player(anim, fps=100, loop=False, color=False, out=io.StringIO(), on_frame=seen.append)
        p.play(blocking=True)
        assert seen == [0, 1, 2]


class TestAsciiMotionAPI:
    def test_load_and_iterate(self):
        path = EXAMPLES / "spinner.json"
        if not path.exists():
            pytest.skip("spinner.json not found")
        am = AsciiMotion.load(path)
        assert len(am) == 4
        assert am.width == 9
        texts = [am.frame_text(i) for i in range(len(am))]
        assert len(texts) == 4

    def test_getitem(self):
        path = EXAMPLES / "spinner.json"
        if not path.exists():
            pytest.skip("spinner.json not found")
        am = AsciiMotion.load(path)
        frame = am[0]
        assert isinstance(frame, Frame)

    def test_repr(self):
        am = AsciiMotion.from_string("Hi\n---\nBye")
        r = repr(am)
        assert "AsciiMotion" in r
        assert "2 frames" in r

    def test_iter(self):
        am = AsciiMotion.from_string("A\n---\nB\n---\nC")
        frames = list(am)
        assert len(frames) == 3


class TestUtils:
    def test_format_duration_seconds(self):
        assert format_duration(5500) == "5.5s"

    def test_format_duration_minutes(self):
        assert format_duration(125000) == "2m 5.0s"


class TestCLI:
    def test_info_command(self, capsys):
        path = EXAMPLES / "spinner.json"
        if not path.exists():
            pytest.skip("spinner.json not found")
        ret = main(["info", str(path)])
        assert ret == 0
        out = capsys.readouterr().out
        assert "Spinner Demo" in out
        assert "4" in out

    def test_frame_command_plain(self, capsys):
        path = EXAMPLES / "spinner.json"
        if not path.exists():
            pytest.skip("spinner.json not found")
        ret = main(["frame", str(path), "--index", "0", "--plain"])
        assert ret == 0

    def test_frame_out_of_range(self, capsys):
        path = EXAMPLES / "spinner.json"
        if not path.exists():
            pytest.skip("spinner.json not found")
        ret = main(["frame", str(path), "--index", "99"])
        assert ret == 1

    def test_no_command(self, capsys):
        ret = main([])
        assert ret == 0

    def test_missing_file(self, capsys):
        ret = main(["info", "/nonexistent/file.json"])
        assert ret == 1


class TestRealExportFormat:
    def _make_real_format(self):
        return {
            "canvas": {"width": 10, "height": 3, "backgroundColor": "#000000"},
            "typography": {"fontSize": 18, "characterSpacing": 1, "lineSpacing": 1},
            "animation": {"frameRate": 25, "looping": False, "currentFrame": 0},
            "frames": [
                {
                    "title": "Frame 0",
                    "duration": 40,
                    "content": "..X.......\n...XX.....\n..........",
                    "colors": {
                        "foreground": {
                            "0,0": "#112233",
                            "1,0": "#112233",
                            "2,0": "#ff0000",
                            "3,1": "#ff0000",
                            "4,1": "#ff0000",
                        }
                    },
                },
                {
                    "title": "Frame 1",
                    "duration": 40,
                    "content": "..........\n..X.......\n...XX.....",
                    "colors": {
                        "foreground": {
                            "2,1": "#00ff00",
                            "3,2": "#00ff00",
                            "4,2": "#00ff00",
                        },
                        "background": {
                            "2,1": "#333333",
                        },
                    },
                },
            ],
        }

    def test_parses_canvas_dimensions(self):
        doc = self._make_real_format()
        anim = loads(json.dumps(doc))
        assert anim.meta.width == 10
        assert anim.meta.height == 3

    def test_parses_animation_settings(self):
        doc = self._make_real_format()
        anim = loads(json.dumps(doc))
        assert anim.meta.frame_rate == 25
        assert anim.meta.loop is False
        assert anim.meta.background_color == "#000000"

    def test_parses_frame_count(self):
        doc = self._make_real_format()
        anim = loads(json.dumps(doc))
        assert anim.frame_count == 2

    def test_parses_content_string(self):
        doc = self._make_real_format()
        anim = loads(json.dumps(doc))
        frame = anim.get_frame(0)
        assert frame.cell_at(2, 0).char == "X"
        assert frame.cell_at(3, 1).char == "X"
        assert frame.cell_at(4, 1).char == "X"

    def test_parses_nested_foreground_colors(self):
        doc = self._make_real_format()
        anim = loads(json.dumps(doc))
        frame = anim.get_frame(0)
        assert frame.cell_at(2, 0).fg == "#ff0000"
        assert frame.cell_at(0, 0).fg == "#112233"

    def test_parses_nested_background_colors(self):
        doc = self._make_real_format()
        anim = loads(json.dumps(doc))
        frame = anim.get_frame(1)
        assert frame.cell_at(2, 1).bg == "#333333"
        assert frame.cell_at(2, 1).fg == "#00ff00"

    def test_parses_frame_duration(self):
        doc = self._make_real_format()
        anim = loads(json.dumps(doc))
        assert anim.get_frame(0).duration_ms == 40
        assert anim.get_frame(1).duration_ms == 40

    def test_roundtrip_via_file(self, tmp_path):
        doc = self._make_real_format()
        path = tmp_path / "export.json"
        path.write_text(json.dumps(doc))
        anim = load(path)
        assert anim.frame_count == 2
        assert anim.meta.frame_rate == 25
        assert anim.get_frame(0).cell_at(2, 0).char == "X"
        assert anim.get_frame(0).cell_at(2, 0).fg == "#ff0000"

    def test_stringified_json_foreground(self):
        doc = {
            "canvas": {"width": 5, "height": 2},
            "animation": {"frameRate": 10, "looping": True},
            "frames": [
                {
                    "content": "AB\nCD",
                    "colors": {
                        "foreground": json.dumps({"0,0": "#ff0000", "1,0": "#00ff00"}),
                    },
                }
            ],
        }
        anim = loads(json.dumps(doc))
        assert anim.get_frame(0).cell_at(0, 0).fg == "#ff0000"
        assert anim.get_frame(0).cell_at(1, 0).fg == "#00ff00"

    def test_stringified_json_background(self):
        doc = {
            "canvas": {"width": 5, "height": 2},
            "animation": {"frameRate": 10, "looping": True},
            "frames": [
                {
                    "content": "AB\nCD",
                    "colors": {
                        "foreground": json.dumps({"0,0": "#ff0000"}),
                        "background": json.dumps({"0,0": "#333333"}),
                    },
                }
            ],
        }
        anim = loads(json.dumps(doc))
        assert anim.get_frame(0).cell_at(0, 0).fg == "#ff0000"
        assert anim.get_frame(0).cell_at(0, 0).bg == "#333333"

    def test_content_as_list(self):
        doc = {
            "canvas": {"width": 5, "height": 2},
            "animation": {"frameRate": 10, "looping": True},
            "frames": [
                {
                    "content": ["AB", "CD"],
                    "colors": {"foreground": {"0,0": "#aabbcc"}},
                }
            ],
        }
        anim = loads(json.dumps(doc))
        assert anim.get_frame(0).cell_at(0, 0).char == "A"
        assert anim.get_frame(0).cell_at(0, 0).fg == "#aabbcc"
        assert anim.get_frame(0).cell_at(1, 1).char == "D"

    def test_content_string_fallback(self):
        doc = {
            "canvas": {"width": 3, "height": 1},
            "animation": {"frameRate": 10, "looping": True},
            "frames": [
                {
                    "contentString": "XYZ",
                    "colors": {"foreground": {"1,0": "#112233"}},
                }
            ],
        }
        anim = loads(json.dumps(doc))
        assert anim.get_frame(0).cell_at(1, 0).char == "Y"
        assert anim.get_frame(0).cell_at(1, 0).fg == "#112233"

    def test_metadata_title(self):
        doc = {
            "metadata": {"title": "My Animation", "appVersion": "2.0.14"},
            "canvas": {"width": 5, "height": 2},
            "animation": {"frameRate": 12, "looping": True},
            "frames": [{"content": "AB\nCD", "colors": {}}],
        }
        anim = loads(json.dumps(doc))
        assert anim.meta.name == "My Animation"
        assert anim.meta.app_version == "2.0.14"


class TestFileRoundTrip:
    def test_write_and_read_session(self, tmp_path):
        doc = {
            "version": "1.0.0",
            "metadata": {"name": "roundtrip"},
            "animation": {
                "frames": [
                    {"cells": {"0,0": {"char": "R", "fg": "#00ff00"}}},
                    {"cells": {"0,0": {"char": "T", "fg": "#0000ff"}}},
                ],
                "frameRate": 10,
                "looping": False,
            },
            "canvas": {"width": 5, "height": 3},
        }
        path = tmp_path / "test.json"
        path.write_text(json.dumps(doc))
        anim = load(path)
        assert anim.frame_count == 2
        assert anim.meta.name == "roundtrip"
        assert not anim.meta.loop
        assert anim.get_frame(0).cell_at(0, 0).char == "R"
        assert anim.get_frame(1).cell_at(0, 0).fg == "#0000ff"

    def test_write_and_read_plain(self, tmp_path):
        path = tmp_path / "test.txt"
        path.write_text("ABC\nDEF\n---\nGHI\nJKL")
        anim = load(path)
        assert anim.frame_count == 2
        assert anim.get_frame(0).cell_at(0, 0).char == "A"
        assert anim.get_frame(1).cell_at(2, 1).char == "L"

    def test_asciimtn_extension(self, tmp_path):
        doc = {
            "version": "1.0.0",
            "metadata": {"name": "ext test"},
            "animation": {
                "frames": [{"cells": {"1,1": {"char": "!"}}}],
                "frameRate": 12,
                "looping": True,
            },
            "canvas": {"width": 10, "height": 5},
        }
        path = tmp_path / "test.asciimtn"
        path.write_text(json.dumps(doc))
        anim = load(path)
        assert anim.frame_count == 1
        assert anim.get_frame(0).cell_at(1, 1).char == "!"
