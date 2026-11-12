# PyInstaller recipe for ProtoLab.exe (run build_exe.bat, or see README).
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# Version: the VERSION file (single source), bundled with the app and shown in the exe's
# Properties > Details on Windows (that version resource needs PyInstaller's Windows modules).
VERSION = Path("VERSION").read_text(encoding="utf-8").strip()
try:
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VarFileInfo, VarStruct, VSVersionInfo,
    )
except ImportError:  # not on Windows: no version resource, the build goes on
    version_info = None
else:
    _numbers = tuple(int(part) for part in VERSION.split("-")[0].split(".")) + (0,)
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=_numbers[:4], prodvers=_numbers[:4]),
        kids=[
            StringFileInfo([StringTable("040C04B0", [
                StringStruct("ProductName", "ProtoLab"),
                StringStruct("FileDescription", "ProtoLab - prototypes dynamiques pour tests utilisateurs"),
                StringStruct("ProductVersion", VERSION),
                StringStruct("FileVersion", VERSION),
                StringStruct("OriginalFilename", "ProtoLab.exe"),
            ])]),
            VarFileInfo([VarStruct("Translation", [0x040C, 1200])]),
        ],
    )

datas = [
    ("frontend/dist", "frontend_dist"),
    # Standalone player inlined into the HTML exports (backend/export_html.py).
    ("frontend/dist-player/protolab-player.js", "player"),
    ("VERSION", "."),
]
icon = os.path.join(SPECPATH, "icone", "protolab.ico")

a = Analysis(
    ["backend/launcher.py"],
    pathex=["backend"],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("uvicorn"),
    excludes=["tkinter", "matplotlib", "IPython", "pandas", "numpy", "watchfiles", "uvloop", "yaml"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ProtoLab",
    icon=icon if os.path.exists(icon) else None,
    version=version_info,
    console=True,
    upx=False,
)
