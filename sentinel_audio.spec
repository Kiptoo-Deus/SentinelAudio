# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for Sentinel Audio.
Run with:  pyinstaller sentinel_audio.spec
"""

import sys
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None

# sounddevice ships its own PortAudio DLL inside _sounddevice_data
try:
    sounddevice_binaries = collect_dynamic_libs("_sounddevice_data")
except Exception:
    sounddevice_binaries = []

a = Analysis(
    ["main.py"],
    pathex=["."],
    binaries=sounddevice_binaries,
    datas=[
        ("assets/sentinel.ico", "assets"),
    ],
    hiddenimports=[
        # sounddevice loads portaudio at runtime
        "sounddevice",
        "_sounddevice_data",
        # scipy internals
        "scipy.signal",
        "scipy.signal._peak_finding",
        "scipy.signal.windows",
        "scipy._lib.messagestream",
        # sklearn internals used by joblib
        "sklearn.utils._cython_blas",
        "sklearn.neighbors.typedefs",
        "sklearn.neighbors.quad_tree",
        "sklearn.tree._utils",
        # OSC
        "pythonosc",
        "pythonosc.udp_client",
        "pythonosc.dispatcher",
        "pythonosc.osc_server",
        # PyQt6 modules
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.sip",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "IPython",
        "jupyter",
        "notebook",
        "test",
        "unittest",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SentinelAudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # no console window
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/sentinel.ico",
    version_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SentinelAudio",
)
