import threading
from pathlib import Path
import tkinter as tk

import state
import theme
import constants
from dpi import _px
from operations import _apply_path_limit


# ── Tooltip ─────────────────────────────────────────────────────────────────

def _reposition_tooltip(cx: int, cy: int):
    """
    Move _tooltip_win so it sits near screen-coordinate (cx, cy).

    If the window would overflow the right or bottom edge of the screen it is
    flipped to the left of / above the cursor respectively.  The window must
    have been packed and update_idletasks() called before this so that
    winfo_reqwidth/height return real values.
    """
    if not state._tooltip_win:
        return
    tw = state._tooltip_win.winfo_reqwidth()
    th = state._tooltip_win.winfo_reqheight()
    sw = state.root.winfo_screenwidth()
    sh = state.root.winfo_screenheight()
    tx = cx + _px(14)
    ty = cy + _px(10)
    if tx + tw > sw:
        tx = cx - tw - _px(4)
    if ty + th > sh:
        ty = cy - th - _px(4)
    state._tooltip_win.wm_geometry(f"+{tx}+{ty}")


def _show_tooltip(event):
    """Show a screen-aware tooltip with the full 'Will become' filename."""
    item = state.preview_tree.identify_row(event.y)
    col  = state.preview_tree.identify_column(event.x)
    if not item or col != "#2":
        _hide_tooltip()
        return
    if state._tooltip_item == item:
        # Same cell — just track the cursor (with screen-boundary clamping)
        _reposition_tooltip(event.x_root, event.y_root)
        return
    _hide_tooltip()
    state._tooltip_item = item
    text = state.preview_tree.set(item, "renamed")
    if not text:
        return
    state._tooltip_win = tk.Toplevel(state.root)
    state._tooltip_win.wm_overrideredirect(True)
    state._tooltip_win.wm_geometry("+0+0")          # temporary off-screen position
    # wraplength caps very long names so the tooltip never exceeds ~80% of screen width
    wrap = min(_px(700), int(state.root.winfo_screenwidth() * 0.80))
    tk.Label(
        state._tooltip_win, text=text,
        font=("Consolas", 9),
        bg=theme.BG_SURF2, fg=theme.FG_ON_SURF,
        highlightthickness=1, highlightbackground=theme.OUTLINE_VAR,
        padx=_px(8), pady=_px(4),
        wraplength=wrap,
        justify="left",
    ).pack()
    state._tooltip_win.update_idletasks()            # force geometry calculation
    _reposition_tooltip(event.x_root, event.y_root)


def _hide_tooltip(*_):
    """Destroy the tooltip window and reset tracking state."""
    if state._tooltip_win:
        try:
            state._tooltip_win.destroy()
        except tk.TclError:
            pass
        state._tooltip_win = None
    state._tooltip_item = None


# ── Preview ──────────────────────────────────────────────────────────────────

def on_active_dir_changed(*_):
    if state._preview_after:
        state.root.after_cancel(state._preview_after)
    state._preview_after = state.root.after(300, refresh_preview)


def refresh_preview():
    state.preview_tree.delete(*state.preview_tree.get_children())
    p = state.active_dir_var.get().strip()
    if not p or not Path(p).is_dir():
        state.preview_count_var.set("Navigate source to see preview")
        state.src_count_var.set("0 audio files")
        return
    state.preview_count_var.set("Scanning\u2026")
    state.src_count_var.set("Scanning\u2026")
    threading.Thread(target=_scan_thread, args=(p,), daemon=True).start()


def _scan_thread(path_str):
    files = [f for f in Path(path_str).rglob("*")
             if f.suffix.lower() in constants.AUDIO_EXTS and f.is_file()]
    state.root.after(0, lambda: _populate_preview(files))


def _populate_preview(files):
    state.preview_tree.delete(*state.preview_tree.get_children())
    total = len(files)
    shown = min(total, constants.MAX_PREVIEW_ROWS)
    for i, f in enumerate(files[:shown]):
        if state.no_rename_var and state.no_rename_var.get():
            new_name = f.name
        else:
            new_name = f"{f.parent.name}_{f.name}"
        if state.profile_var:
            limit = constants.PROFILES[state.profile_var.get()]["path_limit"]
            if limit is not None:
                d = state.dest_var.get().strip() if state.dest_var else ""
                if d:
                    new_name = _apply_path_limit(new_name, d, limit)
        tag = "odd" if i % 2 else "even"
        state.preview_tree.insert("", "end", values=(f.name, new_name), tags=(tag,))
    state.preview_tree.tag_configure("odd",  background=theme.TREE_ROW_ODD, foreground=theme.FG_ON_SURF)
    state.preview_tree.tag_configure("even", background=theme.BG_SURF2,     foreground=theme.FG_VARIANT)

    s = "s" if total != 1 else ""
    state.src_count_var.set(f"{total} audio file{s}")
    if total == 0:
        state.preview_count_var.set("No audio files in this directory tree")
    elif total > constants.MAX_PREVIEW_ROWS:
        state.preview_count_var.set(f"Showing {shown} of {total} files")
    elif state.no_rename_var and state.no_rename_var.get():
        state.preview_count_var.set(f"{total} file{s}  —  names unchanged")
    else:
        state.preview_count_var.set(f"{total} file{s} will be renamed")
