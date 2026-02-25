import shutil
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk

# ── Constants (dark theme defaults — overwritten by _apply_theme_colors) ───

AUDIO_EXTS = {".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg"}
MAX_PREVIEW_ROWS = 500

BG_ROOT    = "#0f0f11"
BG_SURFACE = "#1c1b1f"
BG_SURF1   = "#25232a"
BG_SURF2   = "#2d2b32"

OUTLINE     = "#79747e"
OUTLINE_VAR = "#49454f"
CARD_BORDER = "#38353f"

FG_ON_SURF = "#e6e1e5"
FG_VARIANT = "#cac4d0"
FG_MUTED   = "#938f99"
FG_DIM     = "#49454f"

CYAN          = "#4dd0e1"
CYAN_CONT     = "#004f57"
CYAN_STRIP    = "#0c2326"
ON_CYAN_CONT  = "#97f0ff"

AMBER         = "#ffb74d"
AMBER_CONT    = "#3e2600"
AMBER_STRIP   = "#1c1100"
ON_AMBER_CONT = "#ffddb3"

C_MOVE = "#f28b82"
C_COPY = "#81c995"
C_DONE = "#4dd0e1"
C_DRY  = "#fdd663"

TREE_ROW_ODD = "#252330"   # alternating row tint for Deck B treeview

# ── Globals ────────────────────────────────────────────────────────────────

root              = None
active_dir_var    = None
source_var        = None
dest_var          = None
move_var          = None
dry_var           = None
src_count_var     = None
preview_count_var = None
status_var        = None
progress_var      = None
preview_tree      = None
log_text          = None
run_btn           = None
dir_browser       = None
nav_path_var      = None
_status_dot       = None
_browser_items    = []
_browser_press_idx = None   # listbox index held during mouse press; None if not pressing
_preview_after    = None
_is_dark          = True    # current theme state
m8_var            = None
_tooltip_win      = None    # active hover tooltip Toplevel (or None)
_tooltip_item     = None    # item_id currently shown in tooltip

# ── Theme ──────────────────────────────────────────────────────────────────

def _apply_theme_colors(dark: bool):
    """
    Update all module-level color constants for the requested theme.

    Dark mode uses a neutral near-black MD3 palette.
    Light mode uses a warm 60s/70s pastel palette: avocado green (Deck A),
    terracotta/burnt orange (Deck B), warm parchment surfaces.
    """
    global BG_ROOT, BG_SURFACE, BG_SURF1, BG_SURF2
    global OUTLINE, OUTLINE_VAR, CARD_BORDER
    global FG_ON_SURF, FG_VARIANT, FG_MUTED, FG_DIM
    global CYAN, CYAN_CONT, CYAN_STRIP, ON_CYAN_CONT
    global AMBER, AMBER_CONT, AMBER_STRIP, ON_AMBER_CONT
    global C_MOVE, C_COPY, C_DONE, C_DRY, TREE_ROW_ODD

    if dark:
        BG_ROOT    = "#0f0f11"
        BG_SURFACE = "#1c1b1f"
        BG_SURF1   = "#25232a"
        BG_SURF2   = "#2d2b32"

        OUTLINE     = "#79747e"
        OUTLINE_VAR = "#49454f"
        CARD_BORDER = "#38353f"

        FG_ON_SURF = "#e6e1e5"
        FG_VARIANT = "#cac4d0"
        FG_MUTED   = "#938f99"
        FG_DIM     = "#49454f"

        CYAN          = "#4dd0e1"
        CYAN_CONT     = "#004f57"
        CYAN_STRIP    = "#0c2326"
        ON_CYAN_CONT  = "#97f0ff"

        AMBER         = "#ffb74d"
        AMBER_CONT    = "#3e2600"
        AMBER_STRIP   = "#1c1100"
        ON_AMBER_CONT = "#ffddb3"

        C_MOVE = "#f28b82"
        C_COPY = "#81c995"
        C_DONE = "#4dd0e1"
        C_DRY  = "#fdd663"

        TREE_ROW_ODD = "#252330"

    else:
        # ── Warm 60s/70s pastel light theme ──────────────────────────────
        # Surfaces: warm parchment/cream hierarchy
        BG_ROOT    = "#f5f0e8"   # warm parchment window background
        BG_SURFACE = "#ede7db"   # warm cream — center column
        BG_SURF1   = "#e8e1d5"   # warm tan — deck card panels
        BG_SURF2   = "#ddd7ca"   # slightly deeper tan — inputs, nav, log bg

        OUTLINE     = "#a89888"
        OUTLINE_VAR = "#c4b8ab"
        CARD_BORDER = "#d0c4b8"

        FG_ON_SURF = "#2e2018"   # warm very dark brown — primary text
        FG_VARIANT = "#5c4a38"   # medium warm brown
        FG_MUTED   = "#8a7060"   # muted warm brown
        FG_DIM     = "#b8a898"   # very muted — disabled / placeholder

        # Deck A — Avocado / sage green: quintessential late-60s/70s colour
        CYAN          = "#5a8a6a"   # sage green (fills Run button, accent)
        CYAN_CONT     = "#c8e4d5"   # light sage tonal container (Browse btn)
        CYAN_STRIP    = "#eaf3ee"   # very light sage — deck strip bg
        ON_CYAN_CONT  = "#1a4030"   # dark forest text on light sage

        # Deck B — Terracotta / burnt orange: warm earthy counterpart
        AMBER         = "#c46a30"   # burnt terracotta
        AMBER_CONT    = "#fae0d0"   # light terracotta tonal container
        AMBER_STRIP   = "#fef3ec"   # very light warm strip bg
        ON_AMBER_CONT = "#5a2010"   # dark terracotta text on light peach

        C_MOVE = "#b33a2e"   # muted red
        C_COPY = "#2e6040"   # muted green
        C_DONE = "#5a8a6a"   # sage
        C_DRY  = "#8a6520"   # mustard gold

        TREE_ROW_ODD = "#e0d9cc"   # warm slightly-darker alternating row


