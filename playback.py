"""macOS playback via AppKit.NSSound (replaces pygame.mixer)."""

import sys
from pathlib import Path

import state

# ── Backend selection ────────────────────────────────────────────────────────
# NSSound on macOS (zero extra deps); pygame fallback for Windows/Linux.
# NOTE: AppKit is imported lazily to avoid race conditions with tkinter init.
_USE_NSSOUND = sys.platform == "darwin"
_NSSound = None  # Lazy-loaded on first use
_current_index = -1
_ns_sound = None


def _ensure_nssound():
    """Lazy-load NSSound to avoid AppKit initialization race with tkinter."""
    global _NSSound
    if _NSSound is None and _USE_NSSOUND:
        from AppKit import NSSound
        _NSSound = NSSound
    return _NSSound


# ── Internal helpers ─────────────────────────────────────────────────────────

def _tree_items():
    return list(state.preview_tree.get_children())


def _load_index(idx):
    global _current_index
    items = _tree_items()
    if not items or not (0 <= idx < len(items)):
        return
    _current_index = idx
    iid = items[idx]
    state.preview_tree.selection_set(iid)
    state.preview_tree.see(iid)
    src = state.preview_tree.set(iid, "srcpath")
    state._playback_file = Path(src) if src else None
    _update_transport_state()


def _is_busy() -> bool:
    """Return True if audio is currently playing."""
    if _USE_NSSOUND:
        return _ns_sound is not None and _ns_sound.isPlaying()
    else:
        import pygame.mixer as _mixer
        return _mixer.music.get_busy()


# ── Public transport API ─────────────────────────────────────────────────────

def play():
    """Play the currently selected file; if already playing, stop (toggle)."""
    global _ns_sound
    if _is_busy():
        stop()
        return
    if not state._playback_file or not state._playback_file.is_file():
        return
    try:
        if _USE_NSSOUND:
            NSSound = _ensure_nssound()
            _ns_sound = NSSound.alloc().initWithContentsOfFile_byReference_(
                str(state._playback_file), True)
            if _ns_sound:
                _ns_sound.play()
                state._is_playing = True
                _update_transport_state()
                state.root.after(200, _poll_playback)
        else:
            import pygame.mixer as _mixer
            _mixer.music.load(str(state._playback_file))
            _mixer.music.play()
            state._is_playing = True
            _update_transport_state()
            state.root.after(200, _poll_playback)
    except Exception:
        state._is_playing = False


def stop():
    """Stop playback and update transport state."""
    global _ns_sound
    if _USE_NSSOUND:
        if _ns_sound and _ns_sound.isPlaying():
            _ns_sound.stop()
        _ns_sound = None
    else:
        import pygame.mixer as _mixer
        _mixer.music.stop()
    state._is_playing = False
    _update_transport_state()


def reset():
    """Stop playback and reset current index (call on source navigate)."""
    global _current_index
    stop()
    _current_index = -1


def next_file():
    stop()
    items = _tree_items()
    if not items:
        return
    idx = min(_current_index + 1, len(items) - 1)
    _load_index(idx)
    play()


def prev_file():
    stop()
    idx = max(_current_index - 1, 0)
    _load_index(idx)
    play()


def on_tree_select(event):
    state.preview_tree.focus_set()
    iid = state.preview_tree.identify_row(event.y)
    if not iid:
        return
    items = _tree_items()
    if iid in items:
        stop()
        _load_index(items.index(iid))
        play()


def on_arrow_key(event):
    state.preview_tree.focus_set()
    iid = state.preview_tree.focus()
    if not iid:
        return
    items = _tree_items()
    if iid in items:
        stop()
        _load_index(items.index(iid))
        play()


def _poll_playback():
    if _is_busy():
        state.root.after(200, _poll_playback)
    else:
        state._is_playing = False
        _update_transport_state()


def _update_transport_state():
    if state.transport_play_btn:
        icon = "■" if state._is_playing else "▶"
        state.transport_play_btn.configure(text=icon)
    has_file = state._playback_file is not None
    items = _tree_items()
    can_prev = has_file and _current_index > 0
    can_next = has_file and _current_index < len(items) - 1
    for btn, enabled in [
        (state.transport_prev_btn, can_prev),
        (state.transport_next_btn, can_next),
    ]:
        if btn:
            btn.configure(state="normal" if enabled else "disabled")
