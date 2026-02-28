# macOS Support & Audio Conversion — Task File

Adds two major features to SAMPSON:
1. **macOS Support** — Native macOS app bundle with proper DPI handling and fonts
2. **Audio Conversion** — Convert samples to device-compatible formats (WAV/AIFF, sample rate, bit depth)

Cross-reference: See `PLAN_MACOS_AND_CONVERSION.md` for detailed architecture and research.

---

## Part A — macOS Support

---

### Architecture Overview

Current SAMPSON is Windows-focused with Windows-specific DPI detection (`ctypes.windll`).
This work makes the codebase truly cross-platform.

**Platform Detection:**
```python
import sys
IS_WINDOWS = sys.platform == "win32"
IS_MACOS   = sys.platform == "darwin"
IS_LINUX   = sys.platform.startswith("linux")
```

**Module Changes:**
| Module | Current | macOS Changes |
|--------|---------|---------------|
| `dpi.py` | Windows ctypes only | Add tkinter scaling + PyObjC fallback |
| `theme.py` | "Segoe UI" hardcoded | Add `-apple-system` font stack |
| `main.py` | No changes needed | No changes needed |
| `SAMPSON.spec` | Windows EXE | Create `SAMPSON_mac.spec` with BUNDLE |

**New Files:**
- `SAMPSON_mac.spec` — macOS PyInstaller configuration
- `requirements.txt` — Dependency manifest with platform conditionals
- `build_macos.sh` — Build automation script

---

## Phase A.1 — Core macOS Compatibility

---

### Task A1.1: Create `requirements.txt`

- [ ] Create `requirements.txt` in project root:
  ```
  # Core dependencies for SAMPSON
  pygame-ce>=2.5.0
  customtkinter>=5.2.0
  
  # macOS-specific (only installed on Darwin)
  pyobjc-framework-Cocoa>=10.0; sys_platform == "darwin"
  ```

---

### Task A1.2: Cross-Platform DPI Detection (`dpi.py`)

- [ ] Add platform detection at top of `dpi.py`:
  ```python
  import sys
  IS_WINDOWS = sys.platform == "win32"
  IS_MACOS   = sys.platform == "darwin"
  ```

- [ ] Refactor `_enable_dpi_awareness()` to be Windows-only:
  ```python
  def _enable_dpi_awareness():
      """Declare per-system DPI awareness (Windows only)."""
      if not IS_WINDOWS:
          return
      try:
          ctypes.windll.shcore.SetProcessDpiAwareness(1)
      except (AttributeError, OSError):
          try:
              ctypes.windll.user32.SetProcessDPIAware()
          except (AttributeError, OSError):
              pass
  ```

- [ ] Refactor `_compute_dpi_scale()` for cross-platform support:
  ```python
  def _compute_dpi_scale() -> float:
      """Return the DPI scale factor relative to the baseline (96 Windows, 72 macOS)."""
      if IS_WINDOWS:
          try:
              return ctypes.windll.shcore.GetDpiForSystem() / 96.0
          except (AttributeError, OSError):
              pass
          try:
              hdc = ctypes.windll.user32.GetDC(0)
              dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)
              ctypes.windll.user32.ReleaseDC(0, hdc)
              return dpi / 96.0
          except (AttributeError, OSError):
              return 1.0
      
      elif IS_MACOS:
          # macOS: Try PyObjC first, then tkinter scaling
          try:
              from Cocoa import NSScreen
              screen = NSScreen.mainScreen()
              if screen:
                  # backingScaleFactor is 1.0 for standard, 2.0 for Retina
                  return float(screen.backingScaleFactor())
          except ImportError:
              pass
          # Fallback: tkinter will set scaling after root is created
          return 1.0
      
      else:  # Linux and others
          return 1.0
  ```

