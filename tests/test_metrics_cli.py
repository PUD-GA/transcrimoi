from contextlib import redirect_stderr, redirect_stdout
import io
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
            self.assertIn("2 marqueur(s) <unk> omis du SRT", out.getvalue())
            self.assertIn(str(work / "result.json"), out.getvalue())

    def test_existing_output_refused_before_backend_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing.srt"
            output.write_text("corrections")
            with redirect_stderr(io.StringIO()):
                code = main(["transcribe", "absent.wav", "-o", str(output), "--work-dir", str(Path(tmp) / "work")])
            self.assertEqual(code, 1)
            self.assertEqual(output.read_text(), "corrections")
