import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.paths import EXPERIMENTS
from transcrimoi.backend import Backend
from transcrimoi.storage import sha256_file, write_json


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "models").mkdir()
        models = {}
        for role in ("asr", "diarization", "vad"):
            path = self.root / "models" / f"{role}.gguf"
            path.write_bytes(b"test-only-not-a-model")
            models[role] = {"file": path.name, "size": path.stat().st_size, "sha256": sha256_file(path)}
        write_json(self.root / "backend.lock.json", {"native": {"commit": "test-commit"}, "models": models})
        binaries = {}
        for name in ("parakeet-cli", "diarize"):
            path = self.root / name
            path.write_bytes(b"test-only-not-an-executable")
            binaries[name] = {"path": str(path), "sha256": sha256_file(path)}
        write_json(self.root / "build/backend.json", {
            "native_commit": "test-commit", "backend": "cpu", "binaries": binaries,
            "lock_sha256": sha256_file(self.root / "backend.lock.json")})

    def tearDown(self):
        self.temp.cleanup()

    def test_commands_use_validated_protocol_and_sequential_models(self):
        backend = Backend.verified(self.root)
        command = backend.asr_command(self.root / "audio été.wav", 4)
        self.assertIn("--json", command)
        self.assertIn("--vad-model", command)
        self.assertNotIn(str(backend.diar_model), command)
        self.assertEqual(backend.diarization_command(self.root / "audio.wav")[-2:], ["--stream", "model"])

    def test_relative_binary_paths_are_resolved_from_root(self):
        path = self.root / "build/backend.json"
        manifest = json.loads(path.read_text())
        for name, item in manifest["binaries"].items():
            item["path"] = name
        write_json(path, manifest)
        backend = Backend.verified(self.root)
        self.assertEqual(backend.cli, self.root / "parakeet-cli")

    def test_default_model_is_fluid_with_frozen_experiment_hash(self):
        root = Path(__file__).resolve().parents[1]
        lock = json.loads((root / "backend.lock.json").read_text())
        experiment = json.loads((EXPERIMENTS / "fluid-q8.lock.json").read_text())
        model = lock["models"]["asr"]
        self.assertEqual(model["checkpoint"], "FluidVoice-Labs/fluid-speech-pro")
        self.assertEqual(model["repository"], experiment["model_repository"])
        self.assertEqual(model["revision"], experiment["model_revision"])
        for key in ("file", "size", "sha256", "precision", "attribution"):
            self.assertEqual(model[key], experiment["model"][key])
        self.assertNotEqual(experiment["baseline_model"]["sha256"], model["sha256"])

    def test_corrupt_model_is_rejected(self):
        (self.root / "models/asr.gguf").write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            Backend.verified(self.root)

    def test_repeated_backend_checks_skip_only_unchanged_model_hashes(self):
        with patch("transcrimoi.model_verification.sha256_file", wraps=sha256_file) as digest:
            first = Backend.verified(self.root)
            self.assertEqual(digest.call_count, 3)
            second = Backend.verified(self.root)
            self.assertEqual(digest.call_count, 3)
            self.assertEqual(first.provenance, second.provenance)
            Backend.verified(self.root, force_models=True)
            self.assertEqual(digest.call_count, 6)
        # Les binaires restent intégralement vérifiés, même avec les modèles en cache.
        (self.root / "diarize").write_bytes(b"modified")
        with self.assertRaises(ValueError):
            Backend.verified(self.root)

    def test_modified_binary_is_rejected(self):
        (self.root / "diarize").write_bytes(b"modified")
        with self.assertRaises(ValueError):
            Backend.verified(self.root)

    def test_lock_change_requires_new_build(self):
        path = self.root / "backend.lock.json"
        lock = json.loads(path.read_text())
        lock["native"]["commit"] = "other"
        write_json(path, lock)
        with self.assertRaises(ValueError):
            Backend.verified(self.root)