- [ ] Add macOS-specific DPI update function for tkinter fallback:
  ```python
  def _update_macos_dpi_from_tk(root):
      """Update DPI scale using tkinter scaling (call after root is created on macOS)."""
      if IS_MACOS:
          try:
              # tkinter scaling: 1.0 = 72 DPI, 1.333 = 96 DPI equivalent
              tk_scale = root.call('tk', 'scaling')
              # Convert to equivalent Windows-style scale (96 DPI baseline)
              state._dpi_scale = tk_scale / 72.0
          except Exception:
              pass
  ```

- [ ] Update `main.py` to call `_update_macos_dpi_from_tk()` after root creation

> **Testing:** Must test on both Retina (2x) and non-Retina Mac displays.

---

### Task A1.3: Platform-Aware Fonts (`theme.py`)

- [ ] Add platform detection at top of `theme.py`:
  ```python
  import sys
  IS_WINDOWS = sys.platform == "win32"
  IS_MACOS   = sys.platform == "darwin"
  ```

- [ ] Replace hardcoded font constants with platform-aware selection:
  ```python
  # Font families by platform
  if IS_WINDOWS:
      FONT_UI = "Segoe UI"
      FONT_MONO = "Consolas"
  elif IS_MACOS:
      FONT_UI = "-apple-system"  # San Francisco on modern macOS
      FONT_MONO = "SF Mono"      # Monospace variant
  else:  # Linux
      FONT_UI = "Ubuntu"
      FONT_MONO = "DejaVu Sans Mono"
  ```

- [ ] Verify all font usage in `theme.py` uses these constants

> **Testing:** Verify fonts render correctly on macOS (not Times Roman fallback).

---

### Task A1.4: macOS PyInstaller Spec (`SAMPSON_mac.spec`)

- [ ] Create `SAMPSON_mac.spec`:
  ```python
  # -*- mode: python ; coding: utf-8 -*-
  from PyInstaller.utils.hooks import collect_data_files
  
  datas = []
  datas += collect_data_files('pygame')
  datas += [('sampsontransparent2.png', '.')]
  
  a = Analysis(
      ['main.py'],
      pathex=[],
      binaries=[],
      datas=datas,
      hiddenimports=[],
      hookspath=[],
      hooksconfig={},
      runtime_hooks=[],
      excludes=[],
      noarchive=False,
      optimize=0,
  )
  pyz = PYZ(a.pure)
  
  exe = EXE(
      pyz,
      a.scripts,
      a.binaries,
      a.datas,
      [],
      name='SAMPSON',
      debug=False,
      bootloader_ignore_signals=False,
      strip=False,
      upx=True,
      upx_exclude=[],
      runtime_tmpdir=None,
      console=False,
      disable_windowed_traceback=False,
      argv_emulation=True,  # Required for macOS app bundles
      target_arch=None,
      codesign_identity=None,
      entitlements_file=None,
  )
  
  app = BUNDLE(
      exe,
      name='SAMPSON.app',
      icon=None,  # TODO: Add .icns file
      bundle_identifier='com.irpina.sampson',
      info_plist={
          'CFBundleName': 'SAMPSON',
          'CFBundleDisplayName': 'SAMPSON',
          'CFBundleShortVersionString': '0.12.0',
          'CFBundleVersion': '0.12.0',
          'CFBundleIdentifier': 'com.irpina.sampson',
          'NSHighResolutionCapable': True,
          'LSMinimumSystemVersion': '10.14',
          'NSRequiresAquaSystemAppearance': False,  # Supports dark mode
      },
  )
  ```

---

### Task A1.5: macOS Build Script

- [ ] Create `build_macos.sh`:
  ```bash
  #!/bin/bash
  set -e
  
  echo "Building SAMPSON for macOS..."
  
  # Clean previous builds
  rm -rf build dist
  
  # Install dependencies
  pip install -r requirements.txt
  
  # Build app bundle
  pyinstaller SAMPSON_mac.spec
  
  echo "Build complete: dist/SAMPSON.app"
  
  # Optional: Create DMG
  if command -v create-dmg &> /dev/null; then
      echo "Creating DMG..."
      create-dmg \
        --volname "SAMPSON Installer" \
        --window-pos 200 120 \
        --window-size 800 400 \
        --icon-size 100 \
        --app-drop-link 600 185 \
        "dist/SAMPSON.dmg" \
        "dist/SAMPSON.app"
      echo "DMG created: dist/SAMPSON.dmg"
  else
      echo "create-dmg not installed. Skipping DMG creation."
      echo "Install with: brew install create-dmg"
  fi
  ```

