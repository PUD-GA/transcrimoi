import ast
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from unittest.mock import patch

from tests.paths import EXPERIMENTS, FIXTURES, ROOT
from tests.tools.check_corpus import inventory
from tests.tools.check_repository import audit


class LayoutTests(unittest.TestCase):
    def test_product_does_not_import_tests_or_developer_tools(self):
        forbidden = {"tests", "scripts", "torch", "moondream", "kestrel"}
        for path in (ROOT / "transcrimoi").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name.split(".")[0] for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imports.append(node.module.split(".")[0])
            with self.subTest(path=path.name):
                self.assertFalse(forbidden.intersection(imports))

    def test_only_application_packages_are_built(self):
        config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(config["tool"]["setuptools"]["packages"]["find"]["include"], ["transcrimoi*"])

    def test_corpus_and_experiment_paths_are_local_and_grouped(self):
        manifest = json.loads((FIXTURES / "corpus_manifest.json").read_text(encoding="utf-8"))
        experiment = json.loads((EXPERIMENTS / "ultra-f16.lock.json").read_text(encoding="utf-8"))
        names = [pair[key] for pair in manifest["pairs"] for key in ("audio", "srt")]
        names += [experiment["source"], experiment["cuts"]]
        for name in names:
            with self.subTest(name=name):
                path = PurePosixPath(name)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertTrue(path.is_relative_to("tests/sources"))

    def test_missing_corpus_cannot_be_frozen_as_empty_reference(self):
        with tempfile.TemporaryDirectory() as tmp, patch("tests.tools.check_corpus.SYNTH", Path(tmp)):
            with self.assertRaisesRegex(FileNotFoundError, "absent ou vide"):
                inventory()


@unittest.skipUnless(shutil.which("git"), "Git nécessaire pour vérifier les règles réelles")
class IgnoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="transcrimoi-publication-")
        self.root = Path(self.temp.name)
        shutil.copyfile(ROOT / ".gitignore", self.root / ".gitignore")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)

    def tearDown(self):
        self.temp.cleanup()

    def touch(self, name, text="test-only"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_private_data_secrets_and_generated_files_are_ignored(self):
        ignored = {
            "tests/sources/reel/interview.wav", "tests/sources/reel/notes.json",
            "tests/sources/synth/srt/reference.srt", "tests/sources/wamatipsia/cuts.json",
            "tests/runs/job/report.json", "tests/runs/job/README.md", "tests/runs/manual.py",
            "tests/models/photon/config.json", "tests/models/baseline.gguf",
            "CorpusReel/source.wav", "CorpusSynth/private.txt", "runs/old/result.json",
            ".venv/pyvenv.cfg", ".venv-gui/pyvenv.cfg", ".venv-macos/pyvenv.cfg",
            "models/model.gguf", "vendor/project/README.md", "build/backend.json",
            "dist/transcrimoi.zip", "bin/ffmpeg", "somewhere/interview.mp3",
            "somewhere/interview.WaV", "somewhere/export.SRT", "private-corpus.Zip",
            "download/corpus.tar.gz", "signing/AuthKey.p8",
            "somewhere/export.srt", "somewhere/export.txt", "somewhere/export.TXT", "somewhere/export.tsv",
            "weights/model.safetensors", "signing/developer.p12",
            "signing/key.pem", ".env", ".env.local", "run.log", ".DS_Store",
            "transcrimoi/__pycache__/gui.cpython-312.pyc",
        }
        allowed = {
            ".gitignore", ".env.example", "README.md", "Plan.md", "pyproject.toml", "MANIFEST.in",
            "LICENSE.txt", "LICENCE.txt", "requirements.txt", "CMakeLists.txt",
            "backend.lock.json", "transcrimoi/gui.py", "transcrimoi/core.py", "scripts/prepare_backend.py",
            "tests/test_gui.py", "tests/paths.py", "tests/tools/check_repository.py",
            "tests/fixtures/corpus_manifest.json", "tests/experiments/ultra-f16.lock.json",
            "tests/README.md", "tests/sources/README.md", "tests/runs/README.md", "tests/models/README.md",
            ".github/workflows/desktop.yml", "docs/interface-minimale.md",
        }
        for name in ignored | allowed:
            if name != ".gitignore":
                self.touch(name)
        # NUL binaire : ne pas transformer LF en CRLF dans le pipe sous Windows.
        result = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--stdin", "-z"],
                                input="".join(name + "\0" for name in sorted(ignored | allowed)).encode("utf-8"),
                                capture_output=True, check=True)
        self.assertEqual(set(result.stdout.decode("utf-8").strip("\0").split("\0")), ignored)
        report = audit(self.root)
        self.assertEqual(set(report["files"]), allowed)
        self.assertEqual(report["errors"], [])

    def test_audit_detects_private_file_already_added_to_index(self):
        name = "tests/sources/reel/private.json"
        self.touch(name)
        subprocess.run(["git", "-C", str(self.root), "add", "-f", name], check=True, capture_output=True)
        report = audit(self.root)
        self.assertTrue(any(name in error for error in report["errors"]))

    def test_audit_flags_large_unignored_file(self):
        self.touch("unexpected.data", "x" * 1024)
        report = audit(self.root, max_file_bytes=512)
        self.assertTrue(any("unexpected.data" in error for error in report["errors"]))

    def test_audit_does_not_create_git_in_uninitialized_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("Public", encoding="utf-8")
            self.assertEqual(audit(root)["files"], ["README.md"])
            self.assertFalse((root / ".git").exists())
