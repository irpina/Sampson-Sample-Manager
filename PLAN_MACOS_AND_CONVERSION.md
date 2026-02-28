# SAMPSON Expansion Plan
## macOS Support & Audio Conversion

> **Status:** Planning Phase  
> **Created:** 2026-02-27  
> **Scope:** Two separate major feature integrations

---

## PART A: macOS Support

### Overview
Port SAMPSON from Windows-only to a true cross-platform application supporting macOS. The codebase is already architecturally cross-platform (Python + tkinter/customtkinter + pygame-ce); the work involves platform detection, DPI handling, packaging, and macOS-specific polish.

### A.1 Platform Compatibility Analysis

| Component | Current State | macOS Requirements |
|-----------|---------------|-------------------|
| `dpi.py` | Windows-only (`ctypes.windll`) | Add macOS DPI detection via `NSScreen` or tkinter scaling |
| `theme.py` | "Segoe UI" font hardcoded | Add `-apple-system` font fallback |
| `playback.py` | `pygame-ce` | Native support |
| `customtkinter` | Pure Python | Compatible |
| `tkinter` | Bundled | Bundled with Python |
| PyInstaller | Windows `.exe` | Add macOS `.app` bundle |

### A.2 Implementation Tasks

#### Phase A.1: Core Compatibility (Foundation)

**Task A.1.1: Cross-Platform DPI Detection (`dpi.py`)**
- [ ] Detect platform via `sys.platform` (`"darwin"` for macOS)
- [ ] macOS: Use `tk.call('tk', 'scaling')` as primary method
- [ ] macOS: Fallback to `NSScreen.mainScreen().backingScaleFactor()` via PyObjC if needed
- [ ] Handle macOS default 72 DPI baseline vs Windows 96 DPI
- [ ] Ensure `_px()` returns correct scaled integers on macOS
- [ ] Test on Retina (2x) and non-Retina displays

**Task A.1.2: macOS Font Fallbacks (`theme.py`)**
- [ ] Create platform-aware `FONT_UI` constant
- [ ] Windows: `"Segoe UI"` (unchanged)
- [ ] macOS: `"-apple-system", "SF Pro", "Helvetica Neue"`
- [ ] Linux fallback: `"Ubuntu", "DejaVu Sans"`

**Task A.1.3: macOS PyInstaller Spec (`SAMPSON_mac.spec`)**
- [ ] Create new spec file for macOS app bundle
- [ ] Use `BUNDLE()` instead of `EXE()` for `.app` generation
- [ ] Set `bundle_identifier='com.irpina.sampson'`
- [ ] Add `info_plist` with:
  - `CFBundleName`: "SAMPSON"
  - `CFBundleShortVersionString`: Current version
  - `CFBundleIdentifier`: `com.irpina.sampson`
  - `NSHighResolutionCapable`: `True`
  - `LSMinimumSystemVersion`: "10.14" (Mojave+)

**Task A.1.4: Dependency Management**
- [ ] Create `requirements.txt`:
  ```
  pygame-ce>=2.5.0
  customtkinter>=5.2.0
  pyobjc-framework-Cocoa>=10.0; sys_platform == "darwin"
  ```
- [ ] Document Python 3.10+ requirement

**Task A.1.5: Build Scripts**
- [ ] Create `build_macos.sh` build automation script
- [ ] Optional DMG creation with `create-dmg`

#### Phase A.2: macOS Polish

**Task A.2.1: macOS Appearance Detection**
- [ ] Detect system dark/light mode on macOS
- [ ] Use `NSApp.appearance()` or query `defaults read -g AppleInterfaceStyle`
- [ ] Auto-detect on first launch, respect user toggle after

**Task A.2.2: macOS Menu Bar**
- [ ] Add native macOS menu bar (optional but nice)
- [ ] Include standard Edit menu (Copy/Paste/Select All)
- [ ] Include Window menu

**Task A.2.3: File Dialog Native Look**
- [ ] Verify `filedialog.askdirectory()` uses native macOS picker
- [ ] Test directory selection on macOS 12+ (Monterey and later)

#### Phase A.3: Testing & Distribution

