"""Deck A browser — pure path logic, returns data for JS rendering."""

from pathlib import Path

import state
import constants
import preview


def navigate_to(path_str: str) -> dict[str, any]:
    """Navigate to path and return directory listing for Deck A.
    
    Returns:
        {
            "current_path": str,
            "parent_path": str | None,
            "entries": [
                {"name": str, "path": str, "type": "up|folder|file", 
                 "checked": bool, "icon": str, "is_audio": bool}
            ],
            "audio_count": int,
        }
    """
    p = Path(path_str)
    if not p.is_dir():
        return {"error": "Not a directory", "current_path": path_str, "entries": []}

    state.set("active_dir", str(p), push=False)
    
    # Clear name overrides on folder navigation
    preview._name_overrides.clear()
    
    # Clear previous selection tracking for this view
    # (Keep existing selections — they persist across navigation)
    
    entries = []
    audio_count = 0

    # Parent entry (up button)
    parent = p.parent
    if parent != p:
        entries.append({
            "name": "..",
            "path": str(parent),
            "type": "up",
            "checked": False,
            "icon": "↑",
            "is_audio": False,
        })

    # Subdirectories
    try:
        subdirs = sorted(d for d in p.iterdir()
                         if d.is_dir() and not d.name.startswith("."))
        for d in subdirs:
            path_str_d = str(d)
            # Auto-select all subdirs on every navigation (matching original behavior)
            state._selected_folders.add(path_str_d)
            is_checked = True
            
            entries.append({
                "name": d.name,
                "path": path_str_d,
                "type": "folder",
                "checked": is_checked,
                "icon": "▶",
                "is_audio": False,
            })
        
        # Leaf directory — no subdirs, include the dir itself
        if not subdirs:
            state._selected_folders.add(str(p))
    except PermissionError:
        pass

    # Audio files
    try:
        audio = sorted(f for f in p.iterdir()
                       if f.is_file() and f.suffix.lower() in constants.AUDIO_EXTS)
        for f in audio:
            state._selected_folders.add(str(f))  # Add files to selection
            entries.append({
                "name": f.name,
                "path": str(f),
                "type": "file",
                "checked": True,        # Default checked
                "icon": "♪",
                "is_audio": True,
            })
            audio_count += 1
    except PermissionError:
        pass

    # Update state
    state._state["dir_entries"] = entries
    state._state["src_count"] = audio_count
    state._sync_selected_folders()
    state.push_keys(["dir_entries", "src_count", "selected_folders", "active_dir"])
    
    # Trigger preview refresh
    preview.refresh()

    return {
        "current_path": str(p),
        "parent_path": str(parent) if parent != p else None,
        "entries": entries,
        "audio_count": audio_count,
    }


def toggle_folder(path: str, checked: bool) -> None:
    """Toggle folder selection state."""
    if checked:
        state._selected_folders.add(path)
    else:
        state._selected_folders.discard(path)
    
    # Update the dir_entries checked state
    for entry in state._state.get("dir_entries", []):
        if entry.get("path") == path:
            entry["checked"] = checked
            break
    
    state._sync_selected_folders()
    state.push_keys(["selected_folders", "dir_entries"])
    preview.refresh()


def select_all_visible() -> None:
    """Select all visible folders and files."""
    for entry in state._state.get("dir_entries", []):
        if entry.get("type") in ("folder", "file"):
            entry["checked"] = True
            state._selected_folders.add(entry["path"])
    
    state._sync_selected_folders()
    state.push_keys(["selected_folders", "dir_entries"])
    preview.refresh()


def deselect_all_visible() -> None:
    """Deselect all visible folders and files."""
    for entry in state._state.get("dir_entries", []):
        if entry.get("type") in ("folder", "file"):
            entry["checked"] = False
            state._selected_folders.discard(entry["path"])
    
    state._sync_selected_folders()
    state.push_keys(["selected_folders", "dir_entries"])
    preview.refresh()


def get_selected_folders() -> list[str]:
    """Return list of selected folder paths."""
    return list(state._selected_folders)


def clear_selection() -> None:
    """Clear all folder selections."""
    state._selected_folders.clear()
    for entry in state._state.get("dir_entries", []):
        entry["checked"] = False
    state._sync_selected_folders()
    state.push_keys(["selected_folders", "dir_entries"])