def toggle_theme():
    """
    Switch between dark and light mode.

    Saves the current source / destination / active-directory paths, tears
    down all widgets, rebuilds with the new theme, then restores paths.
    The source-var trace will trigger browser navigation to the source root;
    if the user had navigated deeper, a deferred call restores that too.
    """
    _hide_tooltip()                    # destroy any visible tooltip before rebuilding
    global _is_dark

    saved_source = source_var.get()     if source_var     else ""
    saved_dest   = dest_var.get()       if dest_var       else ""
    saved_active = active_dir_var.get() if active_dir_var else ""

    _is_dark = not _is_dark
    _apply_theme_colors(_is_dark)

    for w in root.winfo_children():
        w.destroy()

    root.configure(bg=BG_ROOT)
    setup_styles()
    build_app()

    if saved_dest:
        dest_var.set(saved_dest)
    if saved_source:
        source_var.set(saved_source)   # trace → navigate_to(source_root)

    # If user had drilled into a subdirectory, restore that after the
    # trace-driven root navigation settles.
    if saved_active and saved_active != saved_source and Path(saved_active).is_dir():
        root.after(50, lambda: navigate_to(saved_active))

# ── Styles ─────────────────────────────────────────────────────────────────

def setup_styles():
    style = ttk.Style(root)
    style.theme_use("clam")

    # ── Entries ──
    _e = dict(
        fieldbackground=BG_SURF2, foreground=FG_ON_SURF,
        insertcolor=CYAN,
        bordercolor=OUTLINE_VAR, lightcolor=OUTLINE_VAR, darkcolor=OUTLINE_VAR,
        relief="flat", padding=(10, 8), font=("Segoe UI", 10),
    )
    style.configure("TEntry", **_e)
    style.map("TEntry", bordercolor=[("focus", CYAN)], lightcolor=[("focus", CYAN)])
    style.configure("B.TEntry", **_e)
    style.map("B.TEntry", bordercolor=[("focus", AMBER)], lightcolor=[("focus", AMBER)])

    # ── Buttons ──
    # Filled primary — Run button
    style.configure("Filled.TButton",
        background=CYAN, foreground="#001e2b" if _is_dark else "#f5f0e8",
        bordercolor=CYAN, lightcolor=CYAN, darkcolor=CYAN,
        relief="flat", padding=(20, 10), font=("Segoe UI", 12, "bold"),
    )
    style.map("Filled.TButton",
        background=[("active", ON_CYAN_CONT), ("pressed", CYAN_CONT), ("disabled", BG_SURF2)],
        foreground=[("active", "#001e2b" if _is_dark else "#1a4030"), ("disabled", FG_DIM)],
    )

    # Tonal A — Browse source
    style.configure("TonalA.TButton",
        background=CYAN_CONT, foreground=ON_CYAN_CONT,
        bordercolor=CYAN_CONT, lightcolor=CYAN_CONT, darkcolor=CYAN_CONT,
        relief="flat", padding=(12, 7), font=("Segoe UI", 9, "bold"),
    )
    style.map("TonalA.TButton",
        background=[("active", "#005f6a" if _is_dark else "#b0d8c4"), ("pressed", CYAN_CONT)],
        foreground=[("active", "#c8f8ff" if _is_dark else "#0f2e22")],
    )

    # Tonal B — Browse dest
    style.configure("TonalB.TButton",
        background=AMBER_CONT, foreground=ON_AMBER_CONT,
        bordercolor=AMBER_CONT, lightcolor=AMBER_CONT, darkcolor=AMBER_CONT,
        relief="flat", padding=(12, 7), font=("Segoe UI", 9, "bold"),
    )
    style.map("TonalB.TButton",
        background=[("active", "#4e3000" if _is_dark else "#f0c8b0"), ("pressed", AMBER_CONT)],
        foreground=[("active", "#ffe8cc" if _is_dark else "#3a1008")],
    )

    # Outlined — utility (Clear log)
    style.configure("Outlined.TButton",
        background=BG_SURFACE, foreground=FG_MUTED,
        bordercolor=OUTLINE_VAR, lightcolor=OUTLINE_VAR, darkcolor=OUTLINE_VAR,
        relief="flat", padding=(10, 5), font=("Segoe UI", 9),
    )
    style.map("Outlined.TButton",
        background=[("active", BG_SURF1)],
        foreground=[("active", FG_ON_SURF)],
    )

    # Icon — ↑ nav up
    style.configure("Icon.TButton",
        background=BG_SURF2, foreground=FG_MUTED,
        bordercolor=BG_SURF2, lightcolor=BG_SURF2, darkcolor=BG_SURF2,
        relief="flat", padding=(5, 3), font=("Segoe UI", 10),
    )
    style.map("Icon.TButton",
        background=[("active", OUTLINE_VAR)],
        foreground=[("active", FG_ON_SURF)],
    )

    # ── Checkbutton ──
    style.configure("Dark.TCheckbutton",
        background=BG_SURFACE, foreground=FG_ON_SURF,
        indicatorbackground=BG_SURF2, indicatorforeground=CYAN,
        font=("Segoe UI", 10), padding=(6, 4),
    )
    style.map("Dark.TCheckbutton",
        indicatorbackground=[("selected", CYAN), ("!selected", BG_SURF2)],
        background=[("active", BG_SURFACE)],
    )

    # ── Preview Treeview ──
    style.configure("Preview.Treeview",
        background=BG_SURF2, foreground=FG_ON_SURF,
        fieldbackground=BG_SURF2,
        bordercolor=OUTLINE_VAR, lightcolor=OUTLINE_VAR, darkcolor=OUTLINE_VAR,
        font=("Consolas", 9), rowheight=24,
    )
    style.configure("Preview.Treeview.Heading",
        background=BG_SURF2, foreground=AMBER,
        bordercolor=OUTLINE_VAR, lightcolor=OUTLINE_VAR, darkcolor=OUTLINE_VAR,
        font=("Segoe UI", 9, "bold"), relief="flat", padding=6,
    )
    style.map("Preview.Treeview",
        background=[("selected", AMBER_CONT)],
        foreground=[("selected", ON_AMBER_CONT)],
    )
    style.map("Preview.Treeview.Heading",
        background=[("active", BG_SURF1)],
    )

    # ── Progressbar ──
    style.configure("MD3.Horizontal.TProgressbar",
        troughcolor=BG_SURF2, background=CYAN,
        bordercolor=BG_SURF2, lightcolor=CYAN, darkcolor=CYAN,
        thickness=4,
    )

    # ── Scrollbars ──
    for ori in ("Vertical", "Horizontal"):
        n = f"Dark.{ori}.TScrollbar"
        style.configure(n,
            background=OUTLINE_VAR, troughcolor=BG_SURF2,
            bordercolor=BG_SURF2, lightcolor=OUTLINE_VAR, darkcolor=OUTLINE_VAR,
            arrowcolor=FG_MUTED, relief="flat",
        )
        style.map(n, background=[("active", FG_MUTED), ("pressed", CYAN)])

    style.configure("Dark.TSeparator", background=OUTLINE_VAR)

