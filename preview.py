import threading
import wave
import contextlib
from pathlib import Path
import tkinter as tk

import state
import theme
import constants
import bpm as bpm_module
import key as key_module
from dpi import _px
from operations import _compute_output
from conversion import get_target_extension


# ── Filter ───────────────────────────────────────────────────────────────────

_preview_rows: list = []   # all populated row data; used by apply_filter()
_duration_cache: dict = {}  # str(path) → float | None; cleared on each scan


def _get_duration(path: Path) -> float | None:
    """Return duration in seconds from file metadata.

    Fast path for WAV/AIFF (stdlib header read, no subprocess).
    Falls back to ffprobe via pydub for MP3/FLAC/OGG.
    Returns None on any error.
    """
    key = str(path)
    if key in _duration_cache:
        return _duration_cache[key]
    val = None
    try:
        ext = path.suffix.lower()
        if ext == '.wav':
            with contextlib.closing(wave.open(str(path))) as wf:
                val = wf.getnframes() / wf.getframerate()
        elif ext in ('.aif', '.aiff'):
            import aifc
            with contextlib.closing(aifc.open(str(path))) as af:
                val = af.getnframes() / af.getframerate()
        else:
            from pydub.utils import mediainfo
            info = mediainfo(str(path))
            dur = info.get('duration')
            val = float(dur) if dur else None
    except Exception:
        val = None
    _duration_cache[key] = val
    return val


def _parse_query(text):
    """Split query into (plain_text, bpm_spec, note_spec, min_len, max_len).

    bpm_spec:  None | int (exact) | (int, int) (inclusive range)
               Wildcard supported: BPM:15* → 150-159, BPM:1* → 100-199
    note_spec: None | str (uppercase note name, e.g. "C", "F#")
    min_len:   None | float  seconds — MinLength:N
    max_len:   None | float  seconds — MaxLength:N
    """
    plain_parts = []
    bpm_spec = None
    note_spec = None
    min_len = None
    max_len = None
    for token in text.strip().split():
        tl = token.lower()
        if tl.startswith("bpm:"):
            val = token[4:]
            if "-" in val:
                try:
                    lo, hi = val.split("-", 1)
                    bpm_spec = (int(lo), int(hi))
                except ValueError:
                    plain_parts.append(token)
            elif val.endswith("*"):
                # Wildcard: 15* → 150-159, 1* → 100-199, 12* → 120-129
                try:
                    prefix = val[:-1]
                    prefix_num = int(prefix)
                    # Assume 3-digit BPM range; multiplier fills remaining digits
                    # 15* → 150-159 (fill 1 digit), 1* → 100-199 (fill 2 digits)
                    digits_to_fill = 3 - len(prefix)
                    multiplier = 10 ** digits_to_fill
                    lo = prefix_num * multiplier
                    hi = lo + multiplier - 1
                    bpm_spec = (lo, hi)
                except ValueError:
                    plain_parts.append(token)
            else:
                try:
                    bpm_spec = int(val)
                except ValueError:
                    plain_parts.append(token)
        elif tl.startswith("note:"):
            note_spec = token[5:].upper()
        elif tl.startswith("minlength:"):
            try:
                min_len = float(token[10:])
            except ValueError:
                plain_parts.append(token)
        elif tl.startswith("maxlength:"):
            try:
                max_len = float(token[10:])
            except ValueError:
                plain_parts.append(token)
        else:
            plain_parts.append(token)
    return " ".join(plain_parts).lower(), bpm_spec, note_spec, min_len, max_len


