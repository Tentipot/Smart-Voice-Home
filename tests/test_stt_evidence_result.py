"""Contract tests: no microphone, model construction or network access."""
import unittest
from unittest.mock import Mock, patch

from app.speech.stt.language_resolver import LanguageResolutionReason
from app.speech.stt.service import SttService
from tests.test_stt_service import TEST_AUDIO_PATH, make_evidence, make_service


class EvidenceResultTests(unittest.TestCase):
    def test_one_pass_and_correct_pairing_for_all_routes(self):
        for bg, en, engine_index, language, reason in (
            (0.1, 0.2, 0, 'bg', LanguageResolutionReason.CTC_BULGARIAN_EVIDENCE),
            (0.2, 0.1, 1, 'en', LanguageResolutionReason.CTC_ENGLISH_EVIDENCE),
            (0.12, 0.1, 2, None, LanguageResolutionReason.CTC_AMBIGUOUS_EVIDENCE),
        ):
            with self.subTest(language=language):
                evidence = make_evidence(bg_entropy=bg, en_entropy=en)
                service, provider, *engines = make_service(evidence)
                report = service.transcribe_with_evidence(TEST_AUDIO_PATH)
                self.assertIs(report.evidence, evidence)
                self.assertEqual(report.audio_path, TEST_AUDIO_PATH)
                self.assertEqual(report.resolution.reason, reason)
                self.assertEqual(report.result.engine, engines[engine_index].engine_name)
                self.assertEqual(provider.calls, 1)
                for index, engine in enumerate(engines):
                    self.assertEqual(engine.calls, [(TEST_AUDIO_PATH, language)]
                                     if index == engine_index else [])

    def test_legacy_result_and_repeated_requests_remain_independent(self):
        first = make_evidence(bg_entropy=0.1, en_entropy=0.2)
        second = make_evidence(bg_entropy=0.2, en_entropy=0.1)
        service, provider, *_ = make_service(first)
        provider.analyze_file = Mock(side_effect=[first, second, first])
        original = service.transcribe_with_evidence(TEST_AUDIO_PATH)
        following = service.transcribe_with_evidence(TEST_AUDIO_PATH)
        legacy = service.transcribe_file(TEST_AUDIO_PATH)
        self.assertIs(original.evidence, first)
        self.assertIs(following.evidence, second)
        self.assertEqual(original.result.text, 'ROUTED-BG')
        self.assertEqual(following.result.text, 'ROUTED-EN')
        self.assertEqual(legacy, original.result)
        self.assertEqual(provider.analyze_file.call_count, 3)

    def test_failed_evidence_does_not_invoke_router(self):
        provider, resolver, router = Mock(), Mock(), Mock()
        provider.analyze_file.side_effect = ValueError('invalid audio')
        service = SttService(evidence_provider=provider,
                             language_resolver=resolver, router=router)
        with self.assertRaisesRegex(ValueError, 'invalid audio'):
            service.transcribe_with_evidence(TEST_AUDIO_PATH)
        resolver.resolve_evidence.assert_not_called()
        router.transcribe_file.assert_not_called()


    def test_runner_uses_returned_evidence(self):
        from tools.validation.run_stt_validation import ROOT, run_case
        evidence = make_evidence(bg_entropy=0.12, en_entropy=0.1)
        service, *_ = make_service(evidence)
        report = service.transcribe_with_evidence(TEST_AUDIO_PATH)
        caller = Mock()
        caller.transcribe_with_evidence.return_value = report
        manager = Mock(spec=['is_loaded', 'active_leases'])
        manager.is_loaded.return_value = True
        manager.active_leases.return_value = 0
        case = dict(audio=ROOT / 'fake_audio.wav', attempt_id='one',
                    sha256='test', prompt_id='MX01', speech_label='MIXED',
                    reference_text='ROUTED-MIXED')
        with patch(
            'tools.validation.run_stt_validation.get_gpu_status', return_value={}
        ):
            row = run_case(case, caller, manager)
        self.assertEqual(
            row['resource_state_after']['whisper_large_v3'],
            {'loaded': True, 'leases': 0},
        )
        self.assertEqual(row['entropy_delta'], evidence.entropy_delta)
        self.assertEqual(row['resolution_reason'], report.resolution.reason)
        self.assertEqual(row['text'], report.result.text)
        self.assertFalse(row['semantic_review']['can_execute'])
        self.assertEqual(row['reference_semantic_review'], 'pending_manual_review')
        caller.transcribe_with_evidence.assert_called_once_with(case['audio'])


if __name__ == '__main__':
    unittest.main()
