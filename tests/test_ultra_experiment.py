from pathlib import Path
import tempfile
import unittest
import wave

from tests.tools.compare_ultra import extract_wave, markdown


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "source.wav"
        self.pcm = b"\x01\x00\x02\x00" * 8000
        with wave.open(str(self.source), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(self.pcm)

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_samples_without_padding(self):
        output = self.root / "exact.wav"
        duration = extract_wave(self.source, output, .1, .4, 0)
        self.assertAlmostEqual(duration, .3)
        with wave.open(str(output), "rb") as audio:
            self.assertEqual(audio.getnframes(), 4800)
            self.assertEqual(audio.readframes(4800), self.pcm[3200:12800])

    def test_padding_adds_4000_samples_on_each_side(self):
        output = self.root / "padded.wav"
        duration = extract_wave(self.source, output, .1, .4, 250)
        self.assertAlmostEqual(duration, .8)
        with wave.open(str(output), "rb") as audio:
            self.assertEqual(audio.getnframes(), 12800)
            self.assertEqual(audio.readframes(12800), b"\0\0" * 4000 + self.pcm[3200:12800] + b"\0\0" * 4000)

    def test_existing_extraction_is_not_overwritten(self):
        output = self.root / "existing.wav"
        output.write_bytes(b"precieux")
        with self.assertRaises(FileExistsError):
            extract_wave(self.source, output, 0, .5, 250)
        self.assertEqual(output.read_bytes(), b"precieux")

    def test_invalid_intervals_and_padding(self):
        for start, end, padding in [(-1, .5, 0), (.5, .1, 0), (0, 2, 0),
                                    (float("nan"), .5, 0), (True, .5, 0),
                                    (0, .5, -1), (0, .5, 0.25), (0, .000001, 0)]:
            with self.subTest(start=start, end=end, padding=padding), self.assertRaises(ValueError):
                extract_wave(self.source, self.root / "invalid.wav", start, end, padding)

    def test_stereo_is_rejected(self):
        with wave.open(str(self.source), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(self.pcm)
        with self.assertRaises(ValueError):
            extract_wave(self.source, self.root / "stereo.wav", 0, .1, 250)


class ReportTests(unittest.TestCase):
    def test_markdown_contains_both_factors_and_escapes_text(self):
        text = markdown({"results": [{"cut_index": 0, "start": .2, "model": "ultra-f16",
                                     "padding_ms_each_side": 250, "seconds": 2, "word_count": 3,
                                     "text": "Bonjour | oui\nVoilà"}]})
        self.assertIn("ultra-f16 | 250", text)
        self.assertIn("Bonjour \\| oui Voilà", text)
        self.assertIn("sans référence humaine", text)
