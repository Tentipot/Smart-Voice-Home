import threading
import unittest

import numpy as np

from app.speech.capture.aurora_capture import (
    AuroraCapture,
    CapturedPhrase,
    _Phrase,
    _WakeJob,
)
from app.speech.capture.wake_detector import (
    CtcWakeDetector,
    WakeDecision,
    contains_wake,
    create_wake_detector,
    keyword_deficit,
)


BLANK = 0
A, B, C = 1, 2, 3


def log_probs_for(path: list[int], vocab_size: int = 4) -> np.ndarray:
    """Frames whose most likely symbol follows `path`."""
    probs = np.full((len(path), vocab_size), 0.02)
    for frame, symbol in enumerate(path):
        probs[frame, symbol] = 0.94
    return np.log(probs / probs.sum(axis=1, keepdims=True))


class FakeDetector:
    name = "fake"

    def __init__(self, decision: WakeDecision) -> None:
        self.decision = decision
        self.calls = 0

    def detect(self, audio: np.ndarray) -> WakeDecision:
        self.calls += 1
        return self.decision


class KeywordDeficitTests(unittest.TestCase):
    def test_keyword_in_greedy_path_scores_zero(self):
        log_probs = log_probs_for([C, BLANK, A, A, BLANK, B, BLANK, C])
        self.assertAlmostEqual(keyword_deficit(log_probs, [A, B], BLANK), 0.0)

    def test_repeated_symbol_needs_blank_between(self):
        merged = log_probs_for([BLANK, A, A, BLANK])
        separated = log_probs_for([BLANK, A, BLANK, A, BLANK])
        self.assertGreater(keyword_deficit(merged, [A, A], BLANK), 0.0)
        self.assertAlmostEqual(keyword_deficit(separated, [A, A], BLANK), 0.0)

    def test_absent_keyword_scores_high(self):
        log_probs = log_probs_for([C, C, BLANK, C, C, BLANK])
        self.assertGreater(keyword_deficit(log_probs, [A, B], BLANK), 2.0)


class CtcWakeDetectorTests(unittest.TestCase):
    def make_detector(self, log_probs: np.ndarray) -> CtcWakeDetector:
        detector = object.__new__(CtcWakeDetector)
        detector._blank = BLANK
        detector._threshold = 1.0
        detector._keywords = {"ab": [A, B], "cc": [C, C]}
        detector.log_probs = lambda audio: log_probs
        return detector

    def test_detects_best_keyword(self):
        detector = self.make_detector(log_probs_for([BLANK, A, B, BLANK]))
        decision = detector.detect(np.zeros(16000, dtype=np.float32))
        self.assertTrue(decision.detected)
        self.assertEqual(decision.text, "ab score=0.00")

    def test_rejects_when_no_keyword(self):
        detector = self.make_detector(log_probs_for([BLANK, C, BLANK, BLANK]))
        decision = detector.detect(np.zeros(16000, dtype=np.float32))
        self.assertFalse(decision.detected)
        self.assertGreater(decision.score, 1.0)

    def test_unknown_kind_is_rejected(self):
        with self.assertRaises(ValueError):
            create_wake_detector("vosk")

    def test_text_match_helper_is_unchanged(self):
        self.assertTrue(contains_wake("Аурора, намали звука"))
        self.assertTrue(contains_wake("Aurora-namali"))
        self.assertFalse(contains_wake("Намали звука"))


class AuroraCaptureWakeTests(unittest.TestCase):
    def run_job(self, decision: WakeDecision) -> tuple[list[CapturedPhrase], AuroraCapture]:
        delivered: list[CapturedPhrase] = []
        detector = FakeDetector(decision)
        capture = AuroraCapture(
            on_phrase=delivered.append,
            verbose=False,
            wake_detector=detector,
        )
        block = np.zeros(1600, dtype=np.int16).tobytes()
        capture.phrases[1] = _Phrase(phrase_id=1, blocks=[block], finished=True, outstanding_checks=1)
        capture.wake_queue.put(_WakeJob(phrase_id=1, blocks=[block], is_final=True))

        worker = threading.Thread(target=capture.wake_worker, daemon=True)
        worker.start()
        capture.wake_queue.join()
        capture.stop()
        worker.join(timeout=2)

        capture.process_wake_results()
        self.assertEqual(detector.calls, 1)
        return delivered, capture

    def test_detected_wake_delivers_phrase(self):
        delivered, capture = self.run_job(WakeDecision(True, "аурора score=0.10", score=0.1))
        self.assertEqual(len(delivered), 1)
        self.assertEqual(delivered[0].wake_text, "аурора score=0.10")
        self.assertTrue(capture.pause_event.is_set())

    def test_rejected_wake_discards_phrase(self):
        delivered, capture = self.run_job(WakeDecision(False, "аурора score=4.00", score=4.0))
        self.assertEqual(delivered, [])
        self.assertNotIn(1, capture.phrases)


if __name__ == "__main__":
    unittest.main()
