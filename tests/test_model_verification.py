import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from transcrimoi.model_verification import verify_model
from transcrimoi.storage import sha256_file


class ModelVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "model.gguf"
        self.path.write_bytes(b"test-only-model")
        self.expected = {"size": self.path.stat().st_size, "sha256": sha256_file(self.path)}
        self.cache = self.path.with_name(f".{self.path.name}.verified.json")

    def tearDown(self):
        self.temp.cleanup()

    def test_first_verification_hashes_then_reuses_persistent_cache(self):
        with patch("transcrimoi.model_verification.sha256_file", wraps=sha256_file) as digest:
            verify_model(self.path, **self.expected)
            self.assertTrue(self.cache.is_file())
            verify_model(Path(str(self.path)), **self.expected)
            digest.assert_called_once_with(self.path)

    def test_changed_timestamp_rehashes_valid_content(self):
        verify_model(self.path, **self.expected)
        stat = self.path.stat()
        os.utime(self.path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
        with patch("transcrimoi.model_verification.sha256_file", wraps=sha256_file) as digest:
            verify_model(self.path, **self.expected)
            verify_model(self.path, **self.expected)
            digest.assert_called_once_with(self.path)

    def test_same_size_corruption_is_rejected_without_updating_cache(self):
        verify_model(self.path, **self.expected)
        previous = self.cache.read_bytes()
        stat = self.path.stat()
        self.path.write_bytes(b"x" * self.expected["size"])
        os.utime(self.path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
        with self.assertRaisesRegex(ValueError, "corrompu"):
            verify_model(self.path, **self.expected)
        self.assertEqual(self.cache.read_bytes(), previous)

    def test_wrong_size_and_missing_model_are_rejected_even_with_cache(self):
        verify_model(self.path, **self.expected)
        self.path.write_bytes(b"short")
        with self.assertRaises(ValueError):
            verify_model(self.path, **self.expected)
        self.path.unlink()
        with self.assertRaises(FileNotFoundError):
            verify_model(self.path, **self.expected)

    def test_replacement_with_same_size_and_mtime_is_rehashed(self):
        verify_model(self.path, **self.expected)
        stat = self.path.stat()
        replacement = self.path.with_suffix(".new")
        replacement.write_bytes(b"x" * stat.st_size)
        os.utime(replacement, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        os.replace(replacement, self.path)
        with self.assertRaises(ValueError):
            verify_model(self.path, **self.expected)

    def test_changed_expected_hash_is_not_hidden_by_cache(self):
        verify_model(self.path, **self.expected)
        with patch("transcrimoi.model_verification.sha256_file", wraps=sha256_file) as digest:
            with self.assertRaises(ValueError):
                verify_model(self.path, size=self.expected["size"], sha256="0" * 64)
            digest.assert_called_once_with(self.path)

    def test_missing_or_invalid_cache_triggers_full_verification(self):
        for content in (None, "truncated{", "[]", '{"schema_version": 999}'):
            with self.subTest(content=content):
                if content is None:
                    self.cache.unlink(missing_ok=True)
                else:
                    self.cache.write_text(content)
                with patch("transcrimoi.model_verification.sha256_file", wraps=sha256_file) as digest:
                    verify_model(self.path, **self.expected)
                    digest.assert_called_once_with(self.path)
                self.assertEqual(json.loads(self.cache.read_text())["sha256"], self.expected["sha256"])

    def test_force_bypasses_unchanged_cache(self):
        verify_model(self.path, **self.expected)
        with patch("transcrimoi.model_verification.sha256_file", wraps=sha256_file) as digest:
            verify_model(self.path, **self.expected, force=True)
            digest.assert_called_once_with(self.path)

    def test_read_only_cache_does_not_prevent_verification(self):
        with patch("transcrimoi.model_verification.write_json", side_effect=PermissionError):
            verify_model(self.path, **self.expected)
        self.assertFalse(self.cache.exists())
        with patch("transcrimoi.model_verification.sha256_file", return_value="incorrect"):
            with self.assertRaises(ValueError):
                verify_model(self.path, **self.expected)

    def test_change_during_hashing_is_not_cached(self):
        def changed(path):
            digest = sha256_file(path)
            stat = path.stat()
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
            return digest
        with patch("transcrimoi.model_verification.sha256_file", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "changé pendant"):
                verify_model(self.path, **self.expected)
        self.assertFalse(self.cache.exists())