- [ ] Make executable: `chmod +x build_macos.sh`

---

## Phase A.2 — macOS Polish

---

### Task A2.1: macOS Appearance Detection (Optional)

- [ ] Add system appearance detection function:
  ```python
  def get_macos_appearance():
      """Return 'dark' or 'light' based on macOS system setting."""
      try:
          from Cocoa import NSUserDefaults
          defaults = NSUserDefaults.standardUserDefaults()
          style = defaults.stringForKey_("AppleInterfaceStyle")
          return "dark" if style == "Dark" else "light"
      except ImportError:
          return None
  ```

- [ ] Optional: Auto-detect on first launch in `main.py` before setting theme

---

### Task A2.2: Update Documentation

- [ ] Update `README.md` "Running from source" section with macOS:
  ```markdown
  ## Running from source
  
  ### macOS
  ```bash
  pip install -r requirements.txt
  python main.py
  ```
  
  ### Windows
  ```bash
  pip install pygame-ce
  python main.py
  ```
  
  ### Linux
  ```bash
  pip install pygame-ce
  python main.py
  ```
  ```

- [ ] Add macOS build instructions to README
- [ ] Update "Limitations" section to remove "Windows only"

---

## Part B — Audio Conversion Support

---

### Architecture Overview

Audio conversion extends SAMPSON from file organizer to sample preparation tool.
Uses `pydub` as primary converter with `ffmpeg` as backend.

**New Module:**
```
conversion.py
  → imports: state, theme, constants
  → provides: check_ffmpeg(), get_audio_info(), convert_file()
  → called by: operations.py (during file operations)
```

**Module Changes:**
| Module | Changes |
|--------|---------|
| `constants.py` | Extend PROFILES with conversion presets |
| `state.py` | Add conversion option variables |
| `conversion.py` | **New module** — audio conversion engine |
| `builders.py` | Add conversion panel to center deck |
| `operations.py` | Call conversion in _run_worker() |
| `preview.py` | Show conversion status in preview tree |

---

## Phase B.1 — Core Conversion Engine

---

### Task B1.1: Add pydub Dependency

- [ ] Update `requirements.txt`:
  ```
  # Core dependencies for SAMPSON
  pygame-ce>=2.5.0
  customtkinter>=5.2.0
  pydub>=0.25.1
  
  # macOS-specific
  pyobjc-framework-Cocoa>=10.0; sys_platform == "darwin"
  ```

- [ ] Document ffmpeg requirement in README:
  ```markdown
  ### Audio Conversion Requirements
  
  For audio format conversion, ffmpeg must be installed:
  
  - **macOS**: `brew install ffmpeg`
  - **Windows**: Download from ffmpeg.org and add to PATH
  - **Linux**: `sudo apt install ffmpeg` (Ubuntu/Debian)
  ```

---

### Task B1.2: Create `conversion.py` Module

