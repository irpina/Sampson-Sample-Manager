"""Audition Stack — layer up to 4 samples and preview the mix."""

from __future__ import annotations

import math
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

import state
import bpm as bpm_module

# ── Windows pydub patch (same as preview.py) ─────────────────────────────────
_patched = False


def _ensure_pydub_patch():
    global _patched
    if _patched or sys.platform != "win32":
        return
    import pydub.utils
    if hasattr(pydub.utils.Popen, '_sampson_patched'):
        _patched = True
        return
    _original_popen = pydub.utils.Popen

    def _popen_with_hidden_console(*args, **kwargs):
        creationflags = kwargs.pop('creationflags', 0)
        creationflags |= 0x08000000
        kwargs['creationflags'] = creationflags
        return _original_popen(*args, **kwargs)

    _popen_with_hidden_console._sampson_patched = True
    pydub.utils.Popen = _popen_with_hidden_console
    _patched = True


# ── Module state ─────────────────────────────────────────────────────────────
_render_gen: int = 0
_render_thread: threading.Thread | None = None


# ── Mix pipeline ─────────────────────────────────────────────────────────────

def _load_and_process(track: dict, target_sr: int = 44100) -> Any | None:
    """Load a track and apply pitch, BPM stretch, volume, offset."""
    from pydub import AudioSegment

    path = track.get("path")
    if not path or not Path(path).is_file():
        return None

    try:
        audio = AudioSegment.from_file(path)
    except Exception:
        return None

    # Normalise to stereo, target sample rate
    if audio.channels == 1:
        audio = audio.set_channels(2)
    if audio.frame_rate != target_sr:
        audio = audio.set_frame_rate(target_sr)

    # Pitch shift (speed-change approximation)
    pitch = track.get("pitch", 0)
    if pitch != 0:
        ratio = 2 ** (pitch / 12)
        new_rate = int(audio.frame_rate * ratio)
        audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(target_sr)

    # BPM stretch (speed-change approximation)
    if track.get("bpm_sync") and track.get("source_bpm"):
        master_bpm = track.get("_master_bpm", 120)
        source_bpm = track["source_bpm"]
        if source_bpm > 0 and master_bpm > 0:
            ratio = source_bpm / master_bpm
            new_rate = int(audio.frame_rate * ratio)
            audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate}).set_frame_rate(target_sr)

    # Volume
    volume = track.get("volume", 80)
    if volume <= 0:
        audio = audio - 120  # effectively silent
    else:
        gain_db = 20 * math.log10(volume / 100)
        audio = audio.apply_gain(gain_db)

    # Start offset
    offset_ms = track.get("offset_ms", 0)
    if offset_ms > 0:
        silence = AudioSegment.silent(duration=offset_ms, frame_rate=target_sr)
        audio = silence + audio
    elif offset_ms < 0:
        trim_ms = abs(offset_ms)
        if len(audio) > trim_ms:
            audio = audio[trim_ms:]
        else:
            return None

    return audio


def mix_tracks(tracks: list[dict | None], master_bpm: float, loop: bool, gen: int) -> dict:
    """Render up to 4 tracks to a temp WAV. Returns {success, path} or {success, error}."""
    _ensure_pydub_patch()
    from pydub import AudioSegment

    # Filter out empty / muted slots
    active = []
    has_solo = any(t.get("solo") for t in tracks if t)

    for t in tracks:
        if not t:
            continue
        if has_solo and not t.get("solo"):
            continue
        if t.get("muted"):
            continue
        # Inject master BPM for stretch calculation
        t_copy = dict(t)
        t_copy["_master_bpm"] = master_bpm
        active.append(t_copy)

    if not active:
        return {"success": False, "error": "No active tracks to mix"}

    # Process each track
    segments = []
    max_len = 0
    for t in active:
        seg = _load_and_process(t)
        if seg is None:
            continue
        segments.append(seg)
        max_len = max(max_len, len(seg))

    if not segments:
        return {"success": False, "error": "Failed to load any tracks"}

    # Check for cancellation
    if gen != _render_gen:
        return {"success": False, "error": "Render cancelled"}

    # Pad to same length
    for i, seg in enumerate(segments):
        if len(seg) < max_len:
            segments[i] = seg + AudioSegment.silent(duration=max_len - len(seg), frame_rate=seg.frame_rate)

    # Loop: extend all to 4x longest (capped at 30s)
    if loop:
        loop_target = min(max_len * 4, 30000)
        for i, seg in enumerate(segments):
            repeated = seg
            while len(repeated) < loop_target:
                repeated = repeated + seg
            if len(repeated) > loop_target:
                repeated = repeated[:loop_target]
            segments[i] = repeated
        max_len = loop_target

    # Check for cancellation again
    if gen != _render_gen:
        return {"success": False, "error": "Render cancelled"}

    # Overlay
    mix = segments[0]
    for seg in segments[1:]:
        mix = mix.overlay(seg)

    # Check for cancellation again
    if gen != _render_gen:
        return {"success": False, "error": "Render cancelled"}

    # Export to temp file
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        mix.export(tmp.name, format="wav")
        return {"success": True, "path": tmp.name}
    except Exception as e:
        return {"success": False, "error": f"Export failed: {e}"}


def start_render_thread(tracks: list[dict | None], master_bpm: float, loop: bool) -> None:
    """Start a background render thread."""
    global _render_gen, _render_thread
    _render_gen += 1
    gen = _render_gen

    state.update({
        "audition_rendering": True,
        "audition_status": "Rendering…",
    }, push=False)
    state.push_keys(["audition_rendering", "audition_status"])

    def _run():
        result = mix_tracks(tracks, master_bpm, loop, gen)
        if gen != _render_gen:
            return  # Stale render
        if result.get("success"):
            import playback
            playback.play_file(result["path"])
            state.update({
                "audition_rendering": False,
                "audition_status": f"Ready · {sum(1 for t in tracks if t)} track(s)",
            }, push=False)
        else:
            state.update({
                "audition_rendering": False,
                "audition_status": result.get("error", "Render failed"),
            }, push=False)
        state.push_keys(["audition_rendering", "audition_status"])

    _render_thread = threading.Thread(target=_run, daemon=True)
    _render_thread.start()


def stop_render() -> None:
    """Cancel any ongoing render by bumping the generation counter."""
    global _render_gen
    _render_gen += 1
