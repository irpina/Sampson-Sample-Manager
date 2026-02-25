import shutil
import threading
from pathlib import Path
from tkinter import messagebox

import state
import theme
import constants
from log_panel import log


def _m8_truncate(new_name: str, dest_path_str: str) -> str:
    """
    Truncate new_name so that the full destination path stays within 127 chars.

    The Dirtywave M8 has a 127-character limit for file paths on its SD card.
    The extension is always preserved; only the stem is shortened.
    """
    full = str(Path(dest_path_str) / new_name)
    if len(full) <= 127:
        return new_name
    p     = Path(new_name)
    ext   = p.suffix
    avail = 127 - len(str(Path(dest_path_str))) - 1 - len(ext)
    if avail < 1:
        avail = 1
    return p.stem[:avail] + ext


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
    threading.Thread(
        target=_run_worker,
        args=(source, dest, state.move_var.get(), state.dry_var.get(), state.m8_var.get()),
        daemon=True,
    ).start()


def _run_worker(source, dest, move_files, dry, m8_friendly):
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
        new_name = f"{f.parent.name}_{f.name}"
        if m8_friendly:
            new_name = _m8_truncate(new_name, str(dest))
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