- [ ] Create `conversion.py`:
  ```python
  """Audio conversion engine for SAMPSON.
  
  Uses pydub with ffmpeg backend for format conversion.
  Supports WAV, AIFF output with configurable sample rate, bit depth.
  """
  
  import shutil
  from pathlib import Path
  from typing import Optional, NamedTuple
  
  import state
  
  # Lazy import pydub to avoid startup overhead
  _pydub = None
  
  def _get_pydub():
      """Lazy load pydub module."""
      global _pydub
      if _pydub is None:
          from pydub import AudioSegment
          _pydub = AudioSegment
      return _pydub
  
  
  class AudioInfo(NamedTuple):
      """Metadata about an audio file."""
      path: Path
      format: str
      sample_rate: int
      bit_depth: Optional[int]
      channels: int
      duration_seconds: float
  
  
  def check_ffmpeg() -> bool:
      """Verify ffmpeg is available on the system."""
      return shutil.which("ffmpeg") is not None
  
  
  def get_audio_info(path: Path) -> Optional[AudioInfo]:
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
          # Actual bit depth detection would require ffmpeg probe
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
          
          # Handle bit depth for WAV export
          parameters = []
          if output_format.lower() == "wav" and bit_depth:
              if bit_depth == 16:
                  parameters = ["-acodec", "pcm_s16le"]
              elif bit_depth == 24:
                  parameters = ["-acodec", "pcm_s24le"]
              elif bit_depth == 32:
                  parameters = ["-acodec", "pcm_s32le"]
          
          dst.parent.mkdir(parents=True, exist_ok=True)
          audio.export(
              str(dst),
              format=export_format,
              parameters=parameters if parameters else None
          )
          return True
          
      except Exception as e:
          if state.root:
              state.root.after(0, lambda: state.status_var.set(f"Conversion error: {e}"))
          return False
  
  
  def get_target_extension(output_format: str) -> str:
      """Get file extension for output format."""
      fmt = output_format.lower()
      if fmt == "aiff":
          return ".aif"
      return ".wav"
  ```

---

### Task B1.3: Extend Hardware Profiles with Conversion Presets

- [ ] Update `constants.py` PROFILES:
  ```python
  # Hardware profiles with conversion presets.
  PROFILES = {
      "Generic": {
          "path_limit": None,
          "conversion": None,  # No auto-conversion
      },
      "M8": {
          "path_limit": 127,
          "conversion": {
              "format": "wav",
              "sample_rate": 44100,
              "bit_depth": 16,
              "channels": None,  # Keep original
              "normalize": False,
          }
      },
      "MPC One": {
          "path_limit": 255,
          "conversion": None,  # User choice
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
              "channels": 1,  # Force mono - Digitakt requirement
              "normalize": False,
          }
      },
      "Elektron Analog Rytm": {
          "path_limit": None,
          "conversion": {
              "format": "wav",
              "sample_rate": 48000,
              "bit_depth": 16,
              "channels": None,  # Keep original
              "normalize": False,
          }
      },
      "Elektron Syntakt": {
          "path_limit": None,
          "conversion": {
              "format": "wav",
              "sample_rate": 48000,
              "bit_depth": 16,
              "channels": None,
              "normalize": False,
          }
      },
  }
  PROFILE_NAMES = list(PROFILES.keys())
  ```

---

## Phase B.2 — UI Integration

---

### Task B2.1: Add Conversion State Variables

- [ ] Add to `state.py`:
  ```python
  # Audio conversion options
  convert_enabled_var = None      # BooleanVar
  convert_format_var = None       # StringVar ("wav" or "aiff")
  convert_sample_rate_var = None  # StringVar ("keep", "44100", "48000", "96000")
  convert_bit_depth_var = None    # StringVar ("keep", "16", "24", "32")
  convert_channels_var = None     # StringVar ("keep", "1", "2")
  convert_normalize_var = None    # BooleanVar
  convert_follow_profile_var = None  # BooleanVar - auto-apply device preset
  ```

---

### Task B2.2: Add Conversion Panel to Center Deck

