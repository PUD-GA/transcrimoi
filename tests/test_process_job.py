import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from transcrimoi.job import Job, work_lock
from transcrimoi.process import Cancelled, ProcessError, run_process
from transcrimoi.srt import parse_srt


class ProcessTests(unittest.TestCase):
    def test_unicode_output_and_path_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="essai été ") as tmp:
            out, err = Path(tmp) / "sortie.json", Path(tmp) / "erreur.log"
            run_process([sys.executable, "-c", "print('été')"], out, err)
            self.assertEqual(out.read_text().strip(), "été")

    def test_failure_does_not_publish_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, err = Path(tmp) / "out", Path(tmp) / "err"
            out.write_text("validé")
            with self.assertRaises(ProcessError):
                run_process([sys.executable, "-c", "import sys; print('partiel'); sys.exit(2)"], out, err)
            self.assertEqual(out.read_text(), "validé")
            self.assertFalse(Path(str(out) + ".part").exists())

    def test_cancellation_during_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            cancel = threading.Event()
            timer = threading.Timer(.2, cancel.set)
            timer.start()
            start = time.monotonic()
            try:
                with self.assertRaises(Cancelled):
                    run_process([sys.executable, "-c", "import time; time.sleep(60)"],
                                Path(tmp) / "out", Path(tmp) / "err", cancel)
            finally:
                timer.cancel()
            self.assertLess(time.monotonic() - start, 5)
            self.assertFalse((Path(tmp) / "out").exists())

    @unittest.skipUnless(os.name == "posix", "Test du groupe POSIX")
    def test_cancellation_kills_child_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "child.pid"
            code = ("import subprocess,sys,time; from pathlib import Path; "
                    "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                    f"Path({str(pidfile)!r}).write_text(str(p.pid)); time.sleep(60)")
            cancel = threading.Event()
            def trigger():
                for _ in range(100):
                    if pidfile.exists():
                        break
                    time.sleep(.02)
                cancel.set()
            thread = threading.Thread(target=trigger)
            thread.start()
            try:
                with self.assertRaises(Cancelled):
                    run_process([sys.executable, "-c", code], Path(tmp) / "out", Path(tmp) / "err", cancel)
                pid = int(pidfile.read_text())
                # Le signal a été envoyé, mais l'ordonnanceur peut ne pas encore
                # avoir fait passer l'orphelin à l'état mort lors de cette lecture.
                deadline = time.monotonic() + 2
                while True:
                    try:
                        if Path("/proc").is_dir():
                            if Path(f"/proc/{pid}/stat").read_text().split()[2] == "Z":
                                break  # mort, en attente de récolte
                        else:
                            os.kill(pid, 0)  # macOS : /proc n'existe pas
                    except (FileNotFoundError, ProcessLookupError):
                        break
                    if time.monotonic() >= deadline:
                        self.fail(f"Le processus enfant {pid} a survécu à l'annulation")
                    time.sleep(.01)
            finally:
                thread.join(timeout=3)


class FakeBackend:
    """Double de test explicite, jamais utilisé par la CLI ou les mesures réelles."""
    provenance = {"test_only": True}
    fail_diarization = False

    def asr_command(self, audio, threads):
        result = {"text": "Bonjour. Oui.", "words": [
            {"w": "Bonjour.", "start": 0, "end": .4}, {"w": "Oui.", "start": .6, "end": .8}]}
        return [sys.executable, "-c", f"print({json.dumps(result)!r})"]

    def diarization_command(self, audio):
        if self.fail_diarization:
            return [sys.executable, "-c", "raise SystemExit(2)"]
        result = {"segments": [{"speaker": 1, "start": 0, "end": .5},
                               {"speaker": 0, "start": .55, "end": 1}]}
        return [sys.executable, "-c", f"print({json.dumps(result)!r})"]


@unittest.skipUnless(shutil.which("ffmpeg"), "FFmpeg nécessaire pour le test de pipeline")
class JobTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="transcrimoi été ")
        self.root = Path(self.temp.name)
        self.source = self.root / "source.wav"
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                        "anullsrc=r=16000:cl=mono", "-t", "1", str(self.source)], check=True)
        self.work = self.root / "travail"
        self.output = self.root / "résultat.srt"
        self.backend = FakeBackend()
        self.events = []
        self.job = Job(self.backend, event=self.events.append)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_pipeline_and_reuse(self):
        result = self.job.run(self.source, self.output, self.work)
        self.assertEqual(result["unknown_words"], 0)
        cues = parse_srt(self.output.read_text())
        self.assertEqual([c.speaker for c in cues], [1, 0])
        self.events.clear()
        self.job.run(self.source, self.root / "autre.srt", self.work)
        self.assertEqual([e["phase"] for e in self.events if e["status"] == "reused"],
                         ["audio", "asr", "diarization"])

    def test_exact_unknown_markers_are_traced_without_modifying_native_output(self):
        raw = {"text": "Oui.", "words": [{"w": "<unk>", "start": .1, "end": .2, "conf": .5},
                                          {"w": "Oui.", "start": .6, "end": .8}]}
        command = [sys.executable, "-c", f"print({json.dumps(raw)!r})"]
        with patch.object(self.backend, "asr_command", return_value=command):
            result = self.job.run(self.source, self.output, self.work)
        original = (self.work / "asr.json").read_bytes()
        self.assertEqual(json.loads(original), raw)
        self.assertEqual(result["native_word_count"], 2)
        self.assertEqual(result["omitted_token_count"], 1)
        self.assertEqual(result["omitted_tokens"], [{"start": .1, "end": .2, "text": "<unk>",
                          "confidence": .5, "reason": "native_unknown_token"}])
        cues = parse_srt(self.output.read_text())
        self.assertEqual([(cue.text, cue.speaker) for cue in cues], [("Oui.", 0)])
        self.assertEqual(len(result["words"]), 1)
        self.assertEqual(result["unknown_words"], 0)
        self.assertEqual(self.events[-1]["omitted_token_count"], 1)
        self.events.clear()
        resumed = self.job.run(self.source, self.root / "second.srt", self.work)
        self.assertEqual(resumed["omitted_tokens"], result["omitted_tokens"])
        self.assertEqual((self.work / "asr.json").read_bytes(), original)
        self.assertEqual([e["phase"] for e in self.events if e["status"] == "reused"],
                         ["audio", "asr", "diarization"])

    def test_only_unknown_markers_produce_empty_srt_with_audit(self):
        raw = {"text": "", "words": [{"w": "<unk>", "start": .1, "end": .2}]}
        with patch.object(self.backend, "asr_command", return_value=[sys.executable, "-c", f"print({json.dumps(raw)!r})"]):
            result = self.job.run(self.source, self.output, self.work)
        self.assertEqual(result["cues"], [])
        self.assertEqual(result["omitted_token_count"], 1)
        self.assertEqual(self.output.read_bytes(), b"")
        self.assertEqual(json.loads((self.work / "result.json").read_text())["omitted_tokens"][0]["start"], .1)

    def test_filter_policy_is_part_of_checkpoint_identity(self):
        self.job.run(self.source, self.output, self.work)
        with patch("transcrimoi.job.OMITTED_ASR_TOKENS", frozenset()), self.assertRaises(ValueError):
            self.job.run(self.source, self.root / "other.srt", self.work)

    def test_failure_and_resume_completed_phases(self):
        self.backend.fail_diarization = True
        with self.assertRaises(ProcessError):
            self.job.run(self.source, self.output, self.work)
        self.assertFalse(self.output.exists())
        state = json.loads((self.work / "state.json").read_text())
        self.assertEqual(state["status"], "failed")
        self.assertEqual(set(state["completed"]), {"audio", "asr"})
        self.events.clear()
        self.backend.fail_diarization = False
        self.job.run(self.source, self.output, self.work)
        self.assertEqual([e["phase"] for e in self.events if e["status"] == "reused"], ["audio", "asr"])

    def test_cancelled_job_keeps_validated_audio(self):
        cancel = threading.Event()
        def event(value):
            if value["phase"] == "audio" and value["status"] == "completed":
                cancel.set()
        job = Job(self.backend, cancel=cancel, event=event)
        with self.assertRaises(Cancelled):
            job.run(self.source, self.output, self.work)
        state = json.loads((self.work / "state.json").read_text())
        self.assertEqual(state["status"], "cancelled")
        self.assertEqual(set(state["completed"]), {"audio"})
        self.assertFalse(self.output.exists())

    def test_different_source_or_parameters_are_not_reused(self):
        self.job.run(self.source, self.output, self.work)
        with self.assertRaises(ValueError):
            Job(self.backend, threads=2).run(self.source, self.root / "new.srt", self.work)

    def test_corrupt_cache_is_recomputed(self):
        self.job.run(self.source, self.output, self.work)
        (self.work / "asr.json").write_text("tronqué")
        self.events.clear()
        self.job.run(self.source, self.root / "new.srt", self.work)
        reused = [e["phase"] for e in self.events if e["status"] == "reused"]
        self.assertEqual(reused, ["audio", "diarization"])
        self.assertEqual(len(parse_srt((self.root / "new.srt").read_text())), 2)

    def test_existing_export_is_protected(self):
        self.output.write_text("corrigé")
        with self.assertRaises(FileExistsError):
            self.job.run(self.source, self.output, self.work)
        self.assertEqual(self.output.read_text(), "corrigé")
        self.assertFalse(self.work.exists())

    def test_exclusive_work_lock(self):
        with work_lock(self.work / ".lock"):
            with self.assertRaises(RuntimeError):
                self.job.run(self.source, self.output, self.work)
