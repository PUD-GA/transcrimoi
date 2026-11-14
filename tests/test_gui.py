"""Tests de fenêtre avec vrais threads/processus et FFmpeg, inférence simulée."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import wave

HAS_QT = importlib.util.find_spec("PySide6") is not None
if HAS_QT:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QCoreApplication, QEvent, QMimeData, QUrl, Qt
    from PySide6.QtGui import QCloseEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from transcrimoi.gui import MainWindow, suggested_output, validate_paths


class FakeBackend:
    """Pas un modèle : sortie stable pour tester uniquement l'intégration UI."""
    provenance = {"test_only": "gui"}
    mode = "normal"

    def asr_command(self, audio, threads):
        if self.mode == "slow":
            return [sys.executable, "-c", "import time; time.sleep(60)"]
        if self.mode == "failure":
            return [sys.executable, "-c", "import sys; sys.stderr.write('échec simulé'); sys.exit(2)"]
        words = [] if self.mode in ("silence", "all_unknown") else [{"w": "Bonjour.", "start": 0, "end": .4}]
        text = "Bonjour." if words else ""
        if self.mode in ("unknown", "all_unknown"):
            words.append({"w": "<unk>", "start": .6, "end": .8})
        result = {"text": text, "words": words}
        return [sys.executable, "-c", f"print({json.dumps(result)!r})"]

    def diarization_command(self, audio):
        return [sys.executable, "-c", 'print(\'{"speakers":8,"segments":[{"speaker":0,"start":0,"end":1}]}\')']


