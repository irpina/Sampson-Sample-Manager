"""Audio conversion engine for SAMPSON.

Uses pydub with ffmpeg backend for format conversion.
Supports WAV, AIFF output with configurable sample rate, bit depth.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, NamedTuple

import state

# Track whether static_ffmpeg paths have been added to PATH
_static_ffmpeg_initialized = False


def _init_static_ffmpeg() -> bool:
    """Add static_ffmpeg binaries (ffmpeg + ffprobe) to PATH. Returns True on success."""
    global _static_ffmpeg_initialized
    if not _static_ffmpeg_initialized:
        try:
            import static_ffmpeg
            static_ffmpeg.add_paths()
            _static_ffmpeg_initialized = True
        except Exception:
            pass
    return _static_ffmpeg_initialized


def _find_ffmpeg_path() -> Optional[str]:
    """Find ffmpeg executable path.

    Priority:
    1. static-ffmpeg bundled binaries (includes both ffmpeg + ffprobe)
    2. System PATH (user override)
    3. Common install locations
    """
    # 1. Try static-ffmpeg bundled binaries first (bundled with app)
    try:
        if _init_static_ffmpeg():
            ffmpeg_exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
            bundled = shutil.which(ffmpeg_exe)
            if bundled and os.path.isfile(bundled):
                return bundled
    except Exception:
        pass
    
    # 2. Check system PATH (allows user override of bundled version)
    ffmpeg_exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    path_result = shutil.which(ffmpeg_exe)
    if path_result:
        return path_result
    
    # 3. Try common install locations (fallback for development)
    if sys.platform == "win32":
        program_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        
        # Winget installs ffmpeg with version in path
        winget_base = os.path.join(local_appdata, "Microsoft", "WinGet", "Packages",
                                   "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe")
        if os.path.isdir(winget_base):
            for item in os.listdir(winget_base):
                if item.startswith("ffmpeg-") and "full_build" in item:
                    candidate = os.path.join(winget_base, item, "bin", "ffmpeg.exe")
                    if os.path.isfile(candidate):
                        return candidate
        
        common_paths = [
            os.path.join(program_files, "ffmpeg", "bin", "ffmpeg.exe"),
            os.path.join(program_files_x86, "ffmpeg", "bin", "ffmpeg.exe"),
            r"C:\ffmpeg\bin\ffmpeg.exe",
        ]
        
        for path in common_paths:
            if os.path.isfile(path):
                return path
    
    return None


def _find_ffprobe_path(ffmpeg_path: str) -> Optional[str]:
    """Find ffprobe executable path based on ffmpeg location.
    
    Args:
        ffmpeg_path: Path to ffmpeg executable
        
    Returns:
        Path to ffprobe executable, or None if not found
    """
    if not ffmpeg_path:
        return None
    
    ffmpeg_dir = os.path.dirname(ffmpeg_path)
    
    # Check same directory as ffmpeg first (imageio-ffmpeg layout)
    ffprobe_exe = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    same_dir = os.path.join(ffmpeg_dir, ffprobe_exe)
    if os.path.isfile(same_dir):
        return same_dir
    
    # Try replacing ffmpeg with ffprobe in the filename (various naming conventions)
    base_name = os.path.basename(ffmpeg_path)
    
    # Handle different ffmpeg naming patterns
    replacements = [
        ("ffmpeg-win-x86_64-", "ffprobe-win-x86_64-"),
        ("ffmpeg-win-", "ffprobe-win-"),
        ("ffmpeg", "ffprobe"),
    ]
    
    for old, new in replacements:
        if old in base_name:
            candidate = os.path.join(ffmpeg_dir, base_name.replace(old, new))
            if os.path.isfile(candidate):
                return candidate
    
    # Try PATH lookup as last resort
    return shutil.which(ffprobe_exe)


def check_ffmpeg() -> bool:
    """Verify ffmpeg is available on the system."""
    return _find_ffmpeg_path() is not None


def get_ffmpeg_version() -> Optional[str]:
    """Get ffmpeg version string if available."""
    ffmpeg_path = _find_ffmpeg_path()
    if not ffmpeg_path:
        return None
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # First line: "ffmpeg version 6.0 Copyright ..."
            first_line = result.stdout.split('\n')[0]
            return first_line.split()[2] if len(first_line.split()) >= 3 else "unknown"
    except Exception:
        pass
    return None


def get_audio_info(path: Path) -> Optional[NamedTuple]:
    """Extract metadata from an audio file.
    
    Returns None if file cannot be read.
    """
    try:
        AudioSegment = _get_pydub()
        audio = AudioSegment.from_file(str(path))
        
        # Determine format from extension
        fmt = path.suffix.lower().lstrip('.')
        if fmt in ('aif', 'aiff'):
            fmt = 'aiff'
        
        # pydub samples are 16-bit internally, so bit_depth is estimated
        return AudioInfo(
            path=path,
            format=fmt,
            sample_rate=audio.frame_rate,
            bit_depth=16,  # pydub uses 16-bit internally
            channels=audio.channels,
            duration_seconds=len(audio) / 1000.0
        )
    except Exception:
        return None


# Define AudioInfo NamedTuple after imports
class AudioInfo(NamedTuple):
    """Metadata about an audio file."""
    path: Path
    format: str
    sample_rate: int
    bit_depth: Optional[int]
    channels: int
    duration_seconds: float


# Lazy import pydub to avoid startup overhead
_pydub = None


def _get_pydub():
    """Lazy load pydub module and configure ffmpeg path."""
    global _pydub
    if _pydub is None:
        from pydub import AudioSegment
        _pydub = AudioSegment
    return _pydub


def convert_file(
    src: Path,
    dst: Path,
    output_format: str = "wav",
    sample_rate: Optional[int] = None,
    bit_depth: Optional[int] = None,
    channels: Optional[int] = None,
    normalize: bool = False,
) -> bool:
    """Convert an audio file to target specifications.
    
    Args:
        src: Source file path
        dst: Destination file path
        output_format: "wav" or "aiff"
        sample_rate: Target sample rate (None = keep original)
        bit_depth: Target bit depth 16, 24, or 32 (None = keep original)
        channels: Target channels 1 or 2 (None = keep original)
        normalize: Apply normalization
    
    Returns:
        True if conversion successful, False otherwise
    """
    try:
        # Verify source file exists
        if not src.exists():
            raise FileNotFoundError(f"Source file not found: {src}")
        
        # Find ffmpeg
        ffmpeg_path = _find_ffmpeg_path()
        if not ffmpeg_path:
            raise RuntimeError("ffmpeg not found - cannot convert audio")
        
        # Ensure PATH includes ffmpeg directory for subprocess calls
        ffmpeg_dir = os.path.dirname(ffmpeg_path)
        current_path = os.environ.get('PATH', '')
        if ffmpeg_dir not in current_path:
            os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
        
        # Explicitly set pydub's ffmpeg path
        import pydub
        pydub.AudioSegment.converter = ffmpeg_path
        
        # Also set ffprobe (needed for reading file info)
        ffprobe_path = _find_ffprobe_path(ffmpeg_path)
        if ffprobe_path:
            pydub.utils.ffprobe = ffprobe_path
        
        # Now load pydub and process the audio
        AudioSegment = _get_pydub()
        audio = AudioSegment.from_file(str(src))
        
        # Apply conversions in order
        if sample_rate and audio.frame_rate != sample_rate:
            audio = audio.set_frame_rate(sample_rate)
        
        if channels and audio.channels != channels:
            if channels == 1:
                audio = audio.set_channels(1)  # Mono
            elif channels == 2:
                audio = audio.set_channels(2)  # Stereo
        
        if normalize:
            # Normalize to -1 dBFS to prevent clipping
            audio = audio.normalize()
            audio = audio.apply_gain(-1.0)
        
        # Export with specified parameters
        export_format = output_format.upper()
        
        # Handle bit depth for WAV export via ffmpeg parameters
        parameters = []
        if output_format.lower() == "wav" and bit_depth:
            if bit_depth == 16:
                parameters = ["-acodec", "pcm_s16le"]
            elif bit_depth == 24:
                parameters = ["-acodec", "pcm_s24le"]
            elif bit_depth == 32:
                parameters = ["-acodec", "pcm_s32le"]
        elif output_format.lower() in ("aiff", "aif") and bit_depth:
            if bit_depth == 16:
                parameters = ["-acodec", "pcm_s16be"]
            elif bit_depth == 24:
                parameters = ["-acodec", "pcm_s24be"]
            elif bit_depth == 32:
                parameters = ["-acodec", "pcm_s32be"]
        
        dst.parent.mkdir(parents=True, exist_ok=True)
        audio.export(
            str(dst),
            format=export_format,
            parameters=parameters if parameters else None
        )
        return True
        
    except Exception as e:
        # Store error info in state for retrieval
        import traceback
        state._last_conversion_error = f"{str(e)}\n{traceback.format_exc()}"
        return False


def get_target_extension(output_format: str) -> str:
    """Get file extension for output format."""
    fmt = output_format.lower()
    if fmt in ("aiff", "aif"):
        return ".aif"
    return ".wav"


def parse_sample_rate(value: str) -> Optional[int]:
    """Parse sample rate dropdown value to integer.
    
    Args:
        value: String like "keep", "44.1k", "48k", "96k", "44100"
    
    Returns:
        Sample rate as int, or None to keep original
    """
    if not value or "keep" in value.lower():
        return None
    # Handle format: 44.1k, 48k, 96k
    value = value.lower().strip()
    if value.endswith('k'):
        try:
            val = float(value[:-1])  # Remove 'k' and parse
            return int(val * 1000)
        except ValueError:
            pass
    # Fallback: extract any number
    import re
    match = re.search(r'(\d+)', value)
    if match:
        return int(match.group(1))
    return None


def parse_bit_depth(value: str) -> Optional[int]:
    """Parse bit depth dropdown value to integer.
    
    Args:
        value: String like "keep", "16bit", "24bit", "32bit"
    
    Returns:
        Bit depth as int (16, 24, 32), or None to keep original
    """
    if not value or value.lower() == "keep":
        return None
    value = value.lower().strip()
    # Handle format: 16bit, 24bit, 32bit
    if value.startswith('16'):
        return 16
    elif value.startswith('24'):
        return 24
    elif value.startswith('32'):
        return 32
    # Fallback: extract any number
    import re
    match = re.search(r'(\d+)', value)
    if match:
        return int(match.group(1))
    return None


def parse_channels(value: str) -> Optional[int]:
    """Parse channels dropdown value to integer.
    
    Args:
        value: String like "keep", "mono", "stereo"
    
    Returns:
        1 for mono, 2 for stereo, or None to keep original
    """
    if not value or value.lower() == "keep":
        return None
    val = value.lower().strip()
    if val == "mono" or val == "1":
        return 1
    elif val == "stereo" or val == "2":
        return 2
    return None
