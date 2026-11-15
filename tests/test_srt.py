from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from tests.paths import FIXTURES, ROOT, SYNTH
from transcrimoi.schema import Cue
from transcrimoi.srt import export_srt, milliseconds, parse_srt, render_srt, timestamp
from transcrimoi.storage import sha256_file

class CorpusTests(unittest.TestCase):
    @unittest.skipUnless((SYNTH / "audio/1Coordinatrice.mp3").is_file(),
                         "Corpus utilisateur non distribué")
    def test_reference_corpus(self):
        manifest = json.loads((FIXTURES / "corpus_manifest.json").read_text())
        self.assertEqual(len(manifest["pairs"]), 4)
        for item in manifest["pairs"]:
            with self.subTest(file=item["srt"]):
                path = ROOT / item["srt"]
                self.assertEqual(sha256_file(path), item["srt_sha256"])
                self.assertEqual(sha256_file(ROOT / item["audio"]), item["audio_sha256"])
                cues = parse_srt(path.read_text(encoding="utf-8-sig"))
                self.assertEqual(len(cues), item["blocks"])
                self.assertEqual(sorted({c.speaker for c in cues}), item["speakers"])
                self.assertEqual(parse_srt(render_srt(cues)), cues)
                self.assertTrue(all(c.end <= item["duration_seconds"] for c in cues))


class SrtTests(unittest.TestCase):
    def setUp(self):
        self.cue = Cue(0.7, 2.46, "Oui, c’est déjà l’été !", 0)

    def test_exact_convention(self):
        self.assertEqual(render_srt([self.cue]),
                         "1\n00:00:00,700 --> 00:00:02,460\nSpeaker 0: Oui, c’est déjà l’été !\n")

    def test_bom_crlf(self):
        text = "\ufeff" + render_srt([self.cue]).replace("\n", "\r\n")
        self.assertEqual(parse_srt(text), [self.cue])

    def test_multiline(self):
        cue = replace(self.cue, text="Première ligne\nDeuxième ligne")
        self.assertEqual(parse_srt(render_srt([cue])), [cue])

    def test_overlap_is_not_shifted(self):
        cues = [self.cue, Cue(1.0, 2.0, "Une interruption.", 1)]
        self.assertEqual(parse_srt(render_srt(cues)), cues)

    def test_unknown_is_not_a_fictitious_speaker(self):
        cue = replace(self.cue, speaker=None)
        text = render_srt([cue])
        self.assertNotIn("Speaker", text)
        self.assertEqual(parse_srt(text), [cue])

    def test_rounding(self):
        self.assertEqual(milliseconds(1.2345), 1235)
        self.assertEqual(timestamp(milliseconds(360_000.001)), "100:00:00,001")
        self.assertEqual(timestamp(milliseconds(3599.9995)), "01:00:00,000")

    def test_empty_result(self):
        self.assertEqual(render_srt([]), "")
        self.assertEqual(parse_srt(""), [])

    def test_invalid_cues(self):
        cases = [replace(self.cue, start=-0.1), replace(self.cue, end=0.7),
                 replace(self.cue, start=float("nan")), replace(self.cue, end=float("inf")),
                 replace(self.cue, text=""), replace(self.cue, text="a\n\nb"),
                 replace(self.cue, text="a\n \t\nb"),
                 replace(self.cue, speaker=-1), replace(self.cue, speaker=True),
                 replace(self.cue, start=1.0001, end=1.0002)]
        for cue in cases:
            with self.subTest(cue=cue), self.assertRaises(ValueError):
                render_srt([cue])

    def test_invalid_srt(self):
        for text in ["2\n00:00:00,000 --> 00:00:01,000\na",
                     "1\n00:00:61,000 --> 00:00:62,000\na",
                     "1\n00:00:00.000 --> 00:00:01.000\na"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_srt(text)

    def test_unordered(self):
        with self.assertRaises(ValueError):
            render_srt([self.cue, Cue(0, 1, "Avant", 1)])

    def test_atomic_refusal_and_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "résultat.srt"
            path.write_text("Correction précieuse", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export_srt(path, [self.cue])
            self.assertEqual(path.read_text(), "Correction précieuse")
            self.assertEqual(list(Path(tmp).glob("*.part")), [])
            export_srt(path, [self.cue], overwrite=True)
            self.assertEqual(parse_srt(path.read_text()), [self.cue])