**Task A.3.1: Testing Matrix**
| macOS Version | Architecture | Priority |
|---------------|--------------|----------|
| macOS 14 Sonoma | Apple Silicon (M1/M2/M3) | Critical |
| macOS 14 Sonoma | Intel | High |
| macOS 13 Ventura | Apple Silicon | High |
| macOS 12 Monterey | Intel | Medium |

**Task A.3.2: Code Signing (Optional but Recommended)**
- [ ] Obtain Apple Developer ID
- [ ] Sign app bundle
- [ ] Notarize for Gatekeeper

**Task A.3.3: Documentation Updates**
- [ ] Update `README.md` with macOS build instructions
- [ ] Add macOS download to Releases page
- [ ] Document any macOS-specific limitations

### A.3 Deliverables

1. `dpi.py` - Cross-platform DPI detection
2. `theme.py` - Platform-aware fonts
3. `SAMPSON_mac.spec` - macOS PyInstaller configuration
4. `requirements.txt` - Dependency manifest
5. `build_macos.sh` - Build automation script
6. Updated `README.md` - macOS instructions

### A.4 Estimated Effort

| Phase | Duration | Blockers |
|-------|----------|----------|
| A.1 Core | 1-2 days | Need Mac hardware for testing |
| A.2 Polish | 1 day | None |
| A.3 Distribution | 1-2 days | Apple Developer account |
| **Total** | **3-5 days** | **Mac access required** |

---

## PART B: Audio Conversion Support

### Overview
Extend SAMPSON from a file organizer to a full sample preparation tool by adding audio format conversion. This enables users to convert samples to device-compatible formats (e.g., 16-bit WAV for older samplers, specific sample rates).

### B.1 Target Device Requirements Analysis

| Device | Preferred Format | Sample Rate | Bit Depth | Special Requirements |
|--------|-----------------|-------------|-----------|---------------------|
| **MPC One** | WAV, AIFF | 44.1kHz, 48kHz | 16, 24, 32 | 255 char path limit |
| **SP-404mkII** | WAV | 44.1kHz, 48kHz | 16, 24 | 255 char path limit |
| **Elektron Analog Rytm** | WAV | 48kHz preferred | 16 | Mono/stereo handled |
| **Elektron Digitakt** | WAV | 48kHz | 16 | Mono only, 48kHz enforced |
| **Elektron Syntakt** | WAV | 48kHz | 16 | Similar to Digitakt |
| **Dirtywave M8** | WAV, AIFF | Any | 16 | 127 char path limit, SD card |

### B.2 Audio Conversion Architecture

```
Input File --> [Format Detection] --> [Converter Selection]
                                             |
                                             v
                    +-------------------------------+
                    |   CONVERSION OPTIONS (UI)     |
                    |  Format: [WAV/AIFF]           |
                    |  Sample Rate: [44.1/48kHz]    |
                    |  Bit Depth: [16/24/32]        |
                    |  Channels: [Mono/Stereo]      |
                    +-------------------------------+
                                             |
                                             v
                    +-------------------------------+
                    |  pydub + ffmpeg backend       |
                    +-------------------------------+
                                             |
                                             v
  Output File <-- [Metadata Preservation] <-- [Quality Check]
```

### B.3 Implementation Tasks

#### Phase B.1: Core Conversion Engine

**Task B.1.1: Audio Backend Selection & Integration**

Research and select conversion library:

| Library | Pros | Cons | Verdict |
|---------|------|------|---------|
| `pydub` | Simple API, ffmpeg wrapper | Requires ffmpeg binary | **Primary choice** |
| `soundfile` | libsndfile backend, no ffmpeg | Limited format support | Fallback |
| `ffmpeg-python` | Direct ffmpeg access | Complex API | Too low-level |
| `sox` | High quality | Requires sox binary | Optional addon |

Implementation:
- [ ] Create `conversion.py` module
- [ ] Implement `AudioConverter` class
- [ ] Add `pydub` to `requirements.txt`
- [ ] Bundle ffmpeg binary or require user installation
- [ ] Implement auto-detection of ffmpeg location

**Task B.1.2: Conversion Engine (`conversion.py`)**

Core functions to implement:
- `check_ffmpeg()` - Verify ffmpeg is available (bundled or system)
- `get_audio_info(path)` - Return format, sample_rate, bit_depth, channels, duration
- `convert_file(src, dst, format, sample_rate, bit_depth, channels, normalize)` - Convert audio file to target specifications

