"""Audio playback — NSSound on macOS, pygame on Windows/Linux."""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any

import state

# ── Backend selection ────────────────────────────────────────────────────────
_USE_NSSOUND = sys.platform == "darwin"
_NSSound = None
_current_index = -1
_ns_sound = None

# Initialize pygame mixer on Windows/Linux
if not _USE_NSSOUND:
    import pygame.mixer as _mixer
    _mixer.init(frequency=48000, size=-16, channels=2, buffer=512)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _ensure_nssound():
    """Lazy-load NSSound."""
    global _NSSound
    if _NSSound is None and _USE_NSSOUND:
        from AppKit import NSSound
        _NSSound = NSSound
    return _NSSound


def _preview_items():
    """Return list of preview entry dicts from state."""
    return state.get("preview_entries", [])


def _load_index(idx: int) -> dict[str, Any]:
    """Load file at index and return entry data."""
    global _current_index
    items = _preview_items()
    if not items or not (0 <= idx < len(items)):
        return {"success": False, "error": "Invalid index"}
    
    _current_index = idx
    entry = items[idx]
    playback_file = Path(entry["srcpath"]) if entry.get("srcpath") else None
    
    state._state["playback_file"] = str(playback_file) if playback_file else None
    state._playback_file = playback_file
    state.push_keys(["playback_file"])
    
    return {"success": True, "file": str(playback_file), "index": idx}


def _is_busy() -> bool:
    """Return True if audio is currently playing."""
    if _USE_NSSOUND:
        return _ns_sound is not None and _ns_sound.isPlaying()
    else:
        return _mixer.music.get_busy()


def _poll_playback():
    """Poll for playback completion."""
    if _is_busy():
        threading.Timer(0.2, _poll_playback).start()
    else:
        state._state["is_playing"] = False
        state._is_playing = False
        state.push_keys(["is_playing"])


# ── Public API ───────────────────────────────────────────────────────────────

def play_file(srcpath: str) -> dict[str, Any]:
    """Play a specific file by path. Returns status dict."""
    global _ns_sound, _current_index
    
    # Find index of this file in preview
    items = _preview_items()
    for i, entry in enumerate(items):
        if entry.get("srcpath") == srcpath:
            _current_index = i
            break
    
    playback_file = Path(srcpath)
    if not playback_file.is_file():
        return {"success": False, "error": "File not found"}
    
    # Stop any current playback
    stop()
    
    try:
        if _USE_NSSOUND:
            NSSound = _ensure_nssound()
            _ns_sound = NSSound.alloc().initWithContentsOfFile_byReference_(
                str(playback_file), True)
            if _ns_sound:
                _ns_sound.play()
                state._state["is_playing"] = True
                state._is_playing = True
                state._state["playback_file"] = str(playback_file)
                state._playback_file = playback_file
                state.push_keys(["is_playing", "playback_file"])
                threading.Timer(0.2, _poll_playback).start()
                return {"success": True, "file": str(playback_file)}
            else:
                return {"success": False, "error": "Failed to load audio"}
        else:
            _mixer.music.load(str(playback_file))
            _mixer.music.play()
            state._state["is_playing"] = True
            state._is_playing = True
            state._state["playback_file"] = str(playback_file)
            state._playback_file = playback_file
            state.push_keys(["is_playing", "playback_file"])
            threading.Timer(0.2, _poll_playback).start()
            return {"success": True, "file": str(playback_file)}
    except Exception as e:
        state._state["is_playing"] = False
        state._is_playing = False
        state.push_keys(["is_playing"])
        return {"success": False, "error": str(e)}


def play() -> dict[str, Any]:
    """Play the currently selected file; if already playing, stop (toggle)."""
    if _is_busy():
        stop()
        return {"success": True, "action": "stopped"}
    
    if _current_index < 0:
        # Try to play first item
        items = _preview_items()
        if items:
            return play_file(items[0]["srcpath"])
        return {"success": False, "error": "No files to play"}
    
    items = _preview_items()
    if _current_index < len(items):
        return play_file(items[_current_index]["srcpath"])
    
    return {"success": False, "error": "Invalid selection"}


def stop() -> None:
    """Stop playback."""
    global _ns_sound
    if _USE_NSSOUND:
        if _ns_sound and _ns_sound.isPlaying():
            _ns_sound.stop()
        _ns_sound = None
    else:
        _mixer.music.stop()
    
    state._state["is_playing"] = False
    state._is_playing = False
    state.push_keys(["is_playing"])


def reset() -> None:
    """Stop playback and reset current index."""
    global _current_index
    stop()
    _current_index = -1
    state._playback_file = None
    state._state["playback_file"] = None
    state.push_keys(["playback_file"])


def next_file() -> dict[str, Any]:
    """Play next file in list."""
    stop()
    items = _preview_items()
    if not items:
        return {"success": False, "error": "No files"}
    
    idx = min(_current_index + 1, len(items) - 1) if _current_index >= 0 else 0
    result = _load_index(idx)
    if result["success"]:
        return play()
    return result


def prev_file() -> dict[str, Any]:
    """Play previous file in list."""
    stop()
    items = _preview_items()
    if not items:
        return {"success": False, "error": "No files"}
    
    idx = max(_current_index - 1, 0) if _current_index >= 0 else 0
    result = _load_index(idx)
    if result["success"]:
        return play()
    return result


def get_current_index() -> int:
    """Return current playback index."""
    return _current_index


def set_current_index(idx: int) -> None:
    """Set current playback index without playing."""
    global _current_index
    _current_index = idx
    _load_index(idx)
