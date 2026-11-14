import os
from pathlib import Path
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.build_desktop import archive_bundle, artifact_name, stage_runtime, stamp_manifest
from transcrimoi.model_verification import verify_model
from transcrimoi.runtime import model_cache_directory, project_root
from transcrimoi.storage import read_json, sha256_file, write_json


class RuntimePathsTests(unittest.TestCase):
    def test_developer_root_and_cache_remain_unchanged(self):
        with patch.object(sys, "frozen", False, create=True):
            self.assertEqual(project_root(), Path(__file__).resolve().parents[1])
            self.assertIsNone(model_cache_directory())

    def test_frozen_root_uses_pyinstaller_resources_not_current_directory(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "_MEIPASS", tmp, create=True):
            self.assertEqual(project_root(), Path(tmp))

    def test_frozen_cache_is_in_user_space_on_each_os(self):
        home = Path.home()
        with patch.object(sys, "frozen", True, create=True):
            for name, env, expected in (
                ("win32", {"LOCALAPPDATA": str(home / "local")}, home / "local"),
                ("darwin", {}, home / "Library/Caches"),
                ("linux", {"XDG_CACHE_HOME": str(home / "cache")}, home / "cache"),
            ):
                with self.subTest(platform=name), patch.object(sys, "platform", name), patch.dict(os.environ, env):
                    self.assertEqual(model_cache_directory(), expected / "transcrimoi/model-verification")

    def test_model_cache_does_not_modify_bundle_resources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            model = root / "bundle/model.gguf"
            model.parent.mkdir()
            model.write_bytes(b"fake model")
            expected = {"size": model.stat().st_size, "sha256": sha256_file(model)}
            with patch("transcrimoi.model_verification.model_cache_directory", return_value=root / "user-cache"):
                verify_model(model, **expected)
                with patch("transcrimoi.model_verification.sha256_file") as digest:
                    verify_model(model, **expected)
                    digest.assert_not_called()
            self.assertEqual(list(model.parent.iterdir()), [model])
            self.assertEqual(len(list((root / "user-cache").glob("*.json"))), 1)


class PackageTests(unittest.TestCase):
    def test_artifact_name_contains_version_os_and_architecture(self):
        with patch("scripts.build_desktop.platform.system", return_value="Windows"), \
                patch("scripts.build_desktop.platform.machine", return_value="AMD64"):
            self.assertEqual(artifact_name(), "transcrimoi-preview-0.2.0-windows-x86_64")

    def test_staging_copies_only_declared_runtime_not_private_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, stage = Path(tmp) / "source", Path(tmp) / "stage"
            (root / "models").mkdir(parents=True)
            (root / "native").mkdir()
            models = {}
            for role in ("asr", "vad", "diarization"):
                path = root / "models" / f"{role}.gguf"
                path.write_bytes(b"fake model")
                models[role] = {"file": path.name}
            (root / "models/private.txt").write_text("never packaged")
            cli, diar, ffmpeg = [root / "native" / name for name in ("cli", "diar", "ffmpeg")]
            for path in (cli, diar, ffmpeg):
                path.write_bytes(b"fake executable")
            lock = {"models": models}
            write_json(root / "backend.lock.json", lock)
            write_json(root / "build/backend.json", {"binaries": {"parakeet-cli": {}, "diarize": {}}})
            backend = SimpleNamespace(cli=cli, diarize=diar, provenance={"lock": lock})
            with patch("scripts.build_desktop.Backend.verified", return_value=backend):
                stage_runtime(root, stage, ffmpeg)
            self.assertEqual(sorted(path.name for path in (stage / "models").iterdir()),
                             ["asr.gguf", "diarization.gguf", "vad.gguf"])
            for item in read_json(stage / "build/backend.json")["binaries"].values():
                self.assertTrue(item["path"].startswith("bin/"))
                self.assertEqual(item["sha256"], sha256_file(stage / item["path"]))

    def test_manifest_uses_final_binary_hashes_after_packaging(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "bin/cli"
            binary.parent.mkdir()
            binary.write_bytes(b"rewritten by PyInstaller")
            write_json(root / "build/backend.json", {"binaries": {"cli": {"path": "bin/cli", "sha256": "old"}}})
            with patch("scripts.build_desktop.importlib.metadata.version", return_value="test-only"):
                stamp_manifest(root)
            manifest = read_json(root / "build/backend.json")
            self.assertEqual(manifest["binaries"]["cli"]["sha256"], sha256_file(binary))
            self.assertFalse(manifest["package"]["signed_for_distribution"])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Archive tar Linux")
    def test_linux_archive_preserves_full_name_and_file_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            bundle = root / "bundle"
            bundle.mkdir()
            binary = bundle / "transcrimoi"
            binary.write_bytes(b"fake executable")
            binary.chmod(0o755)
            archive = archive_bundle(bundle, root / "transcrimoi-preview-0.2.0-linux-x86_64")
            self.assertEqual(archive.name, "transcrimoi-preview-0.2.0-linux-x86_64.tar.gz")
            with tarfile.open(archive) as stream:
                self.assertEqual(stream.getmember("transcrimoi/transcrimoi").mode & 0o111, 0o111)

    def test_macos_archive_uses_ditto_and_preserves_full_name(self):
        with patch.object(sys, "platform", "darwin"), patch("scripts.build_desktop.subprocess.run") as run:
            result = archive_bundle(Path("transcrimoi.app"), Path("transcrimoi-preview-0.2.0-macos-arm64"))
        self.assertEqual(result.name, "transcrimoi-preview-0.2.0-macos-arm64.app.zip")
        self.assertIn("--keepParent", run.call_args.args[0])
