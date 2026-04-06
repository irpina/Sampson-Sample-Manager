"""All mutable application state — v0.8.0 PyWebView edition.

Plain Python dict + push() for JS synchronization. No tkinter dependencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Core state dict
# ---------------------------------------------------------------------------
_state: dict[str, Any] = {
    # Paths
    "source": "",
    "dest": "",
    "active_dir": "",
    
    # Selection
    "selected_folders": [],  # list of paths (was: set())
    
    # Options
    "move": False,
    "dry": True,
    "modify_names": False,
    "custom_prefix": "",
    "profile": "Generic",
    "struct_mode": "flat",  # "flat" | "mirror" | "parent"
    
    # Audio conversion
    "convert_enabled": False,
    "convert_format": "wav",  # "wav" | "aiff"
    "convert_sample_rate": "keep",
    "convert_bit_depth": "keep",
    "convert_channels": "keep",
    "convert_normalize": False,
    "convert_follow_profile": True,
    
    # BPM detection
    "bpm_enabled": False,
    "bpm_append": False,
    "bpm_fresh": False,
    
    # Key detection
    "key_enabled": False,
    "key_append": False,
    "key_fresh": False,
    
    # UI state
    "status": "Ready",
    "progress": 0,
    "is_running": False,
    "is_playing": False,
    "playback_file": None,
    "section_open": {
        "struct": False,
        "device": False,
        "conversion": False,
        "bpm": False,
        "key": False,
        "sync": False,
    },
    "is_dark": True,
    "preview_filter": "",
    
    # Data for UI
    "dir_entries": [],  # [{name, path, type, checked, icon}...]
    "src_count": 0,
    "preview_count": 0,
    "preview_entries": [],  # [{src_name, dest_name, bpm, key, length, srcpath}...]
    "log_lines": [],  # [{message, type, time}...]
    
    # Sync system state
    "sync_mode": "additive",  # "mirror" | "additive"
    "sync_plan": [],  # list of plan entry dicts
    "sync_plan_ready": False,  # plan computed and ready to execute
    "sync_plan_counts": {"add": 0, "update": 0, "delete": 0, "skip": 0},
    "sync_in_progress": False,
    "sync_show_plan": False,  # whether to show sync plan in Deck B
    "sync_auto_detected": False,  # true when previous run detected in dest
    
    # Duplicate detection
    "dedup_enabled": True,  # skip files with identical content
}

# ---------------------------------------------------------------------------
# Window reference for JS sync
# ---------------------------------------------------------------------------
_window: Any = None  # pywebview window
_push_callback: Callable | None = None  # Optional callback for testing


def set_window(window) -> None:
    """Set the pywebview window reference for JS sync."""
    global _window
    _window = window


def set_push_callback(callback: Callable) -> None:
    """Set a callback for state push (useful for testing)."""
    global _push_callback
    _push_callback = callback


def get(key: str, default: Any = None) -> Any:
    """Get a state value."""
    return _state.get(key, default)


def set(key: str, value: Any, push: bool = True) -> None:
    """Set a state value and optionally push to JS."""
    _state[key] = value
    if push:
        push_keys([key])


def update(updates: dict[str, Any], push: bool = True) -> None:
    """Update multiple state values at once."""
    _state.update(updates)
    if push:
        push_keys(list(updates.keys()))


def get_all() -> dict[str, Any]:
    """Get full state copy."""
    # Deep copy to prevent accidental mutations
    import copy
    return copy.deepcopy(_state)


def push_keys(keys: list[str] | None = None) -> None:
    """Push state subset (or full state) to JS via window.evaluate_js().
    
    Called automatically on state.set() and state.update().
    Can also be called manually after batch operations.
    """
    if _push_callback:
        payload = {k: _state[k] for k in keys} if keys else _state
        _push_callback(payload)
        return
        
    if not _window:
        return
        
    try:
        payload = {k: _state[k] for k in keys} if keys else _state
        json_str = json.dumps(payload)
        _window.evaluate_js(f"window._onStateUpdate && window._onStateUpdate({json_str})")
    except Exception as e:
        print(f"State push failed: {e}")


def add_log(message: str, log_type: str = "info") -> None:
    """Add a log entry and push to UI."""
    from datetime import datetime
    entry = {
        "message": message,
        "type": log_type,  # "info" | "success" | "error" | "warn"
        "time": datetime.now().isoformat(),
    }
    _state["log_lines"].append(entry)
    # Keep last 500 lines
    if len(_state["log_lines"]) > 500:
        _state["log_lines"] = _state["log_lines"][-500:]
    push_keys(["log_lines"])


def clear_log() -> None:
    """Clear all log entries."""
    _state["log_lines"] = []
    push_keys(["log_lines"])


def set_status(text: str, progress: int | None = None) -> None:
    """Update status text and optional progress."""
    updates = {"status": text}
    if progress is not None:
        updates["progress"] = max(0, min(100, progress))
    update(updates)


def set_progress(value: int) -> None:
    """Update just the progress bar value (0-100)."""
    set("progress", max(0, min(100, value)))


def register_refresh_callback(callback) -> None:
    """Register callback for preview refresh (used by operations)."""
    global _refresh_preview_cb
    _refresh_preview_cb = callback


# ---------------------------------------------------------------------------
# Legacy compatibility helpers
# ---------------------------------------------------------------------------

root = None  # No tk root in webview edition


# For modules that still reference state.active_dir_var.get()
class _VarCompat:
    """Compatibility shim for old tk.StringVar-style access."""
    def __init__(self, key: str):
        self._key = key
    
    def get(self) -> Any:
        return _state.get(self._key, "")
    
    def set(self, value: Any) -> None:
        set(self._key, value)


# Expose compatibility vars
active_dir_var = _VarCompat("active_dir")
source_var = _VarCompat("source")
dest_var = _VarCompat("dest")
move_var = _VarCompat("move")
dry_var = _VarCompat("dry")
src_count_var = _VarCompat("src_count")
preview_count_var = _VarCompat("preview_count")
status_var = _VarCompat("status")
progress_var = _VarCompat("progress")
nav_path_var = _VarCompat("active_dir")
profile_var = _VarCompat("profile")
struct_mode_var = _VarCompat("struct_mode")
modify_names_var = _VarCompat("modify_names")
custom_prefix_var = _VarCompat("custom_prefix")
convert_enabled_var = _VarCompat("convert_enabled")
convert_format_var = _VarCompat("convert_format")
convert_sample_rate_var = _VarCompat("convert_sample_rate")
convert_bit_depth_var = _VarCompat("convert_bit_depth")
convert_channels_var = _VarCompat("convert_channels")
convert_normalize_var = _VarCompat("convert_normalize")
convert_follow_profile_var = _VarCompat("convert_follow_profile")
bpm_enabled_var = _VarCompat("bpm_enabled")
bpm_append_var = _VarCompat("bpm_append")
bpm_fresh_var = _VarCompat("bpm_fresh")
key_enabled_var = _VarCompat("key_enabled")
key_append_var = _VarCompat("key_append")
key_fresh_var = _VarCompat("key_fresh")
preview_filter_var = _VarCompat("preview_filter")

# Legacy widget references (now None)
dir_browser = None
preview_tree = None
log_text = None
run_btn = None
_status_dot = None
transport_prev_btn = None
transport_play_btn = None
transport_next_btn = None

# Internal state (not synced to JS)
import builtins
_selected_folders: set = builtins.set()
_preview_after = None
_is_dark = True
_dpi_scale = 1.0
_tooltip_win = None
_tooltip_item = None
_playback_file = None
_is_playing = False
_last_conversion_error = None
_section_open = _state["section_open"]
_refresh_preview_cb = None


def _sync_selected_folders() -> None:
    """Sync the internal _selected_folders set to state."""
    _state["selected_folders"] = list(_selected_folders)
