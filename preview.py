import threading
from pathlib import Path
import tkinter as tk

import state
import theme
import constants
import bpm as bpm_module
from dpi import _px
from operations import _compute_output
from conversion import get_target_extension


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
        font=(theme.FONT_MONO, 9),
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


def _on_bpm_double_click(event):
    """Handle double-click on BPM column to allow manual editing."""
    item = state.preview_tree.identify_row(event.y)
    col = state.preview_tree.identify_column(event.x)
    
    # Only handle double-click on BPM column (#4)
    if not item or col != "#4":
        return
    
    # Get the file path from the row
    file_path_str = state.preview_tree.set(item, "srcpath")
    if not file_path_str:
        return
    
    file_path = Path(file_path_str)
    current_bpm_display = state.preview_tree.set(item, "bpm")
    
    # Don't allow editing if BPM column is hidden or no file
    if not current_bpm_display or current_bpm_display == "":
        return
    
    # Create edit dialog
    dialog = tk.Toplevel(state.root)
    dialog.title("Edit BPM")
    dialog.transient(state.root)
    dialog.grab_set()
    
    # Position near the click
    dialog.geometry(f"+{event.x_root + 20}+{event.y_root}")
    
    # Frame for padding
    frame = tk.Frame(dialog, padx=16, pady=16, bg=theme.BG_SURF1)
    frame.pack(fill="both", expand=True)
    
    # File name label
    tk.Label(frame, text=file_path.name, font=(theme.FONT_UI, 10, "bold"),
             bg=theme.BG_SURF1, fg=theme.FG_ON_SURF).pack(anchor="w", pady=(0, 8))
    
    # Current value
    current_text = f"Current: {current_bpm_display} BPM" if current_bpm_display != "???" else "Current: Not detected"
    tk.Label(frame, text=current_text, font=(theme.FONT_UI, 9),
             bg=theme.BG_SURF1, fg=theme.FG_MUTED).pack(anchor="w")
    
    # Entry frame
    entry_frame = tk.Frame(frame, bg=theme.BG_SURF1)
    entry_frame.pack(fill="x", pady=(12, 8))
    
    tk.Label(entry_frame, text="BPM:", font=(theme.FONT_UI, 10),
             bg=theme.BG_SURF1, fg=theme.FG_ON_SURF).pack(side="left", padx=(0, 8))
    
    bpm_var = tk.StringVar(value="" if current_bpm_display == "???" else current_bpm_display)
    entry = tk.Entry(entry_frame, textvariable=bpm_var, font=(theme.FONT_UI, 11),
                     bg=theme.BG_SURF2, fg=theme.FG_ON_SURF, width=10,
                     highlightbackground=theme.OUTLINE_VAR, highlightthickness=1)
    entry.pack(side="left")
    entry.select_range(0, "end")
    entry.focus()
    
    def save_bpm():
        try:
            bpm_val = float(bpm_var.get().strip())
            if bpm_val < 30 or bpm_val > 300:
                raise ValueError("BPM must be between 30 and 300")
            
            # Update cache
            if bpm_module.set_cached_bpm(file_path, bpm_val):
                # Refresh preview to show new BPM
                refresh_preview()
                
                # Log the change
                for msg in bpm_module.get_log_messages():
                    from log_panel import log
                    log(msg)
            
            dialog.destroy()
        except ValueError as e:
            tk.Label(frame, text=str(e), font=(theme.FONT_UI, 9),
                    bg=theme.BG_SURF1, fg="#ff6b6b").pack(anchor="w", pady=(4, 0))
    
    def cancel():
        dialog.destroy()
    
    # Buttons
    btn_frame = tk.Frame(frame, bg=theme.BG_SURF1)
    btn_frame.pack(fill="x", pady=(12, 0))
    
    tk.Button(btn_frame, text="Cancel", command=cancel,
              bg=theme.BG_SURF2, fg=theme.FG_ON_SURF,
              activebackground=theme.BG_ROOT, activeforeground=theme.FG_ON_SURF,
              relief="flat", padx=12, pady=4).pack(side="right", padx=(8, 0))
    
    tk.Button(btn_frame, text="Save", command=save_bpm,
              bg=theme.CYAN, fg=theme.BG_ROOT,
              activebackground=theme.CYAN_CONT, activeforeground=theme.BG_ROOT,
              relief="flat", padx=12, pady=4).pack(side="right")
    
    # Bind Enter key to save
    entry.bind("<Return>", lambda _: save_bpm())
    entry.bind("<Escape>", lambda _: cancel())


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
    source_root = Path(path_str)
    if state._selected_folders:
        files = []
        for folder_path in state._selected_folders:
            p = Path(folder_path)
            if p.is_dir():
                files += [f for f in p.rglob("*")
                          if f.suffix.lower() in constants.AUDIO_EXTS and f.is_file()]
    else:
        files = []   # empty selection → _populate_preview shows appropriate message
    state.root.after(0, lambda: _populate_preview(files, source_root))


