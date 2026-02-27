import tkinter.ttk as ttk

import state
from dpi import _px

# ── Color constants (dark theme defaults) ──────────────────────────────────
# These are module-level variables mutated by _apply_theme_colors().
# Other modules access them as `theme.BG_ROOT`, `theme.CYAN`, etc.

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

        # Deck A — Avocado / sage green
        CYAN          = "#5a8a6a"
        CYAN_CONT     = "#c8e4d5"
        CYAN_STRIP    = "#eaf3ee"
        ON_CYAN_CONT  = "#1a4030"

        # Deck B — Terracotta / burnt orange
        AMBER         = "#c46a30"
        AMBER_CONT    = "#fae0d0"
        AMBER_STRIP   = "#fef3ec"
        ON_AMBER_CONT = "#5a2010"

        C_MOVE = "#b33a2e"
        C_COPY = "#2e6040"
        C_DONE = "#5a8a6a"
        C_DRY  = "#8a6520"

        TREE_ROW_ODD = "#e0d9cc"


def setup_styles():
    style = ttk.Style(state.root)
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
    style.configure("Filled.TButton",
        background=CYAN, foreground="#001e2b" if state._is_dark else "#f5f0e8",
        bordercolor=CYAN, lightcolor=CYAN, darkcolor=CYAN,
        relief="flat", padding=(20, 10), font=("Segoe UI", 12, "bold"),
    )
    style.map("Filled.TButton",
        background=[("active", ON_CYAN_CONT), ("pressed", CYAN_CONT), ("disabled", BG_SURF2)],
        foreground=[("active", "#001e2b" if state._is_dark else "#1a4030"), ("disabled", FG_DIM)],
    )

    style.configure("TonalA.TButton",
        background=CYAN_CONT, foreground=ON_CYAN_CONT,
        bordercolor=CYAN_CONT, lightcolor=CYAN_CONT, darkcolor=CYAN_CONT,
        relief="flat", padding=(12, 7), font=("Segoe UI", 9, "bold"),
    )
    style.map("TonalA.TButton",
        background=[("active", "#005f6a" if state._is_dark else "#b0d8c4"), ("pressed", CYAN_CONT)],
        foreground=[("active", "#c8f8ff" if state._is_dark else "#0f2e22")],
    )

    style.configure("TonalB.TButton",
        background=AMBER_CONT, foreground=ON_AMBER_CONT,
        bordercolor=AMBER_CONT, lightcolor=AMBER_CONT, darkcolor=AMBER_CONT,
        relief="flat", padding=(12, 7), font=("Segoe UI", 9, "bold"),
    )
    style.map("TonalB.TButton",
        background=[("active", "#4e3000" if state._is_dark else "#f0c8b0"), ("pressed", AMBER_CONT)],
        foreground=[("active", "#ffe8cc" if state._is_dark else "#3a1008")],
    )

    style.configure("Outlined.TButton",
        background=BG_SURFACE, foreground=FG_MUTED,
        bordercolor=OUTLINE_VAR, lightcolor=OUTLINE_VAR, darkcolor=OUTLINE_VAR,
        relief="flat", padding=(10, 5), font=("Segoe UI", 9),
    )
    style.map("Outlined.TButton",
        background=[("active", BG_SURF1)],
        foreground=[("active", FG_ON_SURF)],
    )

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
        font=("Consolas", 9), rowheight=_px(24),
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

    # ── Combobox ──
    style.configure("Dark.TCombobox",
        fieldbackground=BG_SURF2, background=BG_SURF2,
        foreground=FG_ON_SURF,
        arrowcolor=CYAN,
        bordercolor=OUTLINE_VAR, lightcolor=OUTLINE_VAR, darkcolor=OUTLINE_VAR,
        insertcolor=CYAN,
        selectbackground=CYAN_CONT, selectforeground=ON_CYAN_CONT,
        font=("Segoe UI", 9), padding=(6, 4),
    )
    style.map("Dark.TCombobox",
        fieldbackground=[("readonly", BG_SURF2), ("disabled", BG_SURF1)],
        foreground=[("readonly", FG_ON_SURF), ("disabled", FG_DIM)],
        bordercolor=[("focus", CYAN)],
        arrowcolor=[("disabled", FG_DIM)],
        selectbackground=[("readonly", BG_SURF2)],
        selectforeground=[("readonly", FG_ON_SURF)],
    )
    # Dropdown list colours — only reachable via option_add
    state.root.option_add("*TCombobox*Listbox.background",       BG_SURF2)
    state.root.option_add("*TCombobox*Listbox.foreground",       FG_ON_SURF)
    state.root.option_add("*TCombobox*Listbox.selectBackground", CYAN_CONT)
    state.root.option_add("*TCombobox*Listbox.selectForeground", ON_CYAN_CONT)
    state.root.option_add("*TCombobox*Listbox.font",             "Segoe UI 9")
