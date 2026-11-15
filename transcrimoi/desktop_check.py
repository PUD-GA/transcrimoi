"""Diagnostic du paquet autonome : Qt, FFmpeg, modèles et silence synthétique."""
from __future__ import annotations

from pathlib import Path
import platform
import sys
import wave

from . import __version__
from .backend import Backend
from .job import Job
from .runtime import project_root
from .storage import write_json


def check_desktop(directory: Path) -> None:
    from PySide6.QtWidgets import QApplication
    from .gui import MainWindow, find_ffmpeg

    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    report = {"status": "running", "application": __version__, "platform": platform.platform(),
              "machine": platform.machine(), "frozen": bool(getattr(sys, "frozen", False))}
    window = None
    try:
        root = project_root()
        ffmpeg = root / "bin" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
        if not ffmpeg.is_file():
            raise FileNotFoundError("FFmpeg doit être embarqué, pas fourni par le PATH de la machine")
        backend = Backend.verified(root)
        app = QApplication.instance() or QApplication([])
        app.setApplicationName("Transcrimoi")
        app.setApplicationDisplayName("Transcrimoi")
        app.setOrganizationName("transcrimoi")
        window = MainWindow(root, directory / "work")
        window.show()
        app.processEvents()
        if not window.grab().save(str(directory / "window.png")):
            raise RuntimeError("Capture Qt impossible")
        source = directory / "silence été.wav"
        with wave.open(str(source), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\0" * 16000 * 3)
        result = Job(backend, ffmpeg=find_ffmpeg(root)).run(source, directory / "result.srt", directory / "work")
        if result["cues"]:
            raise ValueError("Le test de silence ne doit pas produire de parole")
        report.update(status="completed", cues=0, omitted_token_count=result["omitted_token_count"],
                      native_commit=backend.provenance["build"]["native_commit"],
                      asr_model=backend.provenance["lock"]["models"]["asr"])
    except BaseException as error:
        report.update(status="failed", error=str(error))
        raise
    finally:
        write_json(directory / "report.json", report)
        if window is not None:
            window.close()
