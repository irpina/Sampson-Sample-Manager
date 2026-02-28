# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.building.build_main import Analysis, PYZ, EXE, BUNDLE, COLLECT
from PyInstaller.utils.hooks import collect_data_files

sys.setrecursionlimit(5000)

# Code signing identity
CODESIGN_IDENTITY = 'Developer ID Application: Zachary Louden (62CG778HFA)'

pygame_datas = collect_data_files('pygame')
ffmpeg_datas = collect_data_files('static_ffmpeg')
logo_file = ('sampsontransparent2.png', '.')
all_datas = [logo_file] + pygame_datas + ffmpeg_datas

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=all_datas,
    hiddenimports=[
        'pygame',
        'pydub',
        'customtkinter',
        'AppKit',
        'audioop',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SAMPSON',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=CODESIGN_IDENTITY,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    name='SAMPSON'
)

app = BUNDLE(
    coll,
    name='SAMPSON.app',
    icon=None,
    bundle_identifier='com.sampson.samplemanager',
    info_plist={
        'CFBundleShortVersionString': '0.3.5',
        'CFBundleVersion': '0.3.5',
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
    },
)
