# operations.py — File Copy/Move/Convert Worker

Runs the actual file operation in a daemon thread. Shares `_compute_output()` with `preview.py` to guarantee preview matches execution.

## Imports
- **Imports:** `state`, `constants`, `bpm`, `key`, `conversion`, `threading`, `shutil`, `pathlib`
- **Imported by:** `api`, `preview` (for `_compute_output`)

## Key Functions

| Function | Description |
|----------|-------------|
| `run_tool()` | Validate inputs (source, dest, folders selected, ffmpeg if converting), spawn worker thread |
| `_run_worker(...)` | Background worker — iterate files, detect BPM/key, convert or copy/move, log, update progress |
| `_compute_output(f, source_root, dest, ...)` | **Deterministic** filename + subfolder calculation — used by both preview and execution |
| `_apply_path_limit(name, dest_path, limit, protect)` | Shorten filename to fit within `path_limit` chars, preserving extension and BPM/key suffixes |

## `_compute_output()` Parameters

```python
_compute_output(
  f,               # Path — source file
  source_root,     # Path — selected folder root
  dest,            # Path — destination root
  no_rename,       # bool — skip parent-prefix rename
  struct_mode,     # "flat" | "mirror" | "parent"
  path_limit,      # int | None — from hardware profile
  bpm,             # str | None — detected/cached BPM
  append_bpm,      # bool
  key,             # str | None
  append_key,      # bool
  custom_prefix,   # str — overrides parent-dir prefix if set
)
# Returns: (new_filename: str, rel_subfolder: str)
```

## Struct Modes

| Mode | Behavior |
|------|----------|
| `"flat"` | All files go directly into `dest/` |
| `"mirror"` | Preserve full relative path from source root |
| `"parent"` | Group by immediate parent folder name |

## Worker Flow

1. Collect all audio files from selected folders (recursive `rglob`)
2. For each file:
   - Call `_compute_output()` → `(new_name, rel_subfolder)`
   - Detect BPM/key if enabled (happens here, NOT in preview)
   - If dry run: log only, no file writes
   - If convert: `conversion.convert_file()` → write to dest; if move, unlink original
   - If copy/move: `shutil.copy2()` / `shutil.move()`
   - Log action (color-coded: red=move, green=copy, yellow=dry)
   - Push progress via `state.set_progress()`
3. Flush BPM/key caches once at end
4. Call registered refresh callback (updates preview)

## Name Overrides

Manual filename overrides from `preview.get_name_override()` take precedence over `_compute_output()`:
- Override is the **stem only** (no extension)
- Extension is auto-added based on conversion settings (`.wav`, `.aif`, or original)
- Subfolder (`rel_sub`) is still computed by `_compute_output()` normally
- Operations use the same override logic as preview for consistency

## Critical Rules

- **`_compute_output()` must stay identical between preview and execution** — any rename logic change must update both
- `move + conversion`: convert first, then `unlink()` original on success; never delete before conversion completes
- Conversion errors: log the error, skip the file, continue (non-fatal)
- Dry run: all logging happens normally; no file system writes at all
- BPM/key suffix is protected from path-limit truncation by `_apply_path_limit(protect=True)`
- `state.set("is_running", True)` at start, `False` at end (even on exception)
- Worker runs in a daemon thread — it will be killed on app exit without cleanup
- **Name overrides** from preview module are checked after `_compute_output()` and override just the filename (not the subfolder)