# ── Builders ───────────────────────────────────────────────────────────────

def build_header(parent):
    frame = tk.Frame(parent, bg=BG_SURF2, height=52)
    frame.pack_propagate(False)

    tk.Label(frame, text="Dirtywave File Helper",
             font=("Segoe UI", 15, "bold"),
             bg=BG_SURF2, fg=FG_ON_SURF).pack(side="left", padx=20, pady=12)
    tk.Label(frame, text="Audio Sample Organiser",
             font=("Segoe UI", 9),
             bg=BG_SURF2, fg=FG_DIM).pack(side="left", padx=2)

    # Theme toggle — right-aligned label that acts as a button.
    # Shows sun (☀) in dark mode (click to go light) and moon (☾) in light mode.
    toggle_icon = "☀" if _is_dark else "☾"
    toggle_tip  = "Light" if _is_dark else "Dark"
    lbl = tk.Label(frame, text=f"{toggle_icon}  {toggle_tip}",
                   font=("Segoe UI", 9),
                   bg=BG_SURF2, fg=FG_MUTED,
                   cursor="hand2", padx=6, pady=4)
    lbl.pack(side="right", padx=12)
    lbl.bind("<Button-1>", lambda _e: toggle_theme())
    lbl.bind("<Enter>",    lambda _e: lbl.configure(fg=FG_ON_SURF))
    lbl.bind("<Leave>",    lambda _e: lbl.configure(fg=FG_MUTED))

    return frame