@unittest.skipUnless(HAS_QT and shutil.which("ffmpeg"), "Installer .[gui] et FFmpeg")
class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setApplicationName("transcrimoi-tests")
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="interface été ")
        self.root = Path(self.temp.name)
        self.source = self.root / "entretien été.wav"
        with wave.open(str(self.source), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\0\0" * 16000)
        self.backend = FakeBackend()
        self.loader = patch("transcrimoi.gui.Backend.verified", return_value=self.backend)
        self.loader.start()
        self.window = MainWindow(self.root, self.root / "work")
        self.window.show()
        self.outcomes = []
        self.window.transcription_finished.connect(self.outcomes.append)
        self.window.set_source(self.source)

    def tearDown(self):
        if self.window.worker is not None:
            self.window.cancel()
            self.wait_for(lambda: self.window.worker is None)
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        self.app.processEvents()
        self.loader.stop()
        self.temp.cleanup()

    def wait_for(self, condition, timeout=30):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(condition(), self.window.status.text())

    def start_and_wait(self):
        count = len(self.outcomes)
        QTest.mouseClick(self.window.start_button, Qt.MouseButton.LeftButton)
        self.wait_for(lambda: len(self.outcomes) > count)
        return self.outcomes[-1]

    def test_initial_state_and_suggestion(self):
        self.assertEqual(Path(self.window.output_edit.text()), self.source.with_suffix(".srt"))
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertFalse(self.window.cancel_button.isEnabled())
        self.assertFalse(self.window.result_button.isEnabled())

    def test_success_unicode_path_and_open_result(self):
        result = self.start_and_wait()
        self.assertEqual(result["status"], "completed")
        output = Path(result["output"])
        self.assertIn("Speaker 0: Bonjour.", output.read_text(encoding="utf-8"))
        self.assertTrue(self.window.result_button.isEnabled())
        self.assertTrue(self.window.logs_button.isEnabled())
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertFalse(self.window.cancel_button.isEnabled())
        self.assertIn("SonalPi2", self.window.status.text())
        with patch("transcrimoi.gui.QDesktopServices.openUrl", return_value=True) as opener:
            self.window.open_result()
            self.assertEqual(Path(opener.call_args.args[0].toLocalFile()), output.parent)

    def test_custom_destination_survives_source_losing_focus(self):
        output = self.root / "destination choisie" / "mon résultat.srt"
        self.window.output_edit.setText(str(output))
        self.window.source_edit.setFocus()
        self.app.processEvents()
        result = self.start_and_wait()
        self.assertEqual(result["status"], "completed")
        # macOS résout /var en /private/var ; Windows développe les noms courts 8.3.
        self.assertEqual(Path(result["output"]), output.resolve())
        self.assertTrue(output.is_file())
        self.assertFalse(self.source.with_suffix(".srt").exists())

    def test_custom_destination_through_directory_alias(self):
        actual = self.root / "destination réelle"
        actual.mkdir()
        alias = self.root / "alias"
        try:
            alias.symlink_to(actual.resolve(), target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f"Création de lien symbolique indisponible : {error}")
        output = alias / "résultat choisi.srt"
        self.window.output_edit.setText(str(output))
        self.window.source_edit.setFocus()
        self.app.processEvents()
        result = self.start_and_wait()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(Path(result["output"]), output.resolve())
        self.assertTrue(Path(result["output"]).samefile(output))
        self.assertTrue((actual / output.name).is_file())
        self.assertFalse(self.source.with_suffix(".srt").exists())

    def test_missing_media_rejected_before_loading_backend(self):
        self.window.source_edit.setText(str(self.root / "absent.mp3"))
        self.window.start()
        self.assertIsNone(self.window.worker)
        self.assertIn("absent", self.window.status.text())
        from transcrimoi.gui import Backend
        Backend.verified.assert_not_called()

    def test_existing_output_never_overwritten(self):
        output = self.source.with_suffix(".srt")
        output.write_text("corrigé", encoding="utf-8")
        self.window.start()
        self.assertIsNone(self.window.worker)
        self.assertEqual(output.read_text(encoding="utf-8"), "corrigé")
        self.assertIn("existe déjà", self.window.status.text())

    def test_output_collision_after_start_is_protected(self):
        output = self.source.with_suffix(".srt")
        def collide(event):
            if event.get("phase") == "asr":
                output.write_text("correction concurrente", encoding="utf-8")
        self.window.on_event = collide
        result = self.start_and_wait()
        self.assertEqual(result["status"], "failed")
        self.assertEqual(output.read_text(encoding="utf-8"), "correction concurrente")

    def test_suggested_output_preserves_all_existing_files(self):
        first = self.source.with_suffix(".srt")
        first.touch()
        second = self.source.with_name(self.source.stem + " (2).srt")
        second.touch()
        self.assertEqual(suggested_output(self.source).name, self.source.stem + " (3).srt")

    def test_path_validation(self):
        for source, output in [("", ""), (str(self.source), str(self.source)),
                               (str(self.source), str(self.root / "out.txt"))]:
            with self.subTest(source=source, output=output), self.assertRaises(ValueError):
                validate_paths(source, output)

    def test_backend_error_restores_controls(self):
        with patch("transcrimoi.gui.Backend.verified", side_effect=ValueError("Modèle corrompu")):
            result = self.start_and_wait()
        self.assertEqual(result["status"], "failed")
        self.assertIn("Modèle corrompu", self.window.status.text())
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertFalse(self.window.result_button.isEnabled())

    def test_long_error_keeps_full_details_without_expanding_status(self):
        message = "Erreur simulée : " + "chemin/" * 100 + "\nDiagnostic complet"
        self.window.set_error(message)
        self.assertLess(len(self.window.status.text()), 180)
        self.assertEqual(self.window._error, message)
        self.assertTrue(self.window.details_button.isVisible())

    def test_native_error_exposes_logs(self):
        self.backend.mode = "failure"
        result = self.start_and_wait()
        self.assertEqual(result["status"], "failed")
        self.assertIn("Journal", self.window.status.text())
        self.assertTrue(self.window.logs_button.isEnabled())
        self.assertFalse(self.source.with_suffix(".srt").exists())

    def test_no_speech_is_explicit(self):
        self.backend.mode = "silence"
        result = self.start_and_wait()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["cues"], 0)
        self.assertIn("Aucune parole", self.window.status.text())
        self.assertEqual(Path(result["output"]).read_bytes(), b"")

    def test_unknown_omissions_are_reported_without_exporting_marker(self):
        self.backend.mode = "unknown"
        result = self.start_and_wait()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["omitted_token_count"], 1)
        self.assertIn("1 marqueur(s) <unk> omis", self.window.status.text())
        self.assertNotIn("<unk>", Path(result["output"]).read_text())
        self.assertTrue(self.window.logs_button.isEnabled())

    def test_all_unknown_is_not_misrepresented_as_no_speech(self):
        self.backend.mode = "all_unknown"
        result = self.start_and_wait()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["cues"], 0)
        self.assertEqual(result["omitted_token_count"], 1)
        self.assertIn("Aucun texte exportable après filtrage", self.window.status.text())
        self.assertNotIn("Aucune parole détectée", self.window.status.text())
        self.assertIn("<unk> omis", self.window.status.text())

    def test_cancellation_and_resume_with_validated_audio(self):
        self.backend.mode = "slow"
        self.window.start()
        self.assertFalse(self.window.source_edit.isEnabled())
        self.assertFalse(self.window.start_button.isEnabled())
        # Ne pas annuler avant le démarrage de la phase ASR.
        self.wait_for(lambda: self.window.status.text().startswith("Transcription"))
        original_worker = self.window.worker
        self.window.start()  # Un second clic ne lance pas une deuxième tâche.
        self.assertIs(self.window.worker, original_worker)
        QTest.mouseClick(self.window.cancel_button, Qt.MouseButton.LeftButton)
        self.wait_for(lambda: self.window.worker is None)
        self.assertEqual(self.outcomes[-1]["status"], "cancelled")
        work = Path(self.outcomes[-1]["work"])
        state = json.loads((work / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(set(state["completed"]), {"audio"})
        self.assertFalse(self.source.with_suffix(".srt").exists())
        self.backend.mode = "normal"
        events = []
        original = self.window.on_event
        def record(event):
            events.append(event)
            original(event)
        self.window.on_event = record
        result = self.start_and_wait()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["work"], str(work))
        self.assertIn("audio", [e["phase"] for e in events if e.get("status") == "reused"])

    def test_changed_destination_does_not_invalidate_checkpoints(self):
        first = self.start_and_wait()
        self.window.output_edit.setText(str(self.root / "autre.srt"))
        self.assertFalse(self.window.result_button.isEnabled())
        second = self.start_and_wait()
        self.assertEqual(first["work"], second["work"])
        self.assertEqual(Path(first["output"]).read_bytes(), Path(second["output"]).read_bytes())

    def test_close_refused_then_cancelled_without_destroying_running_thread(self):
        self.backend.mode = "slow"
        self.window.start()
        self.wait_for(lambda: self.window.status.text().startswith("Transcription"))
        with patch("transcrimoi.gui.QMessageBox.question", return_value=QMessageBox.StandardButton.No):
            event = QCloseEvent()
            self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertFalse(self.window.worker.cancel.is_set())
        with patch("transcrimoi.gui.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
            event = QCloseEvent()
            self.window.closeEvent(event)
            self.assertFalse(event.isAccepted())
        self.wait_for(lambda: self.window.worker is None)
        self.assertFalse(self.window.isVisible())
        self.assertEqual(self.outcomes[-1]["status"], "cancelled")

    def test_only_one_local_file_is_accepted_for_drop(self):
        class Drop:
            def __init__(self, urls):
                self.data = QMimeData()
                self.data.setUrls(urls)
            def mimeData(self):
                return self.data
        one = QUrl.fromLocalFile(str(self.source))
        self.assertEqual(self.window._dropped_file(Drop([one])), self.source)
        self.assertIsNone(self.window._dropped_file(Drop([one, one])))
        self.assertIsNone(self.window._dropped_file(Drop([QUrl("https://example.org/a.mp3")])))
