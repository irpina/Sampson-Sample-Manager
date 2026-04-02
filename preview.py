"""Preview generation — populates state["preview_entries"] for Deck B."""

from __future__ import annotations

import contextlib
import re
import sys
import threading
import wave
from pathlib import Path

import state
import constants
import bpm as bpm_module
import key as key_module
from operations import _compute_output
from conversion import get_target_extension

# ── Module state ─────────────────────────────────────────────────────────────

_preview_rows: list = []   # All row data for filtering/sorting
_duration_cache: dict = {}  # str(path) → float | None
_sort_col: str | None = None  # "bpm" | "key" | "duration" | None
_sort_asc: bool = True
_name_overrides: dict[str, str] = {}  # srcpath → manual dest stem


# ── Duration & helpers ───────────────────────────────────────────────────────

def _get_duration(path: Path) -> float | None:
    """Return duration in seconds from file metadata."""
    key = str(path)
    if key in _duration_cache:
        return _duration_cache[key]
    
    val = None
    try:
        ext = path.suffix.lower()
        if ext == '.wav':
            with contextlib.closing(wave.open(str(path))) as wf:
                val = wf.getnframes() / wf.getframerate()
        elif ext in ('.aif', '.aiff'):
            import aifc
            with contextlib.closing(aifc.open(str(path))) as af:
                val = af.getnframes() / af.getframerate()
        else:
            # Windows: Patch pydub's subprocess calls
            if sys.platform == "win32":
                import pydub.utils
                if not hasattr(pydub.utils.Popen, '_sampson_patched'):
                    _original_popen = pydub.utils.Popen
                    
                    def _popen_with_hidden_console(*args, **kwargs):
                        creationflags = kwargs.pop('creationflags', 0)
                        creationflags |= 0x08000000
                        kwargs['creationflags'] = creationflags
                        return _original_popen(*args, **kwargs)
                    
                    _popen_with_hidden_console._sampson_patched = True
                    pydub.utils.Popen = _popen_with_hidden_console
            
            from pydub.utils import mediainfo
            info = mediainfo(str(path))
            dur = info.get('duration')
            val = float(dur) if dur else None
    except Exception:
        val = None
    
    _duration_cache[key] = val
    return val


def _fmt_duration(secs: float | None) -> str:
    """Format seconds as m:ss (or h:mm:ss for files ≥ 1 hour)."""
    if secs is None:
        return ""
    s = int(round(secs))
    m, s = divmod(s, 60)
    if m >= 60:
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# ── Sorting ──────────────────────────────────────────────────────────────────

def _sort_key_for(col: str, row: dict):
    """Return a comparable sort key for the given column and row."""
    if col == "bpm":
        try:
            return (0, int(row.get("bpm", 0)))
        except (ValueError, TypeError):
            return (1, 0)
    elif col == "key":
        val = row.get("key", "")
        return (1, "") if val in ("", "???") else (0, val)
    elif col == "duration":
        dur = row.get("duration_sec")
        return (1, 0) if dur is None else (0, dur)
    return (0, "")


def _apply_sort():
    """Sort _preview_rows in-place by the current _sort_col."""
    global _preview_rows
    if _sort_col is None:
        return
    _preview_rows.sort(key=lambda row: _sort_key_for(_sort_col, row),
                       reverse=not _sort_asc)


def sort_by(col: str):
    """Toggle sort direction if col is active; otherwise sort ASC by col."""
    global _sort_col, _sort_asc
    _sort_asc = not _sort_asc if _sort_col == col else True
    _sort_col = col
    _apply_sort()
    filter_text = state.get("preview_filter", "")
    apply_filter(filter_text)


# ── Filter ───────────────────────────────────────────────────────────────────

def _parse_query(text: str):
    """Split query into (plain_text, bpm_spec, note_spec, min_len, max_len)."""
    plain_parts = []
    bpm_spec = None
    note_spec = None
    min_len = None
    max_len = None
    
    for token in text.strip().split():
        tl = token.lower()
        if tl.startswith("bpm:"):
            val = token[4:]
            if "-" in val:
                try:
                    lo, hi = val.split("-", 1)
                    bpm_spec = (int(lo), int(hi))
                except ValueError:
                    plain_parts.append(token)
            elif val.endswith("*"):
                try:
                    prefix = val[:-1]
                    prefix_num = int(prefix)
                    digits_to_fill = 3 - len(prefix)
                    multiplier = 10 ** digits_to_fill
                    lo = prefix_num * multiplier
                    hi = lo + multiplier - 1
                    bpm_spec = (lo, hi)
                except ValueError:
                    plain_parts.append(token)
            else:
                try:
                    bpm_spec = int(val)
                except ValueError:
                    plain_parts.append(token)
        elif tl.startswith("note:"):
            note_spec = token[5:].upper()
        elif tl.startswith("minlength:"):
            try:
                min_len = float(token[10:])
            except ValueError:
                plain_parts.append(token)
        elif tl.startswith("maxlength:"):
            try:
                max_len = float(token[10:])
            except ValueError:
                plain_parts.append(token)
        else:
            plain_parts.append(token)
    
    return " ".join(plain_parts).lower(), bpm_spec, note_spec, min_len, max_len