def build_deck_a(parent):
    global source_var, src_count_var, dir_browser, nav_path_var

    frame = tk.Frame(parent, bg=BG_SURF1,
                     highlightthickness=1,
                     highlightbackground=CARD_BORDER,
                     highlightcolor=CYAN)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    # Strip: thin left accent line + subtle tinted bg
    strip = tk.Frame(frame, bg=CYAN_STRIP)
    strip.grid(row=0, column=0, sticky="ew")
    tk.Frame(strip, bg=CYAN, width=3).pack(side="left", fill="y")
    tk.Label(strip, text="A", font=("Segoe UI", 11, "bold"),
             bg=CYAN_STRIP, fg=CYAN).pack(side="left", padx=(10, 4), pady=8)
    tk.Label(strip, text="·", font=("Segoe UI", 9),
             bg=CYAN_STRIP, fg=FG_DIM).pack(side="left", padx=(0, 4))
    tk.Label(strip, text="SOURCE", font=("Segoe UI", 8),
             bg=CYAN_STRIP, fg=FG_MUTED).pack(side="left")

    # Source path row
    path_row = tk.Frame(frame, bg=BG_SURF1)
    path_row.grid(row=1, column=0, sticky="ew", padx=12, pady=(12, 0))
    path_row.columnconfigure(0, weight=1)
    source_var = tk.StringVar()
    ttk.Entry(path_row, textvariable=source_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
    ttk.Button(path_row, text="Browse", style="TonalA.TButton",
               command=browse_source).grid(row=0, column=1)

    # Nav bar
    nav_bar = tk.Frame(frame, bg=BG_SURF2)
    nav_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(8, 0))
    nav_bar.columnconfigure(1, weight=1)
    ttk.Button(nav_bar, text="↑", style="Icon.TButton",
               command=nav_up).grid(row=0, column=0, padx=(4, 6), pady=4)
    nav_path_var = tk.StringVar(value="—")
    tk.Label(nav_bar, textvariable=nav_path_var,
             font=("Consolas", 8), bg=BG_SURF2, fg=FG_DIM,
             anchor="w").grid(row=0, column=1, sticky="ew", padx=(0, 6))

    # File browser — press/release bindings so navigation only fires on release
    browser_wrap = tk.Frame(frame, bg=BG_SURF2)
    browser_wrap.grid(row=3, column=0, sticky="nsew", padx=12, pady=(4, 0))
    browser_wrap.columnconfigure(0, weight=1)
    browser_wrap.rowconfigure(0, weight=1)
    dir_browser = tk.Listbox(
        browser_wrap,
        bg=BG_SURF2, fg=FG_ON_SURF,
        selectbackground=CYAN_CONT, selectforeground=ON_CYAN_CONT,
        font=("Segoe UI", 10), bd=0, relief="flat",
        activestyle="none", highlightthickness=0,
    )
    dir_browser.grid(row=0, column=0, sticky="nsew")
    # Navigate on release, not on press — gives visual press feedback first
    dir_browser.bind("<ButtonPress-1>",   on_browser_press)
    dir_browser.bind("<ButtonRelease-1>", on_browser_release)
    bsb = ttk.Scrollbar(browser_wrap, orient="vertical", command=dir_browser.yview,
                        style="Dark.Vertical.TScrollbar")
    bsb.grid(row=0, column=1, sticky="ns")
    dir_browser.configure(yscrollcommand=bsb.set)

    # File count
    src_count_var = tk.StringVar(value="0 audio files")
    tk.Label(frame, textvariable=src_count_var,
             font=("Segoe UI", 9), bg=BG_SURF1, fg=CYAN,
             anchor="w").grid(row=4, column=0, sticky="w", padx=12, pady=(6, 10))

    # Prevent the frame from shrinking/growing to fit its children —
    # size is dictated entirely by the parent grid.
    frame.grid_propagate(False)
    return frame


def build_center(parent):
    global move_var, dry_var, m8_var, run_btn

    frame = tk.Frame(parent, bg=BG_SURFACE,
                     highlightthickness=1,
                     highlightbackground=CARD_BORDER)
    frame.columnconfigure(0, weight=1)
    # Row 3 is the expanding spacer — pushes Run/Clear to the bottom
    frame.rowconfigure(3, weight=1)

    move_var = tk.BooleanVar(value=False)
    dry_var  = tk.BooleanVar(value=True)
    m8_var   = tk.BooleanVar(value=False)

    ttk.Checkbutton(frame, text="Move files  (copy by default)",
                    variable=move_var, style="Dark.TCheckbutton").grid(
        row=0, column=0, sticky="w", padx=16, pady=(16, 2))

    ttk.Checkbutton(frame, text="Dry run  (no changes written)",
                    variable=dry_var, style="Dark.TCheckbutton").grid(
        row=1, column=0, sticky="w", padx=16)

    ttk.Checkbutton(frame, text="M8 Friendly  (\u2264127 char paths)",
                    variable=m8_var, style="Dark.TCheckbutton").grid(
        row=2, column=0, sticky="w", padx=16, pady=(2, 0))

    # row 3 expands — spacer pushes controls below it to the bottom

    ttk.Separator(frame, orient="horizontal", style="Dark.TSeparator").grid(
        row=4, column=0, sticky="ew", padx=16, pady=(0, 14))

    run_btn = ttk.Button(frame, text="Run", style="Filled.TButton", command=run_tool)
    run_btn.grid(row=5, column=0, padx=16, sticky="ew")

    ttk.Button(frame, text="Clear log", style="Outlined.TButton",
               command=clear_log).grid(row=6, column=0, padx=16, pady=(10, 16))

    return frame


