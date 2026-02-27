from pathlib import Path
import tkinter as tk
import tkinter.ttk as ttk

import state
import theme
import constants
import browser
import preview
import log_panel
import operations
from dpi import _px


# ── Header ───────────────────────────────────────────────────────────────────

def build_header(parent):
    frame = tk.Frame(parent, bg=theme.BG_SURF2, height=_px(52))
    frame.pack_propagate(False)

    tk.Label(frame, text="Dirtywave File Helper",
             font=("Segoe UI", 15, "bold"),
             bg=theme.BG_SURF2, fg=theme.FG_ON_SURF).pack(side="left", padx=20, pady=12)
    tk.Label(frame, text="Audio Sample Organiser",
             font=("Segoe UI", 9),
             bg=theme.BG_SURF2, fg=theme.FG_DIM).pack(side="left", padx=2)

    # Theme toggle — right-aligned label that acts as a button.
    # Shows sun (☀) in dark mode (click to go light) and moon (☾) in light mode.
    toggle_icon = "☀" if state._is_dark else "☾"
    toggle_tip  = "Light" if state._is_dark else "Dark"
    lbl = tk.Label(frame, text=f"{toggle_icon}  {toggle_tip}",
                   font=("Segoe UI", 9),
                   bg=theme.BG_SURF2, fg=theme.FG_MUTED,
                   cursor="hand2", padx=6, pady=4)
    lbl.pack(side="right", padx=12)
    lbl.bind("<Button-1>", lambda _e: toggle_theme())
    lbl.bind("<Enter>",    lambda _e: lbl.configure(fg=theme.FG_ON_SURF))
    lbl.bind("<Leave>",    lambda _e: lbl.configure(fg=theme.FG_MUTED))

    return frame


# ── Deck A — Source ──────────────────────────────────────────────────────────

def build_deck_a(parent):
    frame = tk.Frame(parent, bg=theme.BG_SURF1,
                     highlightthickness=1,
                     highlightbackground=theme.CARD_BORDER,
                     highlightcolor=theme.CYAN)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    # Strip: thin left accent line + subtle tinted bg
    strip = tk.Frame(frame, bg=theme.CYAN_STRIP)
    strip.grid(row=0, column=0, sticky="ew")
    tk.Frame(strip, bg=theme.CYAN, width=_px(3)).pack(side="left", fill="y")
    tk.Label(strip, text="A", font=("Segoe UI", 11, "bold"),
             bg=theme.CYAN_STRIP, fg=theme.CYAN).pack(side="left", padx=(10, 4), pady=8)
    tk.Label(strip, text="·", font=("Segoe UI", 9),
             bg=theme.CYAN_STRIP, fg=theme.FG_DIM).pack(side="left", padx=(0, 4))
    tk.Label(strip, text="SOURCE", font=("Segoe UI", 8),
             bg=theme.CYAN_STRIP, fg=theme.FG_MUTED).pack(side="left")

    # Source path row
    path_row = tk.Frame(frame, bg=theme.BG_SURF1)
    path_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(12, 0))
    path_row.columnconfigure(0, weight=1)
    state.source_var = tk.StringVar()
    ttk.Entry(path_row, textvariable=state.source_var).grid(
        row=0, column=0, sticky="ew", padx=(0, 8))
    ttk.Button(path_row, text="Browse", style="TonalA.TButton",
               command=browser.browse_source).grid(row=0, column=1)

    # Nav bar
    nav_bar = tk.Frame(frame, bg=theme.BG_SURF2)
    nav_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 0))
    nav_bar.columnconfigure(1, weight=1)
    ttk.Button(nav_bar, text="↑", style="Icon.TButton",
               command=browser.nav_up).grid(row=0, column=0, padx=(4, 6), pady=4)
    state.nav_path_var = tk.StringVar(value="—")
    tk.Label(nav_bar, textvariable=state.nav_path_var,
             font=("Consolas", 8), bg=theme.BG_SURF2, fg=theme.FG_DIM,
             anchor="w").grid(row=0, column=1, sticky="ew", padx=(0, 6))

    # File browser — press/release bindings so navigation only fires on release
    browser_wrap = tk.Frame(frame, bg=theme.BG_SURF2)
    browser_wrap.grid(row=3, column=0, sticky="nsew", padx=12, pady=(4, 0))
    browser_wrap.columnconfigure(0, weight=1)
    browser_wrap.rowconfigure(0, weight=1)
    state.dir_browser = tk.Listbox(
        browser_wrap,
        bg=theme.BG_SURF2, fg=theme.FG_ON_SURF,
        selectbackground=theme.CYAN_CONT, selectforeground=theme.ON_CYAN_CONT,
        font=("Segoe UI", 10), bd=0, relief="flat",
        activestyle="none", highlightthickness=0,
    )
    state.dir_browser.grid(row=0, column=0, sticky="nsew")
    state.dir_browser.bind("<ButtonPress-1>",   browser.on_browser_press)
    state.dir_browser.bind("<ButtonRelease-1>", browser.on_browser_release)
    bsb = ttk.Scrollbar(browser_wrap, orient="vertical", command=state.dir_browser.yview,
                        style="Dark.Vertical.TScrollbar")
    bsb.grid(row=0, column=1, sticky="ns")
    state.dir_browser.configure(yscrollcommand=bsb.set)

    # File count
    state.src_count_var = tk.StringVar(value="0 audio files")
    tk.Label(frame, textvariable=state.src_count_var,
             font=("Segoe UI", 9), bg=theme.BG_SURF1, fg=theme.CYAN,
             anchor="w").grid(row=4, column=0, sticky="w", padx=12, pady=(6, 10))

    # Prevent the frame from shrinking/growing to fit its children —
    # size is dictated entirely by the parent grid.
    frame.grid_propagate(False)
    return frame


