# Plan: Hybrid BPM Detection (Ours + Librosa)

## Current State

| Algorithm | Drum Breaks | Melodic/Vocal | Bundle Size |
|-----------|-------------|---------------|-------------|
| Our Energy-Based | 95% (excellent) | 0-20% (poor) | +0 MB |
| Librosa | 0-20% (poor) | 20-40% (okay) | +50 MB |

**Insight**: The algorithms have complementary strengths - ours excels at drums, librosa at melodic material.

---

## Goal

Create a hybrid system that:
1. Maintains 95%+ accuracy on drum breaks
2. Improves to 60%+ accuracy on melodic/sustained material
3. Minimizes bundle size impact
4. Resolves conflicts intelligently

---

## Approach 1: Signal-Based Algorithm Selection (Recommended)

### Concept
Analyze signal characteristics to determine if audio is "drum-like" or "melodic-like", then run the appropriate algorithm.

### Signal Classification Metrics

```python
def classify_signal_type(samples, sample_rate):
    """
    Classify audio as 'percussive' or 'melodic'.
    
    Metrics:
    1. Transient density (peaks per second)
    2. Spectral centroid variance
    3. Zero-crossing rate
    4. Attack characteristics
    """
    
    # Calculate envelope
    envelope = calculate_envelope(samples, sample_rate)
    
    # Metric 1: Peak density (transients per second)
    peaks = find_peaks(envelope, threshold=mean + std)
    peak_density = len(peaks) / (len(samples) / sample_rate)
    # > 8 peaks/sec = likely drums
    # < 4 peaks/sec = likely melodic
    
    # Metric 2: Attack sharpness (drums have sharp attacks)
    attack_slopes = calculate_attack_slopes(envelope, peaks)
    avg_attack = statistics.mean(attack_slopes)
    # High slope = sharp attack = drum-like
    
    # Metric 3: Spectral flux variance
    spectral_flux = calculate_spectral_flux(samples, sample_rate)
    flux_variance = statistics.variance(spectral_flux)
    # High variance = drum-like
    
    # Classification score
    drum_score = (
        (peak_density / 10) * 0.4 +
        (avg_attack / max_attack) * 0.4 +
        (flux_variance / max_flux) * 0.2
    )
    
    return 'percussive' if drum_score > 0.6 else 'melodic'
```

### Decision Flow

```
┌─────────────────┐
│  Load Audio     │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Signal Analysis │
│ (5-10ms)        │
└────────┬────────┘
         ▼
    ┌────────┐
    │ Type?  │
    └────┬───┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐ ┌────────┐
│Drums  │ │Melodic │
│(Ours) │ │(Librosa│
│       │ │Fallback│
└───┬───┘ └────┬───┘
    │          │
    └────┬─────┘
         ▼
┌─────────────────┐
│ Return BPM      │
└─────────────────┘
```

### Pros
- No conflict resolution needed (only runs one algorithm)
- Maintains fast path for drums (our algorithm)
- Only uses librosa when needed

### Cons
- Classification must be accurate
- Edge cases (mixed drums + melodic) may be misclassified

---

## Approach 2: Confidence-Based Selection

### Concept
Run both algorithms, compare results, and select based on internal confidence metrics.

### Confidence Metrics

**Our Algorithm Confidence:**
```python
def calculate_our_confidence(acorr_peaks, signal):
    """
    Confidence based on:
    1. Peak clarity (ratio of highest to second highest)
    2. Peak consistency across tempo octaves
    3. Signal-to-noise in autocorrelation
    """
    
    # Peak clarity
    sorted_peaks = sorted(acorr_peaks, key=lambda x: x[1], reverse=True)
    peak_clarity = sorted_peaks[0][1] / sorted_peaks[1][1] if len(sorted_peaks) > 1 else 1.0
    
    # Check if harmonic relationships exist (2x, 0.5x tempos also have peaks)
    bpm = sorted_peaks[0][0]
    harmonic_support = 0
    for p in sorted_peaks[1:]:
        if abs(p[0] - bpm*2) / (bpm*2) < 0.05:
            harmonic_support += p[1]
        if abs(p[0] - bpm/2) / (bpm/2) < 0.05:
            harmonic_support += p[1]
    
    # Combine
    confidence = (peak_clarity * 0.6) + (min(1.0, harmonic_support) * 0.4)
    return confidence
```