def build_deck_b(parent):
    global dest_var, preview_count_var, preview_tree

    frame = tk.Frame(parent, bg=BG_SURF1,
                     highlightthickness=1,
                     highlightbackground=CARD_BORDER,
                     highlightcolor=AMBER)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(3, weight=1)

    # Strip: thin left accent line + subtle amber-tinted bg
    strip = tk.Frame(frame, bg=AMBER_STRIP)
    strip.grid(row=0, column=0, columnspan=2, sticky="ew")
    tk.Frame(strip, bg=AMBER, width=3).pack(side="left", fill="y")
    tk.Label(strip, text="B", font=("Segoe UI", 11, "bold"),
             bg=AMBER_STRIP, fg=AMBER).pack(side="left", padx=(10, 4), pady=8)
    tk.Label(strip, text="·", font=("Segoe UI", 9),
             bg=AMBER_STRIP, fg=FG_DIM).pack(side="left", padx=(0, 4))
    tk.Label(strip, text="DESTINATION", font=("Segoe UI", 8),
             bg=AMBER_STRIP, fg=FG_MUTED).pack(side="left")

    # Dest path row
    path_row = tk.Frame(frame, bg=BG_SURF1)
    path_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 0))
    path_row.columnconfigure(0, weight=1)
    dest_var = tk.StringVar()
    ttk.Entry(path_row, textvariable=dest_var, style="B.TEntry").grid(
        row=0, column=0, sticky="ew", padx=(0, 8))
    ttk.Button(path_row, text="Browse", style="TonalB.TButton",
               command=browse_dest).grid(row=0, column=1)

    # Preview count
    preview_count_var = tk.StringVar(value="Navigate source to see preview")
    tk.Label(frame, textvariable=preview_count_var,
             font=("Segoe UI", 9), bg=BG_SURF1, fg=AMBER,
             anchor="w").grid(row=2, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 4))

    # Treeview
    preview_tree = ttk.Treeview(frame, style="Preview.Treeview",
                                 columns=("original", "renamed"),
                                 show="headings", selectmode="none")
    preview_tree.heading("original", text="Original name")
    preview_tree.heading("renamed",  text="Will become")
    preview_tree.column("original", width=160, anchor="w", minwidth=80)
    preview_tree.column("renamed",  width=200, anchor="w", minwidth=80)
    preview_tree.grid(row=3, column=0, sticky="nsew", padx=(12, 0), pady=(0, 12))

    vsb = ttk.Scrollbar(frame, orient="vertical", command=preview_tree.yview,
                        style="Dark.Vertical.TScrollbar")
    vsb.grid(row=3, column=1, sticky="ns", padx=(0, 8), pady=(0, 12))
    preview_tree.configure(yscrollcommand=vsb.set)

    # Tooltip: hovering over the "Will become" column shows the full filename
    preview_tree.bind("<Motion>", _show_tooltip)
    preview_tree.bind("<Leave>",  _hide_tooltip)

    # Prevent the frame from resizing when preview content changes —
    # size is dictated entirely by the parent grid.
    frame.grid_propagate(False)
    return frame


def build_status_bar(parent):
    global status_var, progress_var, _status_dot

    frame = tk.Frame(parent, bg=BG_SURF2, height=36)
    frame.pack_propagate(False)

    progress_var = tk.IntVar(value=0)
    ttk.Progressbar(frame, variable=progress_var, maximum=100,
                    style="MD3.Horizontal.TProgressbar",
                    mode="determinate", length=160).pack(side="left", padx=(16, 10), pady=12)

    # State dot: FG_DIM (idle) → CYAN (running) → C_COPY (complete)
    _status_dot = tk.Label(frame, text="●", font=("Segoe UI", 8),
                           bg=BG_SURF2, fg=FG_DIM)
    _status_dot.pack(side="left", padx=(0, 6))

    status_var = tk.StringVar(value="Ready")
    tk.Label(frame, textvariable=status_var,
             font=("Segoe UI", 9), bg=BG_SURF2, fg=FG_MUTED,
             anchor="w").pack(side="left", fill="x", expand=True)
    return frame


