from pathlib import Path
from tkinter import filedialog

import state
import theme
import constants


def navigate_to(path_str):
    p = Path(path_str)
    if not p.is_dir():
        return

    state.dir_browser.delete(0, "end")
    state._browser_items = []
    state.nav_path_var.set(str(p))

    parent = p.parent
    if parent != p:
        state.dir_browser.insert("end", "   \u2191  ..")
        state._browser_items.append(("up", "..", str(parent)))
        state.dir_browser.itemconfigure(0, fg=theme.FG_DIM)

    try:
        subdirs = sorted(d for d in p.iterdir() if d.is_dir() and not d.name.startswith("."))
        for d in subdirs:
            state.dir_browser.insert("end", f"   \u25b6  {d.name}")
            state._browser_items.append(("folder", d.name, str(d)))
            state.dir_browser.itemconfigure(len(state._browser_items) - 1, fg=theme.ON_CYAN_CONT)
    except PermissionError:
        pass

    try:
        audio = sorted(f for f in p.iterdir()
                       if f.is_file() and f.suffix.lower() in constants.AUDIO_EXTS)
        for f in audio:
            state.dir_browser.insert("end", f"   \u266a  {f.name}")
            state._browser_items.append(("file", f.name, str(f)))
            state.dir_browser.itemconfigure(len(state._browser_items) - 1, fg=theme.FG_VARIANT)
    except PermissionError:
        pass

    state.active_dir_var.set(path_str)


def on_browser_press(event):
    """
    Mouse-button-down on the file browser.

    Highlights the item under the cursor and darkens the listbox background
    slightly to give tactile press feedback. Navigation is deferred to
    on_browser_release so the user sees a response before anything happens.
    """
    idx = state.dir_browser.nearest(event.y)
    if 0 <= idx < len(state._browser_items) and state._browser_items[idx][0] in ("folder", "up"):
        state._browser_press_idx = idx
        state.dir_browser.selection_clear(0, "end")
        state.dir_browser.selection_set(idx)
        press_bg = "#222028" if state._is_dark else "#cdc7ba"
        state.dir_browser.configure(bg=press_bg)
    else:
        state._browser_press_idx = None


def on_browser_release(event):
    """
    Mouse-button-up on the file browser.

    Restores the normal background colour, then navigates into the folder
    that was pressed (if any). Only navigates if the release occurs over
    the same item that was pressed — prevents accidental navigation when
    the user drags off an item.
    """
    state.dir_browser.configure(bg=theme.BG_SURF2)

    if state._browser_press_idx is None:
        return

    pressed = state._browser_press_idx
    state._browser_press_idx = None

    release_idx = state.dir_browser.nearest(event.y)
    if release_idx != pressed:
        return

    if pressed < len(state._browser_items):
        item_type, _name, path = state._browser_items[pressed]
        if item_type in ("folder", "up"):
            navigate_to(path)


def nav_up():
    current = state.active_dir_var.get()
    if not current:
        return
    p = Path(current)
    parent = p.parent
    if parent != p:
        navigate_to(str(parent))


def browse_source():
    path = filedialog.askdirectory(parent=state.root)
    if path:
        state.source_var.set(path)   # trace → on_source_var_changed → navigate_to


def browse_dest():
    path = filedialog.askdirectory(parent=state.root)
    if path:
        state.dest_var.set(path)


def on_source_var_changed(*_):
    p = state.source_var.get().strip()
    if Path(p).is_dir():
        navigate_to(p)
