"""
BPM detection and cache management.

Uses energy envelope autocorrelation with harmonic analysis.
Optimized for drum breaks and rhythmic material.
"""

import json
import math
import os
import shutil
import statistics
import sys
from pathlib import Path
from typing import Optional, List, Tuple

# ── Cache ─────────────────────────────────────────────────────────────────────
_CACHE_DIR  = Path.home() / ".sampson"
_CACHE_FILE = _CACHE_DIR / "bpm_cache.json"
_cache: dict = {}
_cache_dirty = False
_cache_loaded = False
_log_messages: list = []
_static_ffmpeg_initialized = False


def _log(msg):
    _log_messages.append(msg)


def get_log_messages():
    global _log_messages
    msgs = _log_messages.copy()
    _log_messages.clear()
    return msgs


def _init_static_ffmpeg():
    global _static_ffmpeg_initialized
    if not _static_ffmpeg_initialized:
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
            _static_ffmpeg_initialized = True
        except Exception:
            pass
    return _static_ffmpeg_initialized


def _find_ffmpeg_path():
    try:
        if _init_static_ffmpeg():
            exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
            bundled = shutil.which(exe)
            if bundled and os.path.isfile(bundled):
                return bundled
    except Exception:
        pass
    
    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    return shutil.which(exe)


def _load_cache():
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    _cache_loaded = True
    try:
        if _CACHE_FILE.exists():
            _cache = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
            _log(f"[BPM] Loaded cache: {len(_cache)} entries")
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


def _store(path, bpm_val):
    global _cache_dirty
    try:
        _cache[str(path)] = {"mtime": path.stat().st_mtime, "bpm": float(bpm_val)}
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

def _calculate_energy_envelope(samples, sample_rate, hop_ms=10):
    """Calculate RMS energy envelope."""
    hop = int(hop_ms * sample_rate / 1000)
    envelope = []
    for i in range(0, len(samples) - hop, hop):
        frame = samples[i:i+hop]
        rms = math.sqrt(sum(s * s for s in frame) / len(frame))
        envelope.append(rms)
    return envelope


def _autocorrelation(signal, max_lag):
    """Calculate autocorrelation."""
    n = len(signal)
    if n == 0:
        return []
    
    result = []
    for lag in range(max_lag + 1):
        if lag >= n:
            result.append(0.0)
            continue
        corr = sum(signal[i] * signal[i + lag] for i in range(n - lag))
        result.append(corr)
    
    # Normalize
    if result[0] > 0:
        result = [r / result[0] for r in result]
    
    return result


def _find_local_maxima(signal, min_distance=5):
    """Find local maxima."""
    peaks = []
    for i in range(1, len(signal) - 1):
        if signal[i] > signal[i-1] and signal[i] > signal[i+1]:
            if not peaks or i - peaks[-1][0] >= min_distance:
                peaks.append((i, signal[i]))
    return peaks


def _lag_to_bpm(lag, hop_ms):
    if lag <= 0:
        return 0
    return 60000.0 / (lag * hop_ms)


