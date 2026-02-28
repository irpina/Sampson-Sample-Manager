# Agent Instructions: SAMPSON macOS Port

## Context & Current State

SAMPSON is a Python audio sample manager (customtkinter + pygame-ce) that runs on Windows and Linux. This document is an instructional set for an AI agent (or developer) to complete the macOS port. **Packaging and verification require a Mac.** Code changes can be written on any platform.

**Current version:** `v0.3.1` (label in `build_status_bar()` in `builders.py`)

**Repo layout** — 11 modules, single `ctk.CTk` window, all shared state in `state.py`:
```
constants.py → state.py → dpi.py → theme.py → log_panel.py
→ operations.py → browser.py / preview.py → playback.py → builders.py → main.py
```

---

## What Is Already Done — Do Not Redo

| Component | File | Status |
|---|---|---|
| Platform-aware font selection | `theme.py` | ✅ macOS uses `SF Pro Display` / `Menlo` |
| Audio conversion engine | `conversion.py` | ✅ Uses `static-ffmpeg` (bundles ffmpeg + ffprobe for all platforms including macOS ARM64/x86_64) |
| macOS PyObjC dependency | `requirements.txt` | ✅ `pyobjc-framework-Cocoa>=10.0; sys_platform == "darwin"` already present |
| Linux DPI | `dpi.py` | ✅ Returns `1.0` on non-Windows — acceptable |

---

## What Needs To Be Done

### Task 1: macOS DPI Detection (`dpi.py`)

**Read `dpi.py` first.** Find `_compute_dpi_scale()` — it currently returns `1.0` on non-Windows. Add a `darwin` branch using PyObjC before the final fallback:

```python
elif sys.platform == "darwin":
    try:
        from AppKit import NSScreen  # provided by pyobjc-framework-Cocoa
        scale = NSScreen.mainScreen().backingScaleFactor()
        if scale and scale > 0:
            return float(scale)
    except Exception:
        pass
    return 1.0
```

`backingScaleFactor()` returns `2.0` on Retina, `1.0` on non-Retina. No unit conversion needed — `_px()` multiplies raw pixel values by this factor directly.

**Do NOT** call `tk.call('tk', 'scaling', ...)` — CTK handles its own DPI and this would interfere.

**Do NOT** touch `_enable_dpi_awareness()` — it already returns early on non-Windows. macOS DPI awareness for bundled apps is declared via `NSHighResolutionCapable` in the Info.plist (set in the spec file below).

**`main.py` needs no changes** — it already calls `_compute_dpi_scale()` and stores the result in `state._dpi_scale` before `build_app()`.

---

### Task 2: Create `SAMPSON_mac.spec`

PyInstaller on macOS requires a `BUNDLE` block to produce a `.app`. Note: `*.spec` is gitignored in this repo — create the file locally, it won't be committed.

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = []
datas += collect_data_files('pygame')
datas += [('sampsontransparent2.png', '.')]
datas += collect_data_files('static_ffmpeg', include_py_files=False)

binaries = []
binaries += collect_dynamic_libs('static_ffmpeg')

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
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
    [],
    exclude_binaries=True,
    name='SAMPSON',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,           # UPX not recommended on macOS
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True, # Required for macOS Apple Events
    target_arch=None,    # None = current arch; use 'universal2' for fat binary
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='SAMPSON',
)

app = BUNDLE(
    coll,
    name='SAMPSON.app',
    icon=None,           # Replace with 'SAMPSON.icns' if an icon exists
    bundle_identifier='com.sampson.audiotools',
    info_plist={
        'NSHighResolutionCapable': True,         # Retina support
        'NSRequiresAquaSystemAppearance': False,  # Allow system dark/light mode
        'LSMinimumSystemVersion': '12.0',
        'CFBundleShortVersionString': '0.3.2',
        'CFBundleName': 'SAMPSON',
        'CFBundleDisplayName': 'SAMPSON',
    },
)
```

---

### Task 3: Version Bump (`builders.py`)

In `build_status_bar()` (search for the version string):
```python
# Change this:
ctk.CTkLabel(frame, text="v0.3.1", ...)
# To:
ctk.CTkLabel(frame, text="v0.3.2", ...)
```

---

### Task 4: Optional — `build_macos.sh`

```bash
#!/usr/bin/env bash
set -e
echo "Building SAMPSON.app..."

