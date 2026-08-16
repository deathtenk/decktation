# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
import os

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules


project_root = Path(SPECPATH)
src_root = project_root / "src"

ydotool_bin = os.environ.get("YDOTOOL_BIN")
ydotoold_bin = os.environ.get("YDOTOOLD_BIN")

binaries = []
for src, dest in [
    (ydotool_bin, "bin"),
    (ydotoold_bin, "bin"),
]:
    if src:
        binaries.append((src, dest))

datas = []
for package in ("faster_whisper", "tokenizers", "onnxruntime"):
    datas += collect_data_files(package)

binaries += collect_dynamic_libs("numpy")
binaries += collect_dynamic_libs("ctranslate2")
binaries += collect_dynamic_libs("onnxruntime")

hiddenimports = []
for package in ("faster_whisper", "ctranslate2", "tokenizers", "onnxruntime"):
    hiddenimports += collect_submodules(package)

analysis = Analysis(
    ["runtime_entry.py"],
    pathex=[str(src_root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="decktation-runtime",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    onefile=True,
)
