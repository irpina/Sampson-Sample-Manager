# AGENTS.md — SAMPSON Project Guide

> This file provides guidance to AI coding agents working on the SAMPSON codebase.
> SAMPSON is a Universal Audio Sample Manager — a cross-platform desktop app for organizing audio sample libraries for hardware samplers.

---

## Project Overview

SAMPSON is a Python desktop application built with tkinter and customtkinter. It provides a dual-deck interface (Source → Destination) for browsing audio sample libraries, previewing files with audio playback, and copying/moving files with automatic renaming based on parent folder names.

**Key Features:**
- Audio playback (click to play, transport controls)
- Hardware profiles with path-length enforcement (M8: 127 chars, MPC One/SP-404mkII: 255 chars)
- Folder structure modes: Flat, Mirror, One folder per parent
- Live rename preview with hover tooltips
- Dark/Light theme toggle
- HiDPI/4K support on Windows

**Supported audio formats:** `.wav`, `.aiff`, `.aif`, `.flac`, `.mp3`, `.ogg`

---

## Technology Stack

| Component | Technology | Version/Notes |
|-----------|-----------|---------------|
| Language | Python | 3.10+ |
| UI Framework | customtkinter | 5.2.2 — modern rounded widgets |
| Standard UI | tkinter / ttk | Treeview, Progressbar, Text |
| Audio | pygame-ce | SDL2-based audio playback |
| Packaging | PyInstaller | Single-file executable |
| Platforms | Windows, Linux | macOS possible with minor adjustments |

**Dependencies:**
```bash
pip install pygame-ce
# customtkinter is expected to be available (bundled or installed)
```

---

## Project Structure

```
SAMPSON/
├── main.py          # Entry point — DPI setup, creates root window, starts app
├── state.py         # All shared mutable globals (widgets, vars, flags)
├── constants.py     # AUDIO_EXTS, MAX_PREVIEW_ROWS, hardware PROFILES
├── dpi.py           # Windows DPI awareness and _px() scaling helper
├── theme.py         # Colour constants, _apply_theme_colors(), setup_styles()
├── log_panel.py     # Operation log helpers (color-coded output)
├── operations.py    # File copy/move worker, _compute_output(), path truncation
├── browser.py       # Deck A file browser — navigation and browse dialogs
├── preview.py       # Deck B rename preview, hover tooltip, background scan
├── playback.py      # Audio playback via pygame-ce, transport controls
├── builders.py      # All build_* UI functions, toggle_theme(), build_app()
├── SAMPSON.spec     # PyInstaller specification
└── sampsontransparent2.png  # Application logo
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
operations.py  → state, theme, constants, log_panel
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

### Run from source
```bash
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

**PyInstaller notes:**
- `--collect-data pygame` bundles SDL DLLs for audio in the binary
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
1. Saves current paths/settings
2. Destroys all children widgets
3. Calls `ctk.set_appearance_mode()` and `theme._apply_theme_colors()`
4. Rebuilds UI via `build_app()`
5. Restores saved paths/settings

---

## Hardware Profiles

Defined in `constants.py`:

```python
PROFILES = {
    "Generic":    {"path_limit": None},
    "M8":         {"path_limit": 127},
    "MPC One":    {"path_limit": 255},
    "SP-404mkII": {"path_limit": 255},
}
```

Path limits truncate filenames so the full destination path fits within device constraints. Extension is always preserved.

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
ctk.CTkLabel(frame, text="v0.2.4", ...)  # ← Update this
```

### Tracing Variables

UI updates that depend on variable changes use `trace_add("write", callback)`:

```python
state.active_dir_var.trace_add("write", preview.on_active_dir_changed)
state.no_rename_var.trace_add("write", lambda *_: preview.refresh_preview())
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
6. Test dry run vs actual copy/move
7. Test theme toggle (preserve paths)
8. Test HiDPI on Windows (verify no blurriness)

---

## Known Limitations

- Preview capped at 500 rows for performance
- File browser only shows non-hidden subfolders and audio files
- Destination collisions not handled — existing files will be overwritten silently
- Windows-focused (DPI awareness and PyInstaller are Windows-targeted)

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
