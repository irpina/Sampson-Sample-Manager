"""SAMPSON — PyWebView entry point. Version lives in constants.VERSION."""

from __future__ import annotations

import os
import sys
import atexit

# Windows: Patch subprocess.Popen globally BEFORE any imports to prevent
# console window flashing in PyInstaller-built GUI apps.
if sys.platform == "win32":
    import subprocess
    _OrigPopen = subprocess.Popen
    class _NoConsoleWindowPopen(_OrigPopen):
        def __init__(self, *args, **kwargs):
            kwargs['creationflags'] = kwargs.get('creationflags', 0) | 0x08000000
            super().__init__(*args, **kwargs)
    subprocess.Popen = _NoConsoleWindowPopen

# macOS: Prevent bytecode caching issues
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

# ---------------------------------------------------------------------------
# PyWebView imports
# ---------------------------------------------------------------------------
import webview

import state
from api import SampsonAPI


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def main():
    """Create and run the PyWebView application."""
    
    # Initialize state
    api = SampsonAPI()
    
    # Determine UI path (works both in dev and PyInstaller bundle)
    base_dir = sys._MEIPASS if getattr(sys, 'frozen', False) \
        else os.path.dirname(os.path.abspath(__file__))
    ui_path = os.path.join(base_dir, 'ui', 'index.html')
    # Runtime window icon, by backend: the Windows EdgeChromium backend feeds
    # the path to System.Drawing.Icon (needs an .ico — a PNG throws); Qt/GTK
    # (Linux) takes a PNG; macOS uses the .app bundle icon, so skip it there.
    if sys.platform == 'win32':
        icon_path = os.path.join(base_dir, 'ui', 'icon.ico')
    elif sys.platform == 'linux':
        icon_path = os.path.join(base_dir, 'ui', 'icon.png')
    else:
        icon_path = None
    
    # Create window
    window = webview.create_window(
        title="SAMPSON",
        url=ui_path,
        js_api=api,
        width=1400,
        height=900,
        min_size=(1100, 700),
        text_select=False,
    )
    
    # Store window reference for state sync
    state.set_window(window)
    
    # macOS: Activate app after window creation
    if sys.platform == "darwin":
        def activate():
            try:
                import Cocoa
                Cocoa.NSApp.activateIgnoringOtherApps_(True)
            except Exception:
                pass
        import threading
        threading.Timer(0.5, activate).start()
    
    # Start webview. icon is honoured by the Qt/GTK backends (Linux); on
    # Windows the taskbar icon comes from the bundled .exe (SAMPSON.spec).
    start_kwargs = dict(
        debug=False,  # Set to True for dev
        http_server=False,
        gui='edgechromium' if sys.platform == 'win32' else ('qt' if sys.platform == 'linux' else 'cocoa'),
    )
    if icon_path and os.path.exists(icon_path):
        start_kwargs['icon'] = icon_path
    try:
        webview.start(**start_kwargs)
    except TypeError:
        # Older pywebview without the icon kwarg
        start_kwargs.pop('icon', None)
        webview.start(**start_kwargs)


if __name__ == "__main__":
    main()
