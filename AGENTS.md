# AGENTS.md — SAMPSON Project Guide

> This file provides guidance to AI coding agents working on the SAMPSON codebase.  
> SAMPSON is a Universal Audio Sample Manager — a cross-platform desktop app for organizing audio sample libraries for hardware samplers.

---

## Project Overview

SAMPSON is a Python desktop application built with tkinter and customtkinter. It provides a dual-deck interface (Source → Destination) for browsing audio sample libraries, previewing files with audio playback, and copying/moving files with automatic renaming based on parent folder names.

**Key Features:**
- Audio playback (click to play, transport controls ◀ ▶ ▶▶)
- Hardware profiles with path-length enforcement and auto-conversion presets:
  - **Generic**: No limits or conversion
  - **M8**: 127-character SD path limit, auto-convert to 44.1kHz/16-bit WAV
  - **MPC One**: 255-character limit
  - **SP-404mkII**: 255-character limit
  - **Elektron Digitakt**: Auto-convert to 48kHz/16-bit mono WAV
  - **Elektron Analog Rytm**: Auto-convert to 48kHz/16-bit WAV
  - **Elektron Syntakt**: Auto-convert to 48kHz/16-bit WAV
- Audio conversion: WAV/AIFF output, configurable sample rate (44.1k/48k/96k), bit depth (16/24/32-bit), mono/stereo
- Folder structure modes: Flat, Mirror, One folder per parent
- Live rename preview with hover tooltips
- Dark/Light theme toggle (preserves session)
- HiDPI/4K support on Windows

**Supported Audio Formats:**
- **Input:** `.wav`, `.aiff`, `.aif`, `.flac`, `.mp3`, `.ogg`
- **Output:** `.wav`, `.aif`

---

## Technology Stack

| Component | Technology | Version/Notes |
|-----------|-----------|---------------|
| Language | Python | 3.10+ |
| UI Framework | customtkinter | 5.2.2 — modern rounded widgets |
| Standard UI | tkinter / ttk | Treeview, Progressbar, Text |
| Audio Playback | pygame-ce | 2.5.0+ — SDL2-based audio playback |
| Audio Conversion | pydub | 0.25.1+ — with bundled ffmpeg |
| FFmpeg Bundling | static-ffmpeg | 2.5.0+ — bundled ffmpeg + ffprobe binaries |
| Packaging | PyInstaller | Single-file executable |
| Platforms | Windows, Linux, macOS | Cross-platform support |

**Python 3.13+ Compatibility:**
- `audioop-lts>=0.2.0` — provides `audioop` module (removed from Python 3.13 stdlib)

**macOS-Specific:**
- `pyobjc-framework-Cocoa>=10.0` — Required only on Darwin platform

---

## Project Structure

```
SAMPSON/
├── main.py                    # Entry point — DPI setup, creates root window, starts app
├── state.py                   # All shared mutable globals (widgets, vars, flags)
├── constants.py               # AUDIO_EXTS, MAX_PREVIEW_ROWS, hardware PROFILES
├── conversion.py              # Audio conversion engine (pydub + ffmpeg)
├── dpi.py                     # Windows DPI awareness and _px() scaling helper
├── theme.py                   # Colour constants, _apply_theme_colors(), setup_styles()
├── log_panel.py               # Operation log helpers (color-coded output)
├── operations.py              # File copy/move/conversion worker
├── browser.py                 # Deck A file browser — navigation and browse dialogs
├── preview.py                 # Deck B rename preview, hover tooltip, background scan
├── playback.py                # Audio playback via pygame-ce, transport controls
├── builders.py                # All build_* UI functions, toggle_theme(), build_app()
├── requirements.txt           # Python dependencies
├── SAMPSON.spec               # PyInstaller configuration (not in git)
├── build_macos.sh             # macOS build script wrapper
└── sampsontransparent2.png    # Application logo
```

---

## Module Dependency Order

**Critical:** No circular imports. Import order matters.

