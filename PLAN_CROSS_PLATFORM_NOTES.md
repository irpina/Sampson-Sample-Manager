# Cross-Platform Implementation Notes for Audio Conversion

## Overview
The audio conversion feature uses pydub with ffmpeg. This document outlines the cross-platform considerations.

## FFmpeg Discovery Strategy

The `conversion.py` module uses a tiered approach to find ffmpeg:

1. **imageio-ffmpeg (bundled)** - Primary source, works on all platforms
2. **System PATH** - User-installed ffmpeg overrides bundled version
3. **Platform-specific locations** - Fallback for common install paths

### Platform-Specific Paths

**Windows:**
- Winget: `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_*`
- Program Files: `%ProgramFiles%\ffmpeg\bin\ffmpeg.exe`
- Manual: `C:\ffmpeg\bin\ffmpeg.exe`

**macOS:**
- Homebrew: `/opt/homebrew/bin/ffmpeg` (Apple Silicon)
- Homebrew: `/usr/local/bin/ffmpeg` (Intel)
- MacPorts: `/opt/local/bin/ffmpeg`

**Linux:**
- Usually in `/usr/bin/ffmpeg` (via package manager)
- PATH lookup finds it automatically

## ffprobe Discovery

pydub requires **ffprobe** (not ffmpeg) to read audio file metadata. The `_find_ffprobe_path()` function:

1. Looks in same directory as ffmpeg (handles imageio-ffmpeg layout)
2. Tries various naming pattern replacements
3. Falls back to PATH lookup

### Important Note for Windows Users

imageio-ffmpeg bundles ffmpeg but **NOT ffprobe**. For Windows builds, you must manually copy ffprobe.exe to the same directory as the bundled ffmpeg:

```powershell
# After pip install imageio-ffmpeg
copy ffprobe.exe %USERPROFILE%\AppData\Roaming\Python\Python3xx\site-packages\imageio_ffmpeg\binaries\
```

For PyInstaller builds, include ffprobe in the spec file.

## PATH Environment Variable

The conversion function ensures the ffmpeg directory is in PATH:

```python
ffmpeg_dir = os.path.dirname(ffmpeg_path)
current_path = os.environ.get('PATH', '')
if ffmpeg_dir not in current_path:
    os.environ['PATH'] = ffmpeg_dir + os.pathsep + current_path
```

This is critical because:
- pydub spawns ffmpeg as a subprocess
- The subprocess inherits PATH to find the executable
- Each thread may have its own PATH state

## PyInstaller Bundling

### Windows (.exe)
```python
# SAMPSON.spec
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = []
datas += collect_data_files('pygame')
datas += collect_data_files('imageio_ffmpeg')  # Includes ffmpeg binary
datas += [('sampsontransparent2.png', '.')]

# Note: Must manually ensure ffprobe.exe is in the imageio_ffmpeg binaries directory
# or add it to datas separately
```

### macOS (.app)
```python
# SAMPSON_mac.spec
# Similar to Windows, but bundle_identifier and info_plist required
datas += collect_data_files('imageio_ffmpeg')
# ffprobe should be included automatically if in the binaries directory
```

### Linux
- Usually relies on system ffmpeg (apt install ffmpeg)
- Can bundle imageio-ffmpeg as fallback

## Testing Matrix

| Platform | FFmpeg Source | ffprobe Status | Notes |
|----------|--------------|----------------|-------|
| Windows (dev) | imageio-ffmpeg | Must copy manually | winget full build has both |
| Windows (exe) | Bundled | Must bundle | Add to PyInstaller spec |
| macOS (dev) | Homebrew or imageio | Usually together | brew install ffmpeg |
| macOS (app) | Bundled | Bundled | Test on clean VM |
| Linux | System or bundled | System or bundled | apt install ffmpeg |

## Known Limitations

1. **Windows + imageio-ffmpeg**: No ffprobe bundled, manual copy required
2. **Worker thread PATH**: May differ from main thread, explicitly set in convert_file()
3. **File paths with spaces**: Well-tested, should work on all platforms
4. **Network drives**: Should work if ffmpeg is locally available

## Future Improvements

- Auto-download ffprobe for Windows if missing
- Use static ffmpeg builds with ffprobe included
- Consider pydub alternatives that don't require ffprobe
