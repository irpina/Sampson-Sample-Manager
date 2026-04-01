# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

SAMPSON is a cross-platform desktop app for organizing audio sample libraries for hardware samplers. It uses **PyWebView** — a Python backend exposed via a JS API bridge to an HTML/CSS/JS frontend (single-page app). Dual-deck interface: Deck A (file browser) → Deck B (rename preview + playback), plus file copy/move/conversion.

## Running from Source

```bash
pip install -r requirements.txt
python main.py
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

`build_macos.sh` runs 7 steps: pre-fetch ffmpeg → PyInstaller → Tcl/Tk cleanup → fix Python.framework → sign → notarize → copy back.

**Hard rules — violations will silently break the build:**

- **Always sign in `/tmp`, never inside the OneDrive folder.** OneDrive injects xattrs mid-signing, invalidating the signature. The script copies to `/tmp/SAMPSON_build_$$.app`, strips xattrs with `xattr -cr`, then signs there.
- **Sign all components individually, not with `codesign --deep`.** Deep signing processes outer before inner — notarization rejects unsigned nested binaries. Sign order: `.so`/`.dylib` files → `ffmpeg`/`ffprobe` → `Python.framework` binary → app bundle last.
- **Every `codesign` call needs `--options runtime --timestamp`**, or notarization rejects the submission.
- **`fix_python_framework()` must run before signing.** PyInstaller creates flat Python.framework binaries; codesign requires `Versions/Current` to be a symlink and `Python` at the root to be a symlink. Do NOT add `Headers` or `Resources` symlinks — if those directories don't exist under `Versions/X.Y/`, the symlinks dangle and Gatekeeper rejects the bundle.
- **Use `ditto` (not `cp -r`) for all `.app` copies.** `cp -r` dereferences symlinks and breaks the Python.framework structure.
- **Never delete `python3.X/` from the bundle.** It contains `lib-dynload/*.so` (all stdlib C extensions). Deletion causes `[PYI-ERROR] Module object for struct is NULL!` on launch.

## Architecture

### Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ |
| UI framework | PyWebView 4.0+ |
| Frontend | HTML5 + CSS3 + Vanilla JS (SPA) |
| Audio playback | pygame-ce (Win/Linux), NSSound (macOS) |
| Audio conversion | pydub + static-ffmpeg |
| BPM/Key detection | Custom autocorrelation (no numpy/librosa) |
| Packaging | PyInstaller |

### Module dependency order (no circular imports)

```
constants.py   ← no imports
state.py       ← no app imports
conversion.py  → state
bpm.py         → conversion
key.py         → conversion
browser.py     → state, constants
preview.py     → state, constants, operations, bpm, key, conversion
playback.py    → state
operations.py  → state, constants, conversion, bpm, key
api.py         → state, browser, preview, playback, operations, conversion
main.py        → state, api
```

### State management (`state.py`)

All shared mutable state lives in a single Python dict in `state.py`. **Never** scatter state across modules.

- **Sync to JS:** call `state.push_keys(['key1', 'key2'])` (or `state.push_keys()` for all) — this calls `window.evaluate_js('window._onStateUpdate(...)')` to patch the JS `APP_STATE`.
- **Reading state in Python:** `state.get('key')` or `state._store['key']`
- **Setting state in Python:** `state.set('key', value)` — does NOT auto-push to JS; caller must push.
- **Compatibility shim:** `state._VarCompat` allows legacy `.get()/.set()` call patterns.

Key state fields: `source`, `dest`, `active_dir`, `selected_folders`, `move`, `dry`, `modify_names`, `custom_prefix`, `profile`, `struct_mode`, `convert_*`, `bpm_*`, `key_*`, `status`, `progress`, `is_running`, `is_dark`, `dir_entries`, `preview_entries`, `log_lines`.

### API bridge (`api.py`)

`SampsonAPI` class is passed as `js_api` to `webview.create_window()`. All public methods are callable from JS as `pywebview.api.method_name(args)`. Methods run on a pywebview background thread — use `state.push_keys()` to send results back to JS; do not return large data directly (prefer state sync).

### Frontend (`ui/`)

- `index.html` — single-page app shell; no server-side rendering
- `app.js` — all JS logic; `APP_STATE` mirrors Python state; `window._onStateUpdate(patch)` receives pushed updates
- `style.css` — CSS variables for theming; dark mode is default (`:root`), light mode overrides via `body.light-mode`

**Theme switching:** `toggleTheme()` in `app.js` adds/removes `body.light-mode` class and calls `pywebview.api.set_option('is_dark', ...)`. No widget rebuild needed — CSS variables cascade automatically.

**Logo:** Both PNGs live in `ui/` (same directory as `index.html`) because PyWebView uses `http_server=False` (file:// URLs), and WKWebView's sandbox blocks `../` parent directory access. Logo swaps on theme toggle: `sampsontransparentwhite.png` (dark mode) / `sampsontransparent2.png` (light mode).

**PyInstaller asset resolution:** For Python-side assets bundled with PyInstaller:
```python
import sys
base = Path(sys._MEIPASS) if hasattr(sys, '_MEIPASS') else Path(".")
asset_path = base / "ui" / "sampsontransparentwhite.png"
```

### Layout

The main body uses a **flex row** layout (`.main-grid`):
```
.main-grid (flex row, fills remaining height)
  ├── .deck-a    (flex: 3, full height, cyan left border)
  ├── .center-col (flex: 2, flex column)
  │     ├── .center-panel  (flex: 1, scrollable options)
  │     ├── .status-bar
  │     └── .log-panel
  └── .deck-b    (flex: 3, full height, amber left border)
```

Both deck accent bars are plain `border-left` — they naturally span full window height because the decks are full-height flex siblings.

### Background threads

Long-running operations (file scan, BPM detection, file copy/move) run in daemon threads. Push state back to JS via `state.push_keys()` — pywebview's `evaluate_js()` is thread-safe.

### Playback (`playback.py`)

Platform-specific backends:
- **macOS:** `AppKit.NSSound` (native, zero extra deps; imported lazily)
- **Windows/Linux:** `pygame-ce` / `pygame.mixer`

Transport reads file path from `APP_STATE.preview_entries[index].srcpath`.

### Audio conversion pipeline (`conversion.py`)

Wraps **pydub** with **ffmpeg** as backend:
- **ffmpeg lookup priority** in `_find_ffmpeg_path()`: (1) static-ffmpeg bundled, (2) system PATH, (3) common install locations.
- `convert_file()` applies changes in order: sample rate → channels → normalize → export with bit-depth codec flags.
- Conversion errors stored in `state._last_conversion_error`.
- In Move mode, original source deleted after successful conversion.

### BPM detection (`bpm.py`)

Energy-envelope autocorrelation — no `numpy`/`librosa`. Delegates ffmpeg discovery to `conversion._find_ffmpeg_path()`.
- Cache: `~/.sampson/bpm_cache.json` (keyed by path + mtime)
- API: `detect_bpm(path, force=False)`, `get_cached_bpm()`, `set_cached_bpm()`, `flush_cache()`
- Manual override: double-click BPM cell in Deck B

### Key detection (`key.py`)

Pitch-period autocorrelation. Mirrors BPM architecture exactly.
- Cache: `~/.sampson/key_cache.json`
- API: `detect_key(path, force=False)`, `get_cached_key()`, `set_cached_key()`, `flush_cache()`

### Hardware profiles (`constants.py`)

Add a new device by inserting one entry into `PROFILES` dict — no other files need changing. Each entry has `path_limit` (int or None) and `conversion` (dict or None for auto-conversion preset).

### Deck B live filter

`preview_filter` state key drives the filter bar. Supports plain text and structured tokens: `BPM:120`, `BPM:100-130`, `BPM:12*`, `Note:C`, `MinLength:30`, `MaxLength:90`. Tokens are combinable with free text. When a filter is active, all matches shown (no row cap). Unfiltered display capped at `MAX_PREVIEW_ROWS` (500) in `constants.py`.

### Rename / output logic

`_compute_output()` in `operations.py` is the single deterministic function for computing final filename + subfolder — called by both preview display and actual execution. Controlled by: `modify_names`, `custom_prefix`, `struct_mode` (`flat`/`mirror`/`parent`), `profile` (path limit), `bpm_append`, `key_append`.

## Quick reference

| Task | Where |
|------|-------|
| Add hardware profile | `constants.py` → `PROFILES` |
| Change theme colors | `ui/style.css` → `:root` (dark) or `body.light-mode` (light) |
| Update version label | `ui/index.html` → `.version` span + `app.js` log line |
| Modify layout | `ui/index.html` + `ui/style.css` |
| Add JS↔Python API endpoint | `api.py` → `SampsonAPI` class + `ui/app.js` |
| Change file operations | `operations.py` → `run_tool()`, `_run_worker()` |
| Audio conversion logic | `conversion.py` → `convert_file()` |
| Adjust preview row limit | `constants.py` → `MAX_PREVIEW_ROWS` |
| Add output structure mode | `operations._compute_output()` + `ui/index.html` + `ui/app.js` |
| BPM detection algorithm | `bpm._detect_bpm_algorithm()` |
| Key detection algorithm | `key._detect_key_algorithm()` |
| macOS code signing | `build_macos.sh` |

## Known limitations

- Unfiltered preview capped at `MAX_PREVIEW_ROWS` (500); filter bar bypasses this cap.
- Destination collisions not handled — existing files are overwritten silently.
- FFmpeg must be available (bundled in PyInstaller builds; installed separately for dev runs using conversion).
- Deck B amber accent bar will not track if the user manually resizes the log panel (structural CSS constraint — the bar height is driven by the flex container, not a calculated offset).
