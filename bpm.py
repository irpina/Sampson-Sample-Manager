"""
BPM detection and cache management.

Uses energy envelope autocorrelation with harmonic analysis.
Optimized for drum breaks and rhythmic material.
"""

import json
import math
import os
import statistics
from pathlib import Path
from typing import Optional, List, Tuple

from conversion import _find_ffmpeg_path
from constants import MIN_BPM_DURATION_MS

# ── Cache ─────────────────────────────────────────────────────────────────────
_CACHE_DIR  = Path.home() / ".sampson"
_CACHE_FILE = _CACHE_DIR / "bpm_cache.json"
_cache: dict = {}
_cache_dirty = False
_cache_loaded = False
_log_messages: list = []


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
    """Cache a result. bpm_val may be None — a cached negative ("no reliable
    tempo") stops every later run from re-decoding and re-analysing the file."""
    global _cache_dirty
    try:
        _cache[str(path)] = {
            "mtime": path.stat().st_mtime,
            "bpm": float(bpm_val) if bpm_val is not None else None,
        }
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
# Pipeline: downsample → onset-novelty function (half-wave-rectified flux of
# log short-time energy) → mean-removed autocorrelation → comb-filter scoring
# with a gentle perceptual tempo prior to resolve the octave → parabolic
# interpolation for sub-frame precision. Pure Python, no numpy.

_BPM_SR = 11025          # analysis sample rate (plenty for tempo)
_BPM_HOP_MS = 10.0       # onset-envelope hop
_BPM_WIN_MS = 20.0       # onset-envelope window (overlapping)
_BPM_MIN = 55.0          # fundamental search bounds
_BPM_MAX = 210.0
_BPM_PRIOR_CENTER = 120.0  # perceptual tempo prior (log-Gaussian)
_BPM_PRIOR_SIGMA = 0.9     # octaves
# The comb score already prevents tempo *doubling* (the half-beat lag carries
# no onset); only *halving* needs the prior. Centre 120 favours the common
# 70-140 BPM range. Trade-off: very fast tempos (~165+) may be reported at
# half-time, and sparse/sustained loops can occasionally land on a subdivision.

# Confidence gates — reject non-rhythmic content (pads, drones, noise) rather
# than assigning it a meaningless tempo. Validated on synthetic ground truth:
# rhythmic material combs >= ~0.7 with a near-zero median across the lag
# range; white noise maxes ~0.04; sustained drones sit flat at 0.17-0.52
# median. BPM_DEBUG=1 prints the gate metrics.
_BPM_MIN_COMB = 0.25        # peak comb score below this = no beat structure
_BPM_MAX_FLAT_MEDIAN = 0.12  # median comb above this = flat landscape (drone)


def _onset_envelope(samples, sr, max_val):
    """Half-wave-rectified flux of log short-time energy (onset novelty)."""
    hop = max(1, int(_BPM_HOP_MS * sr / 1000.0))
    win = max(hop, int(_BPM_WIN_MS * sr / 1000.0))
    n = len(samples)
    n_frames = (n - win) // hop + 1
    if n_frames < 64:
        return [], 0.0

    log_energy = [0.0] * n_frames
    inv = 1.0 / max_val
    for f in range(n_frames):
        start = f * hop
        e = 0.0
        for j in range(win):
            v = samples[start + j] * inv
            e += v * v
        log_energy[f] = math.log1p(1000.0 * (e / win))

    # Half-wave-rectified first difference = onset detection function
    odf = [0.0] * n_frames
    for f in range(1, n_frames):
        d = log_energy[f] - log_energy[f - 1]
        if d > 0.0:
            odf[f] = d

    # Remove mean so autocorrelation isn't dominated by DC
    mean = sum(odf) / n_frames
    odf = [v - mean for v in odf]
    fps = sr / hop
    return odf, fps


def _autocorr_full(signal, max_lag):
    """Normalized autocorrelation 0..max_lag (A[0] == 1.0)."""
    n = len(signal)
    a0 = sum(v * v for v in signal)
    if a0 <= 0:
        return [0.0] * (max_lag + 1)
    out = [0.0] * (max_lag + 1)
    out[0] = 1.0
    for lag in range(1, max_lag + 1):
        s = 0.0
        for i in range(n - lag):
            s += signal[i] * signal[i + lag]
        out[lag] = s / a0
    return out


def _tempo_prior(bpm):
    """Gentle log-Gaussian preference around a typical tempo."""
    return math.exp(-0.5 * (math.log2(bpm / _BPM_PRIOR_CENTER) / _BPM_PRIOR_SIGMA) ** 2)