**Librosa Confidence:**
```python
def calculate_librosa_confidence(y, sr, tempo):
    """
    Confidence based on:
    1. Beat tracking strength
    2. Onset envelope periodicity
    3. Tempogram peak clarity
    """
    # Use librosa's beat tracking confidence
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    
    # More beats detected = higher confidence
    beat_density = len(beats) / (len(y) / sr)
    expected_beats = (len(y) / sr) / (60 / tempo)
    
    density_ratio = min(1.0, beat_density / expected_beats)
    
    # Tempogram analysis
    tempogram = librosa.feature.tempogram(y=y, sr=sr)
    tempogram_max = np.max(tempogram, axis=1)
    peak_idx = np.argmax(tempogram_max)
    peak_value = tempogram_max[peak_idx]
    
    # Normalize confidence
    confidence = (density_ratio * 0.5) + (peak_value * 0.5)
    return confidence
```

### Selection Logic

```python
def hybrid_detect_bpm(path):
    # Run both algorithms
    our_bpm, our_conf = our_detect_with_confidence(path)
    lib_bpm, lib_conf = librosa_detect_with_confidence(path)
    
    # High confidence threshold
    HIGH_CONF = 0.7
    
    if our_conf >= HIGH_CONF and lib_conf < HIGH_CONF:
        return our_bpm, 'ours_high_conf'
    elif lib_conf >= HIGH_CONF and our_conf < HIGH_CONF:
        return lib_bpm, 'librosa_high_conf'
    elif our_conf >= HIGH_CONF and lib_conf >= HIGH_CONF:
        # Both confident - check agreement
        if abs(our_bpm - lib_bpm) <= 5:
            return our_bpm, 'agreement'  # Average or pick ours
        else:
            # Conflict! Use signal classification as tiebreaker
            signal_type = classify_signal_type(audio)
            if signal_type == 'percussive':
                return our_bpm, 'ours_tiebreak'
            else:
                return lib_bpm, 'librosa_tiebreak'
    else:
        # Both low confidence - use signal classification
        signal_type = classify_signal_type(audio)
        if signal_type == 'percussive':
            return our_bpm, 'ours_fallback'
        else:
            return lib_bpm, 'librosa_fallback'
```

### Pros
- Uses both algorithms' strengths
- Confidence metrics provide quality indicators
- Fallback strategies for edge cases

### Cons
- Always runs both algorithms (slower, 2x compute)
- Conflict resolution adds complexity
- Larger bundle size (librosa always included)

---

## Approach 3: Optional Librosa Plugin (Lazy Loading)

### Concept
Keep our algorithm as default, but allow users to install librosa for improved melodic detection.

### Implementation

```python
def detect_bpm(path, use_librosa_if_available=True):
    # Always run our algorithm (fast)
    our_bpm = our_detect_bpm(path)
    our_confidence = estimate_confidence(our_bpm, path)
    
    # If low confidence and librosa is available, try it
    if our_confidence < 0.6 and use_librosa_if_available:
        try:
            lib_bpm = librosa_detect_bpm(path)
            if lib_bpm:
                return lib_bpm, 'librosa_fallback'
        except ImportError:
            pass  # Librosa not installed
    
    return our_bpm, 'ours'


def librosa_detect_bpm(path):
    """Only called if librosa is installed."""
    import librosa  # Lazy import
    y, sr = librosa.load(str(path), sr=22050, mono=True, duration=60)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(tempo[0] if hasattr(tempo, "__len__") else tempo)
```

### Installation Options

```bash
# Minimal install (our algorithm only)
pip install sampson

# Full install (with librosa for melodic detection)
pip install sampson[librosa]
```

### Pros
- Zero bundle size impact for basic install
- Users can opt-in for better melodic detection
- Maintains fast path for drums

### Cons
- Users must know to install optional dependency
- Two different experiences depending on install
- Documentation complexity

---

## Approach 4: Onset-Based Enhancement (No Librosa)

### Concept
Improve our algorithm by adding onset detection (like librosa) without the heavy dependencies.

### Pure-Python Onset Detection