def apply_filter(text: str):
    """Show only rows matching the structured query (case-insensitive).

    Supports plain filename substring, BPM:120, BPM:100-130, Note:C,
    MinLength:N, MaxLength:N (seconds) tokens. All tokens AND together.
    When no filter is active, caps display at MAX_PREVIEW_ROWS.
    """
    if state.preview_tree is None:
        return
    has_query = bool(text.strip())
    plain_text, bpm_spec, note_spec, min_len, max_len = _parse_query(text)

    def _matches(row):
        orig    = row[0]
        bpm_val = row[3]
        key_val = row[4]
        dur     = row[6] if len(row) > 6 else None

        if plain_text and plain_text not in orig.lower():
            return False
        if bpm_spec is not None:
            try:
                b = int(bpm_val)
            except (ValueError, TypeError):
                return False
            if isinstance(bpm_spec, tuple):
                if not (bpm_spec[0] <= b <= bpm_spec[1]):
                    return False
            elif b != bpm_spec:
                return False
        if note_spec is not None and key_val.upper() != note_spec:
            return False
        if min_len is not None:
            if dur is None or dur < min_len:
                return False
        if max_len is not None:
            if dur is None or dur > max_len:
                return False
        return True

    state.preview_tree.delete(*state.preview_tree.get_children())
    matched = [row for row in _preview_rows if not has_query or _matches(row)]
    display_rows = matched if has_query else matched[:constants.MAX_PREVIEW_ROWS]

    for i, (orig, renamed, subfolder, bpm_display, key_display, srcpath, *_) in enumerate(display_rows):
        tag = "odd" if i % 2 else "even"
        state.preview_tree.insert("", "end",
                                  values=(orig, renamed, subfolder, bpm_display, key_display, srcpath),
                                  tags=(tag,))

    # Update Deck B count label
    total_cached = len(_preview_rows)
    if state.preview_count_var and total_cached > 0:
        modify_names = bool(state.modify_names_var and state.modify_names_var.get())
        n = len(matched)
        s = "s" if n != 1 else ""
        if has_query:
            state.preview_count_var.set(f"{n} of {total_cached} match")
        elif total_cached > constants.MAX_PREVIEW_ROWS:
            state.preview_count_var.set(f"Showing {constants.MAX_PREVIEW_ROWS} of {total_cached}")
        elif modify_names:
            state.preview_count_var.set(f"{total_cached} file{s} will be renamed")
        else:
            state.preview_count_var.set(f"{total_cached} audio file{s}")


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


def _on_tree_double_click(event):
    """Unified double-click handler for preview tree columns."""
    item = state.preview_tree.identify_row(event.y)
    col = state.preview_tree.identify_column(event.x)
    
    if not item:
        return
    
    # Delegate to appropriate handler based on column
    if col == "#4":  # BPM column
        _on_bpm_double_click(event)
    elif col == "#5":  # Key column
        _on_key_double_click(event)


def _on_key_double_click(event):
    """Handle double-click on Key column to allow manual editing."""
    item = state.preview_tree.identify_row(event.y)
    col = state.preview_tree.identify_column(event.x)
    
    # Only handle double-click on Key column (#5)
    if not item or col != "#5":
        return
    
    # Get the file path from the row
    file_path_str = state.preview_tree.set(item, "srcpath")
    if not file_path_str:
        return
    
    file_path = Path(file_path_str)
    current_key_display = state.preview_tree.set(item, "key")
    
    # Don't allow editing if Key column is hidden or no file
    if not current_key_display or current_key_display == "":
        return
    
    # Create edit dialog
    dialog = tk.Toplevel(state.root)
    dialog.title("Edit Key")
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
    current_text = f"Current: {current_key_display}" if current_key_display != "???" else "Current: Not detected"
    tk.Label(frame, text=current_text, font=(theme.FONT_UI, 9),
             bg=theme.BG_SURF1, fg=theme.FG_MUTED).pack(anchor="w")
    
    # Entry frame
    entry_frame = tk.Frame(frame, bg=theme.BG_SURF1)
    entry_frame.pack(fill="x", pady=(12, 8))
    
    tk.Label(entry_frame, text="Key:", font=(theme.FONT_UI, 10),
             bg=theme.BG_SURF1, fg=theme.FG_ON_SURF).pack(side="left", padx=(0, 8))
    
    key_var = tk.StringVar(value="" if current_key_display == "???" else current_key_display)
    entry = tk.Entry(entry_frame, textvariable=key_var, font=(theme.FONT_UI, 11),
                     bg=theme.BG_SURF2, fg=theme.FG_ON_SURF, width=10,
                     highlightbackground=theme.OUTLINE_VAR, highlightthickness=1)
    entry.pack(side="left")
    entry.select_range(0, "end")
    entry.focus()
    
    # Valid keys hint
    tk.Label(frame, text="Valid: C, C#, D, D#, E, F, F#, G, G#, A, A#, B", 
             font=(theme.FONT_UI, 8),
             bg=theme.BG_SURF1, fg=theme.FG_DIM).pack(anchor="w", pady=(4, 0))
    
    def save_key():
        try:
            key_val = key_var.get().strip()
            
            # Update cache
            if key_module.set_cached_key(file_path, key_val):
                # Refresh preview to show new key
                refresh_preview()
                
                # Log the change
                for msg in key_module.get_log_messages():
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
    
    tk.Button(btn_frame, text="Save", command=save_key,
              bg=theme.CYAN, fg=theme.BG_ROOT,
              activebackground=theme.CYAN_CONT, activeforeground=theme.BG_ROOT,
              relief="flat", padx=12, pady=4).pack(side="right")
    
    # Bind Enter key to save
    entry.bind("<Return>", lambda _: save_key())
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
    global _duration_cache
    _duration_cache = {}           # clear stale entries from previous scan
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
    durations = {f: _get_duration(f) for f in files}
    state.root.after(0, lambda: _populate_preview(files, source_root, durations))