- [ ] In `builders.py` `build_center()`, add conversion panel below profile selector:
  ```python
  # --- Audio Conversion ---
  conv_frame = ctk.CTkFrame(frame, fg_color="transparent")
  conv_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(12, 0))
  
  state.convert_enabled_var = tk.BooleanVar(value=False)
  conv_cb = ctk.CTkCheckBox(conv_frame, text="Convert audio files",
                            variable=state.convert_enabled_var,
                            font=(theme.FONT_UI, 9),
                            text_color=theme.FG_ON_SURF,
                            checkbox_width=16, checkbox_height=16,
                            corner_radius=4)
  conv_cb.pack(anchor="w")
  
  # Conversion options frame (enabled/disabled based on checkbox)
  conv_opts = ctk.CTkFrame(conv_frame, fg_color=theme.BG_SURF1,
                           corner_radius=6, height=_px(100))
  conv_opts.pack(fill="x", pady=(8, 0))
  
  # Format dropdown
  fmt_row = ctk.CTkFrame(conv_opts, fg_color="transparent")
  fmt_row.pack(fill="x", padx=8, pady=(6, 2))
  ctk.CTkLabel(fmt_row, text="Format:", font=(theme.FONT_UI, 8),
               text_color=theme.FG_VARIANT).pack(side="left")
  state.convert_format_var = tk.StringVar(value="wav")
  fmt_combo = ctk.CTkComboBox(fmt_row, values=["wav", "aiff"],
                              variable=state.convert_format_var,
                              width=_px(80), state="readonly",
                              font=(theme.FONT_UI, 8))
  fmt_combo.pack(side="left", padx=(8, 0))
  
  # Sample rate dropdown
  sr_row = ctk.CTkFrame(conv_opts, fg_color="transparent")
  sr_row.pack(fill="x", padx=8, pady=2)
  ctk.CTkLabel(sr_row, text="Sample rate:", font=(theme.FONT_UI, 8),
               text_color=theme.FG_VARIANT).pack(side="left")
  state.convert_sample_rate_var = tk.StringVar(value="keep")
  sr_combo = ctk.CTkComboBox(sr_row, values=["keep original", "44.1 kHz", "48 kHz", "96 kHz"],
                             variable=state.convert_sample_rate_var,
                             width=_px(100), state="readonly",
                             font=(theme.FONT_UI, 8))
  sr_combo.pack(side="left", padx=(8, 0))
  
  # Bit depth dropdown
  bd_row = ctk.CTkFrame(conv_opts, fg_color="transparent")
  bd_row.pack(fill="x", padx=8, pady=2)
  ctk.CTkLabel(bd_row, text="Bit depth:", font=(theme.FONT_UI, 8),
               text_color=theme.FG_VARIANT).pack(side="left")
  state.convert_bit_depth_var = tk.StringVar(value="keep")
  bd_combo = ctk.CTkComboBox(bd_row, values=["keep original", "16-bit", "24-bit", "32-bit float"],
                             variable=state.convert_bit_depth_var,
                             width=_px(100), state="readonly",
                             font=(theme.FONT_UI, 8))
  bd_combo.pack(side="left", padx=(8, 0))
  
  # Channels dropdown
  ch_row = ctk.CTkFrame(conv_opts, fg_color="transparent")
  ch_row.pack(fill="x", padx=8, pady=2)
  ctk.CTkLabel(ch_row, text="Channels:", font=(theme.FONT_UI, 8),
               text_color=theme.FG_VARIANT).pack(side="left")
  state.convert_channels_var = tk.StringVar(value="keep")
  ch_combo = ctk.CTkComboBox(ch_row, values=["keep original", "mono", "stereo"],
                             variable=state.convert_channels_var,
                             width=_px(100), state="readonly",
                             font=(theme.FONT_UI, 8))
  ch_combo.pack(side="left", padx=(8, 0))
  
  # Follow profile preset checkbox
  state.convert_follow_profile_var = tk.BooleanVar(value=True)
  follow_cb = ctk.CTkCheckBox(conv_opts, text="Auto-apply device preset",
                              variable=state.convert_follow_profile_var,
                              font=(theme.FONT_UI, 8),
                              text_color=theme.FG_MUTED,
                              checkbox_width=14, checkbox_height=14,
                              corner_radius=3)
  follow_cb.pack(anchor="w", padx=8, pady=(4, 6))
  
  # Enable/disable options based on convert_enabled
  def _toggle_conv_opts(*_):
      enabled = state.convert_enabled_var.get()
      for child in conv_opts.winfo_children():
          try:
              child.configure(state="normal" if enabled else "disabled")
          except Exception:
              pass
      # Also update comboboxes specifically
      for combo in [fmt_combo, sr_combo, bd_combo, ch_combo]:
          try:
              combo.configure(state="readonly" if enabled else "disabled")
          except Exception:
              pass
  
  state.convert_enabled_var.trace_add("write", _toggle_conv_opts)
  _toggle_conv_opts()  # Set initial state
  ```

