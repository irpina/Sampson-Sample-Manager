# Plan: BPM Detection Feature

## Context

Add opt-in BPM detection to SAMPSON that runs during file operations (not preview scan), caches results in a JSON sidecar so repeated operations are fast, and optionally appends the detected BPM to the output filename (e.g. `Kicks_kick_01_120bpm.wav`) while respecting device path-limit rules.

The Deck B preview tree gains a **BPM column** that shows the cached value when known, or `???` when not yet scanned. The renamed filename column also reflects cache state: `Kicks_kick_01_120bpm.wav` if cached, `Kicks_kick_01_???bpm.wav` placeholder if not.

Chosen: **aubio + numpy** (~30MB bundle increase), **`_120bpm` suffix**, preview is **read-only cache lookup** (no detection).

---

## New File: `bpm.py`

No app-level imports — keeps the dependency graph clean. All aubio/numpy imports are lazy (inside `detect_bpm()` only).

**Public API:**
- `get_cached_bpm(path) -> float | None` — read-only cache lookup (used by preview)
- `detect_bpm(path) -> float | None` — checks cache first, then runs aubio (used by run worker)
- `flush_cache()` — writes cache to disk if dirty (called at end of run)

**Cache location:** `Path.home() / ".sampson" / "bpm_cache.json"`

**Cache structure:**
```json
{ "/abs/path/to/kick.wav": { "mtime": 1698765432.1, "bpm": 120.0 } }
```
Invalidation is mtime-based: if the file's mtime differs from the cached value, BPM is re-detected.

**Detection algorithm (aubio):**
```python
def detect_bpm(file_path: Path) -> float | None:
    cached = get_cached_bpm(file_path)
    if cached is not None:
        return cached
    try:
        from aubio import source, tempo
        from numpy import diff, median
        samplerate, hop_s = 44100, 512
        src = source(str(file_path), samplerate, hop_s)
        samplerate = src.samplerate
        o = tempo("default", 2048, hop_s, samplerate)
        beats = []
        while True:
            samples, read = src()
            if o(samples):
                beats.append(o.get_last_s())
            if read < hop_s:
                break
        if len(beats) > 1:
            bpm_val = float(median(60 / diff(beats)))
            cache_bpm(file_path, bpm_val)
            return bpm_val
    except Exception:
        pass
    return None
```

---

## Files to Modify

### 1. `state.py`
Add after the conversion block:
```python
bpm_enabled_var = None   # tk.BooleanVar — master toggle for BPM detection
bpm_append_var  = None   # tk.BooleanVar — append _120bpm to output filename
```

### 2. `operations.py`

**`_apply_path_limit()`** — add `protect_suffix=""` param so the BPM tag is never truncated away:
```python
def _apply_path_limit(new_name, dest_path_str, limit, protect_suffix=""):
    full = str(Path(dest_path_str) / new_name)
    if len(full) <= limit:
        return new_name
    p, ext = Path(new_name), Path(new_name).suffix
    avail = limit - len(str(Path(dest_path_str))) - 1 - len(ext) - len(protect_suffix)
    avail = max(1, avail)
    stem = p.stem
    if protect_suffix and stem.endswith(protect_suffix):
        stem = stem[:-len(protect_suffix)]
    return stem[:avail] + protect_suffix + ext
```

**`_compute_output()`** — add `bpm=None, append_bpm=False` (safe defaults mean `preview.py` call sites need no changes):
```python
def _compute_output(f, source_root, dest, no_rename, struct_mode, path_limit,
                    bpm=None, append_bpm=False):
    # ... existing filename + subfolder logic unchanged ...

    bpm_suffix = f"_{int(round(bpm))}bpm" if (bpm is not None and append_bpm) else ""
    p = Path(new_name)
    new_name = p.stem + bpm_suffix + p.suffix
    if path_limit is not None:
        new_name = _apply_path_limit(new_name, effective_dest, path_limit,
                                     protect_suffix=bpm_suffix)
    return new_name, rel_sub
```

**`run_tool()`** — read new state vars, pass to worker:
```python
bpm_enabled = state.bpm_enabled_var.get() if state.bpm_enabled_var else False
bpm_append  = state.bpm_append_var.get()  if state.bpm_append_var  else False
# add bpm_enabled, bpm_append to threading.Thread args
```

**`_run_worker()`** — add `bpm_enabled=False, bpm_append=False`. In per-file loop:
```python
import bpm as bpm_module
bpm_val = bpm_module.detect_bpm(f) if bpm_enabled else None
new_name, rel_sub = _compute_output(..., bpm=bpm_val, append_bpm=bpm_append)
```
After `"Done."` log: `if bpm_enabled: bpm_module.flush_cache()`

### 3. `preview.py`

**New import:** `import bpm as bpm_module`

**BPM column** added to `_populate_preview()`. The column is shown at `_px(60)` wide when `bpm_enabled_var` is True, `width=0` otherwise (same pattern as Subfolder column).

