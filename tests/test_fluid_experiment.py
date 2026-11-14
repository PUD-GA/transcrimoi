import shutil
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

from tests.paths import EXPERIMENTS
from tests.test_process_job import FakeBackend
from tests.tools.compare_fluid import MeasuredBackend, markdown, run_case, score, summarize
from transcrimoi.storage import read_json


class FluidExperimentTests(unittest.TestCase):
    def test_candidate_and_baseline_are_frozen_and_distinct(self):
        config = read_json(EXPERIMENTS / "fluid-q8.lock.json")
        self.assertEqual(config["model_repository"], "FluidVoice-Labs/fluid-speech-pro-gguf")
        self.assertEqual(len(config["model_revision"]), 40)
        self.assertEqual(config["model"]["precision"], "Q8_0")
        self.assertEqual(config["baseline_model"]["checkpoint"], "moondream/parakeet-ultra")
        self.assertNotEqual(config["baseline_model"]["sha256"], config["model"]["sha256"])
        self.assertEqual(config["wamatipsia"]["cut_indices"], [0, 20, 100, 180])

    def test_score_uses_existing_explicit_normalization(self):
        self.assertEqual(score("L’été, oui !", "l'été oui"), {"errors": 0, "reference_words": 2, "wer": 0})
        self.assertEqual(score("oui non", "oui"), {"errors": 1, "reference_words": 2, "wer": .5})
        self.assertIsNone(score("", "oui")["wer"])

    def test_summary_is_weighted_by_reference_words_and_excludes_unreferenced_clips(self):
        def item(errors, count, memory):
            return {"model": "fluid-q8", "suite": "corpus", "srt_score": {"errors": errors, "reference_words": count},
                    "raw_score": {"errors": errors}, "asr_seconds": 2, "asr_peak_rss_kib": memory}
        results = [item(1, 2, 1024), item(1, 8, 2048),
                   {"model": "fluid-q8", "suite": "wamatipsia", "srt_score": {"wer": None}}]
        summary = summarize(results)
        self.assertEqual(summary["fluid-q8"]["srt_wer"], .2)
        self.assertEqual(summary["fluid-q8"]["corpus_cases"], 2)
        self.assertEqual(summary["fluid-q8"]["asr_peak_rss_kib"], 2048)
        self.assertIsNone(summary["ultra-f16"]["srt_wer"])

    def test_unavailable_memory_is_not_reported_as_zero(self):
        self.assertIsNone(summarize([])["fluid-q8"]["asr_peak_rss_kib"])

    def test_measurement_wraps_asr_only_and_preserves_backend_provenance(self):
        backend = Mock()
        backend.asr_command.return_value = ["parakeet-cli", "transcribe"]
        backend.diarization_command.return_value = ["diarize", "audio.wav"]
        with patch("tests.tools.compare_fluid.platform.system", return_value="Linux"), \
                patch("tests.tools.compare_fluid.Path.is_file", return_value=True):
            measured = MeasuredBackend(backend, Path("memory.txt"))
        self.assertEqual(measured.asr_command(Path("audio.wav"), 4),
                         ["/usr/bin/time", "-f", "%M", "-o", "memory.txt", "parakeet-cli", "transcribe"])
        self.assertEqual(measured.diarization_command(Path("audio.wav")), ["diarize", "audio.wav"])
        self.assertIs(measured.provenance, backend.provenance)
        backend.asr_command.assert_called_once_with(Path("audio.wav"), 4)

    def test_other_platforms_run_without_linux_measurement(self):
        backend = Mock()
        backend.asr_command.return_value = ["parakeet-cli.exe"]
        with patch("tests.tools.compare_fluid.platform.system", return_value="Windows"):
            measured = MeasuredBackend(backend, Path("memory.txt"))
        self.assertFalse(measured.measure)
        self.assertEqual(measured.asr_command(Path("audio.wav"), 4), ["parakeet-cli.exe"])

    @unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg nécessaire pour le pipeline simulé")
    def test_case_runner_with_explicit_fake_inference(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.wav"
            with wave.open(str(source), "wb") as audio:
                audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
                audio.writeframes(b"\0\0" * 16000)
            item = run_case(FakeBackend(), source, root / "result", suite="corpus", name="fake",
                            label="fluid-q8", threads=4, reference="Bonjour. Oui.")
            self.assertEqual(item["srt_score"]["wer"], 0)
            self.assertEqual(item["word_count"], 2)
            self.assertTrue(item["timestamps_structurally_valid"])
            self.assertTrue((root / "result/result.srt").is_file())
            self.assertEqual(summarize([item])["fluid-q8"]["corpus_cases"], 1)

    def test_markdown_identifies_limits_and_handles_absent_reference(self):
        report = {"results": [{"case": "cut-0", "model": "fluid-q8", "suite": "wamatipsia",
                               "asr_peak_rss_kib": None, "asr_seconds": 1, "cues": 2,
                               "srt_score": {"wer": None}, "raw_score": {"wer": None}, "text": "a|b\nc"}]}
        text = markdown(report)
        self.assertIn("précisions différents", text)
        self.assertIn("pas une référence humaine", text)
        self.assertIn("leur justesse n'est pas mesurée", text)
        self.assertIn("a\\|b c", text)
        self.assertIn("| — | — |", text)
