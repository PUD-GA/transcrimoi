from dataclasses import replace
import unittest

from transcrimoi.assignment import Segmentation, assign_words, resolve_contextual_speakers, segment_words
from transcrimoi.schema import AssignedWord, Turn, Word, parse_asr, parse_diarization
from transcrimoi.srt import parse_srt, render_srt


class SchemaTests(unittest.TestCase):
    def test_native_asr(self):
        self.assertEqual(parse_asr({"text": "oui", "words": [{"w": "oui", "start": 0, "end": .4, "conf": .9}]}, 1),
                         [Word(0, .4, "oui", .9)])

    def test_zero_duration_native_word(self):
        words = parse_asr({"text": "?", "words": [{"w": "?", "start": .4, "end": .4}]}, 1)
        self.assertEqual(len(words), 1)

    def test_reject_invalid_native_asr(self):
        base = {"w": "mot", "start": 0, "end": .4}
        for update in [{"start": -1}, {"end": 2}, {"end": float("nan")},
                       {"start": True}, {"conf": 1.1}, {"w": ""}, {"end": None}]:
            with self.subTest(update=update), self.assertRaises(ValueError):
                parse_asr({"text": "mot", "words": [base | update]}, 1)
        with self.assertRaises(ValueError):
            parse_asr({"text": "mot", "words": []}, 1)
        with self.assertRaises(ValueError):
            parse_asr({"words": []}, 1)

    def test_native_tail_frame_is_clamped(self):
        words = parse_asr({"text": "oui", "words": [{"w": "oui", "start": .9, "end": 1.04}]}, 1)
        self.assertEqual(words[0].end, 1)

    def test_diarization_capacity_is_not_observed_count(self):
        turns = parse_diarization({"speakers": 8, "segments": [{"speaker": 2, "start": .2, "end": .7}]}, 1)
        self.assertEqual(turns, [Turn(.2, .7, 2)])

    def test_invalid_speaker(self):
        for value in [-1, 8, True, "0"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_diarization({"segments": [{"speaker": value, "start": 0, "end": 1}]}, 2)


class AssignmentTests(unittest.TestCase):
    def test_majority_overlap(self):
        result = assign_words([Word(0, 1, "Bonjour")], [Turn(0, .2, 0), Turn(.2, 1, 1)])
        self.assertEqual((result[0].speaker, result[0].reason), (1, "overlap"))

    def test_exact_tie(self):
        result = assign_words([Word(0, 1, "Bonjour")], [Turn(0, .5, 0), Turn(.5, 1, 1)])
        self.assertEqual((result[0].speaker, result[0].reason), (None, "overlap_tie"))

    def test_simultaneous_speech(self):
        result = assign_words([Word(0, 1, "Bonjour")], [Turn(0, 1, 0), Turn(0, 1, 1)])
        self.assertIsNone(result[0].speaker)

    def test_nearest_only_within_threshold(self):
        words = [Word(.4, .5, "oui"), Word(1, 1.1, "non")]
        result = assign_words(words, [Turn(.6, .9, 3)])
        self.assertEqual([(x.speaker, x.reason) for x in result], [(3, "nearest"), (3, "nearest")])
        result = assign_words(words, [Turn(3, 4, 3)])
        self.assertTrue(all(x.speaker is None for x in result))

    def test_duplicate_ranges_do_not_bias_vote(self):
        result = assign_words([Word(0, 1, "mot")], [Turn(0, .4, 0), Turn(0, .4, 0), Turn(.4, 1, 1)])
        self.assertEqual(result[0].speaker, 1)

    def test_boundary_and_long_silence(self):
        words = [Word(0, .4, "oui"), Word(100, 100.4, "non")]
        result = assign_words(words, [Turn(0, .5, 4), Turn(100, 101, 4)])
        self.assertEqual([x.speaker for x in result], [4, 4])

    def test_zero_duration_and_no_turns(self):
        result = assign_words([Word(.5, .5, "?")], [])
        self.assertEqual(result[0].reason, "no_speech")

    def test_context_same_speaker(self):
        words = [AssignedWord(Word(0, .4, "avant"), 2, "overlap"),
                 AssignedWord(Word(.5, .7, "mot"), None, "overlap_tie"),
                 AssignedWord(Word(.8, 1, "après"), 2, "overlap")]
        result = resolve_contextual_speakers(words)
        self.assertEqual((result[1].speaker, result[1].reason), (2, "context_same_speaker"))

    def test_context_uses_asymmetric_temporal_bounds(self):
        words = [AssignedWord(Word(0, .4, "avant"), 0, "overlap"),
                 AssignedWord(Word(.8, 1, "mot"), None, "overlap_tie"),
                 AssignedWord(Word(1.05, 1.4, "après"), 1, "overlap")]
        result = resolve_contextual_speakers(words)
        self.assertEqual((result[1].speaker, result[1].reason), (1, "context_nearest_next"))

    def test_context_tie_uses_previous_speaker(self):
        words = [AssignedWord(Word(0, .4, "avant"), 0, "overlap"),
                 AssignedWord(Word(.5, .7, "mot"), None, "overlap_tie"),
                 AssignedWord(Word(.8, 1, "après"), 1, "overlap")]
        result = resolve_contextual_speakers(words)
        self.assertEqual((result[1].speaker, result[1].reason), (0, "context_previous_tie"))

    def test_context_has_no_distance_or_margin_threshold(self):
        words = [AssignedWord(Word(0, .4, "avant"), 0, "overlap"),
                 AssignedWord(Word(10, 10.2, "mot"), None, "no_speech"),
                 AssignedWord(Word(11, 11.4, "après"), 1, "overlap")]
        result = resolve_contextual_speakers(words)
        self.assertEqual((result[1].speaker, result[1].reason), (1, "context_nearest_next"))

    def test_context_uses_only_available_speaker(self):
        words = [AssignedWord(Word(0, .2, "mot"), None, "no_speech"),
                 AssignedWord(Word(5, 5.4, "après"), 4, "overlap")]
        result = resolve_contextual_speakers(words)
        self.assertEqual((result[0].speaker, result[0].reason), (4, "context_only_next"))

    def test_punctuation_inherits_previous_speaker(self):
        words = [AssignedWord(Word(0, .4, "question"), 3, "overlap"),
                 AssignedWord(Word(1, 1.1, "?"), None, "no_speech")]
        result = resolve_contextual_speakers(words)
        self.assertEqual((result[1].speaker, result[1].reason), (3, "punctuation_previous"))


class SegmentationTests(unittest.TestCase):
    def test_preserves_short_reply_and_speaker_changes(self):
        words = [AssignedWord(Word(0, 1, "Bonjour"), 1, "overlap"),
                 AssignedWord(Word(1, 1.1, "Oui"), 0, "overlap"),
                 AssignedWord(Word(1.2, 2, "Alors"), 1, "overlap")]
        cues = segment_words(words, 2, Segmentation())
        self.assertEqual([c.speaker for c in cues], [1, 0, 1])
        self.assertEqual([c.text for c in cues], ["Bonjour", "Oui", "Alors"])

    def test_gaps_and_sentence_end(self):
        words = [AssignedWord(Word(i, i + .2, text), 0, "overlap")
                 for i, text in [(0, "Oui."), (.3, "Alors"), (.6, "bonjour"), (3, "enfin")]]
        cues = segment_words(words, 4, Segmentation())
        self.assertEqual([c.text for c in cues], ["Oui.", "Alors bonjour", "enfin"])

    def test_duration_and_length_limits(self):
        words = [AssignedWord(Word(i, i + .5, "bonjour"), 0, "overlap") for i in range(10)]
        config = Segmentation(max_duration=2, max_characters=15)
        cues = segment_words(words, 10, config)
        self.assertTrue(all(c.end - c.start <= 2 and len(c.text) <= 15 for c in cues))
        self.assertEqual(sum(len(c.text.split()) for c in cues), 10)

    def test_standalone_punctuation_is_exportable(self):
        for time in [0, .4, 1]:
            with self.subTest(time=time):
                words = [AssignedWord(Word(time, time, "?"), None, "no_speech")]
                cues = segment_words(words, 1, Segmentation())
                self.assertEqual(len(parse_srt(render_srt(cues))), 1)

    def test_late_punctuation_merges_without_extending_cue(self):
        words = [AssignedWord(Word(0, .4, "Question"), 1, "overlap"),
                 AssignedWord(Word(2, 2.1, "?"), 1, "punctuation_previous"),
                 AssignedWord(Word(3, 3.4, "Réponse"), 2, "overlap")]
        cues = segment_words(words, 4, Segmentation())
        self.assertEqual([(c.text, c.speaker) for c in cues], [("Question?", 1), ("Réponse", 2)])
        self.assertEqual(cues[0].end, .4)

    def test_empty_is_empty(self):
        self.assertEqual(segment_words([], 1, Segmentation()), [])
