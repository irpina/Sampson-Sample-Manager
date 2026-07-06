"""Tests for BPM/key detection: the non-rhythmic confidence gate, root
detection, and negative-result caching.

Uses a duck-typed AudioSegment so the DSP runs without pydub/ffmpeg.
"""

import math
import random

import pytest

import bpm as bpm_mod
import key as key_mod


class FakeSeg:
    """Minimal AudioSegment stand-in for the detection algorithms."""

    def __init__(self, samples, sr):
        self._s = samples
        self.frame_rate = sr
        self.sample_width = 2

    def set_frame_rate(self, sr):
        assert sr == self.frame_rate, "tests generate at the analysis rate"
        return self

    def get_array_of_samples(self):
        return self._s


def drum_loop(bpm, sr, seconds=15.0, hats=True, seed=1):
    """Kick on beats, optional offbeat hats, light noise floor."""
    rng = random.Random(seed)
    n = int(sr * seconds)
    out = [0.0] * n
    beat = 60.0 / bpm

    def burst(t0, dur, amp, tone):
        i0 = int(t0 * sr)
        for j in range(int(dur * sr)):
            i = i0 + j
            if i >= n:
                return
            env = math.exp(-j / (dur * sr) * 6)
            if tone:
                out[i] += amp * env * (math.sin(2 * math.pi * 60 * j / sr)
                                       + 0.3 * (rng.random() * 2 - 1))
            else:
                out[i] += amp * env * (rng.random() * 2 - 1)

    t = 0.0
    while t < seconds:
        burst(t, 0.05, 0.9, tone=True)
        if hats:
            burst(t + beat / 2, 0.02, 0.35, tone=False)
        t += beat

    for i in range(n):
        out[i] += 0.005 * (rng.random() * 2 - 1)
    peak = max(abs(v) for v in out) or 1.0
    return [int(v / peak * 30000) for v in out]


def drone(sr, seconds=15.0, freq=110.0):
    n = int(sr * seconds)
    return [int(20000 * math.sin(2 * math.pi * freq * i / sr)
                * (1 + 0.1 * math.sin(2 * math.pi * 0.3 * i / sr)))
            for i in range(n)]


def white_noise(sr, seconds=15.0, seed=2):
    rng = random.Random(seed)
    return [int(25000 * (rng.random() * 2 - 1)) for _ in range(int(sr * seconds))]


def triad(root_midi, sr, seconds=2.0, minor=False, harmonics=4):
    n = int(sr * seconds)
    third = 3 if minor else 4
    freqs = []
    for interval in (0, third, 7):
        f0 = 440.0 * 2 ** ((root_midi + interval - 69) / 12)
        for h in range(1, harmonics + 1):
            if f0 * h < sr * 0.45:
                freqs.append((f0 * h, 1.0 / h))
    out = [0.0] * n
    for f, a in freqs:
        w = 2 * math.pi * f / sr
        for i in range(n):
            out[i] += a * math.sin(w * i)
    peak = max(abs(v) for v in out) or 1.0
    return [int(v / peak * 28000) for v in out]


BPM_SR = bpm_mod._BPM_SR
KEY_SR = 8000


class TestBpmDetection:
    def test_steady_120(self):
        got = bpm_mod._detect_bpm_algorithm(FakeSeg(drum_loop(120, BPM_SR), BPM_SR))
        assert got is not None and abs(got - 120) <= 2

    def test_sparse_90_no_hats(self):
        got = bpm_mod._detect_bpm_algorithm(
            FakeSeg(drum_loop(90, BPM_SR, hats=False), BPM_SR))
        assert got is not None and abs(got - 90) <= 2


