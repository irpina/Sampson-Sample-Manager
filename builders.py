from pathlib import Path
import tkinter as tk
import tkinter.ttk as ttk
import customtkinter as ctk

import state
import theme
import constants
import browser
import preview
import playback
import log_panel
import operations
from dpi import _px


# ── Header ───────────────────────────────────────────────────────────────────

def _get_logo_path():
    """Get path to logo file, handling both dev and PyInstaller bundles."""
    import sys
    if hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / "sampsontransparent2.png"
    return Path("sampsontransparent2.png")


def build_header(parent):
    frame = ctk.CTkFrame(parent, fg_color=theme.BG_SURF2, corner_radius=0, height=_px(52))
    frame.pack_propagate(False)

    # Logo image using tkinter (no PIL required)
    try:
        logo_path = _get_logo_path()
        logo_tk = tk.PhotoImage(file=str(logo_path))
        # Subsample to fit header (reduce size by factor based on DPI)
        # Original is ~1125px wide, target ~150-200px at 96 DPI
        factor = max(1, logo_tk.width() // _px(150))
        if factor > 1:
            logo_tk = logo_tk.subsample(factor, factor)
        logo_lbl = tk.Label(frame, image=logo_tk, bg=theme.BG_SURF2)
        logo_lbl.image = logo_tk  # Keep reference
        logo_lbl.pack(side="left", padx=(_px(16), _px(8)), pady=_px(6))
    except Exception:
        # Fallback to text if image fails
        ctk.CTkLabel(frame, text="SAMPSON",
                     font=(theme.FONT_UI, 15, "bold"),
                     text_color=theme.FG_ON_SURF).pack(side="left", padx=20, pady=12)
    
    ctk.CTkLabel(frame, text="Universal Audio Sample Manager",
                 font=(theme.FONT_UI, 9),
                 text_color=theme.FG_DIM).pack(side="left", padx=2)

    toggle_icon = "☀" if state._is_dark else "☾"
    toggle_tip  = "Light" if state._is_dark else "Dark"
    lbl = ctk.CTkLabel(frame, text=f"{toggle_icon}  {toggle_tip}",
                       font=(theme.FONT_UI, 9),
                       text_color=theme.FG_MUTED,
                       cursor="hand2")
    lbl.pack(side="right", padx=12)
    lbl.bind("<Button-1>", lambda _e: toggle_theme())
    lbl.bind("<Enter>",    lambda _e: lbl.configure(text_color=theme.FG_ON_SURF))
    lbl.bind("<Leave>",    lambda _e: lbl.configure(text_color=theme.FG_MUTED))

    return frame


# ── Deck A — Source ──────────────────────────────────────────────────────────

def build_deck_a(parent):
    frame = ctk.CTkFrame(parent, fg_color=theme.BG_SURF1,
                         corner_radius=12,
                         border_width=1, border_color=theme.CARD_BORDER)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    # Strip: transparent so card's rounded corners show through
    strip = tk.Frame(frame, bg=theme.BG_SURF1, height=_px(14))
    strip.grid(row=0, column=0, sticky="ew")
    strip.grid_propagate(False)
    tk.Frame(strip, bg=theme.CYAN, width=_px(3), height=_px(14)).pack(side="left")
    tk.Label(strip, text="A", font=(theme.FONT_UI, 11, "bold"),
                 bg=theme.BG_SURF1, fg=theme.CYAN).pack(side="left", padx=(10, 4))
    tk.Label(strip, text="·", font=(theme.FONT_UI, 9),
                 bg=theme.BG_SURF1, fg=theme.FG_DIM).pack(side="left", padx=(0, 4))
    tk.Label(strip, text="SOURCE", font=(theme.FONT_UI, 8),
                 bg=theme.BG_SURF1, fg=theme.FG_MUTED).pack(side="left")

    # Source path row
    path_row = ctk.CTkFrame(frame, fg_color="transparent")
    path_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(4, 0))
    path_row.columnconfigure(0, weight=1)
    state.source_var = tk.StringVar()
    ctk.CTkEntry(path_row, textvariable=state.source_var,
                 fg_color=theme.BG_SURF2, text_color=theme.FG_ON_SURF,
                 border_color=theme.OUTLINE_VAR, border_width=1,
                 corner_radius=6).grid(row=0, column=0, sticky="ew", padx=(0, 8))
    ctk.CTkButton(path_row, text="Browse",
                  fg_color=theme.CYAN_CONT, text_color=theme.ON_CYAN_CONT,
                  hover_color=theme.CYAN, corner_radius=8,
                  command=browser.browse_source).grid(row=0, column=1)

    # Nav bar
    nav_bar = ctk.CTkFrame(frame, fg_color=theme.BG_SURF2, corner_radius=6)
    nav_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 0))
    nav_bar.columnconfigure(1, weight=1)
    ctk.CTkButton(nav_bar, text="↑", width=_px(32), corner_radius=6,
                  fg_color="transparent", text_color=theme.FG_MUTED,
                  hover_color=theme.CYAN_CONT,
                  command=browser.nav_up).grid(row=0, column=0, padx=(4, 6), pady=4)
    state.nav_path_var = tk.StringVar(value="—")
    _nav_lbl = ctk.CTkLabel(nav_bar, text="—",
                             font=(theme.FONT_MONO, 8), text_color=theme.FG_DIM,
                             anchor="w")
    _nav_lbl.grid(row=0, column=1, sticky="ew", padx=(0, 6))
    state.nav_path_var.trace_add("write",
        lambda *_: _nav_lbl.configure(text=state.nav_path_var.get()))

    # File browser (ttk.Treeview with checkbox column)
    browser_wrap = ctk.CTkFrame(frame, fg_color=theme.BG_SURF2, corner_radius=6)
    browser_wrap.grid(row=3, column=0, sticky="nsew", padx=12, pady=(4, 0))
    browser_wrap.columnconfigure(0, weight=1)
    browser_wrap.rowconfigure(0, weight=1)
    state.dir_browser = ttk.Treeview(browser_wrap, style="Browser.Treeview",
        columns=("chk", "name", "path", "itype"),
        show="", selectmode="browse")
    state.dir_browser.heading("chk",   text="")
    state.dir_browser.heading("name",  text="")
    state.dir_browser.heading("path",  text="")
    state.dir_browser.heading("itype", text="")
    state.dir_browser.column("chk",   width=_px(28), minwidth=_px(28), stretch=False, anchor="center")
    state.dir_browser.column("name",  stretch=True)
    state.dir_browser.column("path",  width=0, minwidth=0, stretch=False)
    state.dir_browser.column("itype", width=0, minwidth=0, stretch=False)
    state.dir_browser.grid(row=0, column=0, sticky="nsew")
    state.dir_browser.bind("<ButtonRelease-1>", browser.on_browser_click)
    bsb = ctk.CTkScrollbar(browser_wrap, orientation="vertical",
                            command=state.dir_browser.yview,
                            button_color=theme.FG_MUTED,
                            button_hover_color=theme.CYAN)
    bsb.grid(row=0, column=1, sticky="ns")
    state.dir_browser.configure(yscrollcommand=bsb.set)

    # File count row + Select/Deselect All buttons
    count_row = ctk.CTkFrame(frame, fg_color="transparent")
    count_row.grid(row=4, column=0, sticky="ew", padx=12, pady=(4, 8))
    state.src_count_var = tk.StringVar(value="0 audio files")
    _src_lbl = ctk.CTkLabel(count_row, text="0 audio files",
                             font=(theme.FONT_UI, 9), text_color=theme.CYAN, anchor="w")
    _src_lbl.pack(side="left")
    state.src_count_var.trace_add("write",
        lambda *_: _src_lbl.configure(text=state.src_count_var.get()))
    ctk.CTkButton(count_row, text="\u2610 All", width=_px(64),
                  fg_color=theme.BG_SURF2, text_color=theme.FG_MUTED,
                  hover_color=theme.CYAN_CONT, corner_radius=6,
                  command=browser.deselect_all_visible).pack(side="right")
    ctk.CTkButton(count_row, text="\u2611 All", width=_px(64),
                  fg_color=theme.BG_SURF2, text_color=theme.FG_MUTED,
                  hover_color=theme.CYAN_CONT, corner_radius=6,
                  command=browser.select_all_visible).pack(side="right", padx=(0, 4))

    frame.grid_propagate(False)
    return frame


