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

There is no test suite.

## Build

```bash
# macOS — produces dist/SAMPSON.app (signed + notarized if env vars set)
APPLE_CODESIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
APPLE_ID="you@example.com" \
APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx" \
APPLE_TEAM_ID="XXXXXXXXXX" \
bash build_macos.sh

# macOS — ad-hoc sign only (no notarization, for local testing):
bash build_macos.sh

# Windows / Linux
pyinstaller SAMPSON.spec      # produces dist/SAMPSON.exe or dist/SAMPSON ELF
```

Linux runtime deps for audio: `libsdl2-2.0-0 libsdl2-mixer-2.0-0` (apt) or `SDL2 SDL2_mixer` (dnf).

### macOS build — critical rules

The venv must be created with a **python.org Python** (not Homebrew — it lacks `_tkinter`).

`build_macos.sh` runs 7 steps: pre-fetch ffmpeg → PyInstaller → Tcl/Tk cleanup → fix Python.framework → sign → notarize → copy back. Full documentation with all gotchas in `memory/build_macos.md` (git-ignored, synced via cloud drive).

**Hard rules — violations will silently break the build:**

- **Never delete `python3.X/` from the bundle.** It contains `lib-dynload/*.so` (all stdlib C extensions — `_struct`, `_json`, etc.). Deletion causes `[PYI-ERROR] Module object for struct is NULL!` on launch. The `python3__dot__14` directory is PyInstaller's codesign alias; the original `python3.14` directory is what the bootloader actually loads.
- **Always sign in `/tmp`, never inside the OneDrive folder.** OneDrive injects xattrs mid-signing, invalidating the signature. The script copies to `/tmp/SAMPSON_build_$$.app`, strips xattrs with `xattr -cr`, then signs there.
- **Sign all components individually, not with `codesign --deep`.** Deep signing processes outer before inner — notarization rejects unsigned nested binaries. Sign order: `.so`/`.dylib` files → `ffmpeg`/`ffprobe` → `Python.framework` binary → app bundle last.
- **Every `codesign` call needs `--options runtime --timestamp`**, or notarization rejects the submission.
- **`fix_python_framework()` must run before signing.** PyInstaller creates flat Python.framework binaries; codesign requires `Versions/Current` to be a symlink and `Python` at the root to be a symlink. Fix both `Contents/Resources/Python.framework` and `Contents/Frameworks/Python.framework`. Do NOT add `Headers` or `Resources` symlinks — if those directories don't exist under `Versions/X.Y/`, the symlinks dangle and Gatekeeper rejects the bundle.
- **Use `ditto` (not `cp -r`) for all `.app` copies.** `cp -r` dereferences symlinks and breaks the Python.framework structure.
- **Do not delete `tcl9/` from the bundle.** PyInstaller cross-links `Resources/tcl9 ↔ Frameworks/tcl9`; deleting one side creates a dangling symlink that Gatekeeper rejects.

## Architecture

### Module dependency order (no circular imports)

```
constants.py   ← no imports
state.py       ← no app imports
bpm.py         → conversion  ← uses conversion._find_ffmpeg_path()
key.py         → conversion  ← uses conversion._find_ffmpeg_path()
dpi.py         → state
theme.py       → state, dpi
log_panel.py   → state, theme
conversion.py  → state
operations.py  → state, theme, constants, log_panel, conversion, bpm, key
browser.py     → state, theme, constants, preview
preview.py     → state, theme, constants, dpi, operations, bpm, key, conversion
playback.py    → state
builders.py    → state, theme, dpi, browser, preview, playback, log_panel, operations
main.py        → state, theme, dpi, builders
```

**`browser.py`** populates `state.dir_browser` (the Deck A `ttk.Treeview`) and manages `state._selected_folders` (a `set` of folder paths to include in the scan). It is stateless beyond what it writes into `state` — other modules never call browser functions directly.

**Key shared function:** `_compute_output()` in `operations.py` is used by both `operations._run_worker()` (actual execution) and `preview._populate_preview()` (preview display). It computes the final filename and subfolder for each source file given the current rename/struct/path-limit settings.

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

The outer `root_frame` is `tk.Frame` (not CTK) to avoid CTK canvas z-order issues with layered panels.

**CTK API differences from ttk:**
- Colors: `fg_color=`, `text_color=`, `border_color=` (not `bg=`, `fg=`)
- Enable/disable: `widget.configure(state="disabled")` (not `.state(["disabled"])`)
- `ctk.CTkLabel` does **not** support `textvariable` — use `trace_add`:
  ```python
  lbl = ctk.CTkLabel(frame, text=var.get())
  var.trace_add("write", lambda *_: lbl.configure(text=var.get()))
  ```
- `ctk.CTkScrollbar` uses `orientation=` (not `orient=`) and `button_color=`, `button_hover_color=`

### DPI scaling

`dpi._px(n)` scales pixel values for non-CTK widgets only. Do **not** call `tk.call('tk', 'scaling', ...)` — CTK handles its own scaling.

