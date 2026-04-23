"""Sample slicer/trimmer module for SAMPSON.

Provides waveform data extraction, auto-slicing, and export functionality.
Uses pydub + FFmpeg (already bundled) - no new dependencies.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any

import state
from conversion import _find_ffmpeg_path

# Track last temp preview file for cleanup
_last_preview_temp: str | None = None


def get_audio_samples(path: str, n_points: int = 4000) -> dict[str, Any]:
    """Extract downsampled waveform data for visualization.
    
    Args:
        path: Path to audio file
        n_points: Number of points to return (downsampled)
        
    Returns:
        Dict with samples, duration, channels, sample_rate
    """
    try:
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(path)
        
        # Convert to mono for visualization (average channels)
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        # Get raw samples as array
        samples = audio.get_array_of_samples()
        
        # Downsample to n_points
        total_samples = len(samples)
        if total_samples <= n_points:
            downsampled = list(samples)
        else:
            # Take max absolute value from each bin
            bin_size = total_samples // n_points
            downsampled = []
            for i in range(n_points):
                start = i * bin_size
                end = min(start + bin_size, total_samples)
                chunk = samples[start:end]
                # Use max absolute value for this bin
                max_val = max(abs(x) for x in chunk) if chunk else 0
                downsampled.append(max_val)
        
        # Normalize to -1.0 to 1.0 range
        max_possible = 2 ** (audio.sample_width * 8 - 1)
        normalized = [s / max_possible for s in downsampled]
        
        return {
            "success": True,
            "samples": normalized,
            "duration": len(audio) / 1000.0,
            "channels": audio.channels,
            "sample_rate": audio.frame_rate,
            "sample_width": audio.sample_width,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _ms_to_str(ms: float) -> str:
    """Convert milliseconds to MM:SS.mmm string."""
    total_seconds = ms / 1000
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:05.3f}"


def auto_slice_silence(
    path: str,
    threshold_db: float = -40.0,
    min_length_ms: float = 100.0,
    padding_ms: float = 10.0,
) -> dict[str, Any]:
    """Auto-slice audio file based on silence detection.
    
    Uses FFmpeg silencedetect filter to find non-silent regions.
    
    Args:
        path: Path to audio file
        threshold_db: Silence threshold in dB (default -40)
        min_length_ms: Minimum slice length in ms
        padding_ms: Padding to add to start/end of each slice
        
    Returns:
        Dict with slices list and metadata
    """
    try:
        ffmpeg_path = _find_ffmpeg_path()
        if not ffmpeg_path:
            return {"success": False, "error": "FFmpeg not found"}
        
        # Run silencedetect filter
        kwargs = {
            "capture_output": True,
            "text": True,
            "timeout": 60
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000
        
        result = subprocess.run(
            [
                ffmpeg_path,
                "-i", path,
                "-af", f"silencedetect=noise={threshold_db}dB:d=0.1",
                "-f", "null",
                "-"
            ],
            **kwargs
        )
        
        # Parse silence detection output
        silence_starts = []
        silence_ends = []
        
        for line in result.stderr.split('\n'):
            if 'silence_start:' in line:
                try:
                    t = float(line.split('silence_start:')[1].strip().split()[0])
                    silence_starts.append(t)
                except (ValueError, IndexError):
                    pass
            elif 'silence_end:' in line:
                try:
                    parts = line.split('silence_end:')[1].strip().split()
                    t = float(parts[0])
                    silence_ends.append(t)
                except (ValueError, IndexError):
                    pass
        
        # Get total duration
        from pydub import AudioSegment
        audio = AudioSegment.from_file(path)
        duration_ms = len(audio)
        
        # Build slices from non-silent regions
        slices = []
        current_start = 0.0
        
        # Pair silence starts with ends. If audio ends in non-silence, FFmpeg may
        # emit a trailing silence_start without a matching silence_end — truncate
        # to paired events only; the final trailing segment is handled below.
        for silence_start, silence_end in zip(silence_starts, silence_ends):
            slice_start = current_start
            slice_end = silence_start * 1000  # Convert to ms
            
            # Apply padding
            slice_start = max(0, slice_start - padding_ms)
            slice_end = min(duration_ms, slice_end + padding_ms)
            
            duration = slice_end - slice_start
            if duration >= min_length_ms:
                slices.append({
                    "start_ms": slice_start,
                    "end_ms": slice_end,
                    "start_str": _ms_to_str(slice_start),
                    "end_str": _ms_to_str(slice_end),
                    "duration_ms": duration,
                    "duration_str": _ms_to_str(duration),
                })
            
            current_start = silence_end * 1000
        
        # Add final slice if there's content after last silence
        if current_start < duration_ms - padding_ms:
            slice_start = max(0, current_start - padding_ms)
            slice_end = duration_ms
            duration = slice_end - slice_start
            if duration >= min_length_ms:
                slices.append({
                    "start_ms": slice_start,
                    "end_ms": slice_end,
                    "start_str": _ms_to_str(slice_start),
                    "end_str": _ms_to_str(slice_end),
                    "duration_ms": duration,
                    "duration_str": _ms_to_str(duration),
                })
        
        # If no slices found, return single slice for entire file
        if not slices:
            slices.append({
                "start_ms": 0.0,
                "end_ms": duration_ms,
                "start_str": _ms_to_str(0),
                "end_str": _ms_to_str(duration_ms),
                "duration_ms": duration_ms,
                "duration_str": _ms_to_str(duration_ms),
            })
        
        return {
            "success": True,
            "slices": slices,
            "count": len(slices),
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def auto_slice_bpm(path: str, bpm: float, beats_per_slice: int = 1) -> dict[str, Any]:
    """Auto-slice audio file based on BPM grid.
    
    Args:
        path: Path to audio file
        bpm: Beats per minute
        beats_per_slice: Number of beats per slice (1, 2, 4, etc.)
        
    Returns:
        Dict with slices list
    """
    try:
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(path)
        duration_ms = len(audio)
        
        # Calculate beat duration in ms
        beat_duration_ms = (60.0 / bpm) * 1000
        slice_duration_ms = beat_duration_ms * beats_per_slice
        
        slices = []
        start_ms = 0.0
        
        while start_ms < duration_ms:
            end_ms = min(start_ms + slice_duration_ms, duration_ms)
            duration = end_ms - start_ms
            
            # Only add if slice is long enough (at least 50ms)
            if duration >= 50:
                slices.append({
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "start_str": _ms_to_str(start_ms),
                    "end_str": _ms_to_str(end_ms),
                    "duration_ms": duration,
                    "duration_str": _ms_to_str(duration),
                })
            
            start_ms = end_ms
        
        return {
            "success": True,
            "slices": slices,
            "count": len(slices),
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def auto_slice_fixed(path: str, slice_length_ms: float) -> dict[str, Any]:
    """Auto-slice audio file into fixed-length chunks.
    
    Args:
        path: Path to audio file
        slice_length_ms: Length of each slice in milliseconds
        
    Returns:
        Dict with slices list
    """
    try:
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(path)
        duration_ms = len(audio)
        
        slices = []
        start_ms = 0.0
        
        while start_ms < duration_ms:
            end_ms = min(start_ms + slice_length_ms, duration_ms)
            duration = end_ms - start_ms
            
            # Only add if slice is long enough (at least 50ms)
            if duration >= 50:
                slices.append({
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "start_str": _ms_to_str(start_ms),
                    "end_str": _ms_to_str(end_ms),
                    "duration_ms": duration,
                    "duration_str": _ms_to_str(duration),
                })
            
            start_ms = end_ms
        
        return {
            "success": True,
            "slices": slices,
            "count": len(slices),
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def auto_slice_transients(
    path: str,
    threshold: float = 3.0,
    min_spacing_ms: float = 100.0,
) -> dict[str, Any]:
    """Auto-slice audio file based on transient/onset detection.
    
    Uses energy delta (relative energy increase) to detect onsets.
    This works well on normalized/limited material where absolute thresholds fail.
    
    Args:
        path: Path to audio file
        threshold: Onset sensitivity ratio (1.5-8.0). Energy must increase by this 
                   factor vs previous frame to count as a transient.
        min_spacing_ms: Minimum spacing between slices
        
    Returns:
        Dict with slices list
    """
    try:
        from pydub import AudioSegment
        
        audio = AudioSegment.from_file(path)
        duration_ms = len(audio)
        
        # Convert to mono and get samples
        if audio.channels > 1:
            audio = audio.set_channels(1)
        
        samples = audio.get_array_of_samples()
        sample_rate = audio.frame_rate
        max_val = 2 ** (audio.sample_width * 8 - 1)
        
        # Normalize samples
        normalized = [abs(s) / max_val for s in samples]
        
        # Find onset points (energy increases, not absolute levels)
        window_size = int(sample_rate * 0.01)  # 10ms window
        hop_size = window_size // 2
        transient_points = []
        
        # Calculate initial energy
        prev_energy = 0.0
        min_energy = 1e-6  # Avoid division by zero
        
        i = window_size
        last_transient_pos = -min_spacing_ms / 1000 * sample_rate
        
        while i < len(normalized) - window_size:
            # Calculate current frame energy
            window = normalized[i:i + window_size]
            energy = sum(x ** 2 for x in window) / len(window)
            
            # Onset detection: energy must increase by threshold ratio
            if prev_energy > min_energy and energy / prev_energy > threshold:
                # Check min spacing
                if i - last_transient_pos >= (min_spacing_ms / 1000 * sample_rate):
                    transient_points.append(i / sample_rate * 1000)  # Convert to ms
                    last_transient_pos = i
                    # Skip ahead by min_spacing to avoid double-detecting
                    skip_samples = int(min_spacing_ms / 1000 * sample_rate)
                    i += max(skip_samples, hop_size)
                    prev_energy = energy
                    continue
            
            prev_energy = energy
            i += hop_size
        
        # Create slices between transient points
        slices = []
        start_ms = 0.0
        
        for transient_ms in transient_points:
            end_ms = transient_ms
            slice_duration = end_ms - start_ms
            
            if slice_duration >= 50:  # At least 50ms
                slices.append({
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "start_str": _ms_to_str(start_ms),
                    "end_str": _ms_to_str(end_ms),
                    "duration_ms": slice_duration,
                    "duration_str": _ms_to_str(slice_duration),
                })
            
            start_ms = end_ms
        
        # Add final slice
        if start_ms < duration_ms - 50:
            slices.append({
                "start_ms": start_ms,
                "end_ms": duration_ms,
                "start_str": _ms_to_str(start_ms),
                "end_str": _ms_to_str(duration_ms),
                "duration_ms": duration_ms - start_ms,
                "duration_str": _ms_to_str(duration_ms - start_ms),
            })
        
        # If no transients found, return single slice
        if not slices:
            slices.append({
                "start_ms": 0.0,
                "end_ms": duration_ms,
                "start_str": _ms_to_str(0),
                "end_str": _ms_to_str(duration_ms),
                "duration_ms": duration_ms,
                "duration_str": _ms_to_str(duration_ms),
            })
        
        return {
            "success": True,
            "slices": slices,
            "count": len(slices),
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def preview_slice(path: str, start_ms: float, end_ms: float) -> dict[str, Any]:
    """Extract a slice to a temp WAV and return its path for playback.
    
    Args:
        path: Source audio file path
        start_ms: Slice start time in milliseconds
        end_ms: Slice end time in milliseconds
        
    Returns:
        Dict with temp_path on success
    """
    global _last_preview_temp
    try:
        ffmpeg_path = _find_ffmpeg_path()
        if not ffmpeg_path:
            return {"success": False, "error": "FFmpeg not found"}
        
        # Clean up previous temp file
        if _last_preview_temp and os.path.exists(_last_preview_temp):
            try:
                os.unlink(_last_preview_temp)
            except Exception:
                pass
        
        # Write to temp WAV
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        tmp.close()
        _last_preview_temp = tmp.name
        
        start_sec = start_ms / 1000
        duration_sec = (end_ms - start_ms) / 1000
        
        kwargs = {"capture_output": True, "text": True, "timeout": 30}
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000
        
        result = subprocess.run([
            ffmpeg_path, "-y",
            "-i", path,
            "-ss", str(start_sec),
            "-t", str(duration_sec),
            "-c:a", "pcm_s16le",
            tmp.name
        ], **kwargs)
        
        if result.returncode != 0:
            return {"success": False, "error": "FFmpeg extraction failed"}
        
        return {"success": True, "temp_path": tmp.name}
    except Exception as e:
        return {"success": False, "error": str(e)}


def export_slices(
    path: str,
    slices: list[dict],
    output_dir: str,
    prefix: str = "",
    suffix: str = "_##",
    output_format: str = "wav",
    normalize: bool = False,
    trim_silence: bool = False,
) -> dict[str, Any]:
    """Export slices to individual files.
    
    Args:
        path: Source audio file path
        slices: List of slice dicts with start_ms, end_ms
        output_dir: Output directory
        prefix: Filename prefix (empty = use source filename)
        suffix: Filename suffix pattern (## = zero-padded index)
        output_format: Output format (wav, aiff, flac)
        normalize: Whether to normalize each slice
        trim_silence: Whether to trim silence from edges
        
    Returns:
        Dict with success status and export info
    """
    try:
        ffmpeg_path = _find_ffmpeg_path()
        if not ffmpeg_path:
            return {"success": False, "error": "FFmpeg not found"}
        
        source_path = Path(path)
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine prefix
        if not prefix:
            prefix = source_path.stem
        
        # Determine codec and extension
        fmt = output_format.lower()
        if fmt == "wav":
            codec = "pcm_s16le"
            ext = ".wav"
        elif fmt in ("aiff", "aif"):
            codec = "pcm_s16be"
            ext = ".aif"
        elif fmt == "flac":
            codec = "flac"
            ext = ".flac"
        else:
            codec = "pcm_s16le"
            ext = ".wav"
        
        exported = []
        total = len(slices)
        
        for i, slice_info in enumerate(slices):
            # Update progress
            progress = int((i / total) * 100)
            state.set("slicer_progress", progress, push=False)
            state.set("slicer_status", f"Exporting slice {i + 1} of {total}...", push=False)
            state.push_keys(["slicer_progress", "slicer_status"])
            
            # Build filename
            index_str = str(i + 1).zfill(len(str(total)))
            filename = f"{prefix}{suffix.replace('##', index_str)}{ext}"
            output_path = out_dir / filename
            
            start_sec = slice_info["start_ms"] / 1000
            end_sec = slice_info["end_ms"] / 1000
            duration = end_sec - start_sec
            
            # Build ffmpeg command
            cmd = [
                ffmpeg_path,
                "-y",  # Overwrite existing files without prompting
                "-i", str(source_path),
                "-ss", str(start_sec),
                "-t", str(duration),
                "-c:a", codec,
            ]
            
            # Add filters
            filters = []
            if normalize:
                filters.append("loudnorm")
            if trim_silence:
                filters.append("silenceremove=start_periods=1:start_threshold=-50dB")
            
            if filters:
                cmd.extend(["-af", ",".join(filters)])
            
            cmd.append(str(output_path))
            
            # Run ffmpeg
            kwargs = {
                "capture_output": True,
                "text": True,
                "timeout": 300
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = 0x08000000
            
            result = subprocess.run(cmd, **kwargs)
            
            if result.returncode == 0:
                exported.append({
                    "index": i + 1,
                    "filename": filename,
                    "path": str(output_path),
                })
        
        state.set("slicer_progress", 100, push=False)
        state.set("slicer_status", f"Exported {len(exported)} slices", push=False)
        state.push_keys(["slicer_progress", "slicer_status"])
        
        return {
            "success": True,
            "exported": exported,
            "count": len(exported),
            "output_dir": str(out_dir),
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def start_export_thread(
    path: str,
    slices: list[dict],
    output_dir: str,
    prefix: str = "",
    suffix: str = "_##",
    output_format: str = "wav",
    normalize: bool = False,
    trim_silence: bool = False,
) -> None:
    """Start export in background thread."""
    def run_export():
        state.set("slicer_exporting", True)
        state.push_keys(["slicer_exporting"])
        
        result = export_slices(
            path, slices, output_dir, prefix, suffix,
            output_format, normalize, trim_silence
        )
        
        state.set("slicer_exporting", False)
        state.set("slicer_export_result", result)
        state.push_keys(["slicer_exporting", "slicer_export_result"])
    
    thread = threading.Thread(target=run_export, daemon=True)
    thread.start()
