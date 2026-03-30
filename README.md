# PyAsciiMotion

Play [ASCII Motion](https://ascii-motion.app/) animations in your Python terminal.

Parses session files (`.json`, `.asciimtn`), JSON exports, and plain-text frame files from ascii-motion.app — then renders them with full ANSI color support, frame-by-frame playback, and interactive controls.

## Install

```
pip install pyasciimotion
```

## Quick start

```python
from pyasciimotion import AsciiMotion

anim = AsciiMotion.load("demo.json")
anim.play()
```

## Python API

### Loading

```python
from pyasciimotion import AsciiMotion

# From a file
anim = AsciiMotion.load("path/to/file.json")
anim = AsciiMotion.load("path/to/file.asciimtn")
anim = AsciiMotion.load("path/to/file.txt")

# From a string
anim = AsciiMotion.from_string(json_text, name="my animation")
```

### Inspecting

```python
print(anim.frame_count)      # number of frames
print(anim.width, anim.height)
print(anim.meta.frame_rate)
print(anim.meta.name)

# Iterate frames
for frame in anim:
    print(frame.to_plain_text())

# Access a single frame
frame = anim[3]
text = anim.frame_text(3)
```

### Playing

```python
# Interactive playback (blocking, keyboard controls)
anim.play(fps=10, loop=True, color=True)

# Render a single frame to stdout
anim.render(index=0, color=True)
```

#### Keyboard controls during playback

| Key | Action |
|---|---|
| `Space` | Pause / Resume |
| `q` | Quit |
| `.` or `]` | Step forward |
| `,` or `[` | Step backward |
| `0` | Jump to first frame |
| `+` | Increase FPS |
| `-` | Decrease FPS |

### Advanced player

```python
player = anim.player(fps=12, loop=True, color=True)
player.play(blocking=False)   # runs in background thread

player.pause()
player.resume()
player.seek(10)
player.step(1)
player.fps = 24
player.stop()

print(player.state)           # State.PLAYING, State.PAUSED, etc.
print(player.current_frame)
```

### Low-level access

```python
from pyasciimotion import load, render_frame, Cell, Frame

animation = load("demo.json")
frame = animation.get_frame(0)

cell = frame.cell_at(5, 3)
print(cell.char, cell.fg, cell.bg)

for cell in frame.row(0):
    print(cell.char, end="")
```

## CLI

```
pyasciimotion play demo.json
pyasciimotion play demo.json --fps 24 --no-loop --no-color
pyasciimotion info demo.json
pyasciimotion frame demo.json --index 3
pyasciimotion frame demo.json --index 0 --plain
```

Also works via module:

```
python -m pyasciimotion play demo.json
```

## Supported formats

| Format | Extension | Description |
|---|---|---|
| Session v1/v2 | `.json`, `.asciimtn` | Full project state from ascii-motion.app |
| JSON export | `.json` | Compact frame data with color dictionaries |
| Plain text | `.txt` | Character-only frames separated by `---` |

## Architecture

```
pyasciimotion/
├── __init__.py    # Public API (AsciiMotion class)
├── models.py      # Cell, Frame, Animation, AnimationMeta
├── parser.py      # File format detection and parsing
├── renderer.py    # ANSI terminal rendering
├── player.py      # Threaded playback with controls
├── cli.py         # Command-line interface
└── utils.py       # Terminal detection, formatting
```

The parser auto-detects format from file extension and content structure. The renderer uses 24-bit ANSI color sequences (truecolor). The player runs playback on a background thread with pause/resume/seek via threading primitives.

## Requirements

- Python 3.10+
- No external dependencies

## License

MIT
