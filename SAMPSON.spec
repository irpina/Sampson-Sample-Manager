# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

datas = []
datas += collect_data_files('pygame')
datas += [('sampsontransparent2.png', '.')]

# Include static-ffmpeg binaries (bundled ffmpeg + ffprobe)
datas += collect_data_files('static_ffmpeg', include_py_files=False)

# Collect any dynamic libraries from static-ffmpeg
binaries = []
binaries += collect_dynamic_libs('static_ffmpeg')


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig=[],
    runtime_hooks=[],
    excludes=['librosa', 'numpy', 'aubio'],
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