def _detect_bpm_algorithm(audio) -> Optional[float]:
    """Detect BPM from an onset-novelty autocorrelation with comb scoring."""
    if audio.frame_rate != _BPM_SR:
        audio = audio.set_frame_rate(_BPM_SR)
    sr = audio.frame_rate
    samples = audio.get_array_of_samples()
    if len(samples) < sr:          # need >= 1s
        return None
    max_val = float(2 ** (audio.sample_width * 8 - 1)) or 1.0

    odf, fps = _onset_envelope(samples, sr, max_val)
    if not odf:
        return None
    n_frames = len(odf)

    # Cover up to ~3 beat periods of the slowest tempo so the comb can use
    # the 2nd/3rd autocorrelation harmonics of the fundamental beat.
    max_lag = min(n_frames - 1, int(fps * 60.0 / _BPM_MIN * 3.2))
    if max_lag < 4:
        return None
    acorr = _autocorr_full(odf, max_lag)

    lag_lo = max(2, int(fps * 60.0 / _BPM_MAX))
    lag_hi = min(max_lag, int(fps * 60.0 / _BPM_MIN))
    if lag_hi <= lag_lo:
        return None

    # Comb-filter score: a true beat period L shows autocorrelation peaks at
    # L, 2L, 3L… Summing them reinforces the fundamental and suppresses
    # spurious double/half-tempo candidates.
    comb_weights = ((1, 1.0), (2, 0.8), (3, 0.6), (4, 0.4))
    comb_scores = []  # (lag, prior-free comb score)
    for lag in range(lag_lo, lag_hi + 1):
        comb = 0.0
        wsum = 0.0
        for k, wk in comb_weights:
            kl = lag * k
            if kl <= max_lag:
                # Local max around k*lag: a true beat period is often fractional
                # (e.g. 160 BPM ≈ lag 37.5), so its autocorrelation peak falls
                # between integer lags. Sampling the neighbours avoids penalising
                # fast tempos and prevents systematic half-tempo errors.
                lo = max(1, kl - 1)
                hi = min(max_lag, kl + 1)
                comb += wk * max(acorr[lo:hi + 1])
                wsum += wk
        if wsum > 0:
            comb_scores.append((lag, comb / wsum))

    if not comb_scores:
        return None

    # Confidence gate: rhythmic material shows one strong comb peak over a
    # near-zero median; noise combs weakly everywhere; sustained drones comb
    # strongly *everywhere* (flat landscape). Reject both rather than
    # labelling a pad "146 BPM".
    max_comb = max(c for _, c in comb_scores)
    median_comb = statistics.median(c for _, c in comb_scores)
    if os.environ.get("BPM_DEBUG"):
        print(f"[BPM] max_comb={max_comb:.3f} median_comb={median_comb:.3f}")
    if max_comb < _BPM_MIN_COMB or median_comb > _BPM_MAX_FLAT_MEDIAN:
        return None

    # Pick the best lag, weighted by the perceptual tempo prior
    best_lag, best_score = None, -1.0
    for lag, comb in comb_scores:
        score = comb * _tempo_prior(60.0 * fps / lag)
        if score > best_score:
            best_score = score
            best_lag = lag

    if best_lag is None:
        return None

    # Parabolic interpolation around the chosen lag for sub-frame precision
    lag = float(best_lag)
    if 1 <= best_lag < max_lag:
        y0, y1, y2 = acorr[best_lag - 1], acorr[best_lag], acorr[best_lag + 1]
        denom = y0 - 2.0 * y1 + y2
        if denom != 0.0:
            delta = 0.5 * (y0 - y2) / denom
            if -1.0 < delta < 1.0:
                lag = best_lag + delta

    bpm_val = 60.0 * fps / lag
    bpm_val = max(40.0, min(220.0, bpm_val))
    return round(bpm_val, 1)


# ── Public API ─────────────────────────────────────────────────────────────────

def get_cached_bpm(path):
    _load_cache()
    if _entry_valid(path):
        val = _cache[str(path)]["bpm"]
        return float(val) if val is not None else None
    return None


def detect_bpm(path, force=False):
    _load_cache()
    if not force and _entry_valid(path):
        cached = _cache[str(path)]["bpm"]
        if cached is not None:
            _log(f"[BPM] CACHE: {path.name} = {float(cached):.1f} BPM")
            return float(cached)
        # Cached negative: analysis already ran and found no reliable tempo
        _log(f"[BPM] CACHE: {path.name} = no reliable tempo (cached)")
        return None

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
        
        # Skip files too short for reliable BPM detection. Deterministic for
        # this file content, so cache the negative.
        if len(audio) < MIN_BPM_DURATION_MS:
            _log(f"[BPM] SKIP: {path.name} too short ({len(audio)}ms < {MIN_BPM_DURATION_MS}ms)")
            _store(path, None)
            return None

        if len(audio) > 60000:
            audio = audio[:60000]

        bpm_val = _detect_bpm_algorithm(audio)

        if bpm_val is None:
            # No beat structure found (gated pad/drone/noise, or too sparse).
            # Deterministic — cache the negative so re-runs skip the analysis.
            _log(f"[BPM] {path.name}: no reliable tempo (non-rhythmic content)")
            _store(path, None)
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
