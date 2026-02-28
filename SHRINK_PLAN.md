# SHRINK_PLAN.md — SAMPSON macOS Build Size Reduction

Target: reduce `dist/SAMPSON.app` from **158MB → ~60MB**.

All work is on the macOS build only (`SAMPSON_mac.spec`, `build_macos.sh`, `playback.py`,
`conversion.py`). Windows/Linux builds are unaffected.

---

## Measured baseline (arm64, v0.3.6)

| Component | Actual size | Notes |
|---|---|---|
| `static_ffmpeg/ffmpeg` | 47 MB | bundled in Frameworks/ |
| `static_ffmpeg/ffprobe` | 47 MB | bundled in Frameworks/ |
| `pygame` dylibs | 16 MB | 31 dylibs in Frameworks/pygame/__dot__dylibs/ |
| `pygame` Resources | 11 MB | includes 7.6 MB docs, 2.1 MB examples, 464 KB tests |
| Tcl/Tk data | 4 MB | encodings + msgs + optional packages |
| libcrypto/libssl | 5 MB | from ssl module |
| libsqlite3 | 1.2 MB | unused |
| Everything else | ~27 MB | Python stdlib, customtkinter, app code |
| **Total** | **158 MB** | |

---

## Phase 1 — Spec-only changes (no Python edits)

**Estimated savings: ~13 MB**
**Risk: very low** — pure build configuration changes.

### 1a. Strip debug symbols

In `SAMPSON_mac.spec`, change both `strip=False` to `strip=True`:

```python
# Line 49 — in EXE()
strip=True,

# Line 64 — in COLLECT()
strip=True,
```

### 1b. Exclude unused stdlib modules

Add to the `excludes=[]` list in `Analysis()` (line 32):

```python
excludes=[
    'sqlite3',    # 1.2 MB dylib + py module — SAMPSON uses no database
    'readline',   # REPL only, not needed in bundled app
    'grp',        # POSIX group info — not used
    'resource',   # POSIX resource limits — not used
    'syslog',     # macOS syslog — not used
    '_multibytecodec',
    'mmap',
],
```

### 1c. Exclude pygame docs, tests, and examples from data collection

The current spec line 12:
```python
pygame_datas = collect_data_files('pygame')
```

Replace with a filtered version that skips the bundled documentation, test fixtures,
and example assets (7.6 MB docs + 2.1 MB examples + 464 KB tests = ~10 MB saved):

```python
from PyInstaller.utils.hooks import collect_data_files

pygame_datas = [
    (src, dst) for src, dst in collect_data_files('pygame')
    if not any(skip in src for skip in [
        '/docs/', '/tests/', '/examples/',
    ])
]
```

### Verify Phase 1

After rebuilding, inspect the bundle:

```bash
bash build_macos.sh
du -sh dist/SAMPSON.app
```

Expected result: ~145 MB.

---

## Phase 2 — Drop ffprobe from the bundle

**Estimated savings: ~47 MB**
**Risk: low** — requires one small code change in `conversion.py` + one spec change.

`ffprobe` (47 MB) is bundled alongside `ffmpeg`. pydub calls ffprobe to auto-detect
the source audio format when `AudioSegment.from_file(path)` is called with no `format=`
argument. If we pass the format explicitly, ffprobe is never invoked and can be removed.

### 2a. Patch `conversion.py` — pass format explicitly to `from_file()`

In `convert_file()`, find the line (currently around line 253):

```python
audio = AudioSegment.from_file(str(src))
```

Replace with:

```python
# Derive format from extension so pydub passes -f to ffmpeg directly,
# making ffprobe unnecessary in the bundle.
_ext = src.suffix.lower().lstrip('.')
_fmt = 'aiff' if _ext in ('aif', 'aiff') else _ext  # ffmpeg uses 'aiff' not 'aif'
audio = AudioSegment.from_file(str(src), format=_fmt)
```

Also remove or make inert the ffprobe path assignment block (lines ~247-249)
since we no longer need it:

```python
# ffprobe is no longer bundled — remove these lines:
# ffprobe_path = _find_ffprobe_path(ffmpeg_path)
# if ffprobe_path:
#     pydub.utils.ffprobe = ffprobe_path
```