# ── Centre — Options ─────────────────────────────────────────────────────────

def _add_tooltip(widget, text):
    """Add a hover tooltip to a widget."""
    def on_enter(e):
        x, y = widget.winfo_pointerxy()
        tooltip = tk.Toplevel(widget)
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{x+10}+{y+10}")
        lbl = tk.Label(tooltip, text=text, bg=theme.BG_SURF2, fg=theme.FG_ON_SURF,
                      font=(theme.FONT_UI, 9), padx=8, pady=4)
        lbl.pack()
        widget._tooltip = tooltip
    def on_leave(e):
        if hasattr(widget, '_tooltip'):
            widget._tooltip.destroy()
            delattr(widget, '_tooltip')
    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)


def build_center(parent):
    frame = ctk.CTkFrame(parent, fg_color=theme.BG_SURFACE,
                         corner_radius=12,
                         border_width=1, border_color=theme.CARD_BORDER)
    frame.columnconfigure(0, weight=1)
    frame.columnconfigure(1, weight=1)

    state.move_var        = tk.BooleanVar(value=False)
    state.dry_var         = tk.BooleanVar(value=True)
    state.no_rename_var   = tk.BooleanVar(value=False)
    state.profile_var     = tk.StringVar(value="Generic")
    state.struct_mode_var = tk.StringVar(value="flat")

    # ── File options (compact side-by-side layout) ────────────────────────────
    _cb_kw = dict(
        fg_color=theme.CYAN, hover_color=theme.CYAN_CONT,
        checkmark_color=theme.BG_ROOT,
        border_color=theme.OUTLINE_VAR,
        text_color=theme.FG_ON_SURF,
        corner_radius=4,
        font=(theme.FONT_UI, 10),
    )
    # Row 0: Move files | Dry run (side by side)
    cb_move = ctk.CTkCheckBox(frame, text="Move files",
                              variable=state.move_var, **_cb_kw)
    cb_move.grid(row=0, column=0, sticky="w", padx=(16, 8), pady=(16, 4))
    _add_tooltip(cb_move, "Move files instead of copying (copy by default)")

    cb_dry = ctk.CTkCheckBox(frame, text="Dry run",
                             variable=state.dry_var, **_cb_kw)
    cb_dry.grid(row=0, column=1, sticky="w", padx=(8, 16), pady=(16, 4))
    _add_tooltip(cb_dry, "Preview changes without writing any files")

    # Row 1: Keep names (full width)
    cb_rename = ctk.CTkCheckBox(frame, text="Keep original names",
                                variable=state.no_rename_var, **_cb_kw)
    cb_rename.grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))
    _add_tooltip(cb_rename, "Don't add parent folder prefix to filenames")

    ctk.CTkFrame(frame, fg_color=theme.OUTLINE_VAR, height=1, corner_radius=0).grid(
        row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 6))

    # ── Folder structure (compact horizontal layout) ──────────────────────────
    ctk.CTkLabel(frame, text="Output structure",
                 font=(theme.FONT_UI, 9), text_color=theme.FG_MUTED,
                 anchor="center").grid(row=3, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 4))

    _rb_kw = dict(
        fg_color=theme.CYAN, hover_color=theme.CYAN_CONT,
        border_color=theme.OUTLINE_VAR,
        text_color=theme.FG_ON_SURF,
        font=(theme.FONT_UI, 10),
    )
    struct_frame = ctk.CTkFrame(frame, fg_color="transparent")
    struct_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12)

    rb_flat = ctk.CTkRadioButton(struct_frame, text="Flat", variable=state.struct_mode_var,
                                  value="flat", **_rb_kw)
    rb_flat.pack(side="left", padx=4)
    _add_tooltip(rb_flat, "All files together in one folder")

    rb_mirror = ctk.CTkRadioButton(struct_frame, text="Mirror", variable=state.struct_mode_var,
                                    value="mirror", **_rb_kw)
    rb_mirror.pack(side="left", padx=4)
    _add_tooltip(rb_mirror, "Preserve source folder hierarchy")

    rb_parent = ctk.CTkRadioButton(struct_frame, text="By parent", variable=state.struct_mode_var,
                                    value="parent", **_rb_kw)
    rb_parent.pack(side="left", padx=4)
    _add_tooltip(rb_parent, "One folder per parent directory")

    ctk.CTkFrame(frame, fg_color=theme.OUTLINE_VAR, height=1, corner_radius=0).grid(
        row=5, column=0, columnspan=2, sticky="ew", padx=16, pady=(8, 6))

    # ── Hardware profile ──────────────────────────────────────────────────────
    ctk.CTkLabel(frame, text="Target device",
                 font=(theme.FONT_UI, 9), text_color=theme.FG_MUTED,
                 anchor="center").grid(row=6, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 4))

    ctk.CTkOptionMenu(frame, variable=state.profile_var,
                      values=constants.PROFILE_NAMES,
                      fg_color=theme.BG_SURF2, text_color=theme.FG_ON_SURF,
                      button_color=theme.CYAN_CONT, button_hover_color=theme.CYAN,
                      dropdown_fg_color=theme.BG_SURF1,
                      dropdown_text_color=theme.FG_ON_SURF,
                      dropdown_hover_color=theme.CYAN_CONT,
                      corner_radius=8).grid(row=7, column=0, columnspan=2, sticky="ew", padx=16)

    # Row 8 is the expanding spacer
    frame.rowconfigure(8, weight=1)

    # ── Transport controls ────────────────────────────────────────────────────
    transport_frame = ctk.CTkFrame(frame, fg_color="transparent")
    transport_frame.grid(row=9, column=0, columnspan=2, pady=(20, 10))

    _tr_kw = dict(
        width=_px(36), corner_radius=8,
        fg_color=theme.BG_SURF2, text_color=theme.FG_MUTED,
        hover_color=theme.CYAN_CONT,
    )
    state.transport_prev_btn = ctk.CTkButton(
        transport_frame, text="◀", command=playback.prev_file, **_tr_kw)
    state.transport_prev_btn.pack(side="left", padx=4)
    state.transport_prev_btn.configure(state="disabled")

    state.transport_play_btn = ctk.CTkButton(
        transport_frame, text="▶", command=playback.play, **_tr_kw)
    state.transport_play_btn.pack(side="left", padx=4)

    state.transport_next_btn = ctk.CTkButton(
        transport_frame, text="▶▶", command=playback.next_file, **_tr_kw)
    state.transport_next_btn.pack(side="left", padx=4)
    state.transport_next_btn.configure(state="disabled")

    ctk.CTkFrame(frame, fg_color=theme.OUTLINE_VAR, height=1, corner_radius=0).grid(
        row=10, column=0, columnspan=2, sticky="ew", padx=16, pady=(0, 14))

    state.run_btn = ctk.CTkButton(frame, text="Run",
                                   font=(theme.FONT_UI, 12, "bold"),
                                   fg_color=theme.CYAN, text_color=theme.BG_ROOT,
                                   hover_color=theme.CYAN_CONT, corner_radius=8,
                                   command=operations.run_tool)
    state.run_btn.grid(row=11, column=0, columnspan=2, padx=16, sticky="ew")

    ctk.CTkButton(frame, text="Clear log",
                  fg_color="transparent", text_color=theme.FG_MUTED,
                  hover_color=theme.BG_SURF2, border_width=1,
                  border_color=theme.OUTLINE_VAR, corner_radius=8,
                  command=log_panel.clear_log).grid(row=12, column=0, columnspan=2, padx=16, pady=(10, 16))

    # Ensure critical UI elements don't collapse on resize
    # Row 8 is the expanding spacer - it can shrink
    # Rows 6-7 (profile), 9 (transport), 11-12 (buttons) need minimum height
    frame.rowconfigure(6, weight=0, minsize=_px(20))
    frame.rowconfigure(7, weight=0, minsize=_px(40))
    frame.rowconfigure(9, weight=0, minsize=_px(50))
    frame.rowconfigure(11, weight=0, minsize=_px(45))
    frame.rowconfigure(12, weight=0, minsize=_px(50))

    return frame