```python
def calculate_onset_strength(samples, sample_rate, hop_ms=10):
    """
    Lightweight onset detection using energy flux.
    Similar to librosa's onset_strength but pure Python.
    """
    hop = int(hop_ms * sample_rate / 1000)
    frame_size = hop * 4
    
    # Multi-band analysis
    bands = {
        'low': (0, 500),      # Kick
        'mid': (500, 4000),   # Snare/clap  
        'high': (4000, 20000) # Hihats
    }
    
    # Simplified: Use time-domain differences as proxy for bands
    onset_env = []
    prev_energy = {'low': 0, 'mid': 0, 'high': 0}
    
    for i in range(0, len(samples) - frame_size, hop):
        frame = samples[i:i+frame_size]
        
        # Simulate frequency bands with different emphasis
        # Low: Slow changes (emphasize lower frequencies by smoothing)
        low_energy = sum(frame[j] * frame[j] for j in range(0, len(frame), 4)) / (len(frame) // 4)
        
        # Mid: Medium changes
        mid_energy = sum(frame[j] * frame[j] for j in range(0, len(frame), 2)) / (len(frame) // 2)
        
        # High: Fast changes (emphasize transients)
        high_energy = sum((frame[j] - frame[j-1])**2 for j in range(1, len(frame)))
        
        # Flux (positive differences)
        low_flux = max(0, low_energy - prev_energy['low'])
        mid_flux = max(0, mid_energy - prev_energy['mid'])
        high_flux = max(0, high_energy - prev_energy['high'])
        
        # Weight drums more heavily
        combined_flux = low_flux * 0.4 + mid_flux * 0.4 + high_flux * 0.2
        onset_env.append(combined_flux)
        
        prev_energy = {'low': low_energy, 'mid': mid_energy, 'high': high_energy}
    
    return onset_env


def detect_bpm_v2(audio):
    """Improved detection using both energy and onset."""
    samples = audio.get_array_of_samples()
    sr = audio.frame_rate
    
    # Get both signals
    energy = calculate_energy_envelope(samples, sr)
    onset = calculate_onset_strength(samples, sr)
    
    # Autocorrelation on both
    energy_acorr = autocorrelation(energy)
    onset_acorr = autocorrelation(onset)
    
    # Combine autocorrelations (weighted)
    combined = [e * 0.6 + o * 0.4 for e, o in zip(energy_acorr, onset_acorr)]
    
    # Find peaks in combined
    peaks = find_peaks(combined)
    
    # Rest of algorithm same as before...
```

### Pros
- No external dependencies
- Better drum detection than energy alone
- Captures transient information

### Cons
- More complex algorithm
- May not match librosa's melodic detection
- Tuning required

---

## Recommendation

**Primary: Approach 1 (Signal-Based Selection) + Approach 4 (Onset Enhancement)**

### Phase 1: Improve Our Algorithm (v0.5.2)
1. Implement multi-band onset detection (Approach 4)
2. Add signal classification (percussive vs melodic)
3. Tune thresholds on test datasets
4. Target: 95% drums, 40% melodic

### Phase 2: Optional Librosa (v0.6.0)
1. Make librosa an optional dependency
2. Use signal classification to route to librosa for melodic material
3. Lazy import librosa only when needed
4. Target: 95% drums, 70% melodic

### Implementation Priority

```
1. Add signal classification to bpm.py
2. Add onset-based detection path
3. Test and tune on both drum and melodic datasets
4. Release v0.5.2

5. Create optional librosa integration
6. Add UI indicator for detection method used
7. Document optional install
8. Release v0.6.0
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `bpm.py` | Add signal classification, onset detection, optional librosa path |
| `requirements.txt` | Add `librosa>=0.10.0; extra == "librosa"` |
| `builders.py` | Add UI indicator showing detection method |
| `AGENTS.md` | Document BPM detection architecture |

---

## Testing Plan

1. **Drum Test**: 20 amen breaks + 20 jungle breaks → Target 95%
2. **Melodic Test**: 20 Splice vocal/synth loops → Target 40% (ours) / 70% (with librosa)
3. **Edge Cases**: 
   - Mixed drums + melodic
   - Very short loops (< 1 sec)
   - Ambient/texture sounds
   - Off-grid/shuffled beats

---

## Notes

- Librosa adds ~50MB but provides significant improvement on melodic material
- Signal classification must be fast (< 10ms) to not impact UX
- Consider caching signal type to avoid re-analysis
- UI should indicate when manual BPM might be needed (low confidence)
