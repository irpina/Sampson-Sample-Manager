# playback.py — Audio Playback Transport

Cross-platform audio playback with transport controls (play/stop/prev/next). Uses NSSound on macOS, pygame-ce on Windows/Linux.

## Imports
- **Imports:** `state`, `sys`, `threading`, `pathlib`; `AppKit.NSSound` (macOS, lazy); `pygame.mixer` (Win/Linux, eager)
- **Imported by:** `api`

## Key Functions

| Function | Description |
|----------|-------------|
| `play_file(srcpath)` | Start playback by file path; returns status dict |
| `play()` | Toggle: play current index if stopped, stop if playing |
| `stop()` | Stop playback; update state |
| `reset()` | Stop and reset current index to -1 |
| `next_file()` | Stop → increment index → play |
| `prev_file()` | Stop → decrement index → play |
| `get_current_index()` | Return current playback index (-1 if none) |
| `set_current_index(idx)` | Set current index without playing |

## Platform Backends

### macOS — NSSound (AppKit)
- Lazy-imported to avoid AppKit/pywebview initialization race
- API: `NSSound.alloc().initWithContentsOfFile_byReference_(path, False)`
- Play: `.play()` / Stop: `.stop()` / Check: `.isPlaying()`

### Windows / Linux — pygame-ce
- Initialized eagerly at module load: `mixer.init(frequency=48000, size=-16, channels=2, buffer=512)`
- API: `mixer.music.load(path)` → `.play()` / `.stop()` / `.get_busy()`
- Wider format support: MP3, OGG, FLAC

## State Sync

| State Key | Description |
|-----------|-------------|
| `is_playing` | `bool` — current playback status |
| `playback_file` | `str` — path of currently playing file |

Both are updated via `state.set()` on every transport event.

## Critical Rules

- **Index -1** means no selection; `next_file()` from -1 starts at index 0
- **Navigation always stops first** — `next_file()` / `prev_file()` stop → load → play
- **Polling:** a 0.2s timer (`threading.Timer`) polls `_is_busy()` and updates `state["is_playing"]` when playback ends naturally
- **File validity** checked before load — invalid paths are skipped silently
- **pygame mixer settings are fixed** (48kHz, 16-bit, stereo) — do not change after init
- NSSound must be imported from `AppKit` (not a standalone package)
- Playlist comes from `state["preview_entries"]` — index corresponds to that list

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
