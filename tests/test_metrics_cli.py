from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

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

    def test_existing_output_refused_before_backend_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "existing.srt"
            output.write_text("corrections")
            with redirect_stderr(io.StringIO()):
                code = main(["transcribe", "absent.wav", "-o", str(output), "--work-dir", str(Path(tmp) / "work")])
            self.assertEqual(code, 1)
            self.assertEqual(output.read_text(), "corrections")
