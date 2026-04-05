# api.py — JS↔Python API Bridge

Exposes Python backend to JavaScript as `window.pywebview.api.*`. All public methods on `SampsonAPI` are callable from JS.

## Imports
- **Imports:** `state`, `constants`, `browser`, `preview`, `playback`, `operations`, `conversion`
- **Imported by:** `main.py` only

## Method Reference

### State
| Method | Description |
|--------|-------------|
| `get_state()` | Return full state dict to JS on init |
| `set_option(key, value)` | Generic setter with side effects (see below) |
| `set_options(options)` | Batch update multiple options |

### Navigation (Deck A)
| Method | Description |
|--------|-------------|
| `browse_source()` | Native OS folder picker → sets `source` + navigates |
| `navigate(path)` | Navigate Deck A to path |
| `nav_up()` | Navigate to parent directory |
| `toggle_folder(path, checked)` | Toggle folder selection checkbox |
| `select_all_folders()` | Select all visible folders |
| `deselect_all_folders()` | Deselect all visible folders |

### Preview (Deck B)
| Method | Description |
|--------|-------------|
| `browse_dest()` | Native OS folder picker → sets `dest` |
| `get_preview()` | Fetch current preview entries |
| `sort_preview(column)` | Sort by `"bpm"` \| `"key"` \| `"duration"` |
| `set_file_bpm(filepath, bpm)` | Manually override BPM for a file |
| `set_file_key(filepath, key)` | Manually override key for a file |
| `set_file_name(filepath, name)` | Manually override output filename (stem only) |

### Playback
| Method | Description |
|--------|-------------|
| `preview_play(srcpath)` | Play file at path |
| `preview_stop()` | Stop playback |
| `preview_next()` | Next file |
| `preview_prev()` | Previous file |

### Operations
| Method | Description |
|--------|-------------|
| `run()` | Validate inputs and start background file operation |
| `check_ffmpeg()` | Return ffmpeg availability + version info |

### System
| Method | Description |
|--------|-------------|
| `get_drives()` | OS root locations (Windows drives / macOS/Linux common dirs) |
| `open_external(path)` | Open path in OS file manager |
| `get_log()` | Fetch log lines |
| `clear_log()` | Clear log |

## `set_option()` Side Effects

Setting these keys triggers additional behavior:

| Key | Side Effect |
|-----|-------------|
| `source` | `browser.navigate_to()` + preview refresh |
| `dest` | preview refresh |
| `profile` | auto-populates conversion settings if `convert_follow_profile` is true |
| `preview_filter` | `preview.apply_filter()` |
| `is_dark` | stored in state (theme applied by JS) |
| Any conversion/BPM/key option | preview refresh |

## Critical Rules

- All methods are exposed to untrusted JS — validate inputs in each method
- `run()` spawns a daemon thread and returns immediately; status flows back via `state.set_status()`
- Never return large data structures directly from methods — push via `state.push_keys()` instead
- `check_ffmpeg()` is non-fatal — absence triggers a warning, not a hard failure
- Platform detection for `get_drives()`: `sys.platform == "win32"` / `"darwin"` / else linux

---
*SAMPSON is licensed under the [GNU General Public License v3.0](../LICENSE).*
