# AGENTS.md — SAMPSON Project Guide

> Guidance for AI agents working on the SAMPSON codebase.
> SAMPSON is a Universal Audio Sample Manager — a cross-platform desktop app for organizing audio sample libraries for hardware samplers.

---

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

No test suite. Testing is manual — run the app and exercise the feature.

---

## Project Overview

SAMPSON uses **PyWebView**: Python backend + HTML/CSS/JS frontend in a single desktop window.

- **Deck A** — file browser (navigate folders, select which to include)
- **Center panel** — options (rename mode, hardware profile, conversion, BPM/key detection)
- **Deck B** — rename preview, filter/sort, audio playback

**Supported audio:** Input: `.wav .aiff .aif .flac .mp3 .ogg` — Output: `.wav .aif`

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ |
| UI framework | PyWebView 4.0+ (`http_server=False`) |
| Frontend | HTML5 + CSS3 + Vanilla JS (SPA in `ui/`) |
| Audio playback | pygame-ce (Win/Linux), NSSound (macOS) |
| Audio conversion | pydub + static-ffmpeg |
| BPM/Key detection | Custom autocorrelation (no numpy/librosa) |
| Packaging | PyInstaller |

---

## Per-Module Documentation

Each module has a focused reference in `docs/`. Load only what you need:

| Working on… | Read |
|-------------|------|
| State / data flow | `docs/state.md` |
| JS↔Python API bridge | `docs/api.md` |
| Hardware profiles, audio formats | `docs/constants.md` |
| Deck A file browser | `docs/browser.md` |
| Deck B preview, filter, sort | `docs/preview.md` |
| File copy/move/convert worker | `docs/operations.md` |
| BPM detection + cache | `docs/bpm.md` |
| Key detection + cache | `docs/key.md` |
| Audio format conversion | `docs/conversion.md` |
| Audio playback transport | `docs/playback.md` |
| HTML/CSS/JS frontend | `docs/ui.md` |

---

## Module Dependency Order (no circular imports)

```
constants.py   ← no imports
state.py       ← stdlib only
settings.py    ← stdlib only
conversion.py  → state
bpm.py         → conversion
key.py         → conversion
browser.py     → state, constants, preview
preview.py     → state, constants, bpm, key, operations, conversion
playback.py    → state
operations.py  → state, constants, bpm, key, conversion
api.py         → state, constants, browser, preview, playback, operations, conversion
main.py        → state, api
```

---

## Project Structure

```
sampson/
├── main.py              # PyWebView entry point
├── api.py               # SampsonAPI — JS↔Python bridge
├── state.py             # Central mutable state + JS sync
├── constants.py         # AUDIO_EXTS, PROFILES, MAX_PREVIEW_ROWS
├── browser.py           # Deck A navigation logic
├── preview.py           # Deck B scan, rename preview, filter, sort
├── operations.py        # File copy/move/convert worker thread
├── bpm.py               # BPM detection + cache
├── key.py               # Key detection + cache
├── conversion.py        # Audio conversion pipeline (pydub + ffmpeg)
├── playback.py          # Audio playback (NSSound / pygame-ce)
├── settings.py          # Persistent settings (~/.sampson/settings.json)
├── ui/
│   ├── index.html       # Single-page app shell
│   ├── app.js           # JS controller (554 lines)
│   ├── style.css        # CSS variables, dark/light themes
│   ├── sampsontransparentwhite.png  # Logo (dark mode)
│   └── sampsontransparent2.png      # Logo (light mode)
├── requirements.txt
├── SAMPSON.spec         # PyInstaller config (Windows/Linux)
├── build_macos.sh       # macOS build + sign + notarize
├── entitlements.plist   # macOS signing entitlements
├── CLAUDE.md            # Architecture reference (kept for Claude Code)
├── AGENTS.md            # This file
├── docs/                # Per-module AI context files
├── README.md
├── BUGS.md
└── TASKS.md
```

---

## Build

```bash
# Windows / Linux
pyinstaller SAMPSON.spec

# macOS (ad-hoc sign, local testing)
bash build_macos.sh

# macOS (Developer ID sign + notarize)
APPLE_CODESIGN_IDENTITY="Developer ID Application: Name (TEAMID)" \
APPLE_ID="you@example.com" \
APPLE_APP_PASSWORD="xxxx-xxxx-xxxx-xxxx" \
APPLE_TEAM_ID="XXXXXXXXXX" \
bash build_macos.sh
```

**macOS build hard rules** (violations silently break the build):
- Always sign in `/tmp`, never inside OneDrive (xattrs invalidate signatures)
- Sign components individually — never `codesign --deep`
- Every `codesign` call needs `--options runtime --timestamp`
- Never delete `python3.X/lib-dynload/` from bundle
- Use `ditto` not `cp -r` for `.app` copies

---

## Key Conventions

- **Version string:** `ui/index.html` `.version` span + `app.js` ready log line
- **Add hardware profile:** `constants.py` → `PROFILES` dict **AND** `ui/index.html` → `#target-device` `<select>`
- **Add audio format:** `constants.py` → `AUDIO_EXTS` set
- **Logo files:** Must live in `ui/` (same dir as `index.html`) — WKWebView `file://` sandbox blocks `../`
- **State sync:** Call `state.push_keys()` after mutations to reflect changes in JS
- **Thread safety:** Long operations run in daemon threads; use `state.set()` (thread-safe) for updates

---

## Known Limitations

- Unfiltered preview capped at 500 rows (`MAX_PREVIEW_ROWS`); filter bypasses cap
- Destination collisions not handled — files overwritten silently
- FFmpeg required for conversion (bundled in dist builds)
- Deck B amber accent bar won't track manual log panel resize (CSS flex constraint)
- Files shorter than 3 seconds are skipped for BPM/key detection (too short for reliable analysis)

---
*SAMPSON is licensed under the [GNU General Public License v3.0](LICENSE).*
