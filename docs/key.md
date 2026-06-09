# key.py — Musical Key Detection + Cache

Goertzel chroma + Krumhansl-Schmuckler key-profile correlation (root pitch
class only). Pure Python — no FFT/numpy. Mirrors bpm.py's cache architecture.

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

1. Load audio (mono, downsampled to 8kHz); skip the first 50ms attack and
   analyse up to ~10s; remove DC offset
2. Build a **chroma** vector: for every semitone C2..B5, compute the DFT
   magnitude at the *exact* note frequency with the **Goertzel algorithm**
   (no integer-lag rounding error), then fold octaves into 12 pitch classes
3. Normalize the chroma
4. Resolve the tonic via **Krumhansl-Schmuckler** correlation — rotate the 12
   major and 12 minor key profiles against the chroma and take the best
   (uses the tonal hierarchy, robust on melodic/polyphonic material)
5. **Confidence gates** — return `None` (atonal/percussive) unless the chroma
   peak is ≥ 2× a flat distribution AND the best key correlation is ≥ 0.5
6. Return the tonic pitch-class name

## Return Values

- `"C"`, `"C#"`, `"D"`, `"D#"`, `"E"`, `"F"`, `"F#"`, `"G"`, `"G#"`, `"A"`, `"A#"`, `"B"`
- `None` — atonal/low-confidence (percussion, noise, or silent)

## Critical Rules

- Detects **root pitch class only** — no major/minor distinction
- Audio downsampled to 8kHz before analysis (speed optimization)
- Requires at least 250ms of audio
- Confidence-gated: percussion and noise return `None` rather than a
  meaningless key (`KEY_DEBUG=1` env var prints the gate metrics)
- Enharmonic normalization in `set_cached_key()`: `Db→C#`, `Eb→D#`, `Gb→F#`, `Ab→G#`, `Bb→A#`
- FFmpeg required (delegated to `conversion._find_ffmpeg_path()`)
- Logs prefixed with `[KEY]`; retrieve with `get_log_messages()`
- Same cache pattern as bpm.py — call `flush_cache()` after bulk operations

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