# ── Centre — Options ─────────────────────────────────────────────────────────

def build_center(parent):
    frame = tk.Frame(parent, bg=theme.BG_SURFACE,
                     highlightthickness=1,
                     highlightbackground=theme.CARD_BORDER)
    frame.columnconfigure(0, weight=1)
    # Row 5 is the expanding spacer — pushes Run/Clear to the bottom
    frame.rowconfigure(5, weight=1)

    state.move_var      = tk.BooleanVar(value=False)
    state.dry_var       = tk.BooleanVar(value=True)
    state.no_rename_var = tk.BooleanVar(value=False)
    state.profile_var   = tk.StringVar(value="Generic")

    ttk.Checkbutton(frame, text="Move files  (copy by default)",
                    variable=state.move_var, style="Dark.TCheckbutton").grid(
        row=0, column=0, sticky="w", padx=16, pady=(16, 2))

    ttk.Checkbutton(frame, text="Dry run  (no changes written)",
                    variable=state.dry_var, style="Dark.TCheckbutton").grid(
        row=1, column=0, sticky="w", padx=16)

    ttk.Checkbutton(frame, text="Keep original names  (no prefix)",
                    variable=state.no_rename_var, style="Dark.TCheckbutton").grid(
        row=2, column=0, sticky="w", padx=16, pady=(2, 0))

    ttk.Separator(frame, orient="horizontal", style="Dark.TSeparator").grid(
        row=3, column=0, sticky="ew", padx=16, pady=(10, 8))

    tk.Label(frame, text="Hardware profile",
             font=("Segoe UI", 9), bg=theme.BG_SURFACE, fg=theme.FG_MUTED,
             anchor="w").grid(row=4, column=0, sticky="w", padx=16, pady=(0, 4))

    ttk.Combobox(frame, textvariable=state.profile_var,
                 values=constants.PROFILE_NAMES,
                 state="readonly", width=14).grid(
        row=5, column=0, sticky="w", padx=16)

    # row 5 also has the combobox but the frame row weight lets it expand below;
    # the real spacer effect comes from the combobox not filling vertically —
    # we add a dedicated spacer row just below it.
    frame.rowconfigure(6, weight=1)
    frame.rowconfigure(5, weight=0)

    ttk.Separator(frame, orient="horizontal", style="Dark.TSeparator").grid(
        row=7, column=0, sticky="ew", padx=16, pady=(0, 14))

    state.run_btn = ttk.Button(frame, text="Run", style="Filled.TButton",
                               command=operations.run_tool)
    state.run_btn.grid(row=8, column=0, padx=16, sticky="ew")

    ttk.Button(frame, text="Clear log", style="Outlined.TButton",
               command=log_panel.clear_log).grid(row=9, column=0, padx=16, pady=(10, 16))

    return frame


