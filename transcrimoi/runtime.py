"""Emplacements du runtime développeur et de l'application gelée."""
from __future__ import annotations

import os
from pathlib import Path
import sys


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[1]


def model_cache_directory() -> Path | None:
    """Ne jamais écrire de caches dans une application gelée/signée."""
    if not getattr(sys, "frozen", False):
        return None
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library/Caches"
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "transcrimoi/model-verification"
