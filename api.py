"""PyWebView API bridge — Python ↔ JS interface for SAMPSON v0.10.0"""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path
from typing import Any

import webview

import state
import constants
import browser
import preview
import playback
import operations
import settings as app_settings
from conversion import check_ffmpeg


class SampsonAPI:
    """Exposed to JS via window.pywebview.api.*"""

    # ========================================================================
    # State getters / setters
    # ========================================================================

    def get_state(self) -> dict[str, Any]:
        """Return full application state."""
        return state.get_all()

    def on_ready(self) -> None:
        """Called by JS after initial render — applies startup source directory."""
        last = app_settings.get_last_source()

        # Fallback chain: saved path → cwd → app dir → nothing
        candidates = []
        if last:
            candidates.append(last)
        candidates.append(os.getcwd())
        if getattr(sys, 'frozen', False):
            candidates.append(os.path.dirname(sys.executable))
        else:
            candidates.append(os.path.dirname(os.path.abspath(__file__)))

        for path in candidates:
            if path and Path(path).is_dir():
                state.set("source", path)
                self._on_source_changed(path)
                return
        # All fallbacks failed — start empty, don't crash

    def set_option(self, key: str, value: Any) -> None:
        """Generic setter for any option key."""
        state.set(key, value)
        
        # Trigger side effects
        if key in ("source", "active_dir") and value:
            self._on_source_changed(value)
        elif key == "dest":
            preview.refresh()
        elif key in ("modify_names", "custom_prefix", "struct_mode", "profile"):
            preview.refresh()
        elif key == "preview_filter":
            preview.apply_filter(value)

    def set_options(self, options: dict[str, Any]) -> None:
        """Batch update multiple options."""
        for key, value in options.items():
            self.set_option(key, value)  # Use set_option to trigger side effects

    # ========================================================================
    # File dialogs (native OS)
    # ========================================================================

    def browse_source(self) -> str | None:
        """Open native folder picker for source. Returns path or None."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=state.get("source") or os.path.expanduser("~")
            )
            if result and len(result) > 0:
                path = result[0]
                state.set("source", path)
                app_settings.set_last_source(path)
                self._on_source_changed(path)
                return path
        except Exception as e:
            state.add_log(f"Browse error: {e}", "error")
        return None

    def browse_dest(self) -> str | None:
        """Open native folder picker for destination. Returns path or None."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=state.get("dest") or os.path.expanduser("~")
            )
            if result and len(result) > 0:
                path = result[0]
                state.set("dest", path)
                preview.refresh()
                return path
        except Exception as e:
            state.add_log(f"Browse error: {e}", "error")
        return None

    # ========================================================================
    # Deck A — In-app browser
    # ========================================================================

    def navigate(self, path: str) -> dict[str, Any]:
        """Navigate to path and return directory listing for Deck A."""
        return browser.navigate_to(path)

    def nav_up(self) -> dict[str, Any] | None:
        """Navigate up one level from current active_dir."""
        current = state.get("active_dir")
        if not current:
            return None
        p = Path(current)
        parent = p.parent
        if parent != p:
            return browser.navigate_to(str(parent))
        return None

    def toggle_folder(self, path: str, checked: bool) -> None:
        """Toggle folder selection in Deck A."""
        browser.toggle_folder(path, checked)

    def select_all_folders(self) -> None:
        """Select all visible folders in Deck A."""
        browser.select_all_visible()

    def deselect_all_folders(self) -> None:
        """Deselect all visible folders in Deck A."""
        browser.deselect_all_visible()

    # ========================================================================
    # Preview & Playback (Deck B)
    # ========================================================================

    def get_preview(self) -> list[dict]:
        """Get current preview entries for Deck B."""
        return state.get("preview_entries", [])

    def preview_play(self, srcpath: str) -> dict:
        """Start playback of a preview file."""
        try:
            result = playback.play_file(srcpath)
            return {"success": True, **result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def preview_stop(self) -> dict:
        """Stop playback."""
        try:
            playback.stop()
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def preview_next(self) -> dict:
        """Play next file in preview list."""
        try:
            return playback.next_file()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def preview_prev(self) -> dict:
        """Play previous file in preview list."""
        try:
            return playback.prev_file()
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Operations — RUN
    # ========================================================================

    def run(self) -> dict:
        """Start the file operation in a background thread."""
        try:
            # Validate
            source = state.get("source")
            dest = state.get("dest")
            
            if not source or not Path(source).is_dir():
                return {"success": False, "error": "Please select a valid source folder"}
            
            if not dest or not Path(dest).is_dir():
                return {"success": False, "error": "Please select a valid destination folder"}
            
            if source == dest:
                return {"success": False, "error": "Source and destination cannot be the same"}
            
            # Check ffmpeg if conversion enabled
            if state.get("convert_enabled") and not check_ffmpeg():
                return {"success": False, "error": "FFmpeg not found. Conversion requires FFmpeg."}
            
            # Start in thread
            import threading
            state.set_status("Running...", 0)
            thread = threading.Thread(target=operations.run_tool, daemon=True)
            thread.start()
            
            return {"success": True, "message": "Operation started"}
            
        except Exception as e:
            state.add_log(f"Run error: {e}", "error")
            return {"success": False, "error": str(e)}

    def check_ffmpeg(self) -> bool:
        """Check if FFmpeg is available."""
        return check_ffmpeg()

    # ========================================================================
    # Log
    # ========================================================================

    def get_log(self) -> list[dict]:
        """Get all log entries."""
        return state.get("log_lines", [])

    def clear_log(self) -> None:
        """Clear log."""
        state.clear_log()

    # ========================================================================
    # System
    # ========================================================================

    def get_drives(self) -> list[dict]:
        """Return root locations for the current OS."""
        system = platform.system()
        drives: list[dict] = []

        if system == "Windows":
            import string
            import ctypes
            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    path = f"{letter}:\\"
                    drives.append({"name": path, "path": path})
                bitmask >>= 1
        elif system == "Darwin":
            home = str(Path.home())
            drives = [
                {"name": "Home", "path": home},
                {"name": "Desktop", "path": os.path.join(home, "Desktop")},
                {"name": "Documents", "path": os.path.join(home, "Documents")},
                {"name": "Downloads", "path": os.path.join(home, "Downloads")},
                {"name": "Volumes", "path": "/Volumes"},
            ]
        else:
            home = str(Path.home())
            drives = [
                {"name": "Home", "path": home},
                {"name": "Desktop", "path": os.path.join(home, "Desktop")},
                {"name": "Documents", "path": os.path.join(home, "Documents")},
                {"name": "Downloads", "path": os.path.join(home, "Downloads")},
                {"name": "Root", "path": "/"},
            ]

        return drives

    def open_external(self, path: str) -> bool:
        """Open a file or folder in the OS file manager."""
        try:
            import subprocess
            system = platform.system()
            if system == "Darwin":
                subprocess.run(["open", path])
            elif system == "Windows":
                subprocess.run(["explorer", path])
            else:
                subprocess.run(["xdg-open", path])
            return True
        except Exception as e:
            state.add_log(f"Open external failed: {e}", "error")
            return False

    # ========================================================================
    # Internal helpers
    # ========================================================================

    def _on_source_changed(self, path: str) -> None:
        """Handle source path change — navigate and refresh preview."""
        browser.navigate_to(path)
        import preview
        preview.refresh()

    # ========================================================================
    # Preview sorting
    # ========================================================================

    def sort_preview(self, column: str) -> None:
        """Sort preview by column (bpm|key|duration)."""
        import preview
        preview.sort_by(column)

    # ========================================================================
    # BPM/Key editing
    # ========================================================================

    def set_file_bpm(self, filepath: str, bpm: float) -> dict:
        """Set BPM for a file."""
        import preview
        success = preview.set_file_bpm(filepath, bpm)
        return {"success": success}

    def set_file_key(self, filepath: str, key: str) -> dict:
        """Set key for a file."""
        import preview
        success = preview.set_file_key(filepath, key)
        return {"success": success}

    def set_file_name(self, filepath: str, name: str) -> dict:
        """Set manual filename override for a file (stem only, no extension)."""
        import preview
        success = preview.set_file_name(filepath, name)
        return {"ok": success}

    # ========================================================================
    # Sync System
    # ========================================================================

    def compute_sync_plan(self) -> dict:
        """Compute the sync plan (Plan phase)."""
        try:
            return operations.compute_sync_plan()
        except Exception as e:
            state.add_log(f"Compute sync plan error: {e}", "error")
            return {"success": False, "error": str(e)}

    def run_sync(self) -> dict:
        """Execute the computed sync plan (Execute phase)."""
        try:
            return operations.run_sync()
        except Exception as e:
            state.add_log(f"Run sync error: {e}", "error")
            return {"success": False, "error": str(e)}

    def clear_sync_plan(self) -> dict:
        """Clear the current sync plan and return to preview view."""
        try:
            return operations.clear_sync_plan()
        except Exception as e:
            state.add_log(f"Clear sync plan error: {e}", "error")
            return {"success": False, "error": str(e)}
