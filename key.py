"""
Musical key detection and cache management.

Uses pitch-period autocorrelation to detect the root pitch class.
Pure Python implementation - no FFT, no numpy.
"""

import json
import math
import os
from pathlib import Path
from typing import Optional

from conversion import _find_ffmpeg_path

# ── Cache ─────────────────────────────────────────────────────────────────────
_CACHE_DIR = Path.home() / ".sampson"
_CACHE_FILE = _CACHE_DIR / "key_cache.json"
_cache: dict = {}
_cache_dirty = False
_cache_loaded = False
_log_messages: list = []

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Standard pitch frequencies for octaves 2-5 (approximate)
# C2 = 65.41 Hz, C3 = 130.81 Hz, C4 = 261.63 Hz, C5 = 523.25 Hz
_PITCH_FREQUENCIES = {
    0: [65.41, 130.81, 261.63, 523.25],   # C
    1: [69.30, 138.59, 277.18, 554.37],   # C#
    2: [73.42, 146.83, 293.66, 587.33],   # D
    3: [77.78, 155.56, 311.13, 622.25],   # D#
    4: [82.41, 164.81, 329.63, 659.25],   # E
    5: [87.31, 174.61, 349.23, 698.46],   # F
    6: [92.50, 185.00, 369.99, 739.99],   # F#
    7: [98.00, 196.00, 392.00, 783.99],   # G
    8: [103.83, 207.65, 415.30, 830.61],  # G#
    9: [110.00, 220.00, 440.00, 880.00],  # A
    10: [116.54, 233.08, 466.16, 932.33], # A#
    11: [123.47, 246.94, 493.88, 987.77], # B
}


def _log(msg):
    _log_messages.append(msg)


def get_log_messages():
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
            _log(f"[KEY] Loaded cache: {len(_cache)} entries")
    except Exception:
        _cache = {}


def _entry_valid(path):
    key = str(path)
    if key not in _cache:
        return False
    try:
        return _cache[key]["mtime"] == path.stat().st_mtime
    except Exception:
        return False


def _store(path, key_val):
    global _cache_dirty
    try:
        _cache[str(path)] = {"mtime": path.stat().st_mtime, "key": key_val}
        _cache_dirty = True
    except Exception:
        pass


def _get_pydub():
    from pydub import AudioSegment
    ffmpeg_path = _find_ffmpeg_path()
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        current_path = os.environ.get('PATH', '')
        if ffmpeg_dir not in current_path:
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
    return AudioSegment


# ── Detection Algorithm ───────────────────────────────────────────────────────

def _calculate_autocorrelation_at_lag(samples, lag):
    """Calculate autocorrelation at a specific lag."""
    if lag <= 0 or lag >= len(samples):
        return 0.0
    
    n = len(samples) - lag
    if n <= 0:
        return 0.0
    
    # Sum of products
    corr = sum(samples[i] * samples[i + lag] for i in range(n))
    
    # Normalize
    sum_sq = sum(s * s for s in samples[:n])
    if sum_sq > 0:
        corr = corr / sum_sq
    
    return corr


def _detect_key_algorithm(audio) -> Optional[str]:
    """
    Detect musical key using pitch-period autocorrelation.
    
    For each of the 12 pitch classes, compute autocorrelation at lags
    corresponding to that pitch across octaves 2-5, then take argmax.
    """
    samples = audio.get_array_of_samples()
    sample_rate = audio.frame_rate
    
    if len(samples) < sample_rate // 4:   # need at least 0.25s at 8000 Hz
        return None
    
    # Calculate chroma vector (12 pitch classes)
    chroma = [0.0] * 12
    
    for pitch_class in range(12):
        total_energy = 0.0
        
        # Sum autocorrelation energies across octaves 2-5
        for freq in _PITCH_FREQUENCIES[pitch_class]:
            # Convert frequency to lag in samples
            period = sample_rate / freq
            lag = int(round(period))
            
            if lag > 0 and lag < len(samples) // 2:
                energy = _calculate_autocorrelation_at_lag(samples, lag)
                # Weight by inverse frequency (lower frequencies often stronger)
                total_energy += max(0, energy) * (1.0 / math.sqrt(freq))
        
        chroma[pitch_class] = total_energy
    
    # Normalize chroma vector
    max_val = max(chroma) if chroma else 0
    if max_val > 0:
        chroma = [c / max_val for c in chroma]
    
    # Find argmax
    if max(chroma) < 0.1:  # Too weak signal
        return None
    
    best_pitch = chroma.index(max(chroma))
    return NOTE_NAMES[best_pitch]