**Task B.1.3: Device Preset System**

Extend `constants.py` PROFILES with conversion presets:

```python
PROFILES = {
    "Generic": {
        "path_limit": None,
        "conversion": None,  # No conversion
    },
    "M8": {
        "path_limit": 127,
        "conversion": {
            "format": "wav",
            "sample_rate": 44100,
            "bit_depth": 16,
            "channels": None,  # Keep original
        }
    },
    "MPC One": {
        "path_limit": 255,
        "conversion": None,  # User's choice
    },
    "SP-404mkII": {
        "path_limit": 255,
        "conversion": None,
    },
    "Elektron Digitakt": {
        "path_limit": None,
        "conversion": {
            "format": "wav",
            "sample_rate": 48000,
            "bit_depth": 16,
            "channels": 1,  # Force mono
        }
    },
    "Elektron Analog Rytm": {
        "path_limit": None,
        "conversion": {
            "format": "wav",
            "sample_rate": 48000,
            "bit_depth": 16,
            "channels": None,
        }
    },
}
```

#### Phase B.2: UI Integration

**Task B.2.1: Conversion Options Panel (Center Deck)**

Add to `build_center()` in `builders.py`:
- [ ] Add "Enable conversion" checkbox
- [ ] Add format dropdown (WAV, AIFF)
- [ ] Add sample rate dropdown (44.1kHz, 48kHz, 96kHz)
- [ ] Add bit depth dropdown (16, 24, 32 float)
- [ ] Add channels dropdown (Keep, Force Mono, Force Stereo)
- [ ] Add "Auto-apply device preset" checkbox

**Task B.2.2: Hardware Profile Integration**
- [ ] When profile changes, auto-populate conversion settings
- [ ] Show "Recommended for [Device]" label
- [ ] Allow user to override preset values
- [ ] Visual indicator when settings deviate from preset

**Task B.2.3: Preview Updates**
- [ ] Add "Will convert" column to preview tree (Deck B)
- [ ] Show conversion icon/checkmark in preview
- [ ] Display target format in hover tooltip
- [ ] Update `_compute_output()` to handle converted extensions

#### Phase B.3: File Operations Integration

**Task B.3.1: Modified Worker Thread**

Update `operations.py` `_run_worker()`:
- Apply extension change if converting
- Convert file instead of copy/move when enabled
- Delete original after conversion if move_files is true

**Task B.3.2: Progress Reporting**
- [ ] Add conversion progress within file progress
- [ ] Update progress bar for conversion + copy phases
- [ ] Log conversion details ("Converting 48kHz/24-bit --> 44.1kHz/16-bit")

#### Phase B.4: Quality & Edge Cases

**Task B.4.1: Metadata Preservation**
- [ ] Preserve loop points when possible
- [ ] Copy basic metadata (artist, description)
- [ ] Handle sampler-specific metadata (MPC programs, etc.)

**Task B.4.2: Error Handling**
- [ ] Handle corrupt input files gracefully
- [ ] Report unsupported format combinations
- [ ] Disk space checking before conversion
- [ ] Rollback on failed conversion

**Task B.4.3: Performance Optimization**
- [ ] Parallel conversion for multiple files
- [ ] Temporary file handling (convert then move)
- [ ] Cancel operation support

### B.4 Deliverables

1. `conversion.py` - Core audio conversion engine
2. `requirements.txt` - Updated with `pydub`, `ffmpeg`
3. `constants.py` - Extended PROFILES with conversion presets
4. `builders.py` - Updated center panel with conversion UI
5. `operations.py` - Integrated conversion in worker thread
6. `preview.py` - Updated preview with conversion indication
7. `ffmpeg/` - Bundled ffmpeg binaries (platform-specific)

### B.5 Estimated Effort

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| B.1 Core Engine | 2-3 days | ffmpeg binaries |
| B.2 UI Integration | 2 days | B.1 complete |
| B.3 Worker Integration | 1-2 days | B.1, B.2 complete |
| B.4 Polish & Testing | 2 days | All above |
| **Total** | **7-9 days** | Can test on any platform |

---

## PART C: Combined Considerations

### C.1 Dependency Matrix

