import tkinter as tk

import state
import theme
from dpi import _enable_dpi_awareness, _compute_dpi_scale
from builders import build_app

if __name__ == "__main__":
    _enable_dpi_awareness()
    state.root = tk.Tk()
    state.root.withdraw()                                       # hide while setting up

    # Compute actual screen DPI and tell tkinter to match it
    state._dpi_scale = _compute_dpi_scale()
    state.root.tk.call('tk', 'scaling', (state._dpi_scale * 96) / 72)

    state.root.title("Dirtywave File Helper")

    from dpi import _px
    state.root.geometry(f"{_px(1100)}x{_px(720)}")
    state.root.minsize(_px(900), _px(600))
    state.root.configure(bg=theme.BG_ROOT)
    theme.setup_styles()
    build_app()
    state.root.deiconify()                                      # show fully built
    state.root.mainloop()