# ── Public API ─────────────────────────────────────────────────────────────────

def get_cached_key(path):
    _load_cache()
    if _entry_valid(path):
        return _cache[str(path)]["key"]
    return None


def detect_key(path):
    _load_cache()
    cached = get_cached_key(path)
    if cached is not None:
        _log(f"[KEY] CACHE: {path.name} = {cached}")
        return cached
    
    _log(f"[KEY] Analyzing: {path.name}")
    
    if not _find_ffmpeg_path():
        _log(f"[KEY] ERROR: ffmpeg not found")
        return None
    
    try:
        AudioSegment = _get_pydub()
        
        fmt = Path(path).suffix.lower().lstrip('.')
        if fmt == 'aif':
            fmt = 'aiff'
        
        try:
            audio = AudioSegment.from_file(str(path), format=fmt)
        except Exception as e:
            _log(f"[KEY] ERROR: Load failed - {e}")
            return None
        
        # Convert to mono
        audio = audio.set_channels(1)
        
        # Downsample to 8000 Hz for faster processing
        if audio.frame_rate > 8000:
            audio = audio.set_frame_rate(8000)
        
        # Analyze first 30 seconds
        if len(audio) > 30000:
            audio = audio[:30000]

        if len(audio) < 250:   # < 250 ms after downsampling
            _log(f"[KEY] {path.name}: too short ({len(audio)} ms), skipping")
            return None

        key_val = _detect_key_algorithm(audio)

        if key_val is None:
            _log(f"[KEY] {path.name}: no clear pitch detected (likely percussion)")
            return None
        
        _log(f"[KEY] DETECTED: {key_val}")
        _store(path, key_val)
        return key_val
        
    except Exception as e:
        _log(f"[KEY] ERROR: {type(e).__name__}: {e}")
        import traceback
        _log(f"[KEY] {traceback.format_exc()[:200]}")
        return None


def set_cached_key(path: Path, key_val: str) -> bool:
    """Manually set key for a file in the cache."""
    _load_cache()
    try:
        key_val = key_val.strip().upper()
        
        # Validate key
        if key_val not in NOTE_NAMES:
            # Try to normalize (e.g., "Db" -> "C#", "Eb" -> "D#", etc.)
            enharmonic_map = {
                "DB": "C#", "EB": "D#", "GB": "F#", "AB": "G#", "BB": "A#"
            }
            if key_val in enharmonic_map:
                key_val = enharmonic_map[key_val]
            else:
                raise ValueError(f"Invalid key: {key_val}")
        
        _cache[str(path)] = {"mtime": path.stat().st_mtime, "key": key_val}
        _cache_dirty = True
        _log(f"[KEY] MANUAL: {path.name} = {key_val}")
        return True
    except Exception as e:
        _log(f"[KEY] ERROR: Failed to set manual key - {e}")
        return False


def flush_cache():
    global _cache_dirty
    if not _cache_dirty:
        _log(f"[KEY] Cache unchanged")
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(_cache, indent=2), encoding="utf-8")
        _cache_dirty = False
        _log(f"[KEY] Cache saved: {len(_cache)} entries")
    except Exception as e:
        _log(f"[KEY] ERROR: Cache save failed - {e}")
