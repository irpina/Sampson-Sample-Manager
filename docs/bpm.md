# bpm.py — BPM Detection + Cache

Energy-envelope autocorrelation BPM detection with persistent cache. No numpy or librosa required.

## Imports
- **Imports:** `conversion` (`_find_ffmpeg_path`, pydub lazy), `json`, `math`, `pathlib`
- **Imported by:** `preview`, `operations`

## Public API

| Function | Description |
|----------|-------------|
| `detect_bpm(path, force=False)` | Detect BPM; returns cached value unless `force=True` or cache miss |
| `get_cached_bpm(path)` | Return cached BPM or `None`; validates file mtime |
| `set_cached_bpm(path, bpm_val)` | Set manual BPM override in cache |
| `flush_cache()` | Write cache to `~/.sampson/bpm_cache.json` |
| `get_log_messages()` | Fetch and clear pending log messages |

## Cache

- **Location:** `~/.sampson/bpm_cache.json`
- **Key:** absolute file path
- **Value:** `{mtime: float, bpm: float}`
- **Invalidation:** mtime mismatch → re-detect
- **Written:** lazily — call `flush_cache()` to persist (operations worker does this once per run)

## Algorithm

1. Load audio via pydub (mono, first 60s)
2. Compute RMS energy envelope (10ms hop)
3. Normalized autocorrelation of envelope
4. Find peaks in 60–200 BPM range
5. Generate candidates with octave variants (half/double tempo, penalized)
6. Group candidates within 5% tolerance; score each group
7. Prefer 80–180 BPM range (1.2× score bonus)
8. Return highest-scoring BPM (clamped to 60–200)

## Critical Rules

- BPM clamped to 60–200 on return; manual override via `set_cached_bpm()` accepts 30–300
- `force=True` bypasses cache and re-detects from audio
- FFmpeg is required (delegated to `conversion._find_ffmpeg_path()`)
- On Windows: pydub subprocess patched with `CREATE_NO_WINDOW` flag to hide console
- Low-energy or silent files may return `None`
- Logs prefixed with `[BPM]`; retrieve with `get_log_messages()` after detection
- Cache stored in user home dir — available across runs, shared between preview and operations
