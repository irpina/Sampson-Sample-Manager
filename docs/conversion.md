# conversion.py — Audio Conversion Pipeline

Wraps pydub + ffmpeg for format conversion. Handles static-ffmpeg bundling, platform-specific binary discovery, and conversion parameter parsing.

## Imports
- **Imports:** `state`, `os`, `shutil`, `subprocess`, `pathlib`, `sys`, `pydub` (lazy)
- **Imported by:** `api`, `bpm`, `key`, `preview`, `operations`

## Key Functions

| Function | Description |
|----------|-------------|
| `check_ffmpeg()` | Return `True` if ffmpeg is available |
| `get_ffmpeg_version()` | Return ffmpeg version string or `None` |
| `get_audio_info(path)` | Extract metadata dict (format, sample_rate, bit_depth, channels, duration) |
| `convert_file(src, dst, output_format, sample_rate, bit_depth, channels, normalize)` | Convert audio; returns `bool` (False = error stored in `state._last_conversion_error`) |
| `get_target_extension(output_format)` | `"wav"` → `".wav"`, `"aiff"` → `".aif"` |
| `parse_sample_rate(value)` | `"keep"` → `None`; `"44100"` → `44100` |
| `parse_bit_depth(value)` | `"keep"` → `None`; `"16"` → `16` |
| `parse_channels(value)` | `"keep"` → `None`; `"mono"` → `1`; `"stereo"` → `2` |

## FFmpeg Discovery Order

1. Static-ffmpeg bundled binaries (PyInstaller `_MEIPASS` bundle path)
2. Static-ffmpeg package (`static_ffmpeg` pip package)
3. System PATH (`shutil.which("ffmpeg")`)
4. Common install locations (Windows: winget paths, Program Files)

The first found path is used. `_find_ffmpeg_path()` is called lazily at first audio load.

## Conversion Flow

```python
convert_file(src, dst, output_format="wav", sample_rate=None, bit_depth=None, channels=None, normalize=False)
```

1. Load via `pydub.AudioSegment.from_file(src, format=ext)`
2. If `sample_rate`: `.set_frame_rate(sample_rate)`
3. If `channels`: `.set_channels(channels)`
4. If `normalize`: `.normalize()` + `.apply_gain(-1.0)` (prevent clipping)
5. Export with codec parameters:
   - WAV: `pcm_s16le` / `pcm_s24le` / `pcm_s32le`
   - AIFF: `pcm_s16be` / `pcm_s24be` / `pcm_s32be`

## Critical Rules

- **Error handling:** conversion failure stores first 200 chars of error in `state._last_conversion_error`; caller checks return value
- **`"aif"` extension** is normalized to `"aiff"` format string for ffmpeg
- **PATH mutation:** ffmpeg directory is prepended to `os.environ["PATH"]` so pydub subprocess finds the binary
- **pydub lazy-loaded** via `_get_pydub()` — avoids startup overhead; do NOT import pydub at module level
- **Windows console:** `CREATE_NO_WINDOW` flag (0x08000000) used for all subprocesses to suppress flash
- **Static-ffmpeg:** only available inside PyInstaller bundles; falls back gracefully in dev
- `_find_ffmpeg_path()` is also called by `bpm.py` and `key.py` — single discovery point for all modules

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
