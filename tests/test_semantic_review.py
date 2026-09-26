import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from app.commands.semantic_review import SemanticReviewer
from app.commands.review_service import CommandReviewService


class SemanticReviewTests(unittest.TestCase):
    def setUp(self):
        self.reviewer = SemanticReviewer()

    def test_supported_commands(self):
        for text, intent in (
            ('Аурора, спри музиката.', 'stop_media'),
            ('Aurora, turn down the volume!', 'volume_down'),
            ('увеличи звука', 'volume_up'),
            ('pause the music', 'pause_media'),
            ('продължи музиката', 'resume_media'),
            ('next song', 'next_track'),
            ('previous song', 'previous_track'),
            ('рестартирай песента', 'restart_track'),
            ('изключи лампата в хола', 'turn_off'),
        ):
            with self.subTest(text=text):
                review = self.reviewer.review(text)
                self.assertEqual(review.status, 'parsed')
                self.assertEqual(review.command.intent, intent)
                self.assertFalse(review.can_execute)

    def test_numeric_values_preserved_not_corrected(self):
        for text, value in (
            ('set volume to 4%', 4), ('set volume to 40 percent', 40),
            ('set volume to thirty-one percent', 31),
            ('задай звука на двадесет и пет процента', 25),
            ('настрой звука на нула процента', 0),
            ('set volume to one hundred percent', 100),
        ):
            with self.subTest(text=text):
                self.assertEqual(self.reviewer.review(text).command.value, value)
        for value in ('-4', '101', '4.5', '4,5', 'thirty forty', '40 or 50', ''):
            with self.subTest(value=value):
                self.assertIsNone(self.reviewer.review(f'set volume to {value}%').command)

    def test_negation_sequences_and_conditions_never_reduce_to_positive_action(self):
        for text in (
            'не спирай музиката', "don't stop the music", 'do not stop the music',
            'включи лампата but keep the music playing',
            'спри музиката и изключи лампата',
            'turn off the light after pause the music',
            'ако свири музика спри музиката', 'спри музиката?',
            'спри музиката; включи лампата', 'спри музиката утре',
            'спри музиката на телевизора', 'restart Epicenter', 'спи музиката',
            'намали звука до 80 процента',
        ):
            with self.subTest(text=text):
                review = self.reviewer.review(text)
                self.assertEqual(review.status, 'needs_clarification')
                self.assertIsNone(review.command)
                self.assertFalse(review.can_execute)

    def test_contradicting_candidates(self):
        for primary, other in (
            ('намали звука', 'увеличи звука'),
            ('включи лампата', 'изключи лампата'),
            ('set volume to 30%', 'set volume to 40%'),
            ('изключи лампата в хола', 'изключи лампата в спалнята'),
        ):
            with self.subTest(primary=primary):
                review = self.reviewer.review(primary, alternatives=(other,))
                self.assertEqual(review.reason, 'conflicting_candidates')
                self.assertIsNone(review.command)

    def test_unparsed_alternative_is_not_ignored(self):
        review = self.reviewer.review('спри музиката', alternatives=('не спирай музиката',))
        self.assertEqual(review.reason, 'unresolved_candidate')
        self.assertEqual(len(review.candidates), 2)
        self.assertIsNone(review.command)

    def test_agreement_is_not_authorization(self):
        review = self.reviewer.review('спри музиката', alternatives=('stop the music',))
        self.assertEqual(review.status, 'parsed')
        self.assertFalse(review.can_execute)

    def test_entities_are_not_invented_or_fuzzily_repaired(self):
        for text in ('play Any New Artist Any New Song', 'пусни', 'изключи',
                     'аурона спри музиката', ''):
            with self.subTest(text=text):
                review = self.reviewer.review(text)
                self.assertIsNone(review.command)
                self.assertEqual(review.candidates[0].text, text)

    def test_device_target_is_open_vocabulary_and_unresolved(self):
        text = 'включи малката лампа до дивана'
        review = self.reviewer.review(text)
        self.assertEqual(review.command.target, 'малката лампа до дивана')
        self.assertFalse(review.can_execute)
        for text in ('turn on lamp. turn off tv', 'включи лампата изключи телевизора'):
            self.assertIsNone(self.reviewer.review(text).command)

    def test_free_media_query_is_preserved_for_resolution(self):
        review = self.reviewer.review('play A New Artist A New Song')
        self.assertEqual(review.status, 'needs_clarification')
        self.assertIsNone(review.command)
        self.assertEqual(review.candidates[0].command.query, 'a new artist a new song')

    def test_review_service_preserves_evidence_and_does_one_stt_call(self):
        transcription = SimpleNamespace(result=SimpleNamespace(text='спри музиката'),
                                        evidence=object(), resolution=object())
        stt = Mock()
        stt.transcribe_with_evidence.return_value = transcription
        result = CommandReviewService(stt).transcribe_and_review(Path('test.wav'))
        self.assertIs(result.transcription, transcription)
        self.assertEqual(result.review.command.intent, 'stop_media')
        stt.transcribe_with_evidence.assert_called_once_with(Path('test.wav'))

    def test_explicit_sequence_preserves_order_across_languages(self):
        review = self.reviewer.review('Aurora, pause the music, после изключи лампата.')
        self.assertEqual(review.status, 'parsed')
        self.assertEqual([s.intent for s in review.command.steps], ['pause_media', 'turn_off'])
        self.assertEqual(review.command.steps[1].target, 'лампата')
        self.assertFalse(review.can_execute)
        reverse = self.reviewer.review('изключи лампата then pause the music')
        self.assertEqual([s.intent for s in reverse.command.steps], ['turn_off', 'pause_media'])
        combined = self.reviewer.review('pause the music then изключи лампата',
                                       alternatives=('изключи лампата then pause the music',))
        self.assertEqual(combined.reason, 'conflicting_candidates')

    def test_preservation_is_constraint_not_extra_action(self):
        for text, constraint in (
            ('включи лампата, but keep the music playing', 'keep_playing'),
            ('turn on the light, но не променяй звука', 'preserve_volume'),
        ):
            with self.subTest(text=text):
                review = self.reviewer.review(text)
                self.assertEqual(review.reason, 'state_constraint_requires_context')
                self.assertIsNone(review.command)
                candidate = review.candidates[0].command
                self.assertEqual(candidate.steps[0].intent, 'turn_on')
                self.assertEqual(candidate.constraints[0].intent, constraint)
                self.assertFalse(review.can_execute)

    def test_partial_compound_is_never_extracted_as_complete_command(self):
        for text in (
            'pause the music then restart Epicenter',
            'не спирай музиката then включи лампата',
            'включи лампата but keep the music playing then изключи лампата',
            'pause the music after I turn off the lamp',
            'pause the music then next song then previous song',
        ):
            with self.subTest(text=text):
                review = self.reviewer.review(text)
                self.assertEqual(review.status, 'needs_clarification')
                self.assertIsNone(review.command)


if __name__ == '__main__':
    unittest.main()