- [ ] Update grid row numbers for elements below conversion panel

---

### Task B2.3: Auto-Apply Device Preset on Profile Change

- [ ] Add profile change handler in `builders.py` `build_app()`:
  ```python
  def _on_profile_changed(*_):
      """Apply device conversion preset when profile changes."""
      if not state.convert_follow_profile_var or not state.convert_follow_profile_var.get():
          return
      
      profile_name = state.profile_var.get()
      profile = constants.PROFILES.get(profile_name, {})
      preset = profile.get("conversion")
      
      if preset:
          state.convert_enabled_var.set(True)
          state.convert_format_var.set(preset.get("format", "wav"))
          
          sr = preset.get("sample_rate")
          state.convert_sample_rate_var.set(
              "keep original" if sr is None else f"{sr // 1000} kHz"
          )
          
          bd = preset.get("bit_depth")
          state.convert_bit_depth_var.set(
              "keep original" if bd is None else f"{bd}-bit"
          )
          
          ch = preset.get("channels")
          if ch == 1:
              state.convert_channels_var.set("mono")
          elif ch == 2:
              state.convert_channels_var.set("stereo")
          else:
              state.convert_channels_var.set("keep original")
      else:
          # No preset - disable conversion
          state.convert_enabled_var.set(False)
      
      preview.refresh_preview()
  
  state.profile_var.trace_add("write", _on_profile_changed)
  ```

---

### Task B2.4: Add Conversion Indication to Preview Tree

- [ ] Update `preview.py` `_populate_preview()` to show conversion status:
  ```python
  # In _populate_preview(), after computing new_name:
  convert_enabled = state.convert_enabled_var and state.convert_enabled_var.get()
  if convert_enabled:
      # Change extension to target format
      target_fmt = state.convert_format_var.get() if state.convert_format_var else "wav"
      new_name = Path(new_name).stem + get_target_extension(target_fmt)
      display_name = f"{new_name} [convert]"
  else:
      display_name = new_name
  
  # Insert with display_name instead of new_name
  state.preview_tree.insert("", "end",
      values=(f.name, display_name, rel_sub, str(f)),
      tags=(tag,))
  ```

- [ ] Add import: `from conversion import get_target_extension`

---

## Phase B.3 — Worker Integration

---

### Task B3.1: Update File Operations for Conversion

- [ ] Modify `operations.py` `run_tool()` to read conversion options:
  ```python
  # Build conversion options dict
  convert_options = None
  if state.convert_enabled_var and state.convert_enabled_var.get():
      # Parse sample rate
      sr_str = state.convert_sample_rate_var.get()
      sample_rate = None if "keep" in sr_str else int(sr_str.split()[0]) * 1000
      
      # Parse bit depth
      bd_str = state.convert_bit_depth_var.get()
      bit_depth = None if "keep" in bd_str else int(bd_str.split("-")[0])
      
      # Parse channels
      ch_str = state.convert_channels_var.get()
      if "mono" in ch_str:
          channels = 1
      elif "stereo" in ch_str:
          channels = 2
      else:
          channels = None
      
      convert_options = {
          "format": state.convert_format_var.get(),
          "sample_rate": sample_rate,
          "bit_depth": bit_depth,
          "channels": channels,
          "normalize": state.convert_normalize_var.get() if state.convert_normalize_var else False,
      }
  ```

- [ ] Pass `convert_options` to `_run_worker()`

