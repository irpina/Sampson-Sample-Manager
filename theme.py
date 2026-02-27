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

    # ── Preview Treeview (ttk — no CTK equivalent) ──
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

    # ── Progressbar (ttk — kept to avoid touching operations.py) ──
    style.configure("MD3.Horizontal.TProgressbar",
        troughcolor=BG_SURF2, background=CYAN,
        bordercolor=BG_SURF2, lightcolor=CYAN, darkcolor=CYAN,
        thickness=4,
    )