def _matches_filter(row: dict, has_query: bool, plain_text: str, 
                    bpm_spec, note_spec, min_len, max_len) -> bool:
    """Check if a row matches the filter criteria."""
    if not has_query:
        return True
    
    orig = row.get("src_name", "").lower()
    bpm_val = row.get("bpm", "")
    key_val = row.get("key", "")
    dur = row.get("duration_sec")
    
    if plain_text and plain_text not in orig:
        return False
    if bpm_spec is not None:
        try:
            b = int(bpm_val) if bpm_val and bpm_val != "???" else None
            if b is None:
                return False
            if isinstance(bpm_spec, tuple):
                if not (bpm_spec[0] <= b <= bpm_spec[1]):
                    return False
            elif b != bpm_spec:
                return False
        except (ValueError, TypeError):
            return False
    if note_spec is not None and key_val.upper() != note_spec:
        return False
    if min_len is not None:
        if dur is None or dur < min_len:
            return False
    if max_len is not None:
        if dur is None or dur > max_len:
            return False
    return True


def apply_filter(text: str = ""):
    """Filter _preview_rows and push to state["preview_entries"]."""
    global _preview_rows
    
    has_query = bool(text.strip())
    plain_text, bpm_spec, note_spec, min_len, max_len = _parse_query(text)
    
    matched = [
        row for row in _preview_rows 
        if _matches_filter(row, has_query, plain_text, bpm_spec, note_spec, min_len, max_len)
    ]
    
    # Apply max preview rows limit when no query
    display_rows = matched if has_query else matched[:constants.MAX_PREVIEW_ROWS]
    
    # Push to state (both together to ensure sync)
    state.update({"preview_entries": display_rows, "preview_count": len(display_rows)})
    
    # Update status message
    total_cached = len(_preview_rows)
    if total_cached > 0:
        modify_names = state.get("modify_names", False)
        n = len(matched)
        
        if has_query:
            status_msg = f"{n} of {total_cached} match"
        elif total_cached > constants.MAX_PREVIEW_ROWS:
            status_msg = f"Showing {constants.MAX_PREVIEW_ROWS} of {total_cached}"
        elif modify_names:
            status_msg = f"{total_cached} files will be renamed"
        else:
            status_msg = f"{total_cached} audio files"
        
        state.set("preview_count_label", status_msg, push=False)


# ── Name overrides ───────────────────────────────────────────────────────────

def get_name_override(filepath) -> str | None:
    """Get manual name override for a file (stem only, no extension)."""
    return _name_overrides.get(str(filepath))


def set_file_name(filepath: str, name: str) -> bool:
    """Set or clear manual name override for a file.
    
    Args:
        filepath: Full path to source file
        name: New filename stem (no extension), or empty to clear override
    
    Returns:
        True if successful
    """
    p = Path(filepath)
    if not p.exists():
        return False
    if name:
        _name_overrides[str(p)] = name
    else:
        _name_overrides.pop(str(p), None)
    refresh()
    return True


# ── Main refresh logic ───────────────────────────────────────────────────────

def refresh():
    """Public entry point — start a preview refresh."""
    p = state.get("active_dir", "")
    if not p or not Path(p).is_dir():
        state.update({
            "preview_entries": [],
            "preview_count": 0,
            "src_count": 0,
        })
        state.set_status("Navigate source to see preview")
        return
    
    state.set_status("Scanning...", 0)
    threading.Thread(target=_scan_thread, args=(p,), daemon=True).start()


def _scan_thread(path_str: str):
    """Background thread to scan files and compute preview."""
    global _duration_cache, _preview_rows
    _duration_cache = {}
    
    source_root = Path(path_str)
    selected = state.get("selected_folders", [])
    
    if selected:
        files = []
        already = set()
        for item_path in selected:
            p = Path(item_path)
            if p.is_dir():
                for f in p.rglob("*"):
                    if f.suffix.lower() in constants.AUDIO_EXTS and f.is_file() and f not in already:
                        files.append(f)
                        already.add(f)
            elif p.is_file() and p.suffix.lower() in constants.AUDIO_EXTS and p not in already:
                files.append(p)
                already.add(p)
    else:
        files = []
    
    # Get durations
    durations = {f: _get_duration(f) for f in files}
    
    # Build preview rows
    _populate_preview(files, source_root, durations)