- **Windows:** `_dpi_scale` = system DPI / 96 (e.g. 1.25 at 120 DPI, 2.0 at 192 DPI)
- **Linux / macOS:** `_dpi_scale` must be `1.0` — tkinter coordinates are already in logical points on macOS and CTK handles Retina rendering internally. **Do not use `backingScaleFactor` for `_dpi_scale`** — it would double all dimensions (BUG-002).

`MIN_ASPECT_RATIO = 1.38`, `MIN_WINDOW_WIDTH = 900`, and `MIN_WINDOW_HEIGHT = 600` are defined in `dpi.py`. The aspect ratio is enforced via a `<Configure>` binding in `main.py` on macOS. `_usable_screen_size()` in `dpi.py` uses `AppKit.NSScreen.visibleFrame()` on macOS to clamp the initial window size below the menu bar and dock.

### PyInstaller asset resolution

For any data file bundled with PyInstaller (e.g., the logo image), resolve the path with:
```python
import sys
base = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(".")
logo_path = base / "sampsontransparent2.png"
```

### Audio conversion pipeline

`conversion.py` wraps **pydub** (high-level audio processing) with **ffmpeg** as the backend:

- **Bundled ffmpeg:** `static-ffmpeg` package ships ffmpeg + ffprobe binaries with the app.
- **ffmpeg lookup priority** in `_find_ffmpeg_path()`: (1) static-ffmpeg bundled, (2) system PATH, (3) common install locations.
- `convert_file()` applies changes in order: sample rate → channels → normalize → export with bit-depth codec flags.
- Bit depth for WAV is passed as ffmpeg codec parameters (`pcm_s16le`, `pcm_s24le`, `pcm_s32le`); for AIFF it uses big-endian variants.
- Conversion errors are stored in `state._last_conversion_error` for the main thread to retrieve after `convert_file()` returns `False`.
- When **Move** mode is on and conversion succeeds, the original source file is deleted after the converted file is written.

### Theme toggle

`toggle_theme()` in `builders.py` saves paths/settings, destroys all widgets, switches CTK appearance mode, then calls `build_app()` and restores state. The function lives in `builders.py` (not `theme.py`) to avoid circular imports.

### Background threads

File scanning and operations run in daemon threads. All UI updates must go through:
```python
state.root.after(0, lambda: state.status_var.set("Done"))
```

Preview refresh is debounced: `on_active_dir_changed()` cancels any pending `after()` call and re-schedules `refresh_preview()` with a 300 ms delay before spawning the scan thread.

### Playback

`playback.py` uses **platform-specific backends**:
- **macOS:** `AppKit.NSSound` — native, zero extra deps; imported lazily to avoid AppKit/tkinter initialization race conditions
- **Windows/Linux:** `pygame-ce` (`pygame.mixer`) — wider format support (MP3, OGG, FLAC)

The play/prev/next transport reads the hidden `srcpath` column from `state.preview_tree` to get the actual file path. Selecting a row in the preview tree (click or arrow key) auto-plays.

### Log coloring

`log_panel.log()` auto-assigns a color tag based on the message prefix:
- `"[DRY]"` anywhere → yellow (`C_DRY`)
- Starts with `"MOVE"` → red (`C_MOVE`)
- Starts with `"COPY"` → green (`C_COPY`)
- `"Done."` exactly → cyan bold (`C_DONE`)
- Otherwise → plain foreground

### Rename pattern

Controlled by `state.modify_names_var` (tk.BooleanVar):
- **False (default — browse mode):** No renaming; Deck B shows only the original filename and BPM columns. Good for auditing a library without touching filenames.
- **True (rename mode):** Files are prefixed with their immediate parent folder name, and Deck B shows "Will become" + Subfolder columns.

```
Source:       Drums/Kicks/kick_01.wav
Destination:  Kicks_kick_01.wav   # rename mode
```

### Deck B live filter

`state.preview_filter_var` (tk.StringVar) drives a search bar above the preview tree. `preview.apply_filter(text)` re-renders the tree from the cached `_preview_rows` list (built by `_populate_preview()`). When a query is active, **all** matches are shown (no row cap). When unfiltered, display is capped at `MAX_PREVIEW_ROWS` (500).

The filter supports structured tokens alongside plain filename substrings:
- `BPM:120` — exact BPM match
- `BPM:100-130` — BPM range
- `BPM:12*` — wildcard (matches 120–129); single-digit wildcards assume 3-digit range (e.g. `BPM:1*` → 100–199)
- `Note:C` or `Note:C#` — root note match (case-insensitive)
- `MinLength:30` — files ≥ 30 seconds
- `MaxLength:90` — files ≤ 90 seconds (e.g. for a 1.5-minute loop)

Tokens can be combined with free text, e.g. `kick BPM:120 MaxLength:5`.

Duration is read from file headers during the background scan (WAV/AIFF via stdlib `wave`/`aifc`; MP3/FLAC/OGG via ffprobe). Files whose duration cannot be read are excluded when a length filter is active.

### Deck B column sorting

Clicking the **BPM**, **Note**, or **Length** column headers cycles through: ascending ▲ → descending ▼ → unsorted. Sort state lives in `preview._sort_col` (`"bpm" | "key" | "duration" | None`) and `preview._sort_asc` (bool). Sorting is applied to `_preview_rows` before filtering, so the filter always operates on a sorted list.

