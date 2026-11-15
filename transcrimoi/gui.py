"""Fenêtre Qt portable ; le noyau ne dépend pas de ce module."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import os
from pathlib import Path
import shutil
import sys
import threading
import time

from PySide6.QtCore import QStandardPaths, QThread, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QCloseEvent, QDesktopServices, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from . import __version__
from .assignment import OMITTED_ASR_TOKENS, Segmentation
from .backend import Backend
from .exports import DEFAULT_FORMAT, FORMATS, get_format, validate_output
from .job import Job
from .process import Cancelled
from .runtime import project_root
from .storage import fingerprint, sha256_file

PHASES = {
    "backend_verification": "Vérification du moteur et des modèles",
    "verification": "Vérification du média",
    "audio": "Préparation de l’audio",
    "asr": "Transcription",
    "diarization": "Distinction des locuteurs",
    "assignment": "Attribution des paroles",
    "export": "Enregistrement du document",
}
MEDIA_FILTER = "Audio et vidéo (*.wav *.mp3 *.m4a *.flac *.mp4 *.mkv *.ogg *.opus *.webm *.mov);;Tous les fichiers (*)"


def available_output(proposed: Path, source: Path | None = None) -> Path:
    """Ne jamais proposer de remplacer un résultat existant ni la source."""
    candidate = proposed
    number = 2
    while candidate.exists() or (source is not None and candidate.resolve() == source.resolve()):
        candidate = proposed.with_name(f"{proposed.stem} ({number}){proposed.suffix}")
        number += 1
    return candidate


def suggested_output(source: Path, format_id: str = DEFAULT_FORMAT) -> Path:
    return available_output(source.with_suffix(get_format(format_id).suffix), source)


def validate_paths(source_text: str, output_text: str, format_id: str = DEFAULT_FORMAT) -> tuple[Path, Path]:
    if not source_text.strip() or not output_text.strip():
        raise ValueError("Choisissez un média et une destination.")
    source = Path(source_text).expanduser().resolve()
    output = Path(output_text).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"Média absent : {source}")
    validate_output(source, output, format_id)
    if output.exists():
        raise FileExistsError("Ce document existe déjà. Choisissez un autre nom pour préserver les corrections.")
    return source, output


def find_ffmpeg(root: Path) -> Path:
    bundled = root / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    path = str(bundled) if bundled.is_file() else shutil.which("ffmpeg")
    if not path:
        raise FileNotFoundError("FFmpeg introuvable. Préparez le moteur avant de transcrire.")
    return Path(path).resolve()


class TranscriptionWorker(QThread):
    event = Signal(dict)
    outcome = Signal(dict)

    def __init__(self, root: Path, cache: Path, source: Path, output: Path, parent=None,
                 *, output_format: str = DEFAULT_FORMAT):
        super().__init__(parent)
        self.root, self.cache, self.source, self.output = root, cache, source, output
        self.output_format = output_format
        self.cancel = threading.Event()

    def run(self) -> None:
        work = None
        try:
            self.event.emit({"phase": "backend_verification", "status": "started"})
            backend = Backend.verified(self.root)
            if self.cancel.is_set():
                raise Cancelled("Traitement annulé")
            ffmpeg = find_ffmpeg(self.root)
            threads = min(4, os.cpu_count() or 1)
            # Identité de reprise indépendante du nom et du format de sortie. Le noyau revérifie
            # lui-même toutes les empreintes et refuse toute reprise incompatible.
            identity = {
                "application": __version__, "source": str(self.source),
                "source_sha256": sha256_file(self.source), "backend": backend.provenance,
                "ffmpeg_sha256": sha256_file(ffmpeg), "threads": threads,
                "segmentation": asdict(Segmentation()),
                "omitted_asr_tokens": sorted(OMITTED_ASR_TOKENS),
            }
            if self.cancel.is_set():
                raise Cancelled("Traitement annulé")
            work = self.cache / fingerprint(identity)
            self.event.emit({"phase": "verification", "status": "started", "work": str(work)})
            result = Job(backend, threads=threads, event=self.event.emit,
                         cancel=self.cancel, ffmpeg=ffmpeg).run(
                             self.source, self.output, work, output_format=self.output_format)
            outcome = {"status": "completed", "output": str(self.output), "output_format": self.output_format,
                       "cues": len(result["cues"]), "unknown_words": result["unknown_words"],
                       "omitted_token_count": result["omitted_token_count"]}
        except Cancelled:
            outcome = {"status": "cancelled"}
        except Exception as error:
            outcome = {"status": "failed", "message": str(error)}
        if work is not None:
            outcome["work"] = str(work)
        self.outcome.emit(outcome)


class MainWindow(QMainWindow):
    transcription_finished = Signal(dict)

    def __init__(self, root: Path, cache: Path | None = None):
        super().__init__()
        self.root = root.resolve()
        self.cache = cache if cache is not None else Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "work"
        self.worker: TranscriptionWorker | None = None
        self._outcome: dict = {}
        self._close_when_done = False
        self._started = 0.0
        self._result: Path | None = None
        self._work: Path | None = None
        self._suggested_source: Path | None = None
        self._error = ""
        self.setWindowTitle("Transcrimoi")
        self.resize(740, 470)
        self.setAcceptDrops(True)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)
        title = QLabel("Transcrimoi")
        font = title.font()
        font.setPointSize(22)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)
        self.subtitle = QLabel("Audio ou vidéo → transcription au format de votre choix\n"
                               "Conception TIPS-IA pour fonctionner sur des ordinateurs modestes")
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)
        self.repository_link = QLabel(
            '<a href="https://github.com/PUD-GA/transcrimoi">github.com/PUD-GA/transcrimoi</a>')
        self.repository_link.setAccessibleName("Dépôt du projet transcrimoi")
        self.repository_link.setOpenExternalLinks(True)
        layout.addWidget(self.repository_link)

        self.source_edit = QLineEdit()
        self.source_edit.setPlaceholderText("Choisissez ou déposez un fichier audio ou vidéo")
        self.source_button = QPushButton("Choisir…")
        self.output_edit = QLineEdit()
        self.output_edit.setPlaceholderText("Destination du document")
        self.output_button = QPushButton("Enregistrer sous…")
        self.format_combo = QComboBox()
        self.format_combo.setAccessibleName("Format de sortie")
        self.format_combo.setToolTip("Sans locuteur : sans étiquette dans le fichier, même pipeline.\n"
                                     "Les choix tabulés sont des exports texte, pas des fichiers de projet.")
        for item in FORMATS:
            self.format_combo.addItem(item.label, item.id)
        for label, field, button in (("Média", self.source_edit, self.source_button),
                                     ("Destination", self.output_edit, self.output_button)):
            if field is self.output_edit:
                layout.addWidget(QLabel("Format de sortie"))
                layout.addWidget(self.format_combo)
            layout.addWidget(QLabel(label))
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(button)
            layout.addLayout(row)
        self.source_edit.setAccessibleName("Média source")
        self.output_edit.setAccessibleName("Destination du document")
        self.source_button.clicked.connect(self.choose_source)
        self.output_button.clicked.connect(self.choose_output)
        self.source_edit.editingFinished.connect(self.suggest_destination)
        self.source_edit.textChanged.connect(self._invalidate_result)
        self.output_edit.textChanged.connect(self._invalidate_result)
        self.format_combo.currentIndexChanged.connect(self.change_format)

        actions = QHBoxLayout()
        self.start_button = QPushButton("Transcrire")
        self.start_button.setDefault(True)
        self.cancel_button = QPushButton("Annuler")
        self.cancel_button.setEnabled(False)
        actions.addWidget(self.start_button)
        actions.addWidget(self.cancel_button)
        actions.addStretch()
        self.elapsed = QLabel("")
        actions.addWidget(self.elapsed)
        layout.addLayout(actions)
        self.start_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status = QLabel("Prêt. Choisissez le format de restitution.")
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        links = QHBoxLayout()
        self.result_button = QPushButton("Ouvrir le dossier du résultat")
        self.result_button.setEnabled(False)
        self.logs_button = QPushButton("Ouvrir les journaux")
        self.logs_button.setEnabled(False)
        links.addWidget(self.result_button)
        links.addWidget(self.logs_button)
        self.details_button = QPushButton("Détails de l’erreur")
        self.details_button.setVisible(False)
        self.details_button.clicked.connect(self.show_error)
        links.addWidget(self.details_button)
        links.addStretch()
        layout.addLayout(links)
        self.result_button.clicked.connect(self.open_result)
        self.logs_button.clicked.connect(self.open_logs)
        self.setCentralWidget(container)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_elapsed)

    @property
    def output_format(self) -> str:
        return self.format_combo.currentData()

    def change_format(self) -> None:
        self._invalidate_result()
        text = self.output_edit.text().strip()
        if text:
            try:
                path = Path(text).expanduser()
                item = get_format(self.output_format)
                if path.suffix.lower() not in item.suffixes:
                    path = path.with_suffix(item.suffix)
                source = Path(self.source_edit.text()).expanduser() if self.source_edit.text().strip() else None
                self.output_edit.setText(str(available_output(path, source)))
            except (OSError, ValueError) as error:
                self.set_error(str(error))
        else:
            self._suggested_source = None
            self.suggest_destination()

    def _invalidate_result(self) -> None:
        self._result = None
        self.result_button.setEnabled(False)

    def set_source(self, source: Path) -> None:
        if self.worker is None:
            self.source_edit.setText(str(source))
            self._suggested_source = None
            self.suggest_destination()

    def suggest_destination(self) -> None:
        source = Path(self.source_edit.text()).expanduser()
        if source.is_file() and source != self._suggested_source:
            self.output_edit.setText(str(suggested_output(source, self.output_format)))
            self._suggested_source = source

    def choose_source(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Choisir un média", "", MEDIA_FILTER)
        if filename:
            self.set_source(Path(filename))

    def choose_output(self) -> None:
        item = get_format(self.output_format)
        filename, _ = QFileDialog.getSaveFileName(
            self, "Destination du document", self.output_edit.text(), item.file_filter)
        if filename:
            path = Path(filename)
            if not path.suffix:
                path = path.with_suffix(item.suffix)
            self.output_edit.setText(str(path))

    def start(self) -> None:
        if self.worker is not None:
            return
        try:
            source, output = validate_paths(self.source_edit.text(), self.output_edit.text(), self.output_format)
        except (OSError, ValueError) as error:
            self.set_error(str(error))
            return
        self._error = ""
        self.details_button.setVisible(False)
        self._invalidate_result()
        self._work = None
        self.logs_button.setEnabled(False)
        self._outcome = {}
        self._set_busy(True)
        self.status.setText("Vérification du moteur et des modèles…")
        self._started = time.monotonic()
        self.update_elapsed()
        self.timer.start()
        self.worker = TranscriptionWorker(self.root, self.cache, source, output, self,
                                          output_format=self.output_format)
        self.worker.event.connect(self.on_event)
        self.worker.outcome.connect(self._remember_outcome)
        self.worker.finished.connect(self._finished)
        self.worker.start()

    def _set_busy(self, busy: bool) -> None:
        for control in (self.source_edit, self.output_edit, self.source_button,
                        self.output_button, self.start_button, self.format_combo):
            control.setEnabled(not busy)
        self.cancel_button.setEnabled(busy)
        self.progress.setRange(0, 0 if busy else 1)
        if not busy:
            self.progress.setValue(0)

    def on_event(self, event: dict) -> None:
        if "work" in event:
            self._work = Path(event["work"])
        if self.worker is not None and self.worker.cancel.is_set():
            return
        phase = PHASES.get(event.get("phase"))
        if phase:
            suffix = " — étape réutilisée" if event.get("status") == "reused" else "…"
            self.status.setText(phase + suffix)

    def update_elapsed(self) -> None:
        seconds = int(time.monotonic() - self._started)
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        self.elapsed.setText(f"{hours:02}:{minutes:02}:{seconds:02}")

    def cancel(self) -> None:
        if self.worker is not None:
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.status.setText("Annulation en cours… Les étapes validées seront conservées.")

    def _remember_outcome(self, outcome: dict) -> None:
        self._outcome = outcome

    def _finished(self) -> None:
        worker = self.worker
        self.worker = None
        if worker is not None:
            worker.deleteLater()
        self.timer.stop()
        self.update_elapsed()
        self._set_busy(False)
        outcome = self._outcome
        if outcome.get("work"):
            self._work = Path(outcome["work"])
        self.logs_button.setEnabled(self._work is not None and self._work.is_dir())
        if outcome.get("status") == "completed":
            self._result = Path(outcome["output"])
            self.result_button.setEnabled(True)
            self.progress.setValue(1)
            if outcome["cues"]:
                message = f"Terminé : {outcome['cues']} segments. "
                if outcome.get("output_format", DEFAULT_FORMAT) == DEFAULT_FORMAT:
                    message += "SRT à importer dans SonalPi2."
                else:
                    message += f"Export {outcome['output_format']} enregistré."
                if outcome["unknown_words"]:
                    message += f" {outcome['unknown_words']} mots sans locuteur."
            elif outcome.get("omitted_token_count", 0):
                message = "Aucun texte exportable après filtrage : aucun segment produit."
            else:
                message = "Aucune parole détectée : aucun segment produit."
            if outcome.get("omitted_token_count", 0):
                message += f" {outcome['omitted_token_count']} marqueur(s) <unk> omis de l’export ; détails dans les journaux."
            self.status.setText(message)
        elif outcome.get("status") == "cancelled":
            self.status.setText("Traitement annulé. Relancez pour reprendre les étapes validées.")
        else:
            self.set_error(outcome.get("message", "Le traitement n’a pas abouti."))
        self.transcription_finished.emit(outcome)
        if self._close_when_done:
            self.close()

    def set_error(self, message: str) -> None:
        self._error = message
        summary = message.splitlines()[0] if message else "Le traitement n’a pas abouti."
        self.status.setText("Erreur : " + (summary[:157] + "…" if len(summary) > 160 else summary))
        self.details_button.setVisible(True)

    def show_error(self) -> None:
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Détails de l’erreur")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText("Impossible de terminer la transcription.")
        dialog.setDetailedText(self._error)
        dialog.exec()

    def _open_directory(self, path: Path | None) -> None:
        if path is not None and not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
            self.status.setText(f"Impossible d’ouvrir le dossier : {path}")

    def open_result(self) -> None:
        if self._result is not None:
            self._open_directory(self._result.parent)

    def open_logs(self) -> None:
        self._open_directory(self._work)

    @staticmethod
    def _dropped_file(event) -> Path | None:
        urls = event.mimeData().urls()
        if len(urls) == 1 and urls[0].isLocalFile():
            path = Path(urls[0].toLocalFile())
            if path.is_file():
                return path
        return None

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.worker is None and self._dropped_file(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if self.worker is None and (path := self._dropped_file(event)) is not None:
            self.set_source(path)
            event.acceptProposedAction()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.worker is None:
            event.accept()
            return
        if not self._close_when_done:
            answer = QMessageBox.question(
                self, "Traitement en cours", "Annuler le traitement et fermer la fenêtre ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if answer == QMessageBox.StandardButton.Yes:
                self._close_when_done = True
                self.cancel()
        # Attendre la fin du thread et des processus enfants, sans bloquer Qt.
        event.ignore()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interface locale transcrimoi — Fluid Speech Pro CPU")
    parser.add_argument("--project-root", type=Path, default=project_root(),
                        help="Dossier contenant backend.lock.json, build/ et models/")
    args = parser.parse_args(argv)
    app = QApplication.instance() or QApplication([sys.argv[0]])
    app.setApplicationName("Transcrimoi")
    app.setApplicationDisplayName("Transcrimoi")
    app.setOrganizationName("transcrimoi")
    window = MainWindow(args.project_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