def build_log_panel(parent):
    global log_text

    frame = tk.Frame(parent, bg=BG_SURF1,
                     highlightthickness=1,
                     highlightbackground=CARD_BORDER)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(1, weight=1)

    tk.Label(frame, text="Operation log",
             font=("Segoe UI", 9),
             bg=BG_SURF1, fg=FG_DIM, anchor="w").grid(
        row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(6, 2))

    log_text = tk.Text(frame, bg=BG_SURF2, fg=FG_ON_SURF,
                       font=("Consolas", 9), bd=0, relief="flat",
                       insertbackground=CYAN, selectbackground=CYAN_CONT,
                       state="disabled", wrap="none", height=8)
    log_text.grid(row=1, column=0, sticky="nsew", padx=(14, 0), pady=(0, 10))

    lvsb = ttk.Scrollbar(frame, orient="vertical", command=log_text.yview,
                         style="Dark.Vertical.TScrollbar")
    lvsb.grid(row=1, column=1, sticky="ns", padx=(0, 6), pady=(0, 10))

    lhsb = ttk.Scrollbar(frame, orient="horizontal", command=log_text.xview,
                         style="Dark.Horizontal.TScrollbar")
    lhsb.grid(row=2, column=0, sticky="ew", padx=(14, 0), pady=(0, 6))

    log_text.configure(yscrollcommand=lvsb.set, xscrollcommand=lhsb.set)
    return frame

# ── Navigation & Browser ───────────────────────────────────────────────────

def navigate_to(path_str):
    global _browser_items
    p = Path(path_str)
    if not p.is_dir():
        return

    dir_browser.delete(0, "end")
    _browser_items = []
    nav_path_var.set(str(p))

    parent = p.parent
    if parent != p:
        dir_browser.insert("end", "   \u2191  ..")
        _browser_items.append(("up", "..", str(parent)))
        dir_browser.itemconfigure(0, fg=FG_DIM)

    try:
        subdirs = sorted(d for d in p.iterdir() if d.is_dir() and not d.name.startswith("."))
        for d in subdirs:
            dir_browser.insert("end", f"   \u25b6  {d.name}")
            _browser_items.append(("folder", d.name, str(d)))
            dir_browser.itemconfigure(len(_browser_items) - 1, fg=ON_CYAN_CONT)
    except PermissionError:
        pass

    try:
        audio = sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in AUDIO_EXTS)
        for f in audio:
            dir_browser.insert("end", f"   \u266a  {f.name}")
            _browser_items.append(("file", f.name, str(f)))
            dir_browser.itemconfigure(len(_browser_items) - 1, fg=FG_VARIANT)
    except PermissionError:
        pass

    active_dir_var.set(path_str)


def on_browser_press(event):
    """
    Mouse-button-down on the file browser.

    Highlights the item under the cursor and darkens the listbox background
    slightly to give tactile press feedback. Navigation is deferred to
    on_browser_release so the user sees a response before anything happens.
    """
    global _browser_press_idx
    idx = dir_browser.nearest(event.y)
    if 0 <= idx < len(_browser_items) and _browser_items[idx][0] in ("folder", "up"):
        _browser_press_idx = idx
        dir_browser.selection_clear(0, "end")
        dir_browser.selection_set(idx)
        # Darken the background slightly — pressed state indicator
        press_bg = "#222028" if _is_dark else "#cdc7ba"
        dir_browser.configure(bg=press_bg)
    else:
        _browser_press_idx = None


def on_browser_release(event):
    """
    Mouse-button-up on the file browser.

    Restores the normal background colour, then navigates into the folder
    that was pressed (if any). Only navigates if the release occurs over
    the same item that was pressed — prevents accidental navigation when
    the user drags off an item.
    """
    global _browser_press_idx
    dir_browser.configure(bg=BG_SURF2)   # restore normal bg

    if _browser_press_idx is None:
        return

    pressed = _browser_press_idx
    _browser_press_idx = None

    # Confirm the cursor is still over the same item
    release_idx = dir_browser.nearest(event.y)
    if release_idx != pressed:
        return

    if pressed < len(_browser_items):
        item_type, _name, path = _browser_items[pressed]
        if item_type in ("folder", "up"):
            navigate_to(path)


def nav_up():
    current = active_dir_var.get()
    if not current:
        return
    p = Path(current)
    parent = p.parent
    if parent != p:
        navigate_to(str(parent))


def browse_source():
    path = filedialog.askdirectory(parent=root)
    if path:
        source_var.set(path)   # trace → on_source_var_changed → navigate_to


def browse_dest():
    path = filedialog.askdirectory(parent=root)
    if path:
        dest_var.set(path)


def on_source_var_changed(*_):
    p = source_var.get().strip()
    if Path(p).is_dir():
        navigate_to(p)

# ── Tooltip ────────────────────────────────────────────────────────────────

