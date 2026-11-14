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
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="transcrimoi",
          console=False, strip=False, upx=False)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="transcrimoi")
if sys.platform == "darwin":
    bundle = BUNDLE(collection, name="transcrimoi.app", bundle_identifier="org.transcrimoi.desktop",
                    info_plist={"NSHighResolutionCapable": True})
