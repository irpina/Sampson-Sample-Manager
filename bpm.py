"""
BPM detection and cache management.

No app-level imports — keeps the dependency graph clean.
Uses pydub for cross-platform audio analysis (no numpy/librosa dependencies).

Public API:
  get_cached_bpm(path) -> float | None   read-only cache lookup (preview)
  detect_bpm(path)     -> float | None   check cache then run analysis (run worker)
  flush_cache()                          write cache to disk if dirty (end of run)
  get_log_messages()   -> list[str]      retrieve and clear accumulated log messages
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

# Debug log messages accumulated during detection
_log_messages: list[str] = []


def _log(msg: str):
    """Accumulate a log message for later retrieval."""
    _log_messages.append(msg)


def get_log_messages() -> list[str]:
    """Retrieve and clear accumulated log messages."""
    global _log_messages
    msgs = _log_messages.copy()
    _log_messages.clear()
    return msgs


def _load_cache():
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    _cache_loaded = True
    try:
        if _CACHE_FILE.exists():
            _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            _log(f"[BPM] Loaded cache with {len(_cache)} entries from {_CACHE_FILE}")
    except Exception as e:
        _log(f"[BPM] Cache load failed: {e}")
        _cache = {}


def _entry_valid(path: Path) -> bool:
    """Return True if cache has a fresh entry for path (mtime matches)."""
    key = str(path)
    if key not in _cache:
        return False
    try:
        cached_mtime = _cache[key]["mtime"]
        current_mtime = path.stat().st_mtime
        if cached_mtime == current_mtime:
            return True
        _log(f"[BPM] Cache stale for {path.name} (mtime changed)")
        return False
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
        bpm = float(_cache[str(path)]["bpm"])
        return bpm
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
        _log(f"[BPM] CACHE HIT: {path.name} = {cached:.1f} BPM")
        return cached
    
    _log(f"[BPM] Analyzing: {path.name}")
    
    try:
        AudioSegment = _get_pydub()
        
        # Determine format for pydub
        fmt = Path(path).suffix.lower().lstrip('.')
        if fmt == 'aif':
            fmt = 'aiff'
        
        _log(f"[BPM]   Format: {fmt}")
        
        # Load audio and downmix to mono for analysis
        try:
            audio = AudioSegment.from_file(str(path), format=fmt)
        except Exception as e:
            _log(f"[BPM]   ERROR: Failed to load file - {e}")
            return None
        
        _log(f"[BPM]   Loaded: {len(audio)}ms, {audio.channels}ch, {audio.frame_rate}Hz")
        
        audio = audio.set_channels(1)
        
        # Limit analysis to first 60 seconds for speed
        if len(audio) > 60000:
            audio = audio[:60000]
            _log(f"[BPM]   Trimmed to first 60s for analysis")
        
        # High-pass filter at 200Hz to focus on transients (kicks/snares)
        filtered = audio.high_pass_filter(200)
        _log(f"[BPM]   Applied 200Hz high-pass filter")
        
        # Split into small chunks and analyze RMS energy
        chunk_ms = 10  # 10ms chunks for decent time resolution
        chunks = [filtered[i:i+chunk_ms] for i in range(0, len(filtered), chunk_ms)]
        rms_values = [chunk.rms for chunk in chunks if len(chunk) > 0]
        
        _log(f"[BPM]   Analyzed {len(rms_values)} chunks")
        
        if not rms_values:
            _log(f"[BPM]   ERROR: No audio data after chunking")
            return None
            
        max_rms = max(rms_values)
        if max_rms == 0:
            _log(f"[BPM]   ERROR: Silent audio (RMS = 0)")
            return None
        
        # Calculate dynamic threshold
        mean_rms = statistics.mean(rms_values)
        std_rms = statistics.stdev(rms_values) if len(rms_values) > 1 else 0
        threshold = mean_rms + (1.5 * std_rms)
        
        _log(f"[BPM]   RMS stats: mean={mean_rms:.1f}, max={max_rms:.1f}, std={std_rms:.1f}")
        _log(f"[BPM]   Peak threshold: {threshold:.1f}")
        
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
        
        _log(f"[BPM]   Found {len(peaks)} peaks")
        
        if len(peaks) < 2:
            _log(f"[BPM]   ERROR: Not enough peaks for BPM detection (need ≥2, got {len(peaks)})")
            return None
        
        # Calculate inter-onset intervals
        intervals = [peaks[i+1] - peaks[i] for i in range(len(peaks)-1)]
        
        # Filter valid intervals (30-300 BPM range)
        # 30 BPM = 2.0s per beat, 300 BPM = 0.2s per beat
        valid_intervals = [i for i in intervals if 0.2 <= i <= 2.0]
        
        _log(f"[BPM]   Valid intervals: {len(valid_intervals)}/{len(intervals)} (0.2-2.0s range)")
        
        if len(valid_intervals) < 2:
            _log(f"[BPM]   ERROR: Not enough valid intervals (need ≥2, got {len(valid_intervals)})")
            return None
        
        # Use median for robustness against outliers
        median_interval = statistics.median(valid_intervals)
        bpm_val = 60.0 / median_interval
        
        # Round to reasonable precision and clamp to valid range
        bpm_val = round(bpm_val, 1)
        bpm_val = max(30.0, min(300.0, bpm_val))
        
        _log(f"[BPM]   DETECTED: {bpm_val:.1f} BPM (interval={median_interval:.3f}s)")
        
        _store(path, bpm_val)
        _log(f"[BPM]   Cached result for {path.name}")
        return bpm_val
        
    except Exception as e:
        _log(f"[BPM]   ERROR: Exception during analysis - {type(e).__name__}: {e}")
        return None


def flush_cache():
    """Write the in-memory cache to ~/.sampson/bpm_cache.json if dirty."""
    global _cache_dirty
    if not _cache_dirty:
        _log(f"[BPM] Cache unchanged, no write needed")
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(_cache, indent=2), encoding="utf-8")
        _cache_dirty = False
        _log(f"[BPM] Cache saved: {_CACHE_FILE} ({len(_cache)} entries)")
    except Exception as e:
        _log(f"[BPM] ERROR: Failed to save cache - {e}")