def _show_tooltip(event):
    """Show a small tooltip near the cursor with the full 'Will become' filename."""
    global _tooltip_win, _tooltip_item
    item = preview_tree.identify_row(event.y)
    col  = preview_tree.identify_column(event.x)
    if not item or col != "#2":
        _hide_tooltip()
        return
    if _tooltip_item == item:
        # Same cell — just track the cursor so the tooltip follows
        if _tooltip_win:
            _tooltip_win.geometry(f"+{event.x_root + 14}+{event.y_root + 10}")
        return
    _hide_tooltip()
    _tooltip_item = item
    text = preview_tree.set(item, "renamed")
    if not text:
        return
    _tooltip_win = tk.Toplevel(root)
    _tooltip_win.wm_overrideredirect(True)
    _tooltip_win.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 10}")
    tk.Label(
        _tooltip_win, text=text,
        font=("Consolas", 9),
        bg=BG_SURF2, fg=FG_ON_SURF,
        highlightthickness=1, highlightbackground=OUTLINE_VAR,
        padx=8, pady=4,
    ).pack()


def _hide_tooltip(*_):
    """Destroy the tooltip window and reset tracking state."""
    global _tooltip_win, _tooltip_item
    if _tooltip_win:
        try:
            _tooltip_win.destroy()
        except tk.TclError:
            pass
        _tooltip_win = None
    _tooltip_item = None


# ── Preview ────────────────────────────────────────────────────────────────

def on_active_dir_changed(*_):
    global _preview_after
    if _preview_after:
        root.after_cancel(_preview_after)
    _preview_after = root.after(300, refresh_preview)


def refresh_preview():
    preview_tree.delete(*preview_tree.get_children())
    p = active_dir_var.get().strip()
    if not p or not Path(p).is_dir():
        preview_count_var.set("Navigate source to see preview")
        src_count_var.set("0 audio files")
        return
    preview_count_var.set("Scanning\u2026")
    src_count_var.set("Scanning\u2026")
    threading.Thread(target=_scan_thread, args=(p,), daemon=True).start()


def _scan_thread(path_str):
    files = [f for f in Path(path_str).rglob("*")
             if f.suffix.lower() in AUDIO_EXTS and f.is_file()]
    root.after(0, lambda: _populate_preview(files))


def _populate_preview(files):
    preview_tree.delete(*preview_tree.get_children())
    total = len(files)
    shown = min(total, MAX_PREVIEW_ROWS)
    for i, f in enumerate(files[:shown]):
        new_name = f"{f.parent.name}_{f.name}"
        if m8_var and m8_var.get():
            d = dest_var.get().strip() if dest_var else ""
            if d:
                new_name = _m8_truncate(new_name, d)
        tag = "odd" if i % 2 else "even"
        preview_tree.insert("", "end", values=(f.name, new_name), tags=(tag,))
    preview_tree.tag_configure("odd",  background=TREE_ROW_ODD, foreground=FG_ON_SURF)
    preview_tree.tag_configure("even", background=BG_SURF2,     foreground=FG_VARIANT)

    s = "s" if total != 1 else ""
    src_count_var.set(f"{total} audio file{s}")
    if total == 0:
        preview_count_var.set("No audio files in this directory tree")
    elif total > MAX_PREVIEW_ROWS:
        preview_count_var.set(f"Showing {shown} of {total} files")
    else:
        preview_count_var.set(f"{total} file{s} will be renamed")

# ── Log ────────────────────────────────────────────────────────────────────

def log(msg):
    log_text.configure(state="normal")
    m = msg.strip()
    if "[DRY]" in m:
        tag = "dry"
    elif m.startswith("MOVE"):
        tag = "move"
    elif m.startswith("COPY"):
        tag = "copy"
    elif m == "Done.":
        tag = "done"
    else:
        tag = "plain"
    log_text.insert("end", msg + "\n", tag)
    log_text.see("end")
    log_text.configure(state="disabled")


def setup_log_tags():
    log_text.tag_configure("plain", foreground=FG_ON_SURF)
    log_text.tag_configure("move",  foreground=C_MOVE)
    log_text.tag_configure("copy",  foreground=C_COPY)
    log_text.tag_configure("dry",   foreground=C_DRY)
    log_text.tag_configure("done",  foreground=C_DONE, font=("Consolas", 9, "bold"))


def clear_log():
    log_text.configure(state="normal")
    log_text.delete("1.0", "end")
    log_text.configure(state="disabled")

# ── M8 path truncation ─────────────────────────────────────────────────────

def _m8_truncate(new_name: str, dest_path_str: str) -> str:
    """
    Truncate new_name so that the full destination path stays within 127 chars.

    The Dirtywave M8 has a 127-character limit for file paths on its SD card.
    The extension is always preserved; only the stem is shortened.
    """
    full = str(Path(dest_path_str) / new_name)
    if len(full) <= 127:
        return new_name
    p    = Path(new_name)
    ext  = p.suffix                              # e.g. ".wav"
    # chars available for the filename: 127 − (dir length + separator)
    avail = 127 - len(str(Path(dest_path_str))) - 1 - len(ext)
    if avail < 1:
        avail = 1
    return p.stem[:avail] + ext


