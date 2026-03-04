# Plan: Musical Key Detection (Root Note Only)

## Context

Add key detection to SAMPSON using only existing dependencies (pydub + stdlib). Detects the root pitch class only ("C", "F#", "Bb") — not major/minor — which is simpler, more accurate, and still highly useful for sample library organization.

## Feasibility

Pure Python chroma via **pitch-period autocorrelation → argmax**. Same foundation as BPM: pydub `get_array_of_samples()` + stdlib `math` only. No FFT, no numpy, no new packages.

| | Pure Python chroma (root only) | + librosa (full key) |
|---|---|---|
| New deps | None | ~150 MB |
| Accuracy | ~78–85% | ~88–92% |
| Speed | ~3–8 s / file | ~1–2 s / file |
| Output | `"C"`, `"F#"` | `"Cmin"`, `"Gmaj"` |

---

## Implementation Plan

Mirrors BPM exactly: new `key.py` + state vars + UI section + preview column + operations integration.

### 1. New file: `key.py`

Public API (same pattern as `bpm.py`):
- `detect_key(path: Path) -> str | None` — returns e.g. `"C"`, `"F#"`, `"Bb"`
- `get_cached_key(path: Path) -> str | None`
- `set_cached_key(path: Path, key: str)`
- `flush_cache()`
- `get_log_messages() -> list[str]`

Algorithm:
1. Load audio via pydub (delegates ffmpeg to `conversion._find_ffmpeg_path()`)
2. Convert to mono, downsample to 8000 Hz
3. `audio.get_array_of_samples()` — analyze first 30 s
4. For each of 12 pitch classes, compute autocorrelation at lags for that pitch (C4=261.6 Hz…) across octaves 2–5
5. Sum lag energies → 12-bin chroma vector, normalize
6. `argmax` → return note label (`NOTE_NAMES[argmax]`, e.g. `["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]`)
7. Cache at `~/.sampson/key_cache.json` (path+mtime key, same as BPM cache)

### 2. `state.py`

```python
key_enabled_var = None   # tk.BooleanVar — master toggle
key_append_var  = None   # tk.BooleanVar — append key label to output filename
```

### 3. `preview.py`

- `_preview_rows` tuple becomes `(filename, renamed, subfolder, bpm_display, key_display, srcpath)` — key at index 4, srcpath moves to index 5
- `_populate_preview()`: call `key_module.get_cached_key(f)` — cache lookup only
- Column display: `"C"` / `"???"` / `""` based on enabled state
- Add `_on_key_double_click` for manual override (same pattern as `_on_bpm_double_click`)
- Show/hide `"key"` column width based on `key_enabled_var`

### 4. `builders.py`

- Add `"key"` column to `preview_tree` columns tuple
- Add Key section (inside or alongside "BPM analysis" collapsible section, key `"key"`)
- Checkbox: `"Detect musical key"` → `state.key_enabled_var`
- Sub-option: `"Append key to filename"` → `state.key_append_var`
- Save/restore across theme toggle; trace → `preview.refresh_preview()`
- Version bump: `"v0.5.10"`

### 5. `operations.py`

In `_run_worker()`:
```python
key_val = key_module.detect_key(f) if key_enabled else None
```
In `_compute_output()`: append `_{key}` to stem when `append_key` is True (e.g. `Kicks_kick_01_F#.wav`).

### 6. `CLAUDE.md`

Add row to Quick reference: `| Key detection algorithm | key.py → _detect_key_algorithm() |`

---

## Files to modify

| File | Change |
|------|--------|
| `key.py` | **New file** |
| `state.py` | +2 vars |
| `preview.py` | Add `"key"` column, cache lookup, double-click edit, update `_preview_rows` tuple |
| `builders.py` | Add key UI section, column, save/restore, version bump |
| `operations.py` | Call `detect_key()` in worker, pass to `_compute_output()` |
| `CLAUDE.md` | Update quick reference |

---

## Verification

1. `python main.py` — Key section appears in center panel
2. Browse folder → key column shows `"???"` for each file
3. Run operation → key column populates (`"C"`, `"F#"`, etc.)
4. "Append key to filename" → output filenames include key suffix
5. Double-click key cell → inline editor, manual override persists
6. Re-open app → key cache loads, no re-detection
