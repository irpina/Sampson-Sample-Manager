# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = []
datas += collect_data_files('pygame')
datas += [('ui/sampsontransparent2.png', '.'), ('ui/sampsontransparentwhite.png', '.')]

# Include UI files
datas += [('ui', 'ui')]

# Include static-ffmpeg binaries (bundled ffmpeg + ffprobe)
datas += collect_data_files('static_ffmpeg', include_py_files=False)

# Collect any dynamic libraries from static-ffmpeg
binaries = []
binaries += collect_dynamic_libs('static_ffmpeg')

# PyWebView may need additional data files on some platforms
try:
    import pywebview
    datas += collect_data_files('pywebview')
except ImportError:
    pass

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=['pywebview', 'pywebview.util', 'webview'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['librosa', 'numpy', 'aubio', 'tkinter', 'customtkinter'],
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
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

app = BUNDLE(
    exe,
    name='SAMPSON.app',
    icon=None,
    bundle_identifier='com.zacharylouden.sampson',
    info_plist={
        'CFBundleShortVersionString': '0.8.2',
        'CFBundleVersion': '0.8.2',
        'NSHighResolutionCapable': True,
    },
)
