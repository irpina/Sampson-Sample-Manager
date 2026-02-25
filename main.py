import tkinter as tk

import state
import theme
from builders import build_app

if __name__ == "__main__":
    state.root = tk.Tk()
    state.root.title("Dirtywave File Helper")
    state.root.geometry("1100x720")
    state.root.minsize(900, 600)
    state.root.configure(bg=theme.BG_ROOT)
    theme.setup_styles()
    build_app()
    state.root.mainloop()