```
constants.py   (no imports)
state.py       (no app imports)
dpi.py         → state
theme.py       → state, dpi
log_panel.py   → state, theme
conversion.py  → state
operations.py  → state, theme, constants, log_panel, conversion
browser.py     → state, theme, constants, preview
preview.py     → state, theme, constants, dpi, operations
playback.py    → state
builders.py    → state, theme, dpi, browser, preview, playback, log_panel, operations
main.py        → state, theme, dpi, builders
```

---

## State Management Pattern

All shared mutable state lives in `state.py`. **Always** import as:

```python
import state      # ✅ CORRECT — attribute mutation visible everywhere
# state.root, state.source_var, etc.
```

**Never** do this:

```python
from state import root   # ❌ WRONG — mutations won't propagate
```

This is the standard Python pattern for shared mutable globals across a multi-file application.

---

## Build Commands

### Run from Source

```bash
pip install -r requirements.txt
python main.py
```

### Package for Windows

```bash
pyinstaller SAMPSON.spec
# Output: dist/SAMPSON.exe
```

### Package for Linux

```bash
pyinstaller SAMPSON.spec
# Output: dist/SAMPSON ELF binary
# Runtime deps: libsdl2-2.0-0 libsdl2-mixer-2.0-0
```

### Package for macOS

```bash
bash build_macos.sh
# Output: dist/SAMPSON.app
```

### Linux Runtime Dependencies

```bash
# Debian/Ubuntu
sudo apt install libsdl2-2.0-0 libsdl2-mixer-2.0-0

# Fedora/RHEL
sudo dnf install SDL2 SDL2_mixer
```

**PyInstaller Notes:**
- `--collect-data pygame` bundles SDL DLLs for audio in the binary
- `collect_data_files('static_ffmpeg')` bundles ffmpeg + ffprobe binaries
- `sampsontransparent2.png` is bundled as a data file

---

## UI Architecture

### Widget Stack — Mixed CTK + tk/ttk

The UI uses customtkinter for modern widgets alongside plain tk/ttk where CTK has no equivalent.

| Widget Type | Library | Notes |
|-------------|---------|-------|
| Root window | `ctk.CTk` | Rounded window chrome |
| Outer root frame | `tk.Frame` | Avoids CTK canvas z-order issues |
| Card panels | `ctk.CTkFrame(corner_radius=12)` | Rounded corners with border |
| Deck strip headers | `tk.Frame` | Transparent, shows card corners |
| Buttons, entries, checkboxes, radio | CTK widgets | Modern styling |
| File browser | `ttk.Treeview` | Uses `style="Browser.Treeview"` |
| Preview table | `ttk.Treeview` | Uses `style="Preview.Treeview"` |
| Log | `tk.Text` | Needed for color tag support |
| Progress bar | `ttk.Progressbar` | Uses `style="MD3.Horizontal.TProgressbar"` |
| Scrollbars | `ctk.CTkScrollbar` | CTK styling |

### CTK API Rules (Different from ttk)

- Colors: `fg_color=`, `text_color=`, `border_color=` — **not** `bg=`, `fg=`
- Disable/enable: `widget.configure(state="disabled"/"normal")` — **not** `.state(["disabled"])`
- `ctk.CTkLabel` does **not** support `textvariable` — use a trace callback:
  ```python
  lbl = ctk.CTkLabel(frame, text=var.get())
  var.trace_add("write", lambda *_: lbl.configure(text=var.get()))
  ```
- `ctk.CTkScrollbar` uses `orientation=` (not `orient=`) and `button_color=`, `button_hover_color=`

### DPI Scaling

- `state._dpi_scale` is set once at startup in `main.py`
- Use `dpi._px(n)` for every pixel value passed to **non-CTK** widgets
- **Do not** call `tk.call('tk', 'scaling', ...)` — CTK handles its own internal scaling
- Windows: Uses `ctypes.windll.shcore.GetDpiForSystem() / 96.0`
- Linux/macOS: Returns 1.0 (no scaling needed)

