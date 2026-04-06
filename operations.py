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


def _hash_file(path: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    import hashlib
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


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
    
    # Duplicate detection setup
    dedup_enabled = state.get("dedup_enabled", True)
    dest_size_index = {}
    dest_hash_cache = {}
    seen_hashes = set()
    seen_hashes_by_size = set()
    
    if dedup_enabled and dest and dest.is_dir():
        # Pre-scan destination: build size -> [paths] index
        for dest_file in dest.rglob("*"):
            if dest_file.suffix.lower() in constants.AUDIO_EXTS and dest_file.is_file():
                size = dest_file.stat().st_size
                if size not in dest_size_index:
                    dest_size_index[size] = []
                dest_size_index[size].append(dest_file)

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
        
        # Duplicate detection check
        if dedup_enabled:
            src_size = f.stat().st_size
            src_hash = None
            duplicate_of = None
            
            # Source-to-dest check (only if not converting, since format changes hash)
            if not convert_options and src_size in dest_size_index:
                for candidate in dest_size_index[src_size]:
                    # Lazy hash computation with cache
                    dest_hash = dest_hash_cache.get(str(candidate))
                    if dest_hash is None:
                        try:
                            dest_hash = _hash_file(candidate)
                            dest_hash_cache[str(candidate)] = dest_hash
                        except Exception:
                            continue
                    if src_hash is None:
                        try:
                            src_hash = _hash_file(f)
                        except Exception:
                            break
                    if src_hash == dest_hash:
                        duplicate_of = candidate.name
                        break
            
            # Source-to-source check (within this run)
            if duplicate_of is None:
                if src_size in seen_hashes_by_size:
                    if src_hash is None:
                        try:
                            src_hash = _hash_file(f)
                        except Exception:
                            pass
                    if src_hash and src_hash in seen_hashes:
                        duplicate_of = "earlier file in this run"
            
            if duplicate_of:
                state.add_log(f"SKIP (duplicate): {f.name} — content already exists as {duplicate_of}")
                continue
            
            # Track this file's hash for future source-to-source checks
            if src_hash is None:
                try:
                    src_hash = _hash_file(f)
                except Exception:
                    pass
            if src_hash:
                seen_hashes.add(src_hash)
                seen_hashes_by_size.add(src_size)
        
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
    
    # Destination dedup cleanup (top level only, not subdirectories)
    if dedup_enabled and dest and dest.is_dir():
        _dedup_dest_flat(dest, dry)
    
    state.add_log("Done.", "success")
    state.set_status(f"Complete — {total} file{s} processed.", 100)
    state.set("is_running", False)
    
    # Refresh preview if BPM was detected
    if bpm_enabled and state._refresh_preview_cb:
        state._refresh_preview_cb()


def _dedup_dest_flat(dest: Path, dry: bool) -> int:
    """Remove content-duplicate audio files from the top level of dest only.
    
    Keeps the alphabetically first file among duplicates. Returns count removed.
    """
    if not dest or not dest.is_dir():
        return 0
    
    # Get only top-level audio files
    files = [f for f in dest.iterdir()
             if f.is_file() and f.suffix.lower() in constants.AUDIO_EXTS]
    
    if len(files) < 2:
        return 0
    
    # Group by size
    size_groups = {}
    for f in files:
        size_groups.setdefault(f.stat().st_size, []).append(f)
    
    removed = 0
    for group in size_groups.values():
        if len(group) < 2:
            continue
        
        seen = {}  # hash -> file path (first occurrence)
        for f in sorted(group):  # alphabetical — keep first
            try:
                h = _hash_file(f)
                if h in seen:
                    prefix = "[DRY] " if dry else ""
                    state.add_log(f"{prefix}DEDUP: {f.name} — duplicate of {seen[h].name}, removed from destination")
                    if not dry:
                        f.unlink()
                    removed += 1
                else:
                    seen[h] = f
            except Exception:
                pass
    
    return removed

# =============================================================================
# SYNC SYSTEM — Plan → Preview → Execute
# =============================================================================

def auto_sync_check(dest: Path):
    """Check if destination contains files from a previous SAMPSON run.
    
    If any expected destination files exist, auto-trigger sync plan computation.
    Called when destination folder is selected.
    """
    if not dest or not dest.is_dir():
        state.set("sync_auto_detected", False)
        return
    
    import preview
    expected = preview.get_expected_dest_paths(dest)
    if not expected:
        state.set("sync_auto_detected", False)
        return  # Source not loaded yet — skip
    
    for path_str in expected:
        if Path(path_str).exists():
            state.set("sync_auto_detected", True)
            state.add_log("Previous SAMPSON run detected — switching to sync mode", "info")
            compute_sync_plan()  # Auto-trigger plan
            return
    
    state.set("sync_auto_detected", False)


def compute_sync_plan():
    """Public entry point — validates inputs and starts plan computation thread."""
    source_str = state.get("active_dir", "").strip()
    dest_str = state.get("dest", "").strip()
    
    source = Path(source_str) if source_str else None
    dest = Path(dest_str) if dest_str else None

    if not source or not source.is_dir():
        state.add_log("Error: Please navigate to a source directory in Deck A", "error")
        state.set_status("Error: No source directory", 0)
        return {"success": False, "error": "No source directory"}
    
    if not dest or not dest.is_dir():
        state.add_log("Error: Please select a valid destination folder in Deck B", "error")
        state.set_status("Error: No destination directory", 0)
        return {"success": False, "error": "No destination directory"}
    
    selected_folders = state.get("selected_folders", [])
    if not selected_folders:
        state.add_log("Warning: Please check at least one folder in Deck A", "warn")
        state.set_status("Warning: No folders selected", 0)
        return {"success": False, "error": "No folders selected"}

    # Reset plan state
    state.update({
        "sync_plan": [],
        "sync_plan_ready": False,
        "sync_plan_counts": {"add": 0, "update": 0, "delete": 0, "skip": 0},
        "sync_show_plan": True,
    })
    
    state.set_status("Computing sync plan...", 0)
    
    threading.Thread(
        target=_sync_plan_worker,
        args=(source, dest),
        daemon=True,
    ).start()
    
    return {"success": True}


def _sync_plan_worker(source: Path, dest: Path):
    """Background worker to build the sync plan."""
    try:
        # Gather options
        profile = state.get("profile", "Generic")
        path_limit = constants.PROFILES.get(profile, {}).get("path_limit") if profile else None
        struct_mode = state.get("struct_mode", "flat")
        modify_names = state.get("modify_names", False)
        no_rename = not modify_names
        custom_prefix = state.get("custom_prefix", "")
        sync_mode = state.get("sync_mode", "additive")
        
        # BPM/Key options
        bpm_enabled = state.get("bpm_enabled", False)
        bpm_append = state.get("bpm_append", False)
        key_enabled = state.get("key_enabled", False)
        key_append = state.get("key_append", False)
        
        # Conversion options
        convert_enabled = state.get("convert_enabled", False)
        convert_format = state.get("convert_format", "wav")
        
        # Duplicate detection setup
        dedup_enabled = state.get("dedup_enabled", True)
        dest_size_index = {}
        dest_hash_cache = {}
        seen_hashes = set()
        seen_hashes_by_size = set()
        
        if dedup_enabled and dest and dest.is_dir():
            # Pre-scan destination: build size -> [paths] index
            for dest_file in dest.rglob("*"):
                if dest_file.suffix.lower() in constants.AUDIO_EXTS and dest_file.is_file():
                    size = dest_file.stat().st_size
                    if size not in dest_size_index:
                        dest_size_index[size] = []
                    dest_size_index[size].append(dest_file)
        
        # Gather source files
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
            state.set("sync_plan_ready", True)
            return
        
        plan = []
        expected_dest_files = set()  # Track expected files for mirror mode
        
        # Destination flat dedup: scan top level for duplicates, add DELETE entries
        if dedup_enabled and dest and dest.is_dir():
            dest_files = [f for f in dest.iterdir()
                          if f.is_file() and f.suffix.lower() in constants.AUDIO_EXTS]
            
            if len(dest_files) >= 2:
                # Group by size
                dest_size_groups = {}
                for f in dest_files:
                    dest_size_groups.setdefault(f.stat().st_size, []).append(f)
                
                dest_seen_hashes = {}
                for group in dest_size_groups.values():
                    if len(group) < 2:
                        continue
                    for f in sorted(group):  # alphabetical — keep first
                        try:
                            h = _hash_file(f)
                            if h in dest_seen_hashes:
                                plan.append({
                                    "action": "delete",
                                    "src_name": "",
                                    "srcpath": None,
                                    "dest_path": str(f),
                                    "dest_display": f.name,
                                    "rel_sub": "",
                                    "new_name": "",
                                    "duplicate_of": dest_seen_hashes[h].name,
                                })
                            else:
                                dest_seen_hashes[h] = f
                        except Exception:
                            pass
        
        for i, f in enumerate(files, 1):
            # Get BPM/Key values
            bpm_val = bpm_module.get_cached_bpm(f) if bpm_enabled else None
            key_val = key_module.get_cached_key(f) if key_enabled else None
            
            # Compute output path using existing logic
            new_name, rel_sub = _compute_output(
                f, source, dest, no_rename, struct_mode, path_limit,
                bpm=bpm_val if (bpm_enabled and bpm_append) else None,
                append_bpm=bpm_append,
                key=key_val if (key_enabled and key_append) else None,
                append_key=key_append,
                custom_prefix=custom_prefix
            )
            
            # Check for manual name override
            manual_override = preview.get_name_override(f)
            if manual_override:
                if convert_enabled:
                    new_name = manual_override + get_target_extension(convert_format)
                else:
                    new_name = manual_override + Path(new_name).suffix
            elif convert_enabled:
                new_name = Path(new_name).stem + get_target_extension(convert_format)
            
            # Build full destination path
            sub_dir = dest / rel_sub if rel_sub else dest
            dest_path = sub_dir / new_name
            dest_path_str = str(dest_path)
            expected_dest_files.add(dest_path_str)
            
            # Duplicate detection check
            is_duplicate = False
            duplicate_of = None
            
            if dedup_enabled:
                src_size = f.stat().st_size
                src_hash = None
                
                # Source-to-dest check (only if not converting)
                if not convert_enabled and src_size in dest_size_index:
                    for candidate in dest_size_index[src_size]:
                        # Lazy hash computation with cache
                        dest_hash = dest_hash_cache.get(str(candidate))
                        if dest_hash is None:
                            try:
                                dest_hash = _hash_file(candidate)
                                dest_hash_cache[str(candidate)] = dest_hash
                            except Exception:
                                continue
                        if src_hash is None:
                            try:
                                src_hash = _hash_file(f)
                            except Exception:
                                break
                        if src_hash == dest_hash:
                            is_duplicate = True
                            duplicate_of = str(candidate.name)
                            break
                
                # Source-to-source check (within this run)
                if not is_duplicate and src_size in seen_hashes_by_size:
                    if src_hash is None:
                        try:
                            src_hash = _hash_file(f)
                        except Exception:
                            pass
                    if src_hash and src_hash in seen_hashes:
                        is_duplicate = True
                        duplicate_of = "earlier file in this run"
                
                # Track this file's hash
                if src_hash is None and not is_duplicate:
                    try:
                        src_hash = _hash_file(f)
                    except Exception:
                        pass
                if src_hash:
                    seen_hashes.add(src_hash)
                    seen_hashes_by_size.add(src_size)
            
            # Determine action
            if is_duplicate:
                action = "skip"
            elif not dest_path.exists():
                action = "add"
            else:
                # Compare size and mtime
                src_stat = f.stat()
                dest_stat = dest_path.stat()
                
                if src_stat.st_size != dest_stat.st_size:
                    action = "update"
                elif src_stat.st_mtime > dest_stat.st_mtime:
                    action = "update"
                else:
                    action = "skip"
            
            plan.append({
                "action": action,
                "src_name": f.name,
                "srcpath": str(f),
                "dest_path": dest_path_str,
                "dest_display": f"{rel_sub}/{new_name}" if rel_sub else new_name,
                "rel_sub": rel_sub,
                "new_name": new_name,
                "duplicate_of": duplicate_of if is_duplicate else None,
            })
            
            progress_pct = int(i / total * 100)
            state.set_status(f"Computing sync plan... {i}/{total}", progress_pct)
        
        # Mirror mode: find orphan files to delete
        if sync_mode == "mirror":
            # Walk destination directory
            delete_count = 0
            for dest_file in dest.rglob("*"):
                if dest_file.suffix.lower() in constants.AUDIO_EXTS and dest_file.is_file():
                    dest_file_str = str(dest_file)
                    if dest_file_str not in expected_dest_files:
                        # Check if this is within our target subdirectories
                        try:
                            rel_to_dest = dest_file.relative_to(dest)
                            plan.append({
                                "action": "delete",
                                "src_name": "",
                                "srcpath": None,
                                "dest_path": dest_file_str,
                                "dest_display": str(rel_to_dest),
                                "rel_sub": "",
                                "new_name": "",
                            })
                            delete_count += 1
                        except ValueError:
                            pass
        
        # Compute counts
        counts = {
            "add": sum(1 for p in plan if p["action"] == "add"),
            "update": sum(1 for p in plan if p["action"] == "update"),
            "delete": sum(1 for p in plan if p["action"] == "delete"),
            "skip": sum(1 for p in plan if p["action"] == "skip"),
        }
        
        # Update state with plan
        state.update({
            "sync_plan": plan,
            "sync_plan_ready": True,
            "sync_plan_counts": counts,
        })
        
        action_summary = f"{counts['add']} add · {counts['update']} update · {counts['delete']} delete · {counts['skip']} skip"
        state.add_log(f"Sync plan ready: {action_summary}", "success")
        state.set_status(f"Sync plan ready — {action_summary}", 100)
        
    except Exception as e:
        state.add_log(f"Sync plan error: {e}", "error")
        state.set_status(f"Sync plan failed: {e}", 0)
        state.set("sync_plan_ready", False)


def run_sync():
    """Public entry point — starts sync execution in background thread."""
    if not state.get("sync_plan_ready", False):
        return {"success": False, "error": "No sync plan ready. Compute plan first."}
    
    if state.get("sync_in_progress", False):
        return {"success": False, "error": "Sync already in progress."}
    
    plan = state.get("sync_plan", [])
    if not plan:
        return {"success": False, "error": "Sync plan is empty."}
    
    state.set("sync_in_progress", True)
    state.set_status("Starting sync execution...", 0)
    
    threading.Thread(
        target=_run_sync_worker,
        args=(plan,),
        daemon=True,
    ).start()
    
    return {"success": True}


def _run_sync_worker(plan: list):
    """Background worker to execute the sync plan."""
    try:
        # Gather conversion options
        convert_options = None
        if state.get("convert_enabled", False):
            if not check_ffmpeg():
                state.add_log(
                    "Sync Error: ffmpeg is required for audio conversion.",
                    "error"
                )
                state.set_status("Error: FFmpeg not found", 0)
                state.set("sync_in_progress", False)
                return
            
            convert_options = {
                "output_format": state.get("convert_format", "wav"),
                "sample_rate": parse_sample_rate(state.get("convert_sample_rate", "keep")),
                "bit_depth": parse_bit_depth(state.get("convert_bit_depth", "keep")),
                "channels": parse_channels(state.get("convert_channels", "keep")),
                "normalize": state.get("convert_normalize", False),
            }
        
        move_files = state.get("move", False)
        
        # Filter to only actionable items
        actionable = [p for p in plan if p["action"] in ("add", "update", "delete")]
        total = len(actionable)
        
        if total == 0:
            state.add_log("Sync: Nothing to do — all files up to date.", "success")
            state.set_status("Sync complete — nothing to do", 100)
            state.set("sync_in_progress", False)
            return
        
        processed = 0
        
        for entry in actionable:
            action = entry["action"]
            dest_path = Path(entry["dest_path"])
            
            if action == "delete":
                try:
                    dest_path.unlink()
                    state.add_log(f"DELETE: {entry['dest_display']}")
                except Exception as e:
                    state.add_log(f"ERROR: Failed to delete {entry['dest_display']}: {e}", "error")
                
                processed += 1
                progress_pct = int(processed / total * 100)
                state.set_status(f"Syncing... {processed}/{total}", progress_pct)
                continue
            
            # Add or Update
            srcpath = Path(entry["srcpath"]) if entry["srcpath"] else None
            if not srcpath or not srcpath.exists():
                state.add_log(f"ERROR: Source file not found: {entry['src_name']}", "error")
                processed += 1
                continue
            
            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            if convert_options:
                try:
                    success = convert_file(srcpath, dest_path, **convert_options)
                    if not success:
                        error_detail = state._last_conversion_error if state._last_conversion_error else "Unknown error"
                        state.add_log(f"ERROR: Failed to convert {entry['src_name']}: {error_detail[:200]}", "error")
                        state._last_conversion_error = None
                        processed += 1
                        continue
                    if move_files:
                        srcpath.unlink()
                except Exception as e:
                    state.add_log(f"ERROR: Failed to convert {entry['src_name']}: {e}", "error")
                    processed += 1
                    continue
            else:
                if move_files:
                    shutil.move(str(srcpath), str(dest_path))
                else:
                    shutil.copy2(str(srcpath), str(dest_path))
            
            action_label = "ADD" if action == "add" else "UPDATE"
            state.add_log(f"{action_label}: {entry['src_name']} → {entry['dest_display']}")
            
            processed += 1
            progress_pct = int(processed / total * 100)
            state.set_status(f"Syncing... {processed}/{total}", progress_pct)
        
        # Clean up empty directories in mirror mode
        if state.get("sync_mode") == "mirror":
            dest = Path(state.get("dest", ""))
            if dest and dest.is_dir():
                _cleanup_empty_dirs(dest)
        
        state.add_log("Sync complete.", "success")
        state.set_status(f"Sync complete — {processed} files processed", 100)
        
        # Clear plan after successful execution
        state.update({
            "sync_plan": [],
            "sync_plan_ready": False,
            "sync_plan_counts": {"add": 0, "update": 0, "delete": 0, "skip": 0},
            "sync_show_plan": False,
        })
        
    except Exception as e:
        state.add_log(f"Sync execution error: {e}", "error")
        state.set_status(f"Sync failed: {e}", 0)
    finally:
        state.set("sync_in_progress", False)


def _cleanup_empty_dirs(root: Path):
    """Remove empty directories recursively (bottom-up)."""
    for dirpath in sorted(root.rglob("*"), reverse=True):
        if dirpath.is_dir():
            try:
                # Only remove if empty
                if not any(dirpath.iterdir()):
                    dirpath.rmdir()
            except Exception:
                pass


def clear_sync_plan():
    """Clear the current sync plan and return to normal preview view."""
    state.update({
        "sync_plan": [],
        "sync_plan_ready": False,
        "sync_plan_counts": {"add": 0, "update": 0, "delete": 0, "skip": 0},
        "sync_show_plan": False,
    })
    return {"success": True}
