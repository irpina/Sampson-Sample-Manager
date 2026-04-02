# browser.py — Deck A File Browser

Pure path logic for Deck A. Returns JSON-serializable data for JS rendering. No UI code.

## Imports
- **Imports:** `state`, `constants`, `preview`
- **Imported by:** `api`, `preview`

## Key Functions

| Function | Description |
|----------|-------------|
| `navigate_to(path_str)` | Navigate to path; list subdirs + audio files; auto-select all subdirs and files; trigger preview refresh |
| `toggle_folder(path, checked)` | Toggle a folder's selection state in `_selected_folders` |
| `select_all_visible()` | Select all currently visible folders and files |
| `deselect_all_visible()` | Deselect all currently visible folders and files |
| `get_selected_folders()` | Return list of selected folder paths |
| `clear_selection()` | Clear all selections |

## `navigate_to()` Return Shape

```python
{
  "current_path": str,
  "parent_path": str | None,
  "entries": [
    {
      "name": str,
      "path": str,
      "type": "up" | "folder" | "file",
      "checked": bool,
      "icon": "↑" | "▶" | "♪",
      "is_audio": bool
    }
  ],
  "audio_count": int
}
```

## Critical Rules

- **Auto-select on navigate:** ALL subdirectories are selected when navigating to a new folder. Leaf dirs (no subdirs) auto-select the dir itself. This is intentional — matches original UI behavior.
- **Audio files are selectable** — they appear with a ♪ icon and have checkboxes just like folders.
- **No recursion at browse time** — only lists the current directory level. Recursion happens during preview scan.
- **PermissionError silently ignored** — inaccessible dirs are skipped without error.
- **`_selected_folders` is a `set` internally** — serialized to `list` for state push.
- **Preview refresh on every navigate** — `preview.refresh()` is called at end of `navigate_to()`.
- Entry `type="up"` is the parent directory link (always first); clicking it calls `navigate_to(parent_path)`.