# ── Deck B — Destination ─────────────────────────────────────────────────────

def build_deck_b(parent):
    frame = tk.Frame(parent, bg=theme.BG_SURF1,
                     highlightthickness=1,
                     highlightbackground=theme.CARD_BORDER,
                     highlightcolor=theme.AMBER)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    # Strip: thin left accent line + subtle amber-tinted bg
    strip = tk.Frame(frame, bg=theme.AMBER_STRIP)
    strip.grid(row=0, column=0, columnspan=2, sticky="ew")
    tk.Frame(strip, bg=theme.AMBER, width=_px(3)).pack(side="left", fill="y")
    tk.Label(strip, text="B", font=("Segoe UI", 11, "bold"),
             bg=theme.AMBER_STRIP, fg=theme.AMBER).pack(side="left", padx=(10, 4), pady=8)
    tk.Label(strip, text="·", font=("Segoe UI", 9),
             bg=theme.AMBER_STRIP, fg=theme.FG_DIM).pack(side="left", padx=(0, 4))
    tk.Label(strip, text="DESTINATION", font=("Segoe UI", 8),
             bg=theme.AMBER_STRIP, fg=theme.FG_MUTED).pack(side="left")

    # Dest path row
    path_row = tk.Frame(frame, bg=theme.BG_SURF1)
    path_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 0))
    path_row.columnconfigure(0, weight=1)
    state.dest_var = tk.StringVar()
    ttk.Entry(path_row, textvariable=state.dest_var, style="B.TEntry").grid(
        row=0, column=0, sticky="ew", padx=(0, 8))
    ttk.Button(path_row, text="Browse", style="TonalB.TButton",
               command=browser.browse_dest).grid(row=0, column=1)

    # Preview count
    state.preview_count_var = tk.StringVar(value="Navigate source to see preview")
    tk.Label(frame, textvariable=state.preview_count_var,
             font=("Segoe UI", 9), bg=theme.BG_SURF1, fg=theme.AMBER,
             anchor="w").grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 4))

    # Treeview
    state.preview_tree = ttk.Treeview(frame, style="Preview.Treeview",
                                      columns=("original", "renamed"),
                                      show="headings", selectmode="none")
    state.preview_tree.heading("original", text="Original name")
    state.preview_tree.heading("renamed",  text="Will become")
    state.preview_tree.column("original", width=_px(160), anchor="w", minwidth=_px(80))
    state.preview_tree.column("renamed",  width=_px(200), anchor="w", minwidth=_px(80))
    state.preview_tree.grid(row=3, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))

    vsb = ttk.Scrollbar(frame, orient="vertical", command=state.preview_tree.yview,
                        style="Dark.Vertical.TScrollbar")
    vsb.grid(row=3, column=1, sticky="ns", padx=(0, 8), pady=(0, 12))
    state.preview_tree.configure(yscrollcommand=vsb.set)

    # Tooltip: hovering over the "Will become" column shows the full filename
    state.preview_tree.bind("<Motion>", preview._show_tooltip)
    state.preview_tree.bind("<Leave>",  preview._hide_tooltip)

    # Prevent the frame from resizing when preview content changes —
    # size is dictated entirely by the parent grid.
    frame.grid_propagate(False)
    return frame


# ── Status bar ───────────────────────────────────────────────────────────────

