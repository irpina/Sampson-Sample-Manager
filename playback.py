import pygame.mixer as _mixer
from pathlib import Path

import state

_mixer.init()
_current_index = -1   # index into preview tree item list


def _tree_items():
    """Return list of all item IDs in preview tree."""
    return list(state.preview_tree.get_children())


def _load_index(idx):
    """Select and prepare the file at tree index idx without playing."""
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


def play():
    """Play the currently selected file; if already playing, stop (toggle)."""
    if _mixer.music.get_busy():
        stop()
        return
    if not state._playback_file or not state._playback_file.is_file():
        return
    try:
        _mixer.music.load(str(state._playback_file))
        _mixer.music.play()
        state._is_playing = True
        _update_transport_state()
        state.root.after(200, _poll_playback)
    except Exception:
        state._is_playing = False


def stop():
    """Stop playback and update transport state."""
    _mixer.music.stop()
    state._is_playing = False
    _update_transport_state()


def reset():
    """Stop playback and reset the current index (call on source navigate)."""
    global _current_index
    stop()
    _current_index = -1


def next_file():
    """Stop, advance to the next file, and auto-play."""
    stop()
    items = _tree_items()
    if not items:
        return
    idx = min(_current_index + 1, len(items) - 1)
    _load_index(idx)
    play()


def prev_file():
    """Stop, retreat to the previous file, and auto-play."""
    stop()
    idx = max(_current_index - 1, 0)
    _load_index(idx)
    play()


def on_tree_select(event):
    """ButtonRelease-1 handler on the preview tree — select and auto-play."""
    iid = state.preview_tree.identify_row(event.y)
    if not iid:
        return
    items = _tree_items()
    if iid in items:
        stop()
        _load_index(items.index(iid))
        play()


def on_arrow_key(event):
    """KeyRelease-Up/Down handler — play whichever row the arrow moved to."""
    iid = state.preview_tree.focus()
    if not iid:
        return
    items = _tree_items()
    if iid in items:
        stop()
        _load_index(items.index(iid))
        play()


def _poll_playback():
    """Re-check every 200 ms; update button icon when track ends naturally."""
    if _mixer.music.get_busy():
        state.root.after(200, _poll_playback)
    else:
        state._is_playing = False
        _update_transport_state()


def _update_transport_state():
    """Sync play/stop icon and enable/disable prev & next buttons."""
    if state.transport_play_btn:
        icon = "■" if state._is_playing else "▶"
        state.transport_play_btn.configure(text=icon)
    has_file = state._playback_file is not None
    items    = _tree_items()
    can_prev = has_file and _current_index > 0
    can_next = has_file and _current_index < len(items) - 1
    for btn, enabled in [
        (state.transport_prev_btn, can_prev),
        (state.transport_next_btn, can_next),
    ]:
        if btn:
            btn.configure(state="normal" if enabled else "disabled")