---

## Theme System

Two themes available: **Dark** (MD3 near-black) and **Light** (60s/70s pastels).

### Color Constants

All colors are module-level variables in `theme.py`:
- `theme.BG_ROOT`, `theme.BG_SURFACE`, `theme.BG_SURF1`, `theme.BG_SURF2`
- `theme.CYAN` (Deck A accent), `theme.AMBER` (Deck B accent)
- `theme.FG_ON_SURF`, `theme.FG_VARIANT`, `theme.FG_MUTED`, `theme.FG_DIM`
- `theme.C_MOVE`, `theme.C_COPY`, `theme.C_DONE`, `theme.C_DRY` — log colors

### Theme Toggle

`toggle_theme()` lives in `builders.py` (not `theme.py`) to avoid circular imports. It:
1. Saves current paths/settings (source, dest, profile, conversion settings)
2. Stops audio playback
3. Destroys all children widgets
4. Calls `ctk.set_appearance_mode()` and `theme._apply_theme_colors()`
5. Rebuilds UI via `build_app()`
6. Restores saved paths/settings

---

## Hardware Profiles

Defined in `constants.py`:

```python
PROFILES = {
    "Generic": {
        "path_limit": None,
        "conversion": None,
    },
    "M8": {
        "path_limit": 127,
        "conversion": {
            "format": "wav",
            "sample_rate": 44100,
            "bit_depth": 16,
            "channels": None,  # Keep original
            "normalize": False,
        }
    },
    "MPC One": {"path_limit": 255, "conversion": None},
    "SP-404mkII": {"path_limit": 255, "conversion": None},
    "Elektron Digitakt": {
        "path_limit": None,
        "conversion": {
            "format": "wav",
            "sample_rate": 48000,
            "bit_depth": 16,
            "channels": 1,  # Force mono
            "normalize": False,
        }
    },
    "Elektron Analog Rytm": {...},
    "Elektron Syntakt": {...},
}
```

Path limits truncate filenames so the full destination path fits within device constraints. Extension is always preserved.

### Auto-Apply Conversion Presets

When a profile with a `conversion` preset is selected and `convert_follow_profile_var` is True, the conversion options are automatically populated.

---

## Audio Conversion

The `conversion.py` module handles format conversion using pydub with ffmpeg backend.

### Key Functions

- `convert_file(src, dst, **options)` — Convert audio with specified parameters
- `check_ffmpeg()` — Verify ffmpeg is available
- `get_target_extension(format)` — Get file extension for output format
- `parse_sample_rate(value)`, `parse_bit_depth(value)`, `parse_channels(value)` — Parse UI values

### FFmpeg Discovery Priority

1. static-ffmpeg bundled binaries (included with app)
2. System PATH (allows user override)
3. Common install locations (Windows winget, Program Files)

---

## File Operations

### Rename Pattern

By default, files are prefixed with their immediate parent folder:
```
Source:       Drums/Kicks/kick_01.wav
Destination:  Kicks_kick_01.wav
```

Disabled with **Keep original names** checkbox.

### Folder Structure Modes

- **Flat** (`"flat"`) — all files in one folder
- **Mirror** (`"mirror"`) — preserve full source directory tree
- **One folder per parent** (`"parent"`) — group by immediate parent folder name

### Worker Thread

File operations run in a daemon thread (`operations._run_worker`). All UI updates go through `root.after()` for thread safety.

### Conversion During Operations

When conversion is enabled:
1. Source file is converted to target format/settings
2. Converted file is written to destination
3. If "Move files" is enabled, original source file is deleted after successful conversion

---

## Audio Playback

Uses `pygame.mixer` from `pygame-ce` (Python 3.14 incompatible — use `pygame-ce`, not vanilla pygame).

**Key functions in `playback.py`:**
- `play()` — toggle play/stop
- `stop()` — stop playback
- `next_file()`, `prev_file()` — navigate and auto-play
- `on_tree_select()` — click row to play
- `on_arrow_key()` — arrow key navigation with auto-play

