# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files


project_root = Path(SPECPATH).parent
package_data = collect_data_files("copyboard_extension")

a = Analysis(
    [str(project_root / "packaging" / "copyboard_entry.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=package_data,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # pyperclip probes several optional GUI toolkits. CopyBoard uses Tkinter,
    # so excluding the others avoids bundling an unused 100+ MB Qt runtime.
    excludes=["PyQt5", "PyQt6", "PySide2", "PySide6", "qtpy", "pygame"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="copyboard-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="CopyBoard",
)
