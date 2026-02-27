import tkinter as tk
import customtkinter as ctk

import state
import theme
from dpi import _enable_dpi_awareness, _compute_dpi_scale
from builders import build_app

if __name__ == "__main__":
    _enable_dpi_awareness()

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    state.root = ctk.CTk()

    # Compute DPI scale for _px() calls (used for non-CTK widget dimensions).
    # CTk handles its own internal scaling — do not call tk.call('tk', 'scaling', …).
    state._dpi_scale = _compute_dpi_scale()

    state.root.title("SAMPSON")

    from dpi import _px
    state.root.geometry(f"{_px(1100)}x{_px(780)}")
    state.root.minsize(_px(900), _px(600))
    state.root.configure(fg_color=theme.BG_ROOT)
    theme.setup_styles()
    build_app()
    state.root.mainloop()