# ── Deck B — Destination ─────────────────────────────────────────────────────

def build_deck_b(parent):
    frame = ctk.CTkFrame(parent, fg_color=theme.BG_SURF1,
                         corner_radius=12,
                         border_width=1, border_color=theme.CARD_BORDER)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    # Strip: transparent so card's rounded corners show through
    strip = tk.Frame(frame, bg=theme.BG_SURF1, height=_px(14))
    strip.grid(row=0, column=0, columnspan=2, sticky="ew")
    strip.grid_propagate(False)
    tk.Frame(strip, bg=theme.AMBER, width=_px(3), height=_px(14)).pack(side="left")
    tk.Label(strip, text="B", font=(theme.FONT_UI, 11, "bold"),
                 bg=theme.BG_SURF1, fg=theme.AMBER).pack(side="left", padx=(10, 4))
    tk.Label(strip, text="·", font=(theme.FONT_UI, 9),
                 bg=theme.BG_SURF1, fg=theme.FG_DIM).pack(side="left", padx=(0, 4))
    tk.Label(strip, text="DESTINATION", font=(theme.FONT_UI, 8),
                 bg=theme.BG_SURF1, fg=theme.FG_MUTED).pack(side="left")

    # Dest path row
    path_row = ctk.CTkFrame(frame, fg_color="transparent")
    path_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(4, 0))
    path_row.columnconfigure(0, weight=1)
    state.dest_var = tk.StringVar()
    ctk.CTkEntry(path_row, textvariable=state.dest_var,
                 fg_color=theme.BG_SURF2, text_color=theme.FG_ON_SURF,
                 border_color=theme.AMBER_CONT, border_width=1,
                 corner_radius=6).grid(row=0, column=0, sticky="ew", padx=(0, 8))
    ctk.CTkButton(path_row, text="Browse",
                  fg_color=theme.AMBER_CONT, text_color=theme.ON_AMBER_CONT,
                  hover_color=theme.AMBER, corner_radius=8,
                  command=browser.browse_dest).grid(row=0, column=1)

    # Preview count
    state.preview_count_var = tk.StringVar(value="Navigate source to see preview")
    _prev_lbl = ctk.CTkLabel(frame, text="Navigate source to see preview",
                              font=(theme.FONT_UI, 9), text_color=theme.AMBER,
                              anchor="w")
    _prev_lbl.grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 4))
    state.preview_count_var.trace_add("write",
        lambda *_: _prev_lbl.configure(text=state.preview_count_var.get()))

    # Treeview — stays ttk (no CTK equivalent)
    state.preview_tree = ttk.Treeview(frame, style="Preview.Treeview",
                                      columns=("original", "renamed", "subfolder", "srcpath"),
                                      show="headings", selectmode="browse")
    state.preview_tree.heading("original",  text="Original name")
    state.preview_tree.heading("renamed",   text="Will become")
    state.preview_tree.heading("subfolder", text="Subfolder")
    state.preview_tree.column("original",  width=_px(160), anchor="w", minwidth=_px(80))
    state.preview_tree.column("renamed",   width=_px(200), anchor="w", minwidth=_px(80))
    state.preview_tree.column("subfolder", width=0,        anchor="w", minwidth=0, stretch=False)
    state.preview_tree.column("srcpath",   width=0,        anchor="w", minwidth=0, stretch=False)
    state.preview_tree.heading("srcpath", text="")
    state.preview_tree.grid(row=3, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))

    vsb = ctk.CTkScrollbar(frame, orientation="vertical",
                            command=state.preview_tree.yview,
                            button_color=theme.FG_MUTED,
                            button_hover_color=theme.AMBER)
    vsb.grid(row=3, column=1, sticky="ns", padx=(0, 8), pady=(0, 12))
    state.preview_tree.configure(yscrollcommand=vsb.set)

    state.preview_tree.bind("<Motion>",          preview._show_tooltip)
    state.preview_tree.bind("<Leave>",           preview._hide_tooltip)
    state.preview_tree.bind("<ButtonRelease-1>", playback.on_tree_select)
    state.preview_tree.bind("<KeyRelease-Up>",   playback.on_arrow_key)
    state.preview_tree.bind("<KeyRelease-Down>", playback.on_arrow_key)

    frame.grid_propagate(False)
    return frame