# Pre-download static-ffmpeg binaries (cached after first run)
python -c "import static_ffmpeg; static_ffmpeg.add_paths()"

pyinstaller SAMPSON_mac.spec --clean

echo "Done: dist/SAMPSON.app"
```

Run `chmod +x build_macos.sh` after creating it.

---

## Verification (requires macOS hardware)

### Dev-mode
```bash
pip install -r requirements.txt
python main.py
```

- [ ] Window opens at correct size (not tiny/huge on Retina)
- [ ] Dark and light themes both work (☀/☾ toggle in header)
- [ ] Deck A browser: browse to a folder, files populate the tree
- [ ] Deck B preview: select destination, Run shows preview
- [ ] Audio playback: click a preview file, transport controls play it
- [ ] Conversion: enable "Convert files", set sample rate to 48 kHz, click Run — log shows success

### DPI sanity check
```bash
python -c "
import sys; sys.path.insert(0, '.')
import state, dpi
state._dpi_scale = dpi._compute_dpi_scale()
print('DPI scale:', state._dpi_scale)  # 2.0 on Retina, 1.0 on non-Retina
"
```

### Packaged build
```bash
./build_macos.sh
open dist/SAMPSON.app
```
Repeat the dev-mode checklist. Confirm audio conversion works — this exercises the `static-ffmpeg` PyInstaller bundle path.

---

## Known Risks

| Risk | Mitigation |
|---|---|
| `static_ffmpeg.add_paths()` fails in frozen `.app` | `collect_data_files('static_ffmpeg')` bundles the binaries alongside the Python package; `add_paths()` finds them via `__file__`-relative paths. Test conversion in packaged build early. |
| pygame-ce SDL2 dylibs not found | `collect_data_files('pygame')` should handle SDL dylibs. If audio fails, run `python -c "import pygame; pygame.mixer.init(); print(pygame.mixer.get_init())"` to diagnose. |
| Retina scale = 1.0 despite Retina display | Confirm `pyobjc-framework-Cocoa` installed: `pip show pyobjc-framework-Cocoa`. If missing, `pip install -r requirements.txt` on macOS should install it. |
| Gatekeeper blocks unsigned app | Right-click → Open in Finder to bypass on dev machines. Production requires an Apple Developer certificate + notarization. |
| `argv_emulation=True` causes crash at launch | SAMPSON doesn't use file-open events; set to `False` as a workaround if needed. |

---

## Files Summary

| File | Action |
|---|---|
| `dpi.py` | **Edit** — add `darwin` branch to `_compute_dpi_scale()` |
| `builders.py` | **Edit** — bump version to `v0.3.2` |
| `SAMPSON_mac.spec` | **Create** — PyInstaller BUNDLE spec |
| `build_macos.sh` | **Create** (optional) — build convenience script |
| `theme.py` | **Leave alone** — macOS fonts already done |
| `requirements.txt` | **Leave alone** — PyObjC already included |
| `conversion.py` | **Leave alone** — no platform-specific changes needed |
| `main.py` | **Leave alone** — already calls `_compute_dpi_scale()` correctly |
| `state.py` | **Leave alone** |
| `constants.py` | **Leave alone** |

## Architecture Reminders

- All shared state: `import state` then `state.<attr>` — never `from state import x`
- CTK widget colors: `fg_color=`, `text_color=`, `border_color=` — not `bg=`, `fg=`
- Non-CTK pixel values: always wrap in `dpi._px(n)`
- CTK manages its own DPI — do not call `tk.call('tk', 'scaling', ...)`
- Version label always lives in `build_status_bar()` in `builders.py`
- Always commit after completing changes
