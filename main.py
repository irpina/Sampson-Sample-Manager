"""SAMPSON v0.9.0 — PyWebView entry point."""

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
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        bundle_dir = sys._MEIPASS
        ui_path = os.path.join(bundle_dir, 'ui', 'index.html')
    else:
        # Running in dev
        script_dir = os.path.dirname(os.path.abspath(__file__))
        ui_path = os.path.join(script_dir, 'ui', 'index.html')
    
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
    
    # Start webview
    webview.start(
        debug=False,  # Set to True for dev
        http_server=False,
        gui='edgechromium' if sys.platform == 'win32' else ('qt' if sys.platform == 'linux' else 'cocoa'),
    )


if __name__ == "__main__":
    main()
