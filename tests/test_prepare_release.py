from pathlib import Path
import tempfile
import unittest

from scripts.prepare_release import PLATFORMS, release_notes, validate_assets
from transcrimoi import __version__
from transcrimoi.storage import sha256_file, write_json


class ReleaseAssetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.archives = []
        for platform, suffix in PLATFORMS.items():
            base = f"transcrimoi-preview-{__version__}-{platform}"
            archive = self.root / f"{base}{suffix}"
            archive.write_bytes(b"fake archive for workflow tests")
            write_json(self.root / f"{archive.name}.sha256.json", {
                "file": archive.name, "bytes": archive.stat().st_size,
                "sha256": sha256_file(archive),
            })
            write_json(self.root / f"{base}-self-test.json", {"status": "completed", "frozen": True})
            self.archives.append(archive)

    def test_three_final_archives_and_companions_are_required(self):
        self.assertEqual(validate_assets(self.root), self.archives)
        self.assertEqual(len(list(self.root.iterdir())), 9)

    def test_missing_platform_blocks_release(self):
        self.archives[1].unlink()
        with self.assertRaisesRegex(ValueError, "absent"):
            validate_assets(self.root)

    def test_tampered_archive_blocks_release_even_when_size_matches(self):
        archive = self.archives[0]
        archive.write_bytes(b"x" * archive.stat().st_size)
        with self.assertRaisesRegex(ValueError, "empreinte"):
            validate_assets(self.root)

    def test_empty_archive_blocks_release(self):
        self.archives[0].write_bytes(b"")
        with self.assertRaisesRegex(ValueError, "Archive vide"):
            validate_assets(self.root)

    def test_invalid_manifest_structure_blocks_release(self):
        write_json(self.root / f"{self.archives[0].name}.sha256.json", [])
        with self.assertRaisesRegex(ValueError, "empreinte"):
            validate_assets(self.root)

    def test_wrong_manifest_filename_blocks_release(self):
        archive = self.archives[0]
        write_json(self.root / f"{archive.name}.sha256.json", {
            "file": "other.zip", "bytes": archive.stat().st_size, "sha256": sha256_file(archive),
        })
        with self.assertRaisesRegex(ValueError, "empreinte"):
            validate_assets(self.root)

    def test_failed_or_non_frozen_diagnostic_blocks_release(self):
        report = next(self.root.glob("*-self-test.json"))
        for diagnostic in ({"status": "failed", "frozen": True},
                           {"status": "completed", "frozen": False}, []):
            with self.subTest(diagnostic=diagnostic):
                write_json(report, diagnostic)
                with self.assertRaisesRegex(ValueError, "Diagnostic"):
                    validate_assets(self.root)

    def test_unexpected_asset_blocks_release(self):
        (self.root / "unexpected.data").write_bytes(b"not for distribution")
        with self.assertRaisesRegex(ValueError, "inattendus"):
            validate_assets(self.root)

    def test_notes_explain_single_extraction_and_preview_limitations(self):
        notes = release_notes()
        self.assertIn(__version__, notes)
        self.assertIn("Une seule extraction", notes)
        self.assertIn("non notariés", notes)
        self.assertIn("Source code", notes)
