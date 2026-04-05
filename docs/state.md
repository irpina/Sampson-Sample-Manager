# state.py — Central State Store

Single source of truth for all mutable application state. Syncs to JS via `window._onStateUpdate(patch)`.

## Imports
- **Imports:** stdlib only (`json`, `pathlib`, `copy`, `datetime`)
- **Imported by:** every other module

## Key Functions

| Function | Description |
|----------|-------------|
| `set_window(window)` | Register pywebview window for JS sync |
| `get(key, default=None)` | Read a state value |
| `set(key, value, push=True)` | Write a state value; auto-pushes to JS unless `push=False` |
| `update(updates, push=True)` | Batch-write multiple keys |
| `get_all()` | Deep copy of full state dict (safe to mutate) |
| `push_keys(keys=None)` | Manually push subset (or all) to JS |
| `add_log(message, log_type)` | Append a log entry (capped at 500, FIFO) |
| `clear_log()` | Clear all log entries |
| `set_status(text, progress=None)` | Update status text + optional progress (0-100) |
| `set_progress(value)` | Update progress bar only (clamped 0-100) |
| `register_refresh_callback(cb)` | Register preview refresh callback (operations calls this) |

## State Schema

```
Paths:       source, dest, active_dir
Selection:   selected_folders (list — internal _selected_folders is a set)
Options:     move, dry, modify_names, custom_prefix, profile, struct_mode
Conversion:  convert_enabled, convert_format, convert_sample_rate,
             convert_bit_depth, convert_channels, convert_normalize, convert_follow_profile
BPM:         bpm_enabled, bpm_append, bpm_fresh
Key:         key_enabled, key_append, key_fresh
UI:          status, progress, is_running, is_playing, playback_file,
             section_open (dict), is_dark, preview_filter
Data:        dir_entries, src_count, preview_count, preview_entries, log_lines
```

## Critical Rules

- `set()` and `update()` auto-push to JS — pass `push=False` to batch then push manually
- `_selected_folders` is a Python `set` internally; `selected_folders` key is serialized as a `list`
- All state values must be JSON-serializable — non-serializable values fail silently in `evaluate_js()`
- `get_all()` returns a deep copy — mutations don't affect the store
- `log_lines` is capped at 500 entries (oldest dropped first)
- `_VarCompat` shim provides legacy `.get()/.set()` API (from old tkinter edition) — don't add new uses
- Progress is clamped to 0–100 in `set_progress()`

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