| Dependency | macOS | Windows | Linux | Notes |
|------------|-------|---------|-------|-------|
| `pygame-ce` | Yes | Yes | Yes | Audio playback |
| `customtkinter` | Yes | Yes | Yes | UI framework |
| `pydub` | Yes | Yes | Yes | Audio conversion |
| ffmpeg binary | Yes | Yes | Yes | Backend for pydub |
| `pyobjc` | Yes | No | No | macOS DPI detection |

### C.2 Recommended Implementation Order

**Option 1: Sequential (Recommended)**
1. Complete macOS support first (A.1-A.3)
2. Then implement audio conversion (B.1-B.4)
3. Test both together in final QA

Rationale: macOS support changes foundational code (DPI, fonts). Better to stabilize platform before adding features.

**Option 2: Parallel**
1. Implement audio conversion engine (B.1) on Windows
2. Implement macOS core compatibility (A.1) in parallel
3. Merge and integrate both

Rationale: Faster overall if resources available. Risk of merge conflicts in shared files.

### C.3 Version Planning

| Version | Features |
|---------|----------|
| v0.12 | macOS support (Part A complete) |
| v0.13 | Audio conversion core (B.1-B.2) |
| v0.14 | Audio conversion polish (B.3-B.4) |
| v1.0 | Both features stable, general release |

### C.4 Testing Strategy

**macOS Testing:**
- Requires physical Mac hardware or cloud Mac (GitHub Actions macOS runner limited for GUI)
- Test DPI on Retina and non-Retina displays
- Test audio playback (pygame-ce SDL2 backend on macOS)
- Test file dialogs (native vs tkinter)

**Audio Conversion Testing:**
- Test all supported input formats
- Test conversion to each device preset
- Verify output files load in target hardware
- Test edge cases: very long files, corrupt files, disk full

### C.5 Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| No Mac hardware for testing | High | Use GitHub Actions macOS runner; community beta testing |
| ffmpeg licensing | Medium | Bundle GPL-compliant build; document attribution |
| Conversion quality issues | Medium | Extensive testing; allow user override |
| Increased bundle size | Low | Compress ffmpeg binary; optional download |
| pygame-ce macOS audio | Medium | Test early; fallback to sounddevice if needed |

---

## PART D: Immediate Next Steps

### Ready to Start (No Blockers)
- [ ] Create feature branch: `feature/macos-support`
- [ ] Task A.1.2: Font fallbacks in `theme.py`
- [ ] Task A.1.4: Create `requirements.txt`

### Requires macOS Hardware
- [ ] Task A.1.1: macOS DPI detection
- [ ] Task A.1.3: macOS PyInstaller spec testing
- [ ] Task A.2.x: All macOS polish tasks

### Can Parallelize
- [ ] Task B.1.1: Research ffmpeg bundling options
- [ ] Task B.1.2: Design `conversion.py` API

### Blocked Until Core Complete
- [ ] Task B.2.x: UI integration (depends on final UI layout)
- [ ] Task B.3.x: Worker integration (depends on B.1)

---

## Appendix: Device-Specific Format Details

### MPC One/X/Live
- **Formats:** WAV, AIFF, SND, MP3
- **Sample Rates:** 44.1kHz, 48kHz, 88.2kHz, 96kHz
- **Bit Depths:** 16, 24, 32-float
- **Special:** Supports stereo, keygroups, programs

### Roland SP-404mkII
- **Formats:** WAV, AIFF, MP3
- **Sample Rates:** 44.1kHz, 48kHz
- **Bit Depth:** 16, 24
- **Special:** 255 char limit, folder depth matters

### Elektron Digitakt
- **Formats:** WAV only
- **Sample Rate:** 48kHz (strictly enforced)
- **Bit Depth:** 16-bit only
- **Special:** Mono only (stereo auto-converted), 64MB sample pool

### Elektron Analog Rytm MKI/MKII
- **Formats:** WAV only
- **Sample Rate:** 48kHz preferred (others resampled)
- **Bit Depth:** 16-bit
- **Special:** Stereo support, 64 sample slots per project

### Dirtywave M8
- **Formats:** WAV, AIFF
- **Sample Rates:** Any (resampled on load)
- **Bit Depth:** 16-bit (others converted)
- **Special:** 127 char path limit, SD card only

---

End of Plan