You can leave `_find_ffprobe_path()` defined (it's harmless) or delete it entirely.

### 2b. Filter ffprobe out of the spec data collection

In `SAMPSON_mac.spec`, change line 13:

```python
ffmpeg_datas = collect_data_files('static_ffmpeg')
```

to:

```python
ffmpeg_datas = [
    (src, dst) for src, dst in collect_data_files('static_ffmpeg')
    if 'ffprobe' not in src
]
```

This prevents PyInstaller from copying the ffprobe binary into the bundle.

### Verify Phase 2

1. Rebuild: `bash build_macos.sh`
2. Confirm ffprobe is absent: `find dist/SAMPSON.app -name "ffprobe"` should return nothing.
3. Run the app and test audio conversion on WAV, AIFF, MP3, FLAC, OGG inputs.
4. Check bundle size: expected ~98 MB.

---

## Phase 3 — Replace pygame with NSSound for macOS playback

**Estimated savings: ~27 MB** (removes all 31 SDL dylibs + pygame Resources)
**Risk: medium** — replaces the entire `playback.py` implementation.
**Scope: macOS-only** — NSSound is macOS native. The Windows/Linux build still uses pygame.

`AppKit.NSSound` is already a bundled dependency (pyobjc is in requirements.txt;
`AppKit` is already imported in `dpi.py`). NSSound supports WAV, AIFF, MP3, FLAC,
and all other formats that macOS Core Audio handles natively — which covers every
format in `constants.AUDIO_EXTS`.

### 3a. Rewrite `playback.py`

Replace the entire file with the implementation below. The external API
(`play`, `stop`, `reset`, `next_file`, `prev_file`, `on_tree_select`, `on_arrow_key`)
must remain identical — no other file needs changing.

```python
"""macOS playback via AppKit.NSSound (replaces pygame.mixer)."""

import sys
from pathlib import Path

import state

# ── Backend selection ────────────────────────────────────────────────────────
# NSSound on macOS (zero extra deps); pygame fallback for Windows/Linux.
if sys.platform == "darwin":
    from AppKit import NSSound as _NSSound
    _USE_NSSOUND = True
else:
    import pygame.mixer as _mixer
    _mixer.init()
    _USE_NSSOUND = False

_current_index = -1   # index into preview tree item list
_ns_sound      = None # active NSSound instance (macOS only)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _tree_items():
    return list(state.preview_tree.get_children())


def _load_index(idx):
    global _current_index
    items = _tree_items()
    if not items or not (0 <= idx < len(items)):
        return
    _current_index = idx
    iid = items[idx]
    state.preview_tree.selection_set(iid)
    state.preview_tree.see(iid)
    src = state.preview_tree.set(iid, "srcpath")
    state._playback_file = Path(src) if src else None
    _update_transport_state()


def _is_busy() -> bool:
    """Return True if audio is currently playing."""
    if _USE_NSSOUND:
        return _ns_sound is not None and _ns_sound.isPlaying()
    else:
        return _mixer.music.get_busy()


# ── Public transport API ─────────────────────────────────────────────────────

def play():
    """Play the currently selected file; if already playing, stop (toggle)."""
    global _ns_sound
    if _is_busy():
        stop()
        return
    if not state._playback_file or not state._playback_file.is_file():
        return
    try:
        if _USE_NSSOUND:
            _ns_sound = _NSSound.alloc().initWithContentsOfFile_byReference_(
                str(state._playback_file), True)
            if _ns_sound:
                _ns_sound.play()
                state._is_playing = True
                _update_transport_state()
                state.root.after(200, _poll_playback)
        else:
            _mixer.music.load(str(state._playback_file))
            _mixer.music.play()
            state._is_playing = True
            _update_transport_state()
            state.root.after(200, _poll_playback)
    except Exception:
        state._is_playing = False


def stop():
    """Stop playback and update transport state."""
    global _ns_sound
    if _USE_NSSOUND:
        if _ns_sound and _ns_sound.isPlaying():
            _ns_sound.stop()
        _ns_sound = None
    else:
        _mixer.music.stop()
    state._is_playing = False
    _update_transport_state()


def reset():
    """Stop playback and reset current index (call on source navigate)."""
    global _current_index
    stop()
    _current_index = -1


def next_file():
    stop()
    items = _tree_items()
    if not items:
        return
    idx = min(_current_index + 1, len(items) - 1)
    _load_index(idx)
    play()


def prev_file():
    stop()
    idx = max(_current_index - 1, 0)
    _load_index(idx)
    play()


def on_tree_select(event):
    state.preview_tree.focus_set()
    iid = state.preview_tree.identify_row(event.y)
    if not iid:
        return
    items = _tree_items()
    if iid in items:
        stop()
        _load_index(items.index(iid))
        play()


def on_arrow_key(event):
    state.preview_tree.focus_set()
    iid = state.preview_tree.focus()
    if not iid:
        return
    items = _tree_items()
    if iid in items:
        stop()
        _load_index(items.index(iid))
        play()


def _poll_playback():
    if _is_busy():
        state.root.after(200, _poll_playback)
    else:
        state._is_playing = False
        _update_transport_state()


def _update_transport_state():
    if state.transport_play_btn:
        icon = "■" if state._is_playing else "▶"
        state.transport_play_btn.configure(text=icon)
    has_file = state._playback_file is not None
    items    = _tree_items()
    can_prev = has_file and _current_index > 0
    can_next = has_file and _current_index < len(items) - 1
    for btn, enabled in [
        (state.transport_prev_btn, can_prev),
        (state.transport_next_btn, can_next),
    ]:
        if btn:
            btn.configure(state="normal" if enabled else "disabled")
```

### 3b. Update `SAMPSON_mac.spec` — remove pygame from hiddenimports and datas

Remove `'pygame'` from `hiddenimports`:

```python
hiddenimports=[
    # 'pygame',   ← remove; no longer used on macOS
    'pydub',
    'customtkinter',
    'AppKit',
    'audioop',
],
```

Change the data collection at the top of the spec to skip pygame entirely:

```python
# pygame_datas = collect_data_files('pygame')   ← remove this line
ffmpeg_datas = [...]   # already filtered in Phase 2
logo_file = ('sampsontransparent2.png', '.')
all_datas = [logo_file] + ffmpeg_datas   # no pygame_datas
```

### 3c. Keep `pygame-ce` in `requirements.txt`

`requirements.txt` is shared across platforms. Leave `pygame-ce` in it. The macOS spec
simply stops collecting and importing it; on Windows/Linux the `playback.py` fallback
branch will still use `_mixer`.

### Verify Phase 3

1. Rebuild: `bash build_macos.sh`
2. Confirm no pygame dylibs: `find dist/SAMPSON.app -name "libSDL2*"` → no results.
3. Test all transport controls: play, stop (toggle), prev, next, arrow keys, click-to-play.
4. Test with each format in `AUDIO_EXTS`: `.wav`, `.aiff`, `.aif`, `.flac`, `.mp3`, `.ogg`.
5. Test that stopping a track and navigating to a new directory stops playback.
6. Check bundle size: expected ~60–65 MB.

---

## Phase 4 — Optional Tcl/Tk data cleanup (post-build script)

**Estimated savings: ~2-3 MB**
**Risk: very low**

Add a cleanup step to `build_macos.sh` after `pyinstaller` completes:

```bash
#!/usr/bin/env bash
set -e
echo "Building SAMPSON.app..."

python -c "import static_ffmpeg; static_ffmpeg.add_paths()"
pyinstaller SAMPSON_mac.spec --clean

echo "Cleaning unused Tcl/Tk data files..."
TCL_DATA="dist/SAMPSON.app/Contents/Resources/_tcl_data"

# Remove all language message catalogs (app is English-only)
rm -rf "$TCL_DATA/msgs"

# Remove all character encodings except the ones tkinter actually needs
KEEP="ascii.enc utf-8.enc iso8859-1.enc cp1252.enc"
for f in "$TCL_DATA/encoding"/*.enc; do
    base=$(basename "$f")
    if ! echo "$KEEP" | grep -qw "$base"; then
        rm "$f"
    fi
done

# Remove optional Tcl packages (cookiejar, http) — SAMPSON doesn't use them
rm -rf "$TCL_DATA/cookiejar0.2"

echo "Done: dist/SAMPSON.app ($(du -sh dist/SAMPSON.app | cut -f1))"
```

> **Note:** Test the app after this step. If any Tcl encoding error appears at startup,
> add the missing `.enc` file back to `KEEP`.

---

## Summary of changes by file

| File | Change |
|---|---|
| `SAMPSON_mac.spec` | `strip=True`; add `excludes`; filter pygame datas; filter ffprobe from ffmpeg datas; remove pygame hiddenimport |
| `conversion.py` | Pass `format=` explicitly to `AudioSegment.from_file()`; remove ffprobe path wiring |
| `playback.py` | Full rewrite using NSSound on macOS, pygame fallback on other platforms |
| `build_macos.sh` | Add post-build Tcl/Tk cleanup step |
| `requirements.txt` | No changes needed |

---

## Expected final size

| Phase | After | Saved |
|---|---|---|
| Baseline | 158 MB | — |
| Phase 1 (spec changes) | ~145 MB | ~13 MB |
| Phase 2 (drop ffprobe) | ~98 MB | ~47 MB |
| Phase 3 (drop pygame) | ~63 MB | ~35 MB |
| Phase 4 (Tcl cleanup) | ~60 MB | ~3 MB |

Do Phases 1–3 in order. Each phase is independently testable. Commit after each
phase passes the verification checklist.
