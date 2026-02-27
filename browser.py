from pathlib import Path
from tkinter import filedialog

import state
import theme
import constants
import preview


def navigate_to(path_str):
    p = Path(path_str)
    if not p.is_dir():
        return

    state.dir_browser.delete(*state.dir_browser.get_children())
    state.nav_path_var.set(str(p))

    parent = p.parent
    if parent != p:
        state.dir_browser.insert("", "end",
            values=("", "  \u2191  ..", str(parent), "up"),
            tags=("up",))

    try:
        subdirs = sorted(d for d in p.iterdir()
                         if d.is_dir() and not d.name.startswith("."))
        for d in subdirs:
            state._selected_folders.add(str(d))   # default: checked on first load
            state.dir_browser.insert("", "end",
                values=("\u2611", f"  \u25b6  {d.name}", str(d), "folder"),
                tags=("folder",))
        if not subdirs:
            # Leaf directory — no subdirs to select, include the dir itself so its
            # direct audio files are picked up by the preview and Run scans.
            state._selected_folders.add(path_str)
    except PermissionError:
        pass

    try:
        audio = sorted(f for f in p.iterdir()
                       if f.is_file() and f.suffix.lower() in constants.AUDIO_EXTS)
        for f in audio:
            state.dir_browser.insert("", "end",
                values=("", f"  \u266a  {f.name}", str(f), "file"),
                tags=("file",))
    except PermissionError:
        pass

    state.dir_browser.tag_configure("folder", foreground=theme.ON_CYAN_CONT)
    state.dir_browser.tag_configure("file",   foreground=theme.FG_VARIANT)
    state.dir_browser.tag_configure("up",     foreground=theme.FG_DIM)

    state.active_dir_var.set(path_str)
    # active_dir_var trace fires preview.on_active_dir_changed() automatically


def on_browser_click(event):
    item = state.dir_browser.identify_row(event.y)
    col  = state.dir_browser.identify_column(event.x)
    if not item:
        return
    itype = state.dir_browser.set(item, "itype")
    path  = state.dir_browser.set(item, "path")

    if col == "#1":   # checkbox column
        if itype == "folder":
            _toggle_folder(item, path)
    else:             # name column — navigate
        if itype in ("folder", "up"):
            navigate_to(path)


def _toggle_folder(item, path):
    if path in state._selected_folders:
        state._selected_folders.discard(path)
        state.dir_browser.set(item, "chk", "\u2610")
    else:
        state._selected_folders.add(path)
        state.dir_browser.set(item, "chk", "\u2611")
    preview.on_active_dir_changed()


def select_all_visible():
    for item in state.dir_browser.get_children():
        if state.dir_browser.set(item, "itype") == "folder":
            path = state.dir_browser.set(item, "path")
            state._selected_folders.add(path)
            state.dir_browser.set(item, "chk", "\u2611")
    preview.on_active_dir_changed()


def deselect_all_visible():
    for item in state.dir_browser.get_children():
        if state.dir_browser.set(item, "itype") == "folder":
            path = state.dir_browser.set(item, "path")
            state._selected_folders.discard(path)
            state.dir_browser.set(item, "chk", "\u2610")
    preview.on_active_dir_changed()


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
