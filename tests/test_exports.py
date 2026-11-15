from dataclasses import asdict
from pathlib import Path
import tempfile
import unittest

from transcrimoi.exports import (
    DEFAULT_FORMAT, FORMATS, cues_from_result, export_document, get_format,
    render_export, speaker_turns, validate_output,
)
from transcrimoi.schema import Cue, SCHEMA_VERSION
from transcrimoi.srt import parse_srt, render_srt


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.cues = [Cue(.7, 1.2, "Bonjour.", 1), Cue(1.5, 2.3, "Ça va ?", 1),
                     Cue(3, 3.5, "Oui !", 0)]

    def test_nine_formats_and_historical_default(self):
        self.assertEqual(len(FORMATS), 9)
        self.assertEqual(len({item.id for item in FORMATS}), 9)
        self.assertEqual(FORMATS[0].id, DEFAULT_FORMAT)
        self.assertEqual(get_format("nvivo").label, "Temps · Locuteur · Texte — tabulations")
        self.assertNotIn("NVivo", get_format("nvivo").label)
        self.assertEqual(render_export(self.cues), render_srt(self.cues))

    def test_plain_text_is_one_block_without_labels_or_times(self):
        self.assertEqual(render_export(self.cues, "txt"), "Bonjour. Ça va ? Oui !\n")

    def test_text_variants_group_consecutive_speaker_blocks(self):
        expected = {
            "speaker-txt": "SPEAKER_01 Bonjour. Ça va ?\nSPEAKER_00 Oui !\n",
            "speaker-tsv": "SPEAKER_01\tBonjour. Ça va ?\nSPEAKER_00\tOui !\n",
            "timed-txt": "0.700 SPEAKER_01 Bonjour. Ça va ?\n3.000 SPEAKER_00 Oui !\n",
            "nvivo": "0.700\tSPEAKER_01\tBonjour. Ça va ?\n3.000\tSPEAKER_00\tOui !\n",
            "elan": "0.700\t2.300\t\tSPEAKER_01\tBonjour. Ça va ?\n3.000\t3.500\t\tSPEAKER_00\tOui !\n",
        }
        for format_id, text in expected.items():
            with self.subTest(format=format_id):
                self.assertEqual(render_export(self.cues, format_id), text)

    def test_elan_merged_end_uses_last_audio_end_not_first_block_end(self):
        cues = [Cue(0, 5, "premier", 1), Cue(1, 2, "second", 1), Cue(8, 9, "dernier", 1)]
        self.assertEqual(speaker_turns(cues), [Cue(0, 9, "premier second dernier", 1)])
        self.assertEqual(render_export(cues, "elan"), "0.000\t9.000\t\tSPEAKER_01\tpremier second dernier\n")

    def test_srt_without_speakers_preserves_times_and_boundaries(self):
        exported = parse_srt(render_export(self.cues, "srt"))
        self.assertEqual(len(exported), len(self.cues))
        for original, result in zip(self.cues, exported):
            self.assertEqual((result.start, result.end, result.text), (original.start, original.end, original.text))
            self.assertIsNone(result.speaker)
        self.assertEqual(self.cues[0].speaker, 1)

    def test_webvtt_uses_dots_header_and_escaped_payload_not_labels(self):
        cues = [Cue(3600.0005, 3601, "Été <b> & >\nsuite", 2)]
        text = render_export(cues, "vtt")
        self.assertEqual(text, "WEBVTT\n\n1\n01:00:00.001 --> 01:00:01.000\nÉté &lt;b&gt; &amp; &gt;\nsuite\n\n")
        self.assertNotIn("Speaker", text)

    def test_text_columns_normalize_tabs_and_linebreaks_without_changing_words(self):
        cues = [Cue(0, 1, "À\t bientôt\nsalut", 0)]
        self.assertEqual(render_export(cues, "nvivo"), "0.000\tSPEAKER_00\tÀ bientôt salut\n")
        self.assertEqual(len(render_export(cues, "elan").strip("\n").split("\t")), 5)

    def test_unknown_speaker_is_an_empty_field_not_an_invented_id(self):
        cues = [Cue(0, 1, "inconnu", None)]
        self.assertEqual(render_export(cues, "nvivo"), "0.000\t\tinconnu\n")
        self.assertEqual(render_export(cues, "speaker-tsv"), "\tinconnu\n")
        self.assertEqual(render_export(cues, "speaker-txt"), "inconnu\n")
        self.assertEqual(render_export(cues), "1\n00:00:00,000 --> 00:00:01,000\ninconnu\n")

    def test_no_content_is_added_on_empty_input(self):
        for item in FORMATS:
            with self.subTest(format=item.id):
                self.assertEqual(render_export([], item.id), "WEBVTT\n\n" if item.id == "vtt" else "")

    def test_sub_millisecond_rounding_and_one_millisecond_intervals(self):
        self.assertEqual(render_export([Cue(.0005, .002, "oui", 0)], "elan"),
                         "0.001\t0.002\t\tSPEAKER_00\toui\n")

    def test_all_formats_reject_invalid_cues_and_unknown_format(self):
        invalid = [Cue(-1, 1, "mot", 0), Cue(1, 1, "mot", 0), Cue(0, 1, "", 0),
                   Cue(0, 1, "mot", True), Cue(float("nan"), 1, "mot", 0), Cue(0, 1, "a\n \nb", 0)]
        for item in FORMATS:
            for cue in invalid:
                with self.subTest(format=item.id, cue=cue), self.assertRaises(ValueError):
                    render_export([cue], item.id)
        with self.assertRaises(ValueError):
            render_export(self.cues, "docx")

    def test_extensions_are_checked_including_optional_tsv(self):
        for format_id in ("speaker-tsv", "nvivo", "elan"):
            validate_output(None, Path("résultat.tsv"), format_id)
            validate_output(None, Path("résultat.TXT"), format_id)
        with self.assertRaises(ValueError):
            validate_output(None, Path("résultat.srt"), "vtt")
        with self.assertRaises(ValueError):
            validate_output(Path("source.txt"), Path("source.txt"), "txt")
        self.assertIn("*.tsv", get_format("elan").file_filter)

    def test_atomic_export_preserves_existing_files_for_every_format(self):
        with tempfile.TemporaryDirectory() as tmp:
            for item in FORMATS:
                path = Path(tmp) / (item.id + item.suffix)
                export_document(path, self.cues, item.id)
                self.assertEqual(path.read_text(encoding="utf-8"), render_export(self.cues, item.id))
                with self.assertRaises(FileExistsError):
                    export_document(path, [], item.id)
                export_document(path, [], item.id, overwrite=True)
                self.assertEqual(path.read_text(), render_export([], item.id))

    def test_result_json_loading_is_independent_of_export_format(self):
        value = {"schema_version": SCHEMA_VERSION, "cues": [asdict(cue) for cue in self.cues]}
        loaded = cues_from_result(value)
        self.assertEqual(loaded, self.cues)
        for item in FORMATS:
            self.assertEqual(render_export(loaded, item.id), render_export(self.cues, item.id))

    def test_result_json_rejects_invalid_versions_fields_or_timestamps(self):
        for value in ([], {}, {"schema_version": True, "cues": []}, {"schema_version": 999, "cues": []},
                      {"schema_version": 1, "cues": [{}]},
                      {"schema_version": 1, "cues": [{"start": -1, "end": 1, "text": "mot", "speaker": 0}]},
                      {"schema_version": 1, "cues": [{"start": 0, "end": 1, "text": 2, "speaker": 0}]}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cues_from_result(value)
