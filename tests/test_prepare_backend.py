import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts.prepare_backend import apply_ggml_patches, download, download_locked_models, find_binary
from transcrimoi.model_verification import verify_model
from transcrimoi.storage import sha256_file


@unittest.skipUnless(shutil.which("git"), "Git requis pour tester les correctifs")
class PatchTests(unittest.TestCase):
    def test_patches_apply_once_and_reject_incompatible_sources(self):
        with tempfile.TemporaryDirectory(prefix="correctifs été ") as tmp:
            source = Path(tmp)
            ggml = source / "third_party/ggml"
            patches = source / "third_party/ggml-patches"
            ggml.mkdir(parents=True)
            patches.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(ggml), *args], check=True, capture_output=True).stdout
            git("init")
            git("config", "core.autocrlf", "false")
            path = ggml / "example.txt"
            path.write_bytes(b"original\n")
            git("add", "example.txt")
            git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-m", "fixture")
            path.write_bytes(b"patched\n")
            (patches / "0001-example.patch").write_bytes(git("diff", "--binary"))
            git("checkout", "--", "example.txt")
            apply_ggml_patches(source)
            apply_ggml_patches(source)
            self.assertEqual(path.read_bytes(), b"patched\n")
            path.write_bytes(b"incompatible\n")
            with self.assertRaisesRegex(RuntimeError, "incompatible"):
                apply_ggml_patches(source)


class DownloadLayoutTests(unittest.TestCase):
    def test_locked_models_use_per_model_sources_without_changing_shared_sources(self):
        lock = {"model_repository": "shared/repo", "model_revision": "shared-revision", "models": {
            "asr": {"file": "fluid.gguf", "repository": "fluid/repo", "revision": "fluid-revision"},
            "vad": {"file": "vad.gguf"}, "diarization": {"file": "diar.gguf"}}}
        with patch("scripts.prepare_backend.download") as fetch:
            download_locked_models(lock)
        self.assertEqual(fetch.call_count, 3)
        self.assertEqual(fetch.call_args_list[0].args,
                         (lock["models"]["asr"], "fluid/repo", "fluid-revision"))
        for call in fetch.call_args_list[1:]:
            self.assertEqual(call.args[1:], ("shared/repo", "shared-revision"))

    def test_experiment_model_can_be_verified_outside_product_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / "tests/models"
            directory.mkdir(parents=True)
            model = directory / "test.gguf"
            model.write_bytes(b"test-only-not-a-model")
            config = {"file": model.name, "size": model.stat().st_size, "sha256": sha256_file(model)}
            with patch("scripts.prepare_backend.urllib.request.urlopen") as network:
                download(config, "unused/repository", "unused-revision", directory=directory)
                network.assert_not_called()
            self.assertEqual(model.read_bytes(), b"test-only-not-a-model")

    def test_download_verifies_content_and_seeds_runtime_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            path = directory / "test.gguf"
            data = b"test-only-not-a-model"
            path.write_bytes(data)
            config = {"file": path.name, "size": len(data), "sha256": sha256_file(path)}
            path.unlink()
            with patch("scripts.prepare_backend.urllib.request.urlopen", return_value=io.BytesIO(data)):
                download(config, "unused/repository", "unused-revision", directory=directory)
            with patch("transcrimoi.model_verification.sha256_file") as digest:
                verify_model(path, size=config["size"], sha256=config["sha256"])
                digest.assert_not_called()
            # Une préparation explicite revérifie même un modèle déjà en cache.
            with patch("transcrimoi.model_verification.sha256_file", wraps=sha256_file) as digest:
                download(config, "unused/repository", "unused-revision", directory=directory)
                digest.assert_called_once_with(path)

    def test_corrupt_download_is_not_published_or_cached(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            config = {"file": "test.gguf", "size": 4, "sha256": "0" * 64}
            with patch("scripts.prepare_backend.urllib.request.urlopen", return_value=io.BytesIO(b"oops")):
                with self.assertRaises(ValueError):
                    download(config, "unused/repository", "unused-revision", directory=directory)
            self.assertEqual(list(directory.iterdir()), [])


class BuildLayoutTests(unittest.TestCase):
    def test_unix_and_visual_studio_layouts(self):
        for relative, windows in (("examples/cli/parakeet-cli", False),
                                  ("examples/cli/Release/parakeet-cli.exe", True),
                                  ("bin/Release/parakeet-cli", False)):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                path = root / relative
                path.parent.mkdir(parents=True)
                path.touch()
                self.assertEqual(find_binary(root, "parakeet-cli", windows=windows), path)

    def test_missing_binary_is_explicit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                find_binary(Path(tmp), "absent")
