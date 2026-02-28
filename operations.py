import shutil
import threading
from pathlib import Path
from tkinter import messagebox

import state
import theme
import constants
from log_panel import log
from conversion import (
    check_ffmpeg, convert_file, get_target_extension,
    parse_sample_rate, parse_bit_depth, parse_channels
)


def _apply_path_limit(new_name: str, dest_path_str: str, limit: int) -> str:
    """
    Truncate new_name so that the full destination path stays within `limit` chars.

    The extension is always preserved; only the stem is shortened.
    """
    full = str(Path(dest_path_str) / new_name)
    if len(full) <= limit:
        return new_name
    p     = Path(new_name)
    ext   = p.suffix
    avail = limit - len(str(Path(dest_path_str))) - 1 - len(ext)
    if avail < 1:
        avail = 1
    return p.stem[:avail] + ext


def _compute_output(f: Path, source_root: Path, dest: Path,
                    no_rename: bool, struct_mode: str,
                    path_limit) -> tuple:
    """
    Return (new_filename, rel_subfolder) for a single source file.

    new_filename  — the final filename written to disk
    rel_subfolder — subfolder relative to dest where the file lands:
                    ""            flat mode  (file goes directly in dest/)
                    "Kicks"       parent mode (file goes in dest/Kicks/)
                    "Kicks/808"   mirror mode (file goes in dest/Kicks/808/)

    struct_mode is one of "flat", "mirror", "parent".
    path_limit is int | None (from the active hardware profile).
    """
    # Filename
    new_name = f.name if no_rename else f"{f.parent.name}_{f.name}"

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
    else:                          # "flat" or unrecognised
        rel_sub = ""

    # Path limit
    effective_dest = str(Path(dest) / rel_sub) if rel_sub else str(dest)
    if path_limit is not None:
        new_name = _apply_path_limit(new_name, effective_dest, path_limit)

    return new_name, rel_sub


def run_tool():
    source = Path(state.active_dir_var.get().strip()) if state.active_dir_var.get().strip() else None
    dest   = Path(state.dest_var.get().strip())

    if not source or not source.is_dir():
        messagebox.showerror("Error",
            "Please navigate to a source directory in Deck A.", parent=state.root)
        return
    if not dest.is_dir():
        messagebox.showerror("Error",
            "Please select a valid destination folder in Deck B.", parent=state.root)
        return

    if not state._selected_folders:
        messagebox.showwarning("No selection",
            "Please check at least one folder in Deck A.", parent=state.root)
        return

    state.run_btn.configure(state="disabled")
    state.run_btn.configure(text="Running\u2026")
    if state._status_dot:
        state._status_dot.configure(text_color=theme.CYAN)
    state.progress_var.set(0)
    state.status_var.set("Collecting files\u2026")
    path_limit  = constants.PROFILES[state.profile_var.get()]["path_limit"]
    struct_mode = state.struct_mode_var.get()
    
    # Build conversion options if enabled
    convert_options = None
    if state.convert_enabled_var and state.convert_enabled_var.get():
        if not check_ffmpeg():
            messagebox.showerror(
                "Conversion Error",
                "ffmpeg is required for audio conversion.\n\n"
                "Install:\n"
                "- Windows: Download from ffmpeg.org and add to PATH\n"
                "- macOS: brew install ffmpeg\n"
                "- Linux: sudo apt install ffmpeg",
                parent=state.root
            )
            state.run_btn.configure(text="Run", state="normal")
            return
        
        convert_options = {
            "output_format": state.convert_format_var.get(),
            "sample_rate": parse_sample_rate(state.convert_sample_rate_var.get()),
            "bit_depth": parse_bit_depth(state.convert_bit_depth_var.get()),
            "channels": parse_channels(state.convert_channels_var.get()),
            "normalize": state.convert_normalize_var.get() if state.convert_normalize_var else False,
        }
    
    threading.Thread(
        target=_run_worker,
        args=(source, dest, state.move_var.get(), state.dry_var.get(),
              path_limit, state.no_rename_var.get(), struct_mode, convert_options),
        daemon=True,
    ).start()


def _run_worker(source, dest, move_files, dry, path_limit, no_rename, struct_mode, convert_options=None):
    files = []
    for folder_path in state._selected_folders:
        p = Path(folder_path)
        if p.is_dir():
            files += [f for f in p.rglob("*")
                      if f.suffix.lower() in constants.AUDIO_EXTS and f.is_file()]
    total = len(files)

    if total == 0:
        state.root.after(0, lambda: state.status_var.set("No audio files found."))
        state.root.after(0, lambda: state.run_btn.configure(text="Run"))
        state.root.after(0, lambda: state.run_btn.configure(state="normal"))
        if state._status_dot:
            state.root.after(0, lambda: state._status_dot.configure(text_color=theme.FG_DIM))
        return

    label  = "MOVE" if move_files else "COPY"
    prefix = "[DRY] " if dry else ""
    conv_label = " [convert]" if convert_options else ""

    for i, f in enumerate(files, 1):
        new_name, rel_sub = _compute_output(f, source, dest,
                                            no_rename, struct_mode, path_limit)
        
        # Apply extension change if converting
        if convert_options:
            new_name = Path(new_name).stem + get_target_extension(
                convert_options["output_format"])
        
        sub_dir = dest / rel_sub if rel_sub else dest
        target  = sub_dir / new_name
        dest_display = f"{rel_sub}/{new_name}" if rel_sub else new_name
        msg = f"{prefix}{label}{conv_label}: {f.name}  \u2192  {dest_display}"

        state.root.after(0, lambda m=msg: log(m))
        state.root.after(0, lambda pct=int(i / total * 100): state.progress_var.set(pct))
        state.root.after(0, lambda s=f"Processing {i} / {total}\u2026": state.status_var.set(s))

        if not dry:
            sub_dir.mkdir(parents=True, exist_ok=True)
            
            if convert_options:
                # Convert file
                try:
                    success = convert_file(f, target, **convert_options)
                    if not success:
                        error_detail = state._last_conversion_error if state._last_conversion_error else "Unknown error"
                        state.root.after(0, lambda fn=f.name, err=error_detail: log(f"ERROR: Failed to convert {fn}: {err[:200]}"))
                        state._last_conversion_error = None  # Clear after logging
                        continue
                    if move_files:
                        f.unlink()  # Delete original after conversion
                except Exception as e:
                    state.root.after(0, lambda fn=f.name, msg=str(e): log(f"ERROR: Failed to convert {fn}: {msg}"))
                    continue
            else:
                # Standard copy/move
                if move_files:
                    shutil.move(str(f), str(target))
                else:
                    shutil.copy2(str(f), str(target))

    s = "s" if total != 1 else ""
    state.root.after(0, lambda: log("Done."))
    state.root.after(0, lambda: state.status_var.set(f"Complete \u2014 {total} file{s} processed."))
    state.root.after(0, lambda: state.run_btn.configure(text="Run"))
    state.root.after(0, lambda: state.run_btn.configure(state="normal"))
    if state._status_dot:
        state.root.after(0, lambda: state._status_dot.configure(text_color=theme.C_COPY))