# ── Run ────────────────────────────────────────────────────────────────────

def run_tool():
    source = Path(active_dir_var.get().strip()) if active_dir_var.get().strip() else None
    dest   = Path(dest_var.get().strip())

    if not source or not source.is_dir():
        messagebox.showerror("Error",
            "Please navigate to a source directory in Deck A.", parent=root)
        return
    if not dest.is_dir():
        messagebox.showerror("Error",
            "Please select a valid destination folder in Deck B.", parent=root)
        return

    run_btn.state(["disabled"])
    run_btn.configure(text="Running\u2026")
    if _status_dot:
        _status_dot.configure(fg=CYAN)
    progress_var.set(0)
    status_var.set("Collecting files\u2026")
    threading.Thread(
        target=_run_worker,
        args=(source, dest, move_var.get(), dry_var.get(), m8_var.get()),
        daemon=True,
    ).start()


def _run_worker(source, dest, move_files, dry, m8_friendly):
    files = [f for f in source.rglob("*")
             if f.suffix.lower() in AUDIO_EXTS and f.is_file()]
    total = len(files)

    if total == 0:
        root.after(0, lambda: status_var.set("No audio files found."))
        root.after(0, lambda: run_btn.configure(text="Run"))
        root.after(0, lambda: run_btn.state(["!disabled"]))
        if _status_dot:
            root.after(0, lambda: _status_dot.configure(fg=FG_DIM))
        return

    label  = "MOVE" if move_files else "COPY"
    prefix = "[DRY] " if dry else ""

    for i, f in enumerate(files, 1):
        new_name = f"{f.parent.name}_{f.name}"
        if m8_friendly:
            new_name = _m8_truncate(new_name, str(dest))
        target   = dest / new_name
        msg      = f"{prefix}{label}: {f.name}  \u2192  {new_name}"

        root.after(0, lambda m=msg: log(m))
        root.after(0, lambda pct=int(i / total * 100): progress_var.set(pct))
        root.after(0, lambda s=f"Processing {i} / {total}\u2026": status_var.set(s))

        if not dry:
            dest.mkdir(parents=True, exist_ok=True)
            if move_files:
                shutil.move(str(f), str(target))
            else:
                shutil.copy2(str(f), str(target))

    s = "s" if total != 1 else ""
    root.after(0, lambda: log("Done."))
    root.after(0, lambda: status_var.set(f"Complete \u2014 {total} file{s} processed."))
    root.after(0, lambda: run_btn.configure(text="Run"))
    root.after(0, lambda: run_btn.state(["!disabled"]))
    if _status_dot:
        root.after(0, lambda: _status_dot.configure(fg=C_COPY))

# ── Assembly ───────────────────────────────────────────────────────────────

def build_app():
    global active_dir_var

    active_dir_var = tk.StringVar()

    root_frame = tk.Frame(root, bg=BG_ROOT)
    root_frame.pack(fill="both", expand=True)

    # uniform="decks" forces cols 0 and 2 to always be the same width,
    # regardless of what content Deck B is displaying.
    root_frame.columnconfigure(0, weight=3, minsize=280, uniform="decks")
    root_frame.columnconfigure(1, weight=2, minsize=180)
    root_frame.columnconfigure(2, weight=3, minsize=280, uniform="decks")
    root_frame.rowconfigure(1, weight=3)
    root_frame.rowconfigure(3, weight=1)

    build_header(root_frame).grid(row=0, column=0, columnspan=3, sticky="ew")
    tk.Frame(root_frame, bg=OUTLINE_VAR, height=1).grid(
        row=0, column=0, columnspan=3, sticky="sew")

    build_deck_a(root_frame).grid(row=1, column=0, sticky="nsew", padx=(10, 4), pady=8)
    build_center(root_frame).grid(row=1, column=1, sticky="nsew", padx=4,       pady=8)
    build_deck_b(root_frame).grid(row=1, column=2, sticky="nsew", padx=(4, 10), pady=8)

    build_status_bar(root_frame).grid(row=2, column=0, columnspan=3, sticky="ew", padx=10)
    tk.Frame(root_frame, bg=OUTLINE_VAR, height=1).grid(
        row=2, column=0, columnspan=3, sticky="sew", padx=10)

    build_log_panel(root_frame).grid(row=3, column=0, columnspan=3, sticky="nsew",
                                     padx=10, pady=(4, 10))

    setup_log_tags()
    active_dir_var.trace_add("write", on_active_dir_changed)
    source_var.trace_add("write", on_source_var_changed)
    root.bind("<Return>", lambda _e: run_tool())

# ── Entry point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Dirtywave File Helper")
    root.geometry("1100x720")
    root.minsize(900, 600)
    root.configure(bg=BG_ROOT)
    setup_styles()
    build_app()
    root.mainloop()
