import shutil
import threading
from pathlib import Path
from tkinter import messagebox

import state
import theme
import constants
from log_panel import log


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

    state.run_btn.state(["disabled"])
    state.run_btn.configure(text="Running\u2026")
    if state._status_dot:
        state._status_dot.configure(fg=theme.CYAN)
    state.progress_var.set(0)
    state.status_var.set("Collecting files\u2026")
    path_limit = constants.PROFILES[state.profile_var.get()]["path_limit"]
    threading.Thread(
        target=_run_worker,
        args=(source, dest, state.move_var.get(), state.dry_var.get(),
              path_limit, state.no_rename_var.get()),
        daemon=True,
    ).start()


def _run_worker(source, dest, move_files, dry, path_limit, no_rename):
    files = [f for f in source.rglob("*")
             if f.suffix.lower() in constants.AUDIO_EXTS and f.is_file()]
    total = len(files)

    if total == 0:
        state.root.after(0, lambda: state.status_var.set("No audio files found."))
        state.root.after(0, lambda: state.run_btn.configure(text="Run"))
        state.root.after(0, lambda: state.run_btn.state(["!disabled"]))
        if state._status_dot:
            state.root.after(0, lambda: state._status_dot.configure(fg=theme.FG_DIM))
        return

    label  = "MOVE" if move_files else "COPY"
    prefix = "[DRY] " if dry else ""

    for i, f in enumerate(files, 1):
        new_name = f.name if no_rename else f"{f.parent.name}_{f.name}"
        if path_limit is not None:
            new_name = _apply_path_limit(new_name, str(dest), path_limit)
        target = dest / new_name
        msg    = f"{prefix}{label}: {f.name}  \u2192  {new_name}"

        state.root.after(0, lambda m=msg: log(m))
        state.root.after(0, lambda pct=int(i / total * 100): state.progress_var.set(pct))
        state.root.after(0, lambda s=f"Processing {i} / {total}\u2026": state.status_var.set(s))

        if not dry:
            dest.mkdir(parents=True, exist_ok=True)
            if move_files:
                shutil.move(str(f), str(target))
            else:
                shutil.copy2(str(f), str(target))

    s = "s" if total != 1 else ""
    state.root.after(0, lambda: log("Done."))
    state.root.after(0, lambda: state.status_var.set(f"Complete \u2014 {total} file{s} processed."))
    state.root.after(0, lambda: state.run_btn.configure(text="Run"))
    state.root.after(0, lambda: state.run_btn.state(["!disabled"]))
    if state._status_dot:
        state.root.after(0, lambda: state._status_dot.configure(fg=theme.C_COPY))