# ── Status bar ───────────────────────────────────────────────────────────────

def build_status_bar(parent):
    frame = ctk.CTkFrame(parent, fg_color=theme.BG_SURF2, corner_radius=0, height=_px(36))
    frame.pack_propagate(False)

    state.progress_var = tk.IntVar(value=0)
    ttk.Progressbar(frame, variable=state.progress_var, maximum=100,
                    style="MD3.Horizontal.TProgressbar",
                    mode="determinate", length=_px(160)).pack(side="left", padx=(16, 10), pady=12)

    state._status_dot = ctk.CTkLabel(frame, text="●", font=(theme.FONT_UI, 8),
                                      text_color=theme.FG_DIM)
    state._status_dot.pack(side="left", padx=(0, 6))

    state.status_var = tk.StringVar(value="Ready")
    _status_lbl = ctk.CTkLabel(frame, text="Ready",
                                font=(theme.FONT_UI, 9), text_color=theme.FG_MUTED,
                                anchor="w")
    _status_lbl.pack(side="left", fill="x", expand=True)
    state.status_var.trace_add("write",
        lambda *_: _status_lbl.configure(text=state.status_var.get()))

    ctk.CTkLabel(frame, text="v0.2.3",
                 font=(theme.FONT_UI, 8), text_color=theme.FG_DIM,
                 anchor="e").pack(side="right", padx=14)

    return frame