def _populate_preview(files: list[Path], source_root: Path, durations: dict):
    """Build preview rows from scanned files."""
    global _preview_rows
    _preview_rows = []
    
    total = len(files)
    if total == 0 and not state.get("selected_folders", []):
        state.update({
            "preview_entries": [],
            "preview_count": 0,
            "src_count": 0,
        })
        state.set_status("No folders selected")
        return
    
    modify_names = state.get("modify_names", False)
    no_rename = not modify_names
    struct_mode = state.get("struct_mode", "flat")
    profile = state.get("profile", "Generic")
    path_limit = constants.PROFILES.get(profile, {}).get("path_limit") if profile else None
    dest = state.get("dest", "")
    dest_path = Path(dest) if dest else source_root
    
    bpm_enabled = state.get("bpm_enabled", False)
    bpm_append = state.get("bpm_append", False)
    key_enabled = state.get("key_enabled", False)
    key_append = state.get("key_append", False)
    
    convert_enabled = state.get("convert_enabled", False)
    target_format = state.get("convert_format", "wav")
    custom_prefix = state.get("custom_prefix", "")
    
    # Check if any files have cached BPM/key values
    has_any_bpm = any(bpm_module.get_cached_bpm(f) is not None for f in files)
    has_any_key = any(key_module.get_cached_key(f) is not None for f in files)
    show_bpm = bpm_enabled or has_any_bpm
    show_key = key_enabled or has_any_key
    
    rows = []
    for f in files:
        # BPM lookup
        bpm_val = bpm_module.get_cached_bpm(f) if show_bpm else None
        bpm_display = str(int(round(bpm_val))) if bpm_val is not None else ("???" if bpm_enabled else "")
        
        # Key lookup
        key_val = key_module.get_cached_key(f) if show_key else None
        key_display = key_val if key_val is not None else ("???" if key_enabled else "")
        
        # Compute output path
        new_name, rel_sub = _compute_output(
            f, source_root, dest_path, no_rename, struct_mode, path_limit,
            bpm=bpm_val if (bpm_enabled and bpm_append) else None,
            append_bpm=bpm_append,
            key=key_val if (key_enabled and key_append) else None,
            append_key=key_append,
            custom_prefix=custom_prefix
        )
        
        # Check for manual name override
        name_manual = False
        manual_override = _name_overrides.get(str(f))
        if manual_override:
            name_manual = True
            # Use manual name — preserve extension from conversion if active
            if convert_enabled:
                new_name = manual_override + get_target_extension(target_format)
            else:
                # Keep original extension
                new_name = manual_override + Path(new_name).suffix
        
        # Add visual placeholders (skip for manual overrides)
        if not manual_override:
            if bpm_enabled and bpm_append and bpm_val is None:
                p = Path(new_name)
                new_name = p.stem + "_???bpm" + p.suffix
            
            if key_enabled and key_append and key_val is None:
                p = Path(new_name)
                new_name = p.stem + "_???" + p.suffix
        
        # Add conversion indicator
        if convert_enabled:
            if not manual_override:
                new_name_stem = Path(new_name).stem
                new_name = new_name_stem + get_target_extension(target_format)
            display_name = f"{new_name} [c]"
        else:
            display_name = new_name
        
        duration_sec = durations.get(f)
        
        row = {
            "src_name": f.name,
            "dest_name": display_name,
            "name_manual": name_manual,
            "subfolder": rel_sub if (modify_names and struct_mode != "flat") else "",
            "bpm": bpm_display,
            "key": key_display,
            "length": _fmt_duration(duration_sec),
            "duration_sec": duration_sec,
            "srcpath": str(f),
        }
        rows.append(row)
    
    _preview_rows = rows
    
    # Apply sort if active
    _apply_sort()
    
    # Update source count
    state.set("src_count", total, push=False)
    
    # Apply filter and push to state
    filter_text = state.get("preview_filter", "")
    apply_filter(filter_text)
    
    # Final status
    s = "s" if total != 1 else ""
    if total == 0:
        state.set_status("No audio files in this directory tree")
    else:
        state.set_status(f"{total} audio file{s} ready")


# ── API helpers for editing BPM/Key ──────────────────────────────────────────

def set_file_bpm(filepath: str, bpm: float) -> bool:
    """Set BPM for a file and refresh preview."""
    from pathlib import Path
    p = Path(filepath)
    if not p.exists():
        return False
    
    if bpm_module.set_cached_bpm(p, bpm):
        refresh()
        return True
    return False


def set_file_key(filepath: str, key: str) -> bool:
    """Set key for a file and refresh preview."""
    from pathlib import Path
    p = Path(filepath)
    if not p.exists():
        return False
    
    if key_module.set_cached_key(p, key):
        refresh()
        return True
    return False


# Register refresh callback with state (for operations to trigger refresh)
state.register_refresh_callback(refresh)
