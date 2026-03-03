"""
BPM detection and cache management.

No app-level imports — keeps the dependency graph clean.
Uses pydub for cross-platform audio analysis (no numpy/librosa dependencies).

Public API:
  get_cached_bpm(path) -> float | None   read-only cache lookup (preview)
  detect_bpm(path)     -> float | None   check cache then run analysis (run worker)
  flush_cache()                          write cache to disk if dirty (end of run)
"""

import json
import statistics
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


def _get_pydub():
    """Lazy-load pydub and configure ffmpeg path."""
    from pydub import AudioSegment
    import static_ffmpeg
    AudioSegment.converter = static_ffmpeg.ffmpeg_path
    AudioSegment.ffprobe = static_ffmpeg.ffprobe_path
    return AudioSegment


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
    Return BPM for path. Checks cache first; runs pydub-based analysis on miss.
    Analyzes first 60 seconds at reduced sample rate for speed.
    Stores result in cache (flush_cache() must be called to persist).
    Returns float or None on failure.
    """
    _load_cache()
    cached = get_cached_bpm(path)
    if cached is not None:
        return cached
    try:
        AudioSegment = _get_pydub()
        
        # Determine format for pydub
        fmt = Path(path).suffix.lower().lstrip('.')
        if fmt == 'aif':
            fmt = 'aiff'
        
        # Load audio and downmix to mono for analysis
        audio = AudioSegment.from_file(str(path), format=fmt)
        audio = audio.set_channels(1)
        
        # Limit analysis to first 60 seconds for speed
        if len(audio) > 60000:
            audio = audio[:60000]
        
        # High-pass filter at 200Hz to focus on transients (kicks/snares)
        filtered = audio.high_pass_filter(200)
        
        # Split into small chunks and analyze RMS energy
        chunk_ms = 10  # 10ms chunks for decent time resolution
        chunks = [filtered[i:i+chunk_ms] for i in range(0, len(filtered), chunk_ms)]
        rms_values = [chunk.rms for chunk in chunks if len(chunk) > 0]
        
        if not rms_values or max(rms_values) == 0:
            return None
        
        # Calculate dynamic threshold
        mean_rms = statistics.mean(rms_values)
        std_rms = statistics.stdev(rms_values) if len(rms_values) > 1 else 0
        threshold = mean_rms + (1.5 * std_rms)
        
        # Find peaks above threshold with local maximum check
        peaks = []
        for i, rms in enumerate(rms_values):
            if rms > threshold:
                # Check if this is a local maximum
                is_peak = True
                if i > 0 and rms <= rms_values[i-1]:
                    is_peak = False
                if i < len(rms_values) - 1 and rms < rms_values[i+1]:
                    is_peak = False
                if is_peak:
                    peaks.append(i * chunk_ms / 1000.0)  # Convert to seconds
        
        if len(peaks) < 2:
            return None
        
        # Calculate inter-onset intervals
        intervals = [peaks[i+1] - peaks[i] for i in range(len(peaks)-1)]
        
        # Filter valid intervals (30-300 BPM range)
        # 30 BPM = 2.0s per beat, 300 BPM = 0.2s per beat
        valid_intervals = [i for i in intervals if 0.2 <= i <= 2.0]
        
        if len(valid_intervals) < 2:
            return None
        
        # Use median for robustness against outliers
        median_interval = statistics.median(valid_intervals)
        bpm_val = 60.0 / median_interval
        
        # Round to reasonable precision and clamp to valid range
        bpm_val = round(bpm_val, 1)
        bpm_val = max(30.0, min(300.0, bpm_val))
        
        _store(path, bpm_val)
        return bpm_val
        
    except Exception:
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