**Per-file logic** inside the population loop:
```python
bpm_enabled = state.bpm_enabled_var and state.bpm_enabled_var.get()
bpm_append  = state.bpm_append_var  and state.bpm_append_var.get()

bpm_val     = bpm_module.get_cached_bpm(f) if bpm_enabled else None
bpm_display = str(int(round(bpm_val))) if bpm_val is not None else ("???" if bpm_enabled else "")

if bpm_append and bpm_enabled:
    if bpm_val is not None:
        new_name, rel_sub = _compute_output(f, ..., bpm=bpm_val, append_bpm=True)
    else:
        new_name, rel_sub = _compute_output(f, ...)   # base name
        p = Path(new_name)
        new_name = p.stem + "_???bpm" + p.suffix       # visual placeholder only
else:
    new_name, rel_sub = _compute_output(f, ...)

state.preview_tree.insert("", "end",
    values=(f.name, new_name, rel_sub, bpm_display, str(f)))
#                                        ^^^^^^^^^^^  new 4th column; srcpath moves to 5th
```

The `"srcpath"` column used by `playback.py` moves from index 4 to 5 — verify `state.preview_tree.set(iid, "srcpath")` still works (column name lookup by string id is unaffected by position).

### 4. `builders.py`

**`build_deck_b()`** — add `"bpm"` column to `state.preview_tree` definition (hidden by default, `width=0`). Column header: `"BPM"`.

**`build_center()`** — add BPM section after conversion (same separator → label → checkbox → bordered options container pattern):
```
────────── separator ──────────
BPM Analysis           [muted section label]
[✓] Detect BPM         [checkbox → bpm_enabled_var]
┌─────────────────────────────┐
│ [✓] Append BPM to filename  │  ← disabled when master toggle is off
└─────────────────────────────┘
```

Enable/disable wiring (same as `_toggle_conv_opts` pattern):
```python
def _toggle_bpm_opts(*_):
    s = "normal" if state.bpm_enabled_var.get() else "disabled"
    append_cb.configure(state=s)
state.bpm_enabled_var.trace_add("write", _toggle_bpm_opts)
_toggle_bpm_opts()
```

**`build_app()`** — register preview-refresh traces:
```python
state.bpm_enabled_var.trace_add("write", lambda *_: preview.refresh_preview())
state.bpm_append_var.trace_add("write",  lambda *_: preview.refresh_preview())
```

**`toggle_theme()`** — save/restore both vars alongside existing save block:
```python
saved_bpm_enabled = state.bpm_enabled_var.get()
saved_bpm_append  = state.bpm_append_var.get()
# ... after build_app() ...
if state.bpm_enabled_var: state.bpm_enabled_var.set(saved_bpm_enabled)
if state.bpm_append_var:  state.bpm_append_var.set(saved_bpm_append)
```

**`build_status_bar()`** — bump version string.

### 5. `requirements.txt`
```
aubio>=0.4.9
numpy>=1.20.0
```

### 6. `SAMPSON_mac.spec`
```python
# hiddenimports — add:
'aubio',
'numpy',

# all_datas — add numpy data files:
numpy_datas = collect_data_files('numpy')
all_datas   = [logo_file] + ffmpeg_datas + numpy_datas
```

### 7. `CLAUDE.md`
Update module dependency order:
```
bpm.py         ← no app imports  (NEW)
operations.py  → state, theme, constants, log_panel, conversion, bpm
preview.py     → state, theme, constants, dpi, operations, bpm
```

---

## Updated Module Dependency Order

```
constants.py   ← no imports
state.py       ← no app imports
bpm.py         ← no app imports        ← NEW
dpi.py         → state
theme.py       → state, dpi
log_panel.py   → state, theme
conversion.py  → state
operations.py  → state, theme, constants, log_panel, conversion, bpm
browser.py     → state, theme, constants, preview
preview.py     → state, theme, constants, dpi, operations, bpm   ← updated
playback.py    → state
builders.py    → state, theme, dpi, browser, preview, playback, log_panel, operations
main.py        → state, theme, dpi, builders
```

---

## Key Invariants

- **Path limit always wins** — BPM suffix is protected from truncation; the overall path still fits within the device limit.
- **Lazy aubio import** — only loaded inside `detect_bpm()`, so startup is unaffected when BPM is disabled.
- **Preview is read-only** — cache lookup is a fast dict read; no audio is analyzed during preview.
- **Placeholder never written to disk** — `_???bpm` is display-only; actual filenames computed at run time from detected BPM.
- **Cache survives restarts** — JSON sidecar is written after each run; next session reuses it immediately.

---

## Verification

1. `pip install aubio numpy` then `python main.py`
2. Enable **Detect BPM** — confirm "Append BPM to filename" sub-option activates; BPM column appears in Deck B preview showing `???` for all files
3. Select a folder, enable **Append BPM to filename**, observe preview shows `stem_???bpm.ext` filenames
4. Run a **Dry-run** — log shows detected BPM per file; filenames show actual BPM values
5. Re-open preview — BPM column now shows actual values (from cache); filenames show correct BPM
6. Run again — second run is significantly faster (cache hits)
7. Confirm `~/.sampson/bpm_cache.json` contains entries with `mtime` + `bpm` fields
8. Select M8 profile + long filenames — verify logged destination paths are ≤ 127 chars with BPM suffix intact
9. Toggle theme — BPM checkboxes preserve state after UI rebuild