def build_status_bar(parent):
    frame = tk.Frame(parent, bg=theme.BG_SURF2, height=_px(36))
    frame.pack_propagate(False)

    state.progress_var = tk.IntVar(value=0)
    ttk.Progressbar(frame, variable=state.progress_var, maximum=100,
                    style="MD3.Horizontal.TProgressbar",
                    mode="determinate", length=_px(160)).pack(side="left", padx=(16, 10), pady=12)

    # State dot: FG_DIM (idle) → CYAN (running) → C_COPY (complete)
    state._status_dot = tk.Label(frame, text="●", font=("Segoe UI", 8),
                                 bg=theme.BG_SURF2, fg=theme.FG_DIM)
    state._status_dot.pack(side="left", padx=(0, 6))

    state.status_var = tk.StringVar(value="Ready")
    tk.Label(frame, textvariable=state.status_var,
             font=("Segoe UI", 9), bg=theme.BG_SURF2, fg=theme.FG_MUTED,
             anchor="w").pack(side="left", fill="x", expand=True)

    tk.Label(frame, text="v0.10",
             font=("Segoe UI", 8), bg=theme.BG_SURF2, fg=theme.FG_DIM,
             anchor="e").pack(side="right", padx=14)
    return frame


# ── Log panel ────────────────────────────────────────────────────────────────

def build_log_panel(parent):
    frame = tk.Frame(parent, bg=theme.BG_SURF1,
                     highlightthickness=1,
                     highlightbackground=theme.CARD_BORDER)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(1, weight=1)

    tk.Label(frame, text="Operation log",
             font=("Segoe UI", 9),
             bg=theme.BG_SURF1, fg=theme.FG_DIM, anchor="w").grid(
        row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(6, 2))

    state.log_text = tk.Text(frame, bg=theme.BG_SURF2, fg=theme.FG_ON_SURF,
                             font=("Consolas", 9), bd=0, relief="flat",
                             insertbackground=theme.CYAN, selectbackground=theme.CYAN_CONT,
                             state="disabled", wrap="none", height=8)
    state.log_text.grid(row=1, column=0, sticky="nsew", padx=(14, 0), pady=(0, 10))

    lvsb = ttk.Scrollbar(frame, orient="vertical", command=state.log_text.yview,
                         style="Dark.Vertical.TScrollbar")
    lvsb.grid(row=1, column=1, sticky="ns", padx=(0, 6), pady=(0, 10))

    lhsb = ttk.Scrollbar(frame, orient="horizontal", command=state.log_text.xview,
                         style="Dark.Horizontal.TScrollbar")
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

    saved_source  = state.source_var.get()     if state.source_var     else ""
    saved_dest    = state.dest_var.get()       if state.dest_var       else ""
    saved_active  = state.active_dir_var.get() if state.active_dir_var else ""
    saved_profile = state.profile_var.get()    if state.profile_var    else "Generic"

    state._is_dark = not state._is_dark
    theme._apply_theme_colors(state._is_dark)

    for w in state.root.winfo_children():
        w.destroy()

    state.root.configure(bg=theme.BG_ROOT)
    theme.setup_styles()
    build_app()

    if saved_profile:
        state.profile_var.set(saved_profile)
    if saved_dest:
        state.dest_var.set(saved_dest)
    if saved_source:
        state.source_var.set(saved_source)   # trace → navigate_to(source_root)

    # If user had drilled into a subdirectory, restore that after the
    # trace-driven root navigation settles.
    if saved_active and saved_active != saved_source and Path(saved_active).is_dir():
        state.root.after(50, lambda: browser.navigate_to(saved_active))


# ── App assembly ─────────────────────────────────────────────────────────────

def build_app():
    state.active_dir_var = tk.StringVar()

    root_frame = tk.Frame(state.root, bg=theme.BG_ROOT)
    root_frame.pack(fill="both", expand=True)

    # uniform="decks" forces cols 0 and 2 to always be the same width,
    # regardless of what content Deck B is displaying.
    root_frame.columnconfigure(0, weight=3, minsize=_px(280), uniform="decks")
    root_frame.columnconfigure(1, weight=2, minsize=_px(180))
    root_frame.columnconfigure(2, weight=3, minsize=_px(280), uniform="decks")
    root_frame.rowconfigure(1, weight=3)
    root_frame.rowconfigure(3, weight=1)

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
    state.source_var.trace_add("write", browser.on_source_var_changed)
    state.no_rename_var.trace_add("write", lambda *_: preview.refresh_preview())
    state.profile_var.trace_add("write",   lambda *_: preview.refresh_preview())
    state.root.bind("<Return>", lambda _e: operations.run_tool())
