"""Persistent app settings — stored in ~/.sampson/settings.json"""

import json
from pathlib import Path

_SETTINGS_DIR  = Path.home() / ".sampson"
_SETTINGS_FILE = _SETTINGS_DIR / "settings.json"
_settings: dict = {}
_loaded = False


def _load():
    global _settings, _loaded
    if _loaded:
        return
    _loaded = True
    try:
        if _SETTINGS_FILE.exists():
            _settings = json.loads(_SETTINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        _settings = {}


def _save():
    try:
        _SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        _SETTINGS_FILE.write_text(json.dumps(_settings, indent=2), encoding="utf-8")
    except Exception:
        pass


def get_last_source() -> str | None:
    """Return last used source directory, or None if not set."""
    _load()
    return _settings.get("last_source")


def set_last_source(path: str) -> None:
    """Persist last used source directory."""
    _load()
    _settings["last_source"] = path
    _save()
