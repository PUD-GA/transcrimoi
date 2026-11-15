# Préversion autonome : seuls le produit, son runtime et les notices sont collectés.
import json
import os
import sys
from pathlib import Path

root = Path(SPECPATH).resolve().parent
stage = Path(os.environ["TRANSCRIMOI_PACKAGE_STAGE"])
lock = json.loads((stage / "backend.lock.json").read_text(encoding="utf-8"))
a = Analysis(
    [str(root / "scripts/desktop_entry.py")],
    pathex=[str(root)],
    binaries=[(str(path), "bin") for path in (stage / "bin").iterdir()],
    datas=[(str(stage / "backend.lock.json"), "."),
           (str(stage / "build/backend.json"), "build"),
           (str(stage / "notices"), "notices")]
          + [(str(stage / "models" / item["file"]), "models") for item in lock["models"].values()],
    excludes=["tests", "scripts", "torch", "moondream", "kestrel"],
    noarchive=False,
)
pyz = PYZ(a.pure)
executable_name = "Transcrimoi" if sys.platform == "win32" else "transcrimoi"
version_info = None
if sys.platform == "win32":
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable,
        VSVersionInfo, VarFileInfo, VarStruct,
    )

    namespace = {}
    exec((root / "transcrimoi/__init__.py").read_text(encoding="utf-8"), namespace)
    version = namespace["__version__"]
    version_parts = tuple(int(part) for part in version.split("."))
    version_tuple = (*version_parts, *([0] * (4 - len(version_parts))))[:4]
    version_info = VSVersionInfo(
        ffi=FixedFileInfo(filevers=version_tuple, prodvers=version_tuple),
        kids=[
            StringFileInfo([StringTable("040904B0", [
                StringStruct("CompanyName", "transcrimoi"),
                StringStruct("FileDescription", "Transcrimoi"),
                StringStruct("FileVersion", version),
                StringStruct("InternalName", "Transcrimoi"),
                StringStruct("OriginalFilename", "Transcrimoi.exe"),
                StringStruct("ProductName", "Transcrimoi"),
                StringStruct("ProductVersion", version),
            ])]),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name=executable_name,
          console=False, strip=False, upx=False, version=version_info)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="transcrimoi")
if sys.platform == "darwin":
    bundle = BUNDLE(collection, name="transcrimoi.app", bundle_identifier="org.transcrimoi.desktop",
                    info_plist={"NSHighResolutionCapable": True})