# ── Log panel ────────────────────────────────────────────────────────────────

def build_log_panel(parent):
    frame = ctk.CTkFrame(parent, fg_color=theme.BG_SURF1,
                         corner_radius=12,
                         border_width=1, border_color=theme.CARD_BORDER)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(1, weight=1)

    ctk.CTkLabel(frame, text="Operation log",
                 font=(theme.FONT_UI, 9),
                 text_color=theme.FG_DIM, anchor="w").grid(
        row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(6, 2))

    state.log_text = tk.Text(frame, bg=theme.BG_SURF2, fg=theme.FG_ON_SURF,
                             font=(theme.FONT_MONO, 9), bd=0, relief="flat",
                             insertbackground=theme.CYAN, selectbackground=theme.CYAN_CONT,
                             state="disabled", wrap="none", height=8)
    state.log_text.grid(row=1, column=0, sticky="nsew", padx=(14, 0), pady=(0, 10))

    lvsb = ctk.CTkScrollbar(frame, orientation="vertical",
                             command=state.log_text.yview,
                             button_color=theme.FG_MUTED,
                             button_hover_color=theme.CYAN)
    lvsb.grid(row=1, column=1, sticky="ns", padx=(0, 6), pady=(0, 10))

    lhsb = ctk.CTkScrollbar(frame, orientation="horizontal",
                             command=state.log_text.xview,
                             button_color=theme.FG_MUTED,
                             button_hover_color=theme.CYAN)
    lhsb.grid(row=2, column=0, sticky="ew", padx=(14, 0), pady=(0, 6))

    state.log_text.configure(yscrollcommand=lvsb.set, xscrollcommand=lhsb.set)
    return frame


