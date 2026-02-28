import sys
import tkinter as tk
import customtkinter as ctk

import state
import theme
from dpi import _enable_dpi_awareness, _compute_dpi_scale, MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT
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

    from dpi import _px, _usable_screen_size, MIN_ASPECT_RATIO
    win_w, win_h = _usable_screen_size(state.root, _px(1100), _px(780))
    state.root.geometry(f"{win_w}x{win_h}")
    state.root.minsize(_px(MIN_WINDOW_WIDTH), _px(MIN_WINDOW_HEIGHT))
    state.root.configure(fg_color=theme.BG_ROOT)
    theme.setup_styles()
    build_app()

    # Enforce aspect ratio on macOS to prevent extreme narrow/tall windows
    if sys.platform == "darwin":
        def _enforce_aspect(event):
            if event.widget is not state.root:
                return
            w, h = event.width, event.height
            if w <= 1 or h <= 1:
                return
            if (w / h) < MIN_ASPECT_RATIO:
                new_h = int(w / MIN_ASPECT_RATIO)
                state.root.geometry(f"{w}x{new_h}")
        state.root.bind("<Configure>", _enforce_aspect)

    state.root.mainloop()