class TestBpmConfidenceGate:
    def test_drone_returns_none(self):
        assert bpm_mod._detect_bpm_algorithm(FakeSeg(drone(BPM_SR), BPM_SR)) is None

    def test_low_drone_returns_none(self):
        assert bpm_mod._detect_bpm_algorithm(
            FakeSeg(drone(BPM_SR, freq=55.0), BPM_SR)) is None

    def test_white_noise_returns_none(self):
        assert bpm_mod._detect_bpm_algorithm(
            FakeSeg(white_noise(BPM_SR), BPM_SR)) is None

    def test_gate_does_not_reject_rhythmic(self):
        for tempo in (85, 120, 150):
            got = bpm_mod._detect_bpm_algorithm(
                FakeSeg(drum_loop(tempo, BPM_SR), BPM_SR))
            assert got is not None, f"gate falsely rejected {tempo} BPM loop"


class TestKeyDetection:
    @pytest.mark.parametrize("root_pc,name", [(0, "C"), (6, "F#"), (9, "A")])
    def test_major_triad_root(self, root_pc, name):
        got = key_mod._detect_key_algorithm(FakeSeg(triad(60 + root_pc, KEY_SR), KEY_SR))
        assert got == name

    def test_minor_triad_root(self):
        got = key_mod._detect_key_algorithm(
            FakeSeg(triad(62, KEY_SR, minor=True), KEY_SR))
        assert got == "D"

    def test_noise_gated(self):
        assert key_mod._detect_key_algorithm(
            FakeSeg(white_noise(KEY_SR, 4.0), KEY_SR)) is None

    def test_drums_gated(self):
        assert key_mod._detect_key_algorithm(
            FakeSeg(drum_loop(120, KEY_SR, seconds=4.0), KEY_SR)) is None


@pytest.fixture
def isolated_caches(tmp_path, monkeypatch):
    """Keep tests away from the user's real ~/.sampson caches, and block
    the analysis path so cache behavior is observable."""
    for mod in (bpm_mod, key_mod):
        monkeypatch.setattr(mod, "_cache", {})
        monkeypatch.setattr(mod, "_cache_loaded", True)
        monkeypatch.setattr(mod, "_cache_dirty", False)
        mod.get_log_messages()  # drain
        # If detect_* ever reaches analysis in these tests, fail loudly
        monkeypatch.setattr(mod, "_get_pydub",
                            lambda: (_ for _ in ()).throw(AssertionError("analysis ran")))
    f = tmp_path / "sample.wav"
    f.write_bytes(b"RIFF0000WAVEdata")
    return f


class TestNegativeCaching:
    def test_bpm_cached_negative_skips_analysis(self, isolated_caches):
        f = isolated_caches
        bpm_mod._store(f, None)
        assert bpm_mod.get_cached_bpm(f) is None
        assert bpm_mod.detect_bpm(f) is None
        logs = " ".join(bpm_mod.get_log_messages())
        assert "cached" in logs.lower()

    def test_bpm_cached_positive_roundtrip(self, isolated_caches):
        f = isolated_caches
        bpm_mod._store(f, 128.0)
        assert bpm_mod.get_cached_bpm(f) == 128.0
        assert bpm_mod.detect_bpm(f) == 128.0

    def test_key_cached_negative_skips_analysis(self, isolated_caches):
        f = isolated_caches
        key_mod._store(f, None)
        assert key_mod.get_cached_key(f) is None
        assert key_mod.detect_key(f) is None
        logs = " ".join(key_mod.get_log_messages())
        assert "cached" in logs.lower()

    def test_mtime_change_invalidates_negative(self, isolated_caches):
        f = isolated_caches
        bpm_mod._store(f, None)
        # Rewrite with a different mtime — entry must become invalid
        import os
        os.utime(f, (1, 1))
        assert not bpm_mod._entry_valid(f)

    def test_force_bypasses_cached_negative(self, isolated_caches):
        f = isolated_caches
        bpm_mod._store(f, None)
        # force=True must go to analysis; our stub makes that path raise,
        # which detect_bpm catches and reports as a detection error (None,
        # but with an ERROR log rather than a CACHE log)
        assert bpm_mod.detect_bpm(f, force=True) is None
        logs = " ".join(bpm_mod.get_log_messages())
        assert "cache:" not in logs.lower()