### Folder structure modes

Controlled by `state.struct_mode_var` (`"flat"` | `"mirror"` | `"parent"`):
- **flat** — all files land directly in destination
- **mirror** — preserves full source directory tree relative to source root
- **parent** — each file goes in a subfolder named after its immediate parent

### BPM detection

`bpm.py` detects tempo using energy-envelope autocorrelation — no `librosa` or `numpy` required, just `pydub`. It delegates ffmpeg discovery to `conversion._find_ffmpeg_path()` so both modules use the same lookup (static-ffmpeg → PATH → common install locations).

- **Cache:** `~/.sampson/bpm_cache.json`, keyed by absolute file path + mtime. Invalidated automatically when the file is modified.
- **Public API:** `detect_bpm(path, force=False)`, `get_cached_bpm(path)`, `set_cached_bpm(path, bpm)`, `flush_cache()`
- **UI integration:** BPM is detected during `_run_worker()` when `state.bpm_enabled_var` is True; results are shown in the `bpm` column of `state.preview_tree`. The column is visible whenever detection is enabled **or** any file already has a cached BPM value. Double-clicking the BPM cell opens an inline editor for manual override (`preview._on_bpm_double_click`).
- **Fresh scan:** `state.bpm_fresh_var` (tk.BooleanVar) — when True, `detect_bpm()` is called with `force=True`, bypassing the cache and re-detecting from audio.
- **Filename suffix:** When `state.bpm_append_var` is True, `_120bpm` is appended to the output stem (e.g. `Kicks_kick_01_120bpm.wav`).

### Key detection

`key.py` detects musical root note (pitch class: C, C#, D, etc.) using pitch-period autocorrelation — no `librosa` or `numpy` required, just `pydub`. Mirrors the BPM architecture exactly.

- **Cache:** `~/.sampson/key_cache.json`, keyed by absolute file path + mtime.
- **Public API:** `detect_key(path, force=False)`, `get_cached_key(path)`, `set_cached_key(path, key)`, `flush_cache()`
- **UI integration:** Key is detected during `_run_worker()` when `state.key_enabled_var` is True; results are shown in the `key` column of `state.preview_tree`. The column is visible whenever detection is enabled **or** any file already has a cached key value. Double-clicking the Key cell opens an inline editor for manual override (`preview._on_key_double_click`).
- **Fresh scan:** `state.key_fresh_var` (tk.BooleanVar) — when True, `detect_key()` is called with `force=True`, bypassing the cache and re-detecting from audio.
- **Filename suffix:** When `state.key_append_var` is True, `_{key}` is appended to the output stem (e.g. `Kicks_kick_01_C.wav`).

### Collapsible center panel sections

`_section_header()` in `builders.py` creates a clickable ▶/▼ header that shows/hides a group of widgets. Section open/closed state is stored in `state._section_open` (dict keyed by section name: `"struct"`, `"device"`, `"conversion"`, `"bpm"`, `"key"`) and persists across theme toggles. Current sections in `build_center()`: Folder structure, Hardware profile, Audio conversion, BPM analysis, Key detection.

## Key conventions

- **Version label**: Update the `"v0.x.x"` string in `build_status_bar()` in `builders.py` when finishing any change.
- **Add hardware profile**: Only `constants.py` → `PROFILES` dict needs changing. Each profile has `path_limit` (int or None) and `conversion` (dict or None). When `convert_follow_profile_var` is True, selecting a profile with a `conversion` preset auto-populates the conversion UI.
- **Add audio input format**: Only `constants.py` → `AUDIO_EXTS` set.
- **Prefer** `pygame-ce` (not vanilla `pygame`) — required for Python 3.14+ compatibility.
- `audioop-lts` is required for Python 3.13+ (stdlib removed `audioop`).
- `pyobjc-framework-Cocoa` is required on macOS for `NSSound` (playback) and `NSScreen` (window sizing).
- `pyi_rth_tk_silence.py` is a PyInstaller runtime hook that must run before tkinter imports to suppress the Tcl/Tk 9.0 deprecation warning in signed macOS bundles.

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
| Add output structure mode | `operations._compute_output()` + `builders.build_center()` |
| BPM detection algorithm | `bpm._detect_bpm_algorithm()` |
| Key detection algorithm | `key._detect_key_algorithm()` |
| macOS code signing / notarization | `notarize.sh` |

## Known limitations

- Unfiltered preview capped at `MAX_PREVIEW_ROWS` (500) for performance; the Deck B search bar bypasses this cap and shows all matches.
- Destination collisions not handled — existing files are overwritten silently.
- FFmpeg must be available (bundled with PyInstaller builds; installed separately for dev runs that use conversion).
- **BUG-001** (open): Center panel collapses at very small window widths — root cause is `minsize` in `build_app()` column config in `builders.py`.
- **BUG-002** (open): macOS window launches oversized and clips behind the menu bar/dock — `_compute_dpi_scale()` in `dpi.py` must return `1.0` on macOS; using `backingScaleFactor` doubles all dimensions.
