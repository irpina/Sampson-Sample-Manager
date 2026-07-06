"""All mutable application state.

Plain Python dict + push() for JS synchronization. No tkinter dependencies.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable

from constants import VERSION

# Guards _state against concurrent mutation — workers run in daemon threads.
# RLock so state functions can call each other while holding it.
_lock = threading.RLock()

# ---------------------------------------------------------------------------
# Core state dict
# ---------------------------------------------------------------------------
_state: dict[str, Any] = {
    "app_version": VERSION,

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
    
    # Slicer state
    "slicer_open": False,
    "slicer_file": "",  # currently loaded file path
    "slicer_file_info": None,  # {name, duration, sample_rate, channels}
    "slicer_slices": [],  # list of slice dicts
    "slicer_waveform": None,  # downsampled waveform data
    "slicer_progress": 0,  # 0-100 during export
    "slicer_status": "",  # status message
    "slicer_exporting": False,  # export in progress
    "slicer_export_result": None,  # result of last export
    
    # Audition Stack state
    "audition_open": False,
    "audition_tracks": [None, None, None, None],  # 4-element list; None = empty slot
    "audition_master_bpm": 120.0,
    "audition_loop": False,
    "audition_rendering": False,
    "audition_status": "",
    "audition_selection": [],  # Deck B srcpaths shift-selected (ordered, max 4)
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
    with _lock:
        return _state.get(key, default)


def set(key: str, value: Any, push: bool = True) -> None:
    """Set a state value and optionally push to JS."""
    with _lock:
        _state[key] = value
    if push:
        push_keys([key])


def update(updates: dict[str, Any], push: bool = True) -> None:
    """Update multiple state values at once."""
    with _lock:
        _state.update(updates)
    if push:
        push_keys(list(updates.keys()))


def get_all() -> dict[str, Any]:
    """Get full state copy."""
    # Deep copy to prevent accidental mutations
    import copy
    with _lock:
        return copy.deepcopy(_state)


def _push_payload(payload: dict[str, Any]) -> None:
    """Send an arbitrary patch dict to JS (or the test callback)."""
    if _push_callback:
        _push_callback(payload)
        return

    if not _window:
        return

    try:
        json_str = json.dumps(payload)
        _window.evaluate_js(f"window._onStateUpdate && window._onStateUpdate({json_str})")
    except Exception as e:
        print(f"State push failed: {e}")


def push_keys(keys: list[str] | None = None) -> None:
    """Push state subset (or full state) to JS via window.evaluate_js().

    Called automatically on state.set() and state.update().
    Can also be called manually after batch operations.
    """
    # Snapshot under lock; evaluate_js happens outside it.
    with _lock:
        payload = {k: _state[k] for k in keys} if keys else dict(_state)
    _push_payload(payload)


def add_log(message: str, log_type: str = "info") -> None:
    """Add a log entry and push to UI.

    Pushes only the appended entry (log_append) — re-sending the whole
    log list on every line made large runs O(n²) in IPC traffic.
    """
    from datetime import datetime
    entry = {
        "message": message,
        "type": log_type,  # "info" | "success" | "error" | "warn"
        "time": datetime.now().isoformat(),
    }
    with _lock:
        _state["log_lines"].append(entry)
        # Keep last 500 lines
        if len(_state["log_lines"]) > 500:
            _state["log_lines"] = _state["log_lines"][-500:]
    _push_payload({"log_append": entry})


def clear_log() -> None:
    """Clear all log entries."""
    with _lock:
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
# Internal state (not synced to JS)
# ---------------------------------------------------------------------------
import builtins
_selected_folders: set = builtins.set()  # canonical selection set (browser.py)
_playback_file = None
_is_playing = False
_last_conversion_error = None
_refresh_preview_cb = None


def _sync_selected_folders() -> None:
    """Sync the internal _selected_folders set to state."""
    _state["selected_folders"] = list(_selected_folders)