**Transport state** stored in `state.transport_*_btn` and updated via `playback._update_transport_state()`.

---

## Development Conventions

### Variable Naming

- tk/ctk widgets: descriptive with type suffix where helpful
- StringVars: `*_var` suffix (e.g., `source_var`, `status_var`)
- Private module state: `_leading_underscore`
- State module globals: no underscore (they're shared)

### Version Management

**Always increment the version** when finishing a change. The label lives in `build_status_bar()` in `builders.py`:

```python
ctk.CTkLabel(frame, text="v0.3.2", ...)  # ← Update this
```

### Tracing Variables

UI updates that depend on variable changes use `trace_add("write", callback)`:

```python
state.active_dir_var.trace_add("write", preview.on_active_dir_changed)
state.no_rename_var.trace_add("write", lambda *_: preview.refresh_preview())
state.profile_var.trace_add("write", _on_profile_changed)
```

### Background Threads

File scanning (`preview._scan_thread`) and operations (`operations._run_worker`) run in daemon threads. Always use `root.after()` for UI updates:

```python
state.root.after(0, lambda: state.status_var.set("Done"))
```

---

## Testing

No automated test suite exists. Testing is manual:

1. Run `python main.py`
2. Test source navigation (browse, click folders, up button)
3. Test checkboxes (select/deselect all)
4. Test audio playback (click preview rows, transport buttons, arrow keys)
5. Test options (rename modes, folder structures, hardware profiles)
6. Test audio conversion (enable conversion, select format/sample rate/bit depth)
7. Test dry run vs actual copy/move
8. Test theme toggle (preserve paths and settings)
9. Test HiDPI on Windows (verify no blurriness)

---

## Known Limitations

- Preview capped at 500 rows for performance
- File browser only shows non-hidden subfolders and audio files
- Destination collisions not handled — existing files will be overwritten silently
- FFmpeg must be available (bundled with PyInstaller builds, or installed separately for dev)

---

## Git Workflow

**Always commit** after completing a change (per `CLAUDE.md` workflow rules).

### .gitignore Notes

The `.gitignore` excludes `CLAUDE.md` itself (meta-documentation not for repo), along with standard Python artifacts, build outputs, and OS files.

---

## Quick Reference

| Task | Where |
|------|-------|
| Add new hardware profile | `constants.py` → `PROFILES` dict |
| Change colors | `theme.py` → color constants, `_apply_theme_colors()` |
| Update version | `builders.py` → `build_status_bar()` |
| Fix DPI scaling | `dpi.py` → `_px()`, `_compute_dpi_scale()` |
| Add audio formats | `constants.py` → `AUDIO_EXTS` |
| Modify UI layout | `builders.py` → `build_app()` and `build_*()` functions |
| Change file operations | `operations.py` → `run_tool()`, `_run_worker()` |
| Adjust preview limit | `constants.py` → `MAX_PREVIEW_ROWS` |
| Add conversion formats | `conversion.py` → `convert_file()`, `get_target_extension()` |

---

## Architecture Decisions

### Why pygame-ce over sounddevice/soundfile?

- `pygame-ce` provides wider format support (MP3, OGG, FLAC)
- Single dependency for all audio needs
- Well-tested with PyInstaller bundling
- SDL2 backend is cross-platform

### Why static-ffmpeg for conversion?

- Bundles ffmpeg + ffprobe binaries automatically
- No separate installation required for end users
- Falls back to system ffmpeg if available

### Why mixed CTK + tk/ttk instead of pure CTK?

- CTK has no Treeview equivalent (needed for file browser and preview)
- CTK Text widget lacks color tag support (needed for log panel)
- ttk Progressbar is more reliable for determinate progress

### Why module-level globals in state.py?

- Simple, Pythonic approach for a single-window desktop app
- Avoids complex state management overhead
- Attribute mutation on module object is visible everywhere
- No risk of circular imports from passing state objects
