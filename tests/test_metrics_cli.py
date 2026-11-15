from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.paths import SYNTH
from tests.tools.run_corpus import tokens, word_errors
from transcrimoi.__main__ import main


class MetricsTests(unittest.TestCase):
    def test_normalization_is_explicit(self):
        self.assertEqual(tokens("L’été, c’est déjà 20 ans !"), ["l'été", "c'est", "déjà", "20", "ans"])

    def test_edit_distance(self):
        self.assertEqual(word_errors(["oui", "alors"], ["oui", "donc"]), 1)
        self.assertEqual(word_errors(["oui"], []), 1)
        self.assertEqual(word_errors([], ["oui"]), 1)


class CliTests(unittest.TestCase):
    def test_validate_small_srt_without_private_corpus(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "test.srt"
            path.write_text("1\n00:00:00,000 --> 00:00:01,000\nSpeaker 0: Bonjour.\n", encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(main(["validate-srt", str(path)]), 0)
            self.assertIn('"blocks": 1', out.getvalue())

    @unittest.skipUnless((SYNTH / "srt/4Etudiants.srt").is_file(),
                         "Corpus utilisateur non distribué")
    def test_validate_reference_srt(self):
        path = SYNTH / "srt/4Etudiants.srt"
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(main(["validate-srt", str(path)]), 0)
        self.assertIn('"blocks": 62', out.getvalue())

    def test_verify_backend_forces_model_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = io.StringIO()
            with patch("transcrimoi.__main__.Backend.verified") as verified, redirect_stdout(out):
                code = main(["verify-backend", "--project-root", tmp])
            self.assertEqual(code, 0)
            verified.assert_called_once_with(Path(tmp).resolve(), force_models=True)
            self.assertIn("SHA-256", out.getvalue())

    def test_verify_backend_reports_corruption(self):
        with patch("transcrimoi.__main__.Backend.verified", side_effect=ValueError("Modèle corrompu")):
            with redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(["verify-backend"]), 1)
            self.assertIn("corrompu", err.getvalue())

    def test_transcription_reports_omitted_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            output, work = Path(tmp) / "out.srt", Path(tmp) / "work"
            out = io.StringIO()
            with patch("transcrimoi.__main__.Backend.verified"), patch("transcrimoi.__main__.Job") as job:
                job.return_value.run.return_value = {"cues": [], "unknown_words": 0, "omitted_token_count": 2}
                with redirect_stdout(out), redirect_stderr(io.StringIO()):
                    code = main(["transcribe", "source.wav", "-o", str(output), "--work-dir", str(work)])
            self.assertEqual(code, 0)
            self.assertIn("2 marqueur(s) <unk> omis de l’export", out.getvalue())
            self.assertIn(str(work / "result.json"), out.getvalue())

    def test_export_saved_result_needs_no_backend_or_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "result.json", Path(tmp) / "result.tsv"
            source.write_text(json.dumps({"schema_version": 1, "cues": [
                {"start": .5, "end": 1, "text": "Bonjour.", "speaker": 2}]}), encoding="utf-8")
            original = source.read_bytes()
            with patch("transcrimoi.__main__.Backend.verified") as backend, patch("transcrimoi.__main__.Job") as job:
                with redirect_stdout(io.StringIO()):
                    code = main(["export", str(source), "-o", str(output), "--format", "nvivo"])
                backend.assert_not_called()
                job.assert_not_called()
            self.assertEqual(code, 0)
            self.assertEqual(output.read_text(), "0.500\tSPEAKER_02\tBonjour.\n")
            self.assertEqual(source.read_bytes(), original)

    def test_export_saved_result_refuses_overwrite_and_invalid_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp) / "result.json", Path(tmp) / "result.vtt"
            source.write_text('{"schema_version": 1, "cues": []}')
            output.write_text("corrections")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["export", str(source), "-o", str(output), "--format", "vtt"]), 1)
            self.assertEqual(output.read_text(), "corrections")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["export", str(source), "-o", str(output), "--format", "vtt", "--overwrite"]), 0)
            self.assertEqual(output.read_text(), "WEBVTT\n\n")
            source.write_text('{"schema_version": 1, "cues": [{}]}')
            missing = Path(tmp) / "invalid.txt"
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["export", str(source), "-o", str(missing), "--format", "txt"]), 1)
            self.assertFalse(missing.exists())

    def test_transcribe_rejects_wrong_format_extension_before_backend_loading(self):
        with patch("transcrimoi.__main__.Backend.verified") as backend, redirect_stderr(io.StringIO()):
            self.assertEqual(main(["transcribe", "absent.wav", "-o", "out.srt", "--work-dir", "work", "--format", "vtt"]), 1)
            backend.assert_not_called()

    def test_existing_output_refused_before_backend_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing.srt"
            output.write_text("corrections")
            with redirect_stderr(io.StringIO()):
                code = main(["transcribe", "absent.wav", "-o", str(output), "--work-dir", str(Path(tmp) / "work")])
            self.assertEqual(code, 1)
            self.assertEqual(output.read_text(), "corrections")
