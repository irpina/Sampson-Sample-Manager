"""
BPM detection and cache management.

No app-level imports — keeps the dependency graph clean.
All aubio/numpy imports are lazy (inside detect_bpm() only).

Public API:
  get_cached_bpm(path) -> float | None   read-only cache lookup (preview)
  detect_bpm(path)     -> float | None   check cache then run aubio (run worker)
  flush_cache()                          write cache to disk if dirty (end of run)
"""

import json
from pathlib import Path

# ── Cache location ─────────────────────────────────────────────────────────────
_CACHE_DIR  = Path.home() / ".sampson"
_CACHE_FILE = _CACHE_DIR / "bpm_cache.json"

# { "/abs/path/to/file.wav": {"mtime": 1698765432.1, "bpm": 120.0} }
_cache: dict        = {}
_cache_dirty: bool  = False
_cache_loaded: bool = False


def _load_cache():
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    _cache_loaded = True
    try:
        if _CACHE_FILE.exists():
            _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        _cache = {}


def _entry_valid(path: Path) -> bool:
    """Return True if cache has a fresh entry for path (mtime matches)."""
    key = str(path)
    if key not in _cache:
        return False
    try:
        return _cache[key]["mtime"] == path.stat().st_mtime
    except Exception:
        return False


def _store(path: Path, bpm_val: float):
    global _cache_dirty
    try:
        _cache[str(path)] = {"mtime": path.stat().st_mtime, "bpm": float(bpm_val)}
        _cache_dirty = True
    except Exception:
        pass


# ── Public API ────────────────────────────────────────────────────────────────

def get_cached_bpm(path: Path):
    """
    Read-only cache lookup. Never runs audio detection.
    Returns float or None.
    """
    _load_cache()
    if _entry_valid(path):
        return float(_cache[str(path)]["bpm"])
    return None


def detect_bpm(path: Path):
    """
    Return BPM for path. Checks cache first; runs librosa beat tracking on miss.
    Loads only the first 60 s at 22050 Hz (mono) for speed.
    Stores result in cache (flush_cache() must be called to persist).
    Returns float or None on failure.
    """
    _load_cache()
    cached = get_cached_bpm(path)
    if cached is not None:
        return cached
    try:
        import librosa
        y, sr   = librosa.load(str(path), sr=22050, mono=True, duration=60)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # tempo may be a scalar or a 1-element array depending on librosa version
        bpm_val = float(tempo[0] if hasattr(tempo, "__len__") else tempo)
        if bpm_val > 0:
            _store(path, bpm_val)
            return bpm_val
    except Exception:
        pass
    return None


def flush_cache():
    """Write the in-memory cache to ~/.sampson/bpm_cache.json if dirty."""
    global _cache_dirty
    if not _cache_dirty:
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(_cache, indent=2), encoding="utf-8")
        _cache_dirty = False
    except Exception:
        pass