def _detect_bpm_algorithm(audio) -> Optional[float]:
    """Detect BPM using energy envelope autocorrelation."""
    samples = audio.get_array_of_samples()
    sample_rate = audio.frame_rate
    hop_ms = 10
    
    if len(samples) < sample_rate:
        return None
    
    envelope = _calculate_energy_envelope(samples, sample_rate, hop_ms)
    
    if len(envelope) < 100:
        return None
    
    # Calculate autocorrelation
    max_lag = min(int(2000 / hop_ms), len(envelope) // 2)
    acorr = _autocorrelation(envelope, max_lag)
    
    # Find peaks in valid tempo range (60-200 BPM)
    min_lag = int(60000 / 200 / hop_ms)  # 30 frames
    max_lag_range = int(60000 / 60 / hop_ms)  # 100 frames
    
    min_lag = max(min_lag, 5)
    max_lag_range = min(max_lag_range, len(acorr) - 1)
    
    if max_lag_range <= min_lag:
        return None
    
    # Find peaks
    peaks = _find_local_maxima(acorr[min_lag:max_lag_range+1], min_distance=3)
    peaks = [(lag + min_lag, acorr[lag + min_lag]) for lag, _ in peaks]
    
    if not peaks:
        return None
    
    # Generate candidates with octave variants
    candidates = []
    for lag, strength in peaks:
        bpm = _lag_to_bpm(lag, hop_ms)
        
        # Original
        if 60 <= bpm <= 200:
            candidates.append((bpm, strength, 'orig'))
        
        # Half tempo
        if bpm / 2 >= 60:
            candidates.append((bpm / 2, strength * 0.85, 'half'))
        
        # Double tempo
        if bpm * 2 <= 200:
            candidates.append((bpm * 2, strength * 0.75, 'double'))
    
    if not candidates:
        return None
    
    # Group by similar tempo (within 5%)
    groups = []
    for bpm, strength, source in candidates:
        found = False
        for group in groups:
            ref_bpm = group[0][0]
            if abs(bpm - ref_bpm) / ref_bpm < 0.05 or abs(bpm*2 - ref_bpm) / ref_bpm < 0.05 or abs(bpm/2 - ref_bpm) / ref_bpm < 0.05:
                group.append((bpm, strength, source))
                found = True
                break
        if not found:
            groups.append([(bpm, strength, source)])
    
    # Score groups
    group_scores = []
    for group in groups:
        # Sort by BPM descending (prefer faster)
        group.sort(key=lambda x: x[0], reverse=True)
        best_bpm = group[0][0]
        total_strength = sum(s for _, s, _ in group)
        
        # Strong bonus for 80-180 range
        if 80 <= best_bpm <= 180:
            bonus = 1.2
        elif 70 <= best_bpm <= 190:
            bonus = 1.0
        else:
            bonus = 0.8
        
        group_scores.append((best_bpm, total_strength * bonus))
    
    # Sort by score
    group_scores.sort(key=lambda x: x[1], reverse=True)
    
    best_bpm = group_scores[0][0]
    best_bpm = max(60.0, min(200.0, best_bpm))
    
    return round(best_bpm, 1)


# ── Public API ─────────────────────────────────────────────────────────────────

def get_cached_bpm(path):
    _load_cache()
    if _entry_valid(path):
        return float(_cache[str(path)]["bpm"])
    return None


def detect_bpm(path):
    _load_cache()
    cached = get_cached_bpm(path)
    if cached is not None:
        _log(f"[BPM] CACHE: {path.name} = {cached:.1f} BPM")
        return cached
    
    _log(f"[BPM] Analyzing: {path.name}")
    
    if not _find_ffmpeg_path():
        _log(f"[BPM] ERROR: ffmpeg not found")
        return None
    
    try:
        AudioSegment = _get_pydub()
        
        fmt = Path(path).suffix.lower().lstrip('.')
        if fmt == 'aif':
            fmt = 'aiff'
        
        try:
            audio = AudioSegment.from_file(str(path), format=fmt)
        except Exception as e:
            _log(f"[BPM] ERROR: Load failed - {e}")
            return None
        
        audio = audio.set_channels(1)
        
        if len(audio) > 60000:
            audio = audio[:60000]
        
        bpm_val = _detect_bpm_algorithm(audio)
        
        if bpm_val is None:
            _log(f"[BPM] ERROR: Detection failed")
            return None
        
        _log(f"[BPM] DETECTED: {bpm_val:.1f} BPM")
        _store(path, bpm_val)
        return bpm_val
        
    except Exception as e:
        _log(f"[BPM] ERROR: {type(e).__name__}: {e}")
        import traceback
        _log(f"[BPM] {traceback.format_exc()[:200]}")
        return None


def set_cached_bpm(path: Path, bpm_val: float) -> bool:
    """Manually set BPM for a file in the cache."""
    _load_cache()
    try:
        bpm_val = float(bpm_val)
        bpm_val = max(30.0, min(300.0, bpm_val))
        
        _cache[str(path)] = {"mtime": path.stat().st_mtime, "bpm": bpm_val}
        _cache_dirty = True
        _log(f"[BPM] MANUAL: {path.name} = {bpm_val:.1f} BPM")
        return True
    except Exception as e:
        _log(f"[BPM] ERROR: Failed to set manual BPM - {e}")
        return False


def flush_cache():
    global _cache_dirty
    if not _cache_dirty:
        _log(f"[BPM] Cache unchanged")
        return
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(_cache, indent=2), encoding="utf-8")
        _cache_dirty = False
        _log(f"[BPM] Cache saved: {len(_cache)} entries")
    except Exception as e:
        _log(f"[BPM] ERROR: Cache save failed - {e}")
