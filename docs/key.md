# key.py — Musical Key Detection + Cache

Pitch-period autocorrelation key detection (root pitch class only). Mirrors bpm.py architecture exactly.

## Imports
- **Imports:** `conversion` (`_find_ffmpeg_path`, pydub lazy), `json`, `math`, `pathlib`
- **Imported by:** `preview`, `operations`

## Public API

| Function | Description |
|----------|-------------|
| `detect_key(path, force=False)` | Detect root pitch class; returns cached unless `force=True` or miss |
| `get_cached_key(path)` | Return cached key or `None`; validates mtime |
| `set_cached_key(path, key_val)` | Set manual key override; normalizes enharmonic spellings |
| `flush_cache()` | Write cache to `~/.sampson/key_cache.json` |
| `get_log_messages()` | Fetch and clear pending log messages |

## Cache

- **Location:** `~/.sampson/key_cache.json`
- **Key:** absolute file path
- **Value:** `{mtime: float, key: str}`
- **Invalidation:** mtime mismatch

## Algorithm

1. Load audio (mono, downsampled to 8kHz, first 30s)
2. For each of 12 pitch classes (C, C#, D, ... B):
   - For each octave (2–5): convert frequency → lag in samples
   - Compute normalized autocorrelation at that lag
   - Weight by `1 / sqrt(freq)` (emphasize lower frequencies)
   - Sum into `chroma[pitch_class]`
3. Normalize chroma vector
4. If max chroma value < 0.1 → return `None` (likely percussion/noise)
5. Return pitch class name with highest chroma value

## Return Values

- `"C"`, `"C#"`, `"D"`, `"D#"`, `"E"`, `"F"`, `"F#"`, `"G"`, `"G#"`, `"A"`, `"A#"`, `"B"`
- `None` — low signal (percussion, noise, or silent)

## Critical Rules

- Detects **root pitch class only** — no major/minor distinction
- Audio downsampled to 8kHz before analysis (speed optimization)
- Requires at least 250ms of audio after downsampling
- Enharmonic normalization in `set_cached_key()`: `Db→C#`, `Eb→D#`, `Gb→F#`, `Ab→G#`, `Bb→A#`
- FFmpeg required (delegated to `conversion._find_ffmpeg_path()`)
- Logs prefixed with `[KEY]`; retrieve with `get_log_messages()`
- Same cache pattern as bpm.py — call `flush_cache()` after bulk operations

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