- [ ] Update `_run_worker()` signature and logic:
  ```python
  def _run_worker(source, dest, move_files, dry, path_limit, no_rename, 
                  struct_mode, convert_options):
      # ... existing file collection ...
      
      # Check ffmpeg if conversion enabled
      if convert_options and not conversion.check_ffmpeg():
          state.root.after(0, lambda: state.status_var.set("Error: ffmpeg not found"))
          state.root.after(0, lambda: messagebox.showerror(
              "Conversion Error",
              "ffmpeg is required for audio conversion.\n\n"
              "Install:\n"
              "- macOS: brew install ffmpeg\n"
              "- Windows: Download from ffmpeg.org\n"
              "- Linux: sudo apt install ffmpeg",
              parent=state.root
          ))
          state.root.after(0, lambda: state.run_btn.configure(text="Run", state="normal"))
          return
      
      for i, f in enumerate(files, 1):
          new_name, rel_sub = _compute_output(f, source, dest,
                                              no_rename, struct_mode, path_limit)
          
          # Apply extension change if converting
          if convert_options:
              new_name = Path(new_name).stem + conversion.get_target_extension(
                  convert_options["format"]
              )
          
          sub_dir = dest / rel_sub if rel_sub else dest
          target = sub_dir / new_name
          dest_display = f"{rel_sub}/{new_name}" if rel_sub else new_name
          
          if convert_options:
              msg = f"{prefix}{label}: {f.name} → {dest_display} [converting]"
          else:
              msg = f"{prefix}{label}: {f.name} → {dest_display}"
          
          # ... logging ...
          
          if not dry:
              sub_dir.mkdir(parents=True, exist_ok=True)
              
              if convert_options:
                  success = conversion.convert_file(f, target, **convert_options)
                  if not success:
                      continue
                  if move_files:
                      f.unlink()  # Delete original after conversion
              else:
                  if move_files:
                      shutil.move(str(f), str(target))
                  else:
                      shutil.copy2(str(f), str(target))
  ```

---

## Phase B.4 — Polish & Version Bump

---

### Task B4.1: Update Version

- [ ] `builders.py` — `build_status_bar()`: bump version for macOS + conversion release
  ```python
  ctk.CTkLabel(frame, text="v0.13.0", ...)  # or appropriate version
  ```

---

### Task B4.2: Update README

- [ ] Add Audio Conversion section to README features
- [ ] Document supported conversion formats
- [ ] Add conversion UI screenshot (when available)
- [ ] Update supported devices list (add Elektron devices)

---

## File Change Summary

| File | Changes |
|------|---------|
| `requirements.txt` | **New** — dependency manifest |
| `dpi.py` | Add macOS DPI detection, platform detection |
| `theme.py` | Add platform-aware font fallbacks |
| `SAMPSON_mac.spec` | **New** — macOS PyInstaller configuration |
| `build_macos.sh` | **New** — macOS build script |
| `constants.py` | Extend PROFILES with conversion presets |
| `state.py` | Add conversion option variables |
| `conversion.py` | **New** — audio conversion engine |
| `builders.py` | Add conversion panel, profile preset handler, version bump |
| `preview.py` | Show conversion status in preview |
| `operations.py` | Integrate conversion into file operations |
| `README.md` | macOS and conversion documentation |

---

## Testing Checklist

### macOS Testing
- [ ] App launches on macOS Sonoma (Apple Silicon)
- [ ] App launches on macOS Sonoma (Intel)
- [ ] Fonts render correctly (San Francisco, not Times Roman)
- [ ] DPI correct on Retina display (2x)
- [ ] DPI correct on non-Retina display (1x)
- [ ] Audio playback works (pygame-ce on macOS)
- [ ] File dialogs use native macOS picker
- [ ] Dark/light theme toggle works
- [ ] PyInstaller .app bundle runs on clean machine

### Audio Conversion Testing
- [ ] ffmpeg detection works (shows error if missing)
- [ ] Convert WAV to AIFF
- [ ] Convert AIFF to WAV
- [ ] Convert MP3 to WAV
- [ ] Sample rate conversion (96kHz → 48kHz)
- [ ] Bit depth conversion (24-bit → 16-bit)
- [ ] Stereo to mono conversion
- [ ] Digitakt preset forces mono + 48kHz
- [ ] Preview shows "[convert]" indicator
- [ ] Output files load in target hardware

---

## Version History

| Version | Features |
|---------|----------|
| v0.12 | Previous release (audio preview) |
| v0.13 | This work: macOS support + Audio conversion |

---

End of Task File
