# FFmpeg Bundling Plan for SAMPSON

## Overview
Bundle a minimal ffmpeg binary with SAMPSON using `imageio-ffmpeg` package instead of requiring users to install ffmpeg separately.

## Why imageio-ffmpeg?

| Aspect | Full FFmpeg | imageio-ffmpeg |
|--------|-------------|----------------|
| Size | 646 MB | 31 MB |
| Audio codecs | All | Common formats (WAV, AIFF, MP3, FLAC, OGG) |
| Video codecs | All | Minimal/none |
| PyInstaller compatible | Manual setup | ✅ Auto-bundles |
| Cross-platform | Manual per-platform | ✅ Windows/Mac/Linux wheels |

## Implementation Plan

### Phase 1: Update Dependencies

**Update `requirements.txt`:**
```python
# Core dependencies
pygame-ce>=2.5.0
customtkinter>=5.2.0
pydub>=0.25.1
imageio-ffmpeg>=0.6.0  # Bundled minimal ffmpeg

# Python 3.13+ compatibility
audioop-lts>=0.2.0; python_version >= "3.13"

# macOS-specific
pyobjc-framework-Cocoa>=10.0; sys_platform == "darwin"
```

### Phase 2: Update conversion.py

**Modify ffmpeg path detection to prioritize imageio-ffmpeg:**

```python
import imageio_ffmpeg

def _find_ffmpeg_path() -> Optional[str]:
    """Find ffmpeg executable path.
    
    Priority:
    1. imageio-ffmpeg bundled binary (preferred - always works)
    2. System PATH (user override)
    3. Common install locations
    """
    # 1. Try imageio-ffmpeg bundled binary first
    try:
        bundled = imageio_ffmpeg.get_ffmpeg_exe()
        if bundled and os.path.isfile(bundled):
            return bundled
    except Exception:
        pass
    
    # 2. Check system PATH (allows user override)
    ffmpeg_exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    path_result = shutil.which(ffmpeg_exe)
    if path_result:
        return path_result
    
    # 3. Try common install locations (fallback)
    # ... existing code ...
    
    return None
```

### Phase 3: Update PyInstaller Spec

**Update `SAMPSON.spec` to include imageio-ffmpeg binaries:**

```python
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

# ... existing datas ...

# Include imageio-ffmpeg binaries
datas += collect_data_files('imageio_ffmpeg', include_py_files=False)

# For binaries (DLLs/SOs), use collect_dynamic_libs
binaries = []
binaries += collect_dynamic_libs('imageio_ffmpeg')
```

### Phase 4: Test Bundled FFmpeg

**Test scenarios:**
1. Run from source (development) - uses imageio-ffmpeg
2. Run PyInstaller build - bundled ffmpeg works
3. Test on clean Windows machine without system ffmpeg
4. Test conversion of all supported formats

## Code Changes Required

### File: conversion.py

1. Add `import imageio_ffmpeg` at top
2. Modify `_find_ffmpeg_path()` to check imageio-ffmpeg first
3. Add `_ensure_ffmpeg_in_path()` to set PATH for subprocess calls

### File: requirements.txt

1. Add `imageio-ffmpeg>=0.6.0`

### File: SAMPSON.spec

1. Add imageio-ffmpeg data collection
2. Add imageio-ffmpeg binary collection

### File: README.md

1. Remove "ffmpeg must be installed separately" section
2. Add note that ffmpeg is bundled

## Size Impact

| Component | Size Added |
|-----------|------------|
| imageio-ffmpeg package | ~31 MB |
| PyInstaller compression (UPX) | ~15-20 MB final |
| Current SAMPSON.exe | ~15 MB |
| **New SAMPSON.exe (est.)** | **~30-35 MB** |

## Supported Formats with imageio-ffmpeg

Based on imageio-ffmpeg's ffmpeg build:

**Input:** WAV, AIFF, MP3, FLAC, OGG, WMA, AAC (limited)
**Output:** WAV, AIFF, MP3, FLAC, OGG

✅ Covers all formats in `constants.AUDIO_EXTS`

## Fallback Strategy

If imageio-ffmpeg fails or user wants custom ffmpeg:

1. User can install system ffmpeg
2. Our code checks system PATH first (user override)
3. Falls back to imageio-ffmpeg bundled version

## Testing Checklist

- [ ] Install imageio-ffmpeg: `pip install imageio-ffmpeg`
- [ ] Verify conversion works without system ffmpeg
- [ ] Build with PyInstaller: `pyinstaller SAMPSON.spec`
- [ ] Test on clean Windows VM without ffmpeg
- [ ] Verify all audio formats convert correctly
- [ ] Test fallback to system ffmpeg (when available)

## Licensing Considerations

imageio-ffmpeg uses LGPL/GPL ffmpeg builds. This is acceptable for SAMPSON since:
- We're not modifying ffmpeg
- We're not linking to ffmpeg (calling as subprocess)
- pydub spawns ffmpeg as separate process

Add attribution to README:
```
## Credits
- FFmpeg bundled via [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg)
```
