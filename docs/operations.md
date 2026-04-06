# operations.py — File Copy/Move/Convert Worker

Runs the actual file operation in a daemon thread. Shares `_compute_output()` with `preview.py` to guarantee preview matches execution.

## Imports
- **Imports:** `state`, `constants`, `bpm`, `key`, `conversion`, `threading`, `shutil`, `pathlib`
- **Imported by:** `api`, `preview` (for `_compute_output`)

## Key Functions

| Function | Description |
|----------|-------------|
| `run_tool()` | Validate inputs (source, dest, folders selected, ffmpeg if converting), spawn worker thread |
| `_run_worker(...)` | Background worker — iterate files, detect BPM/key, convert or copy/move, dedup, log, update progress |
| `_compute_output(f, source_root, dest, ...)` | **Deterministic** filename + subfolder calculation — used by both preview and execution |
| `_apply_path_limit(name, dest_path, limit, protect)` | Shorten filename to fit within `path_limit` chars, preserving extension and BPM/key suffixes |
| `compute_sync_plan()` | Validate inputs and start sync plan computation in background thread |
| `_sync_plan_worker(source, dest)` | Classify each source file as add/update/skip, find mirror-mode deletes, detect dest duplicates |
| `run_sync()` | Read `state["sync_plan"]` and start execution thread |
| `_run_sync_worker(plan)` | Execute ADD/UPDATE/DELETE entries; SKIP is no-op |
| `clear_sync_plan()` | Reset sync plan state and return Deck B to normal preview |
| `auto_sync_check(dest)` | Check if dest contains prior run output; auto-trigger `compute_sync_plan()` if so |
| `_hash_file(path)` | SHA-256 of file contents (64KB chunks) — used for duplicate detection |
| `_dedup_dest_flat(dest, dry)` | Remove content-duplicate audio files from top level of dest only |

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

## Worker Flow (`_run_worker`)

1. Pre-scan dest for audio file sizes → `dest_size_index` (dedup setup)
2. Collect all audio files from selected folders (recursive `rglob`)
3. For each file:
   - Call `_compute_output()` → `(new_name, rel_subfolder)`
   - Detect BPM/key if enabled (happens here, NOT in preview)
   - **Dedup check** (if `dedup_enabled`):
     - Source-to-dest: hash size-matched dest candidates; skip if content match found
     - Source-to-source: hash against `seen_hashes` set; skip if already seen this run
   - If dry run: log only, no file writes
   - If convert: `conversion.convert_file()` → write to dest; if move, unlink original
   - If copy/move: `shutil.copy2()` / `shutil.move()`
   - Log action; push progress
4. Flush BPM/key caches
5. **Dest flat dedup** (if `dedup_enabled`): call `_dedup_dest_flat()` to clean up existing top-level duplicates
6. Call registered refresh callback (updates preview)

## Sync Plan Flow (`_sync_plan_worker`)

1. Pre-scan dest top-level for content duplicates → add DELETE plan entries
2. Pre-scan dest for audio file sizes → `dest_size_index` (dedup setup)
3. Collect source files from selected folders
4. For each source file:
   - `_compute_output()` → resolved dest path
   - Dedup check (same logic as `_run_worker`)
   - Classify: `add` / `update` / `skip` based on dest existence + size/mtime comparison
5. Mirror mode: walk dest for orphan files → add DELETE entries
6. Compute counts `{add, update, delete, skip}`, push to state

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

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
