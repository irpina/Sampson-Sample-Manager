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
    # Note: subprocess.Popen is patched globally in main.py for Windows
    
    ffmpeg_path = _find_ffmpeg_path()
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        current_path = os.environ.get('PATH', '')
        if ffmpeg_dir not in current_path:
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
    return AudioSegment


# ── Detection Algorithm ───────────────────────────────────────────────────────
#
# Build a chroma vector with the Goertzel algorithm: for each semitone from
# C2..B5 we evaluate the DFT magnitude at the *exact* note frequency (no
# integer-lag rounding error), then fold octaves into 12 pitch classes. The
# argmax is the root pitch class. Pure Python — no FFT/numpy.

_KEY_MIDI_LO = 36   # C2 (~65.4 Hz)
_KEY_MIDI_HI = 83   # B5 (~987.8 Hz)
_KEY_MAX_SECONDS = 10.0

# Krumhansl-Kessler key profiles (major / minor). Correlating the chroma
# against all 24 rotations recovers the tonic via the tonal hierarchy, which
# is far more robust for melodic/polyphonic material than picking the single
# loudest pitch class.
_KS_MAJOR = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_KS_MINOR = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]


def _pearson(a, b):
    """Pearson correlation between two equal-length sequences."""
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((x - mb) ** 2 for x in b))
    if da == 0 or db == 0:
        return 0.0
    return num / (da * db)


def _best_tonic(chroma):
    """Return the tonic pitch class via Krumhansl-Schmuckler correlation."""
    best_pc, best_corr = 0, -2.0
    for tonic in range(12):
        for profile in (_KS_MAJOR, _KS_MINOR):
            rotated = [profile[(i - tonic) % 12] for i in range(12)]
            corr = _pearson(chroma, rotated)
            if corr > best_corr:
                best_corr = corr
                best_pc = tonic
    return best_pc


def _goertzel_mag(samples, sr, freq):
    """DFT magnitude at `freq` via the Goertzel algorithm (normalized by N)."""
    n = len(samples)
    if n == 0:
        return 0.0
    coeff = 2.0 * math.cos(2.0 * math.pi * freq / sr)
    prev1 = 0.0
    prev2 = 0.0
    for x in samples:
        s = x + coeff * prev1 - prev2
        prev2 = prev1
        prev1 = s
    power = prev1 * prev1 + prev2 * prev2 - coeff * prev1 * prev2
    if power <= 0.0:
        return 0.0
    return math.sqrt(power) / n


def _detect_key_algorithm(audio) -> Optional[str]:
    """Detect the root pitch class from a Goertzel chroma (octave-folded)."""
    sr = audio.frame_rate
    raw = audio.get_array_of_samples()
    n = len(raw)
    if n < sr // 4:                       # need >= 0.25s
        return None
    max_val = float(2 ** (audio.sample_width * 8 - 1)) or 1.0

    # Stable window: skip the first 50ms (attack transient) and analyse up to
    # _KEY_MAX_SECONDS — long enough for a stable pitch, fast enough per file.
    start = min(int(0.05 * sr), n - 1)
    end = min(n, start + int(_KEY_MAX_SECONDS * sr))
    samples = [raw[i] / max_val for i in range(start, end)]
    N = len(samples)
    if N < sr // 4:
        return None

    # Remove DC offset
    mean = sum(samples) / N
    samples = [s - mean for s in samples]

    nyquist = sr * 0.45
    chroma = [0.0] * 12
    for midi in range(_KEY_MIDI_LO, _KEY_MIDI_HI + 1):
        freq = 440.0 * (2.0 ** ((midi - 69) / 12.0))
        if freq >= nyquist:
            continue
        chroma[midi % 12] += _goertzel_mag(samples, sr, freq)

    total = sum(chroma)
    if total <= 0.0:
        return None
    chroma = [c / total for c in chroma]

    peak = max(chroma)
    # Reject flat / atonal content (uniform chroma ≈ 1/12 ≈ 0.083 per bin)
    if peak < 0.13:
        return None

    # Resolve the tonic from the tonal hierarchy (robust for melodic material)
    return NOTE_NAMES[_best_tonic(chroma)]


# ── Public API ─────────────────────────────────────────────────────────────────

def get_cached_key(path):
    _load_cache()
    if _entry_valid(path):
        return _cache[str(path)]["key"]
    return None


def detect_key(path, force=False):
    _load_cache()
    if not force:
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
