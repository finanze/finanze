# -*- mode: python ; coding: utf-8 -*-
import platform
from PyInstaller.utils.hooks import (
    collect_submodules,
    collect_data_files,
    collect_dynamic_libs,
)
from PyInstaller.building.build_main import Analysis, PYZ, EXE

numpy_submodules = collect_submodules("numpy")
numpy_datas = collect_data_files("numpy")
numpy_binaries = collect_dynamic_libs("numpy")

a = Analysis(
    ['finanze/__main__.py'],
    pathex=[],
    binaries=numpy_binaries,
    datas=numpy_datas,
    hiddenimports=numpy_submodules,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['speech_recognition', 'pydub', 'aiohttp', 'selenium', 'seleniumwire', 'playwright'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

if (platform_name := platform.system().lower()) == 'darwin':
    platform_name = f"macos-{'arm64' if platform.machine() == 'arm64' else 'x64'}"

exec_name = 'finanze-server-{}'.format(platform_name)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=exec_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
