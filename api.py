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
import slicer
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
                break
        # All fallbacks failed — start empty, don't crash
        
        # Restore last destination (no fallback, blank if not valid)
        last_dest = app_settings.get_last_dest()
        if last_dest and Path(last_dest).is_dir():
            state.set("dest", last_dest)
            preview.refresh()
        # Note: no auto_sync_check here — preview scan not complete yet

    def set_option(self, key: str, value: Any) -> None:
        """Generic setter for any option key."""
        state.set(key, value)
        
        # Trigger side effects
        if key in ("source", "active_dir") and value:
            self._on_source_changed(value)
        elif key == "dest":
            preview.refresh()
            # Save and check for previous SAMPSON run
            if value and isinstance(value, str) and Path(value).is_dir():
                app_settings.set_last_dest(value)
                operations.auto_sync_check(Path(value))
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
                app_settings.set_last_dest(path)
                preview.refresh()
                # Check for previous SAMPSON run and auto-trigger sync if found
                operations.auto_sync_check(Path(path))
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

    # ========================================================================
    # Sample Slicer
    # ========================================================================

    def slicer_open(self, filepath: str) -> dict:
        """Open a file in the slicer - load waveform and file info."""
        try:
            from pathlib import Path
            
            if not filepath or not Path(filepath).exists():
                return {"success": False, "error": "File not found"}
            
            # Load waveform data
            waveform_result = slicer.get_audio_samples(filepath)
            if not waveform_result.get("success"):
                return waveform_result
            
            # Get file info
            file_info = {
                "path": filepath,
                "name": Path(filepath).name,
                "duration": waveform_result["duration"],
                "sample_rate": waveform_result["sample_rate"],
                "channels": waveform_result["channels"],
            }
            
            # Batch update all state at once for single push
            state.update({
                "slicer_file": filepath,
                "slicer_file_info": file_info,
                "slicer_waveform": waveform_result["samples"],
                "slicer_slices": [{
                    "start_ms": 0.0,
                    "end_ms": waveform_result["duration"] * 1000,
                    "start_str": "0:00.000",
                    "end_str": slicer._ms_to_str(waveform_result["duration"] * 1000),
                    "duration_ms": waveform_result["duration"] * 1000,
                    "duration_str": slicer._ms_to_str(waveform_result["duration"] * 1000),
                }],
                "slicer_open": True,
                "slicer_progress": 0,
                "slicer_status": "Ready"
            }, push=False)
            state.push_keys(["slicer_file", "slicer_file_info", "slicer_waveform", 
                           "slicer_slices", "slicer_open", "slicer_progress", "slicer_status"])
            
            return {"success": True, "file_info": file_info}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def slicer_close(self) -> dict:
        """Close the slicer modal."""
        state.set("slicer_open", False)
        return {"success": True}

    def slicer_set_slices(self, slices: list) -> dict:
        """Update the current slices from JS."""
        state.set("slicer_slices", slices)
        return {"success": True}

    def slicer_auto_silence(self, filepath: str, threshold_db: float = -40.0, 
                            min_length_ms: float = 100.0, padding_ms: float = 10.0) -> dict:
        """Run auto-slice based on silence detection."""
        try:
            result = slicer.auto_slice_silence(filepath, threshold_db, min_length_ms, padding_ms)
            if result.get("success"):
                state.set("slicer_slices", result["slices"])
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def slicer_auto_bpm(self, filepath: str, bpm: float, beats_per_slice: int = 1) -> dict:
        """Run auto-slice based on BPM grid."""
        try:
            result = slicer.auto_slice_bpm(filepath, bpm, beats_per_slice)
            if result.get("success"):
                state.set("slicer_slices", result["slices"])
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def slicer_auto_fixed(self, filepath: str, slice_length_ms: float) -> dict:
        """Run auto-slice based on fixed length."""
        try:
            result = slicer.auto_slice_fixed(filepath, slice_length_ms)
            if result.get("success"):
                state.set("slicer_slices", result["slices"])
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def slicer_auto_transients(self, filepath: str, sensitivity: float = 1.5,
                               min_spacing_ms: float = 100.0) -> dict:
        """Run auto-slice based on transient detection."""
        try:
            result = slicer.auto_slice_transients(filepath, sensitivity, min_spacing_ms)
            if result.get("success"):
                state.set("slicer_slices", result["slices"])
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def slicer_export(self, filepath: str, slices: list, output_dir: str,
                      prefix: str = "", suffix: str = "_##", 
                      output_format: str = "wav",
                      normalize: bool = False, 
                      trim_silence: bool = False) -> dict:
        """Start exporting slices in background thread."""
        try:
            slicer.start_export_thread(
                filepath, slices, output_dir, prefix, suffix,
                output_format, normalize, trim_silence
            )
            return {"success": True, "message": "Export started"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def slicer_preview_slice(self, filepath: str, start_ms: float, end_ms: float) -> dict:
        """Extract and play a single slice for preview."""
        try:
            result = slicer.preview_slice(filepath, start_ms, end_ms)
            if not result.get("success"):
                return result
            playback.play_file(result["temp_path"])
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def slicer_browse_output(self) -> dict:
        """Browse for slicer output directory."""
        try:
            result = webview.windows[0].create_file_dialog(
                webview.FOLDER_DIALOG,
                directory=state.get("source") or os.path.expanduser("~")
            )
            if result and len(result) > 0:
                return {"success": True, "path": result[0]}
        except Exception as e:
            state.add_log(f"Browse error: {e}", "error")
        return {"success": False, "path": None}
