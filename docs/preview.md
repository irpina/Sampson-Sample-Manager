# preview.py — Deck B Preview, Filter, Sort

Scans selected folders in a background thread; populates `state["preview_entries"]` with file rename previews, BPM, key, duration, and filter/sort state.

## Imports
- **Imports:** `state`, `constants`, `bpm` (as `bpm_module`), `key` (as `key_module`), `operations` (`_compute_output`), `conversion` (`get_target_extension`)
- **Imported by:** `api`, `browser`, `operations`

## Key Functions

| Function | Description |
|----------|-------------|
| `refresh()` | Entry point — spawn background thread to scan selected folders/files |
| `sort_by(col)` | Toggle sort on `"bpm"` \| `"key"` \| `"duration"`; cycles asc → desc → off |
| `apply_filter(text)` | Filter `_preview_rows` by query, update `state["preview_entries"]` |
| `set_file_bpm(filepath, bpm)` | Set manual BPM override + refresh |
| `set_file_key(filepath, key)` | Set manual key override + refresh |
| `set_file_name(filepath, name)` | Set manual filename override (stem only) + refresh |
| `get_name_override(filepath)` | Get manual name override for a file (or None) |

## Preview Entry Shape

```python
{
  "src_name": str,       # original filename
  "dest_name": str,      # output filename (after rename/BPM/key suffix)
  "bpm": str,            # "120" | "???" (detecting) | "" (disabled)
  "key": str,            # "C#" | "???" | ""
  "length": str,         # "1:23" | ""
  "srcpath": str         # absolute source path (used for playback)
}
```

## Filter Query Syntax

Plain text and structured tokens; multiple tokens = AND logic.

| Token | Example | Matches |
|-------|---------|---------|
| plain text | `kick` | filename substring (case-insensitive) |
| BPM exact | `BPM:120` | BPM == 120 |
| BPM range | `BPM:100-130` | 100 ≤ BPM ≤ 130 |
| BPM prefix | `BPM:12*` | 120–129 |
| Note | `Note:C#` | root note match |
| Min length | `MinLength:30` | duration ≥ 30s |
| Max length | `MaxLength:90` | duration ≤ 90s |

Filter bypasses the 500-row `MAX_PREVIEW_ROWS` cap — all matches shown.

## Module-Level State

| Variable | Description |
|----------|-------------|
| `_preview_rows` | All unfiltered rows (set by scan thread) |
| `_duration_cache` | `path → float` seconds (cleared each refresh) |
| `_sort_col` | `"bpm" \| "key" \| "duration" \| None` |
| `_sort_asc` | `bool` |
| `_name_overrides` | `srcpath → manual dest stem` (persists across refreshes) |

## Manual Name Overrides

Users can double-click the "Will become" column in Deck B to manually override the output filename. This bypasses the normal rename logic (including custom prefix).

**API:**
- `set_file_name(filepath, name)` — Set override (stem only, extension auto-added) or empty to clear
- `get_name_override(filepath)` — Retrieve override stem (or None)

**Behavior:**
- Overrides persist across settings changes (BPM append, struct mode, etc.)
- Overrides are cleared when navigating to a new folder in Deck A (`browser.navigate_to()`)
- Manual names show in amber italic (`td.col-dest.overridden`) to indicate override active
- Extension is always preserved based on conversion settings (manual stem + auto extension)
- Row entry has `"name_manual": true` when an override is active

## Critical Rules

- BPM/key shows `"???"` if detection enabled but no value available yet; `""` if detection disabled
- Conversion changes preview: shows `"[c]"` in dest_name and swaps extension (e.g. `.mp3` → `.wav`)
- `_compute_output()` from `operations.py` is the single source of truth for output filenames — preview and actual execution use the same function
- Sorting puts `"???"` and `None` last for BPM/duration columns
- Duration cache cleared each `refresh()` call to avoid stale values
- `apply_filter()` operates on `_preview_rows` — always call after sort, not instead of sort
- `files with unreadable headers` show no length and are excluded from `MinLength`/`MaxLength` filters
- Filename matching is case-insensitive substring (not glob, not regex)
- **Name overrides** take precedence over `_compute_output()` but subfolder (`rel_sub`) is still computed normally
- **Unified selection** — `_scan_thread` handles both directories (scanned via `rglob`) and individual files (added directly) from `selected_folders`

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
