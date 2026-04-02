"""File operations — copy/move/convert with progress tracking."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path

import state
import constants
import bpm as bpm_module
import key as key_module
import preview
from conversion import (
    check_ffmpeg, convert_file, get_target_extension,
    parse_sample_rate, parse_bit_depth, parse_channels
)


def _apply_path_limit(new_name: str, dest_path_str: str, limit: int,
                      protect_suffixes: list = None) -> str:
    """Truncate new_name so full path stays within limit chars."""
    if protect_suffixes is None:
        protect_suffixes = []
    
    full = str(Path(dest_path_str) / new_name)
    if len(full) <= limit:
        return new_name
    
    p = Path(new_name)
    ext = p.suffix
    total_protect_len = sum(len(s) for s in protect_suffixes)
    avail = limit - len(str(Path(dest_path_str))) - 1 - len(ext) - total_protect_len
    if avail < 1:
        avail = 1
    
    stem = p.stem
    for suffix in sorted(protect_suffixes, key=len, reverse=True):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)]
    
    all_suffixes = "".join(protect_suffixes)
    return stem[:avail] + all_suffixes + ext


def _compute_output(f: Path, source_root: Path, dest: Path,
                    no_rename: bool, struct_mode: str,
                    path_limit, bpm=None, append_bpm=False,
                    key=None, append_key=False, custom_prefix="") -> tuple:
    """Return (new_filename, rel_subfolder) for a single source file."""
    # Filename
    if custom_prefix:
        new_name = f"{custom_prefix}_{f.name}"
    elif not no_rename:
        new_name = f"{f.parent.name}_{f.name}"
    else:
        new_name = f.name

    # Subfolder
    if struct_mode == "mirror":
        try:
            rel_sub = str(f.parent.relative_to(source_root))
        except ValueError:
            rel_sub = ""
        if rel_sub == ".":
            rel_sub = ""
    elif struct_mode == "parent":
        rel_sub = f.parent.name if f.parent != source_root else ""
    else:
        rel_sub = ""

    # BPM suffix
    bpm_suffix = f"_{int(round(bpm))}bpm" if (bpm is not None and append_bpm) else ""
    if bpm_suffix:
        p = Path(new_name)
        new_name = p.stem + bpm_suffix + p.suffix

    # Key suffix
    key_suffix = f"_{key}" if (key is not None and append_key) else ""
    if key_suffix:
        p = Path(new_name)
        new_name = p.stem + key_suffix + p.suffix

    # Path limit
    effective_dest = str(Path(dest) / rel_sub) if rel_sub else str(dest)
    if path_limit is not None:
        protect_suffixes = []
        if bpm_suffix:
            protect_suffixes.append(bpm_suffix)
        if key_suffix:
            protect_suffixes.append(key_suffix)
        new_name = _apply_path_limit(new_name, effective_dest, path_limit,
                                     protect_suffixes=protect_suffixes)

    return new_name, rel_sub


def run_tool():
    """Main entry point — validates inputs and starts worker thread."""
    state.set("is_running", True)
    
    source_str = state.get("active_dir", "").strip()
    dest_str = state.get("dest", "").strip()
    
    source = Path(source_str) if source_str else None
    dest = Path(dest_str) if dest_str else None

    if not source or not source.is_dir():
        state.add_log("Error: Please navigate to a source directory in Deck A", "error")
        state.set_status("Error: No source directory", 0)
        return
    
    if not dest or not dest.is_dir():
        state.add_log("Error: Please select a valid destination folder in Deck B", "error")
        state.set_status("Error: No destination directory", 0)
        return

    selected_folders = state.get("selected_folders", [])
    if not selected_folders:
        state.add_log("Warning: Please check at least one folder in Deck A", "warn")
        state.set_status("Warning: No folders selected", 0)
        state.set("is_running", False)
        return

    # Gather options
    profile = state.get("profile", "Generic")
    path_limit = constants.PROFILES.get(profile, {}).get("path_limit") if profile else None
    struct_mode = state.get("struct_mode", "flat")
    
    move_files = state.get("move", False)
    dry = state.get("dry", True)
    no_rename = not state.get("modify_names", False)
    custom_prefix = state.get("custom_prefix", "")
    
    # Conversion options
    convert_options = None
    if state.get("convert_enabled", False):
        if not check_ffmpeg():
            state.add_log(
                "Conversion Error: ffmpeg is required for audio conversion.\n\n"
                "Install:\n"
                "- Windows: Download from ffmpeg.org and add to PATH\n"
                "- macOS: brew install ffmpeg\n"
                "- Linux: sudo apt install ffmpeg",
                "error"
            )
            state.set_status("Error: FFmpeg not found", 0)
            state.set("is_running", False)
            return
        
        convert_options = {
            "output_format": state.get("convert_format", "wav"),
            "sample_rate": parse_sample_rate(state.get("convert_sample_rate", "keep")),
            "bit_depth": parse_bit_depth(state.get("convert_bit_depth", "keep")),
            "channels": parse_channels(state.get("convert_channels", "keep")),
            "normalize": state.get("convert_normalize", False),
        }
    
    bpm_enabled = state.get("bpm_enabled", False)
    bpm_append = state.get("bpm_append", False)
    bpm_fresh = state.get("bpm_fresh", False)
    
    key_enabled = state.get("key_enabled", False)
    key_append = state.get("key_append", False)
    key_fresh = state.get("key_fresh", False)

    state.set_status("Collecting files...", 0)

    threading.Thread(
        target=_run_worker,
        args=(source, dest, move_files, dry,
              path_limit, no_rename, struct_mode, convert_options,
              bpm_enabled, bpm_append, bpm_fresh,
              key_enabled, key_append, key_fresh, custom_prefix),
        daemon=True,
    ).start()


def _run_worker(source, dest, move_files, dry, path_limit, no_rename, struct_mode,
                convert_options=None, bpm_enabled=False, bpm_append=False, bpm_fresh=False,
                key_enabled=False, key_append=False, key_fresh=False, custom_prefix=""):
    """Background worker for file operations."""
    files = []
    selected_folders = state.get("selected_folders", [])
    
    for folder_path in selected_folders:
        p = Path(folder_path)
        if p.is_dir():
            files += [f for f in p.rglob("*")
                      if f.suffix.lower() in constants.AUDIO_EXTS and f.is_file()]
    
    total = len(files)

    if total == 0:
        state.set_status("No audio files found.", 0)
        return

    label = "MOVE" if move_files else "COPY"
    prefix = "[DRY] " if dry else ""
    conv_label = " [convert]" if convert_options else ""

    for i, f in enumerate(files, 1):
        bpm_val = bpm_module.detect_bpm(f, force=bpm_fresh) if bpm_enabled else None
        
        # Output BPM detection log messages
        for bpm_log_msg in bpm_module.get_log_messages():
            state.add_log(bpm_log_msg)
        
        key_val = key_module.detect_key(f, force=key_fresh) if key_enabled else None
        
        # Output Key detection log messages
        for key_log_msg in key_module.get_log_messages():
            state.add_log(key_log_msg)
        
        new_name, rel_sub = _compute_output(
            f, source, dest, no_rename, struct_mode, path_limit,
            bpm=bpm_val, append_bpm=bpm_append,
            key=key_val, append_key=key_append,
            custom_prefix=custom_prefix
        )
        
        # Check for manual name override
        manual_override = preview.get_name_override(f)
        if manual_override:
            if convert_options:
                new_name = manual_override + get_target_extension(
                    convert_options["output_format"])
            else:
                new_name = manual_override + Path(new_name).suffix
        
        # Apply extension change if converting (only if no manual override)
        elif convert_options:
            new_name = Path(new_name).stem + get_target_extension(
                convert_options["output_format"])
        
        sub_dir = dest / rel_sub if rel_sub else dest
        target = sub_dir / new_name
        dest_display = f"{rel_sub}/{new_name}" if rel_sub else new_name
        msg = f"{prefix}{label}{conv_label}: {f.name}  →  {dest_display}"

        state.add_log(msg)
        
        progress_pct = int(i / total * 100)
        state.set_status(f"Processing {i} / {total}...", progress_pct)

        if not dry:
            sub_dir.mkdir(parents=True, exist_ok=True)
            
            if convert_options:
                try:
                    success = convert_file(f, target, **convert_options)
                    if not success:
                        error_detail = state._last_conversion_error if state._last_conversion_error else "Unknown error"
                        state.add_log(f"ERROR: Failed to convert {f.name}: {error_detail[:200]}", "error")
                        state._last_conversion_error = None
                        continue
                    if move_files:
                        f.unlink()
                except Exception as e:
                    state.add_log(f"ERROR: Failed to convert {f.name}: {e}", "error")
                    continue
            else:
                if move_files:
                    shutil.move(str(f), str(target))
                else:
                    shutil.copy2(str(f), str(target))

    if bpm_enabled:
        bpm_module.flush_cache()
        for bpm_log_msg in bpm_module.get_log_messages():
            state.add_log(bpm_log_msg)
    
    if key_enabled:
        key_module.flush_cache()
        for key_log_msg in key_module.get_log_messages():
            state.add_log(key_log_msg)

    s = "s" if total != 1 else ""
    
    if bpm_enabled:
        detected_count = sum(1 for f in files if bpm_module.get_cached_bpm(f) is not None)
        state.add_log(f"[BPM] Detected BPM for {detected_count}/{total} file{s}")
    
    if key_enabled:
        detected_count = sum(1 for f in files if key_module.get_cached_key(f) is not None)
        state.add_log(f"[KEY] Detected key for {detected_count}/{total} file{s}")
    
    state.add_log("Done.", "success")
    state.set_status(f"Complete — {total} file{s} processed.", 100)
    state.set("is_running", False)
    
    # Refresh preview if BPM was detected
    if bpm_enabled and state._refresh_preview_cb:
        state._refresh_preview_cb()
