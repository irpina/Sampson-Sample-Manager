# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SAMPSON is a Python desktop GUI app (tkinter + customtkinter) for organizing audio sample libraries for hardware samplers. It has a dual-deck interface: Deck A (file browser) → Deck B (rename preview + playback), plus file copy/move/conversion.

## Running from Source

```bash
# macOS: Homebrew Python does NOT include tkinter — use python.org or pyenv
# The venv must be built with a tkinter-capable Python
pip install -r requirements.txt
python main.py
```

**macOS tkinter issue:** Homebrew Python 3.14 (`/opt/homebrew/Cellar/python@3.14/`) lacks `_tkinter`. Fix with:
```bash
brew install python-tk@3.13   # or use python.org installer
```

## Build

```bash
# macOS
bash build_macos.sh           # produces dist/SAMPSON.app via pyinstaller SAMPSON_mac.spec

# Windows / Linux
pyinstaller SAMPSON.spec      # produces dist/SAMPSON.exe or dist/SAMPSON ELF
```

Linux runtime deps for audio: `libsdl2-2.0-0 libsdl2-mixer-2.0-0` (apt) or `SDL2 SDL2_mixer` (dnf).

## Architecture

### Module dependency order (no circular imports)

```
constants.py   ← no imports
state.py       ← no app imports
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

### State management

All shared mutable state lives in `state.py`. **Always** import as the module, never destructure:

```python
import state           # ✅
state.root.after(...)  # ✅

from state import root  # ❌ mutations won't propagate
```

### UI widget stack

The app mixes customtkinter (modern rounded widgets) with plain tk/ttk where CTK has no equivalent:
- File browser and preview table: `ttk.Treeview` (CTK has no equivalent)
- Operation log: `tk.Text` (needs color tag support)
- Everything else: CTK widgets

**CTK API differences from ttk:**
- Colors: `fg_color=`, `text_color=`, `border_color=` (not `bg=`, `fg=`)
- Enable/disable: `widget.configure(state="disabled")` (not `.state(["disabled"])`)
- `ctk.CTkLabel` does **not** support `textvariable` — use `trace_add`:
  ```python
  lbl = ctk.CTkLabel(frame, text=var.get())
  var.trace_add("write", lambda *_: lbl.configure(text=var.get()))
  ```

### DPI scaling

`dpi._px(n)` scales pixel values for non-CTK widgets only. Do **not** call `tk.call('tk', 'scaling', ...)` — CTK handles its own scaling.

- **Windows:** `_dpi_scale` = system DPI / 96 (e.g. 1.25 at 120 DPI, 2.0 at 192 DPI)
- **Linux / macOS:** `_dpi_scale` must be `1.0` — tkinter coordinates are already in logical points on macOS and CTK handles Retina rendering internally. **Do not use `backingScaleFactor` for `_dpi_scale`** — it would double all dimensions (BUG-002).

`MIN_ASPECT_RATIO = 1.38` is defined in `dpi.py` and should be enforced via a `<Configure>` binding on macOS to prevent the window from becoming too narrow when zoomed or resized.

### Theme toggle

`toggle_theme()` in `builders.py` saves paths/settings, destroys all widgets, switches CTK appearance mode, then calls `build_app()` and restores state. The function lives in `builders.py` (not `theme.py`) to avoid circular imports.

### Background threads

File scanning and operations run in daemon threads. All UI updates must go through:
```python
state.root.after(0, lambda: state.status_var.set("Done"))
```

## Key conventions

- **Version label**: Update the `"v0.x.x"` string in `build_status_bar()` in `builders.py` when finishing any change.
- **Add hardware profile**: Only `constants.py` → `PROFILES` dict needs changing.
- **Add audio input format**: Only `constants.py` → `AUDIO_EXTS` set.
- **Prefer** `pygame-ce` (not vanilla `pygame`) — required for Python 3.14+ compatibility.
- `audioop-lts` is required for Python 3.13+ (stdlib removed `audioop`).

## Quick reference

| Task | Where |
|------|-------|
| Add hardware profile | `constants.py` → `PROFILES` |
| Change UI colors | `theme.py` → color constants + `_apply_theme_colors()` |
| Update version | `builders.py` → `build_status_bar()` |
| Modify layout | `builders.py` → `build_app()` and `build_*()` |
| Change file operations | `operations.py` → `run_tool()`, `_run_worker()` |
| Audio conversion logic | `conversion.py` → `convert_file()` |
| Adjust preview row limit | `constants.py` → `MAX_PREVIEW_ROWS` |
