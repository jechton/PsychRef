# -*- mode: python ; coding: utf-8 -*-
import os
import sys

a = Analysis(
    ["src/psychref.py"],
    pathex=[],
    binaries=[],
    datas=[("src", "src")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
python_dll = os.path.join(sys.base_prefix, "python312.dll")
a.binaries += [("python312.dll", python_dll, "BINARY")]

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="psychref",
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    env={"PATH": os.path.dirname(sys.executable) + os.pathsep + os.environ["PATH"]},
)