# ── Theme toggle ─────────────────────────────────────────────────────────────

def toggle_theme():
    """
    Switch between dark and light mode.

    Saves the current source / destination / active-directory paths, tears
    down all widgets, rebuilds with the new theme, then restores paths.
    """
    preview._hide_tooltip()
    playback.stop()

    saved_source      = state.source_var.get()      if state.source_var      else ""
    saved_dest        = state.dest_var.get()        if state.dest_var        else ""
    saved_active      = state.active_dir_var.get()  if state.active_dir_var  else ""
    saved_profile     = state.profile_var.get()     if state.profile_var     else "Generic"
    saved_struct_mode = state.struct_mode_var.get() if state.struct_mode_var else "flat"

    state._is_dark = not state._is_dark
    theme._apply_theme_colors(state._is_dark)
    ctk.set_appearance_mode("dark" if state._is_dark else "light")

    for w in state.root.winfo_children():
        w.destroy()

    state.root.configure(fg_color=theme.BG_ROOT)
    theme.setup_styles()
    build_app()

    if saved_profile:
        state.profile_var.set(saved_profile)
    if saved_struct_mode:
        state.struct_mode_var.set(saved_struct_mode)
    if saved_dest:
        state.dest_var.set(saved_dest)
    if saved_source:
        state.source_var.set(saved_source)   # trace → navigate_to(source_root)

    if saved_active and saved_active != saved_source and Path(saved_active).is_dir():
        state.root.after(50, lambda: browser.navigate_to(saved_active))


