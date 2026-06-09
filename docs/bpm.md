# bpm.py — BPM Detection + Cache

Onset-novelty autocorrelation with comb-filter octave resolution and a
perceptual tempo prior. Persistent cache. No numpy or librosa required.

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

1. Load audio via pydub (mono, first 60s), downsample to 11025 Hz
2. Build an **onset-novelty function**: half-wave-rectified flux of log
   short-time energy (20ms window, 10ms hop), then subtract its mean so the
   autocorrelation isn't dominated by DC
3. Normalized autocorrelation of the onset function (out to ~3 beat periods
   of the slowest tempo, so the comb can use the 2nd/3rd harmonics)
4. **Comb-filter score** for each candidate beat period: sum the
   autocorrelation at the period and its 2×/3×/4× multiples (local-max around
   each, since real beat periods are fractional), weighted by a gentle
   log-Gaussian **perceptual prior** (centre 120 BPM). This reinforces the
   fundamental and suppresses spurious half/double tempos.
5. Parabolic interpolation around the winning lag for sub-frame precision
6. Return BPM (clamped to 40–220)

## Critical Rules

- BPM clamped to 40–220 on return; manual override via `set_cached_bpm()` accepts 30–300
- The comb naturally blocks tempo *doubling* (the half-beat lag carries no
  onset); only *halving* is governed by the prior, so very fast tempos
  (~165+) may be reported at half-time, and sparse/sustained loops can
  occasionally land on a subdivision
- `force=True` bypasses cache and re-detects from audio
- FFmpeg is required (delegated to `conversion._find_ffmpeg_path()`)
- On Windows: pydub subprocess patched with `CREATE_NO_WINDOW` flag to hide console
- Low-energy or silent files may return `None`
- Logs prefixed with `[BPM]`; retrieve with `get_log_messages()` after detection
- Cache stored in user home dir — available across runs, shared between preview and operations

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