def _populate_preview(files, source_root, durations=None):
    global _preview_rows
    _preview_rows = []
    state.preview_tree.delete(*state.preview_tree.get_children())
    total = len(files)
    if total == 0 and not state._selected_folders:
        state.preview_count_var.set("No folders selected")
        state.src_count_var.set("0 audio files")
        return

    modify_names = bool(state.modify_names_var and state.modify_names_var.get())
    no_rename    = not modify_names
    struct_mode  = state.struct_mode_var.get() if state.struct_mode_var else "flat"
    path_limit   = constants.PROFILES[state.profile_var.get()]["path_limit"] \
                   if state.profile_var else None
    dest_path    = Path(state.dest_var.get().strip()) \
                   if (state.dest_var and state.dest_var.get().strip()) else source_root

    # "Will become" and "Subfolder" columns only shown in Modify mode
    state.preview_tree.column("renamed",
                               width=_px(200) if modify_names else 0,
                               minwidth=0, stretch=False)
    sub_width = _px(140) if (modify_names and struct_mode != "flat") else 0
    state.preview_tree.column("subfolder", width=sub_width, minwidth=0, stretch=False)

    bpm_enabled = bool(state.bpm_enabled_var and state.bpm_enabled_var.get())
    bpm_append  = bool(state.bpm_append_var  and state.bpm_append_var.get())
    key_enabled = bool(state.key_enabled_var and state.key_enabled_var.get())
    key_append  = bool(state.key_append_var  and state.key_append_var.get())

    # Show BPM/Key columns if detection is enabled OR if any file has a cached value
    has_any_bpm = any(bpm_module.get_cached_bpm(f) is not None for f in files)
    has_any_key = any(key_module.get_cached_key(f) is not None for f in files)
    show_bpm = bpm_enabled or has_any_bpm
    show_key = key_enabled or has_any_key

    state.preview_tree.column("bpm", width=_px(60) if show_bpm else 0,
                               minwidth=0, stretch=False)
    state.preview_tree.column("key", width=_px(50) if show_key else 0,
                               minwidth=0, stretch=False)

    # Check if conversion is enabled
    convert_enabled = (state.convert_enabled_var and
                       state.convert_enabled_var.get())
    target_format = state.convert_format_var.get() if state.convert_format_var else "wav"

    for f in files:
        # BPM: always look up cache when column is visible
        bpm_val     = bpm_module.get_cached_bpm(f) if show_bpm else None
        bpm_display = str(int(round(bpm_val))) if bpm_val is not None \
                      else ("???" if bpm_enabled else "")

        # Key: always look up cache when column is visible
        key_val     = key_module.get_cached_key(f) if show_key else None
        key_display = key_val if key_val is not None \
                      else ("???" if key_enabled else "")

        new_name, rel_sub = _compute_output(
            f, source_root, dest_path, no_rename, struct_mode, path_limit,
            bpm=bpm_val if (bpm_enabled and bpm_append) else None,
            append_bpm=bpm_append,
            key=key_val if (key_enabled and key_append) else None,
            append_key=key_append)

        if bpm_enabled and bpm_append and bpm_val is None:
            # Visual placeholder for BPM — never written to disk
            p        = Path(new_name)
            new_name = p.stem + "_???bpm" + p.suffix

        if key_enabled and key_append and key_val is None:
            # Visual placeholder for Key — never written to disk
            p        = Path(new_name)
            new_name = p.stem + "_???" + p.suffix

        # Apply extension change and conversion indicator if converting
        if convert_enabled:
            new_name_stem = Path(new_name).stem
            new_name      = new_name_stem + get_target_extension(target_format)
            display_name  = f"{new_name} [c]"
        else:
            display_name = new_name

        duration_sec = durations.get(f) if durations else None
        _preview_rows.append((f.name, display_name, rel_sub, bpm_display, key_display, str(f), duration_sec))

    state.preview_tree.tag_configure("odd",  background=theme.TREE_ROW_ODD, foreground=theme.FG_ON_SURF)
    state.preview_tree.tag_configure("even", background=theme.BG_SURF2,     foreground=theme.FG_VARIANT)

    s = "s" if total != 1 else ""
    state.src_count_var.set(f"{total} audio file{s}")
    if total == 0:
        state.preview_count_var.set("No audio files in this directory tree")
        return

    # Apply active filter — also updates preview_count_var
    filter_text = state.preview_filter_var.get() if state.preview_filter_var else ""
    apply_filter(filter_text)
