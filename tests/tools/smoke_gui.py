#!/usr/bin/env python3
"""Essai bout-en-bout de la fenêtre avec le vrai backend du produit (sans Photon)."""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Sans cette option : trois secondes de silence synthétique")
    parser.add_argument("--output-dir", required=True, type=Path, help="Nouveau dossier pour rapport, SRT et captures")
    parser.add_argument("--project-root", default=ROOT, type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--preview-only", action="store_true", help="Afficher/capturer la fenêtre sans inférence")
    args = parser.parse_args()
    directory = args.output_dir.resolve()
    directory.mkdir(parents=True, exist_ok=False)

    from PySide6.QtCore import QTimer, Qt, qVersion
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from transcrimoi.gui import MainWindow
    from transcrimoi.storage import read_json, write_json

    source = args.source.resolve() if args.source else directory / "silence été.wav"
    if args.source is None:
        with wave.open(str(source), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\0" * 16000 * 3)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("transcrimoi")
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow(args.project_root, directory / "work")
    window.set_source(source)
    window.output_edit.setText(str(directory / "resultat.srt"))
    window.show()
    started = time.monotonic()
    events = []
    report = {"platform": platform.platform(), "machine": platform.machine(),
              "python": platform.python_version(), "qt": qVersion(),
              "preview_only": args.preview_only, "synthetic_silence": args.source is None,
              "source": str(source), "events": events}
    timed_out = False

    def completed(outcome):
        report.update(outcome=outcome, seconds=round(time.monotonic() - started, 3))
        report["status_text"] = window.status.text()
        window.grab().save(str(directory / "completed.png"))
        write_json(directory / "report.json", report)
        valid = outcome.get("status") == "completed" and not timed_out
        if args.source is None:
            valid = valid and outcome.get("cues") == 0
        else:
            valid = valid and outcome.get("cues", 0) > 0
        app.exit(0 if valid else 1)

    window.transcription_finished.connect(completed)
    original = window.on_event
    def record(event):
        events.append(event)
        original(event)
    window.on_event = record

    def begin():
        window.grab().save(str(directory / "ready.png"))
        if args.preview_only:
            write_json(directory / "report.json", report)
            app.exit(0)
            return
        report["asr_model"] = read_json(args.project_root / "backend.lock.json")["models"]["asr"]
        QTest.mouseClick(window.start_button, Qt.MouseButton.LeftButton)
        if window.worker is None:
            completed({"status": "failed", "message": window.status.text()})

    def timeout():
        nonlocal timed_out
        timed_out = True
        window.cancel()
        if window.worker is None:
            completed({"status": "failed", "message": "Délai de test dépassé"})

    QTimer.singleShot(250, begin)
    QTimer.singleShot(args.timeout * 1000, timeout)
    code = app.exec()
    window.close()
    print(f"Rapport GUI : {directory / 'report.json'}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
