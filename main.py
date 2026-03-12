import sys
import os
import atexit

# Fix for Tcl/Tk 9.0 console crash in bundled app
os.environ['TK_SILENCE_DEPRECATION'] = '1'
os.environ['TCL_NO_STACK_TRACE'] = '1'

# macOS: Prevent "application is not open anymore" errors
if sys.platform == "darwin":
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

# Single instance check (macOS)
_single_instance_lock = None

def _ensure_single_instance():
    """Prevent multiple app instances using a lock file."""
    global _single_instance_lock
    if sys.platform != "darwin":
        return True
    
    import fcntl
    lock_path = os.path.expanduser("~/.sampson/app.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    
    try:
        _single_instance_lock = open(lock_path, "w")
        fcntl.flock(_single_instance_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _single_instance_lock.write(str(os.getpid()))
        _single_instance_lock.flush()
        return True
    except (IOError, OSError):
        print("SAMPSON is already running.")
        return False

def _release_lock():
    """Release the single instance lock on exit."""
    global _single_instance_lock
    if _single_instance_lock:
        try:
            import fcntl
            fcntl.flock(_single_instance_lock, fcntl.LOCK_UN)
            _single_instance_lock.close()
        except:
            pass

if sys.platform == "darwin" and not _ensure_single_instance():
    sys.exit(0)

atexit.register(_release_lock)

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
    
    # macOS: Ensure proper app activation
    if sys.platform == "darwin":
        try:
            from AppKit import NSApp, NSApplication
            app = NSApplication.sharedApplication()
            app.setActivationPolicy_(0)  # NSApplicationActivationPolicyRegular
            app.activateIgnoringOtherApps_(True)
        except Exception:
            pass

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