# ── App assembly ─────────────────────────────────────────────────────────────

def build_app():
    state.active_dir_var = tk.StringVar()

    root_frame = tk.Frame(state.root, bg=theme.BG_ROOT)
    root_frame.pack(fill="both", expand=True)

    root_frame.columnconfigure(0, weight=3, minsize=_px(280), uniform="decks")
    root_frame.columnconfigure(1, weight=2, minsize=_px(180))
    root_frame.columnconfigure(2, weight=3, minsize=_px(280), uniform="decks")
    root_frame.rowconfigure(1, weight=3, minsize=_px(380))
    root_frame.rowconfigure(3, weight=1, minsize=_px(100))

    build_header(root_frame).grid(row=0, column=0, columnspan=3, sticky="ew")
    tk.Frame(root_frame, bg=theme.OUTLINE_VAR, height=1).grid(
        row=0, column=0, columnspan=3, sticky="sew")

    build_deck_a(root_frame).grid(row=1, column=0, sticky="nsew", padx=(10, 4), pady=8)
    build_center(root_frame).grid(row=1, column=1, sticky="nsew", padx=4,       pady=8)
    build_deck_b(root_frame).grid(row=1, column=2, sticky="nsew", padx=(4, 10), pady=8)

    build_status_bar(root_frame).grid(row=2, column=0, columnspan=3, sticky="ew", padx=10)
    tk.Frame(root_frame, bg=theme.OUTLINE_VAR, height=1).grid(
        row=2, column=0, columnspan=3, sticky="sew", padx=10)

    build_log_panel(root_frame).grid(row=3, column=0, columnspan=3, sticky="nsew",
                                     padx=10, pady=(4, 10))

    log_panel.setup_log_tags()
    state.active_dir_var.trace_add("write", preview.on_active_dir_changed)
    state.active_dir_var.trace_add("write", lambda *_: playback.reset())
    state.source_var.trace_add("write", browser.on_source_var_changed)
    state.no_rename_var.trace_add("write",   lambda *_: preview.refresh_preview())
    state.profile_var.trace_add("write",    lambda *_: preview.refresh_preview())
    state.struct_mode_var.trace_add("write", lambda *_: preview.refresh_preview())
    state.root.bind("<Return>", lambda _e: operations.run_tool())