def _populate_preview(files, source_root):
    state.preview_tree.delete(*state.preview_tree.get_children())
    total = len(files)
    if total == 0 and not state._selected_folders:
        state.preview_count_var.set("No folders selected")
        state.src_count_var.set("0 audio files")
        return
    shown = min(total, constants.MAX_PREVIEW_ROWS)

    no_rename   = state.no_rename_var.get()   if state.no_rename_var  else False
    struct_mode = state.struct_mode_var.get() if state.struct_mode_var else "flat"
    path_limit  = constants.PROFILES[state.profile_var.get()]["path_limit"] \
                  if state.profile_var else None
    dest_path   = Path(state.dest_var.get().strip()) \
                  if (state.dest_var and state.dest_var.get().strip()) else source_root

    # Show Subfolder column only when not in flat mode
    sub_width = 0 if struct_mode == "flat" else _px(140)
    state.preview_tree.column("subfolder", width=sub_width, minwidth=0, stretch=False)

    # Show BPM column only when BPM detection is enabled
    bpm_enabled = bool(state.bpm_enabled_var and state.bpm_enabled_var.get())
    bpm_append  = bool(state.bpm_append_var  and state.bpm_append_var.get())
    state.preview_tree.column("bpm", width=_px(60) if bpm_enabled else 0,
                               minwidth=0, stretch=False)

    # Check if conversion is enabled
    convert_enabled = (state.convert_enabled_var and
                       state.convert_enabled_var.get())
    target_format = state.convert_format_var.get() if state.convert_format_var else "wav"

    for i, f in enumerate(files[:shown]):
        # BPM: cache lookup only (no detection in preview)
        bpm_val     = bpm_module.get_cached_bpm(f) if bpm_enabled else None
        bpm_display = str(int(round(bpm_val))) if bpm_val is not None \
                      else ("???" if bpm_enabled else "")

        new_name, rel_sub = _compute_output(
            f, source_root, dest_path, no_rename, struct_mode, path_limit)

        if bpm_enabled and bpm_append:
            if bpm_val is not None:
                new_name, rel_sub = _compute_output(
                    f, source_root, dest_path, no_rename, struct_mode, path_limit,
                    bpm=bpm_val, append_bpm=True)
            else:
                # Visual placeholder — never written to disk
                p        = Path(new_name)
                new_name = p.stem + "_???bpm" + p.suffix

        # Apply extension change and conversion indicator if converting
        if convert_enabled:
            new_name_stem = Path(new_name).stem
            new_name      = new_name_stem + get_target_extension(target_format)
            display_name  = f"{new_name} [c]"
        else:
            display_name = new_name

        tag = "odd" if i % 2 else "even"
        state.preview_tree.insert("", "end",
                                  values=(f.name, display_name, rel_sub,
                                          bpm_display, str(f)),
                                  tags=(tag,))
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
