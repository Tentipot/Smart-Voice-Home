"""Hardware-free checks for validation data preservation and failure handling."""

import hashlib
import json
from pathlib import Path
import queue
import tempfile
import unittest
import wave

from collect_stt_validation import append_event, read_prompts, save_audio, wait_for_phrase


class Worker:
    def __init__(self, alive):
        self.alive = alive

    def is_alive(self):
        return self.alive


class ValidationCollectorTests(unittest.TestCase):
    def test_plan_has_balanced_groups(self):
        prompts = read_prompts()
        self.assertEqual(len(prompts), 24)
        for label in ("BG", "EN", "MIXED"):
            self.assertEqual(sum(row[1] == label for row in prompts), 8)

    def test_audio_roundtrip_and_collision_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.wav"
            pcm = b"\x00\x00\x01\x00" * 160
            digest = save_audio(path, (pcm[:100], pcm[100:]))
            original = path.read_bytes()
            self.assertEqual(digest, hashlib.sha256(original).hexdigest())
            with wave.open(str(path), "rb") as stream:
                self.assertEqual((stream.getnchannels(), stream.getsampwidth(), stream.getframerate()), (1, 2, 16000))
                self.assertEqual(stream.readframes(stream.getnframes()), pcm)
            with self.assertRaises(FileExistsError):
                save_audio(path, (b"\x01\x01",))
            self.assertEqual(path.read_bytes(), original)

    def test_journal_keeps_capture_and_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "manifest.jsonl"
            events = [
                {"event": "captured", "attempt_id": "one", "wake_text": "Аурора"},
                {"event": "review", "attempt_id": "one", "status": "rejected", "reason": "Изрязано начало"},
            ]
            for event in events:
                append_event(path, event)
            self.assertEqual([json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()], events)

    def test_timeout_is_not_a_successful_capture(self):
        with self.assertRaises(TimeoutError):
            wait_for_phrase(queue.Queue(), Worker(True), queue.Queue(), 0)

    def test_capture_failure_and_dead_worker_do_not_hang(self):
        failures = queue.Queue()
        failures.put(ValueError("Microphone unavailable"))
        with self.assertRaises(RuntimeError) as result:
            wait_for_phrase(queue.Queue(), Worker(True), failures, 1)
        self.assertIsInstance(result.exception.__cause__, ValueError)
        with self.assertRaises(RuntimeError):
            wait_for_phrase(queue.Queue(), Worker(False), queue.Queue(), 1)

    def test_delivered_phrase_is_returned(self):
        inbox = queue.Queue()
        phrase = object()
        inbox.put(phrase)
        self.assertIs(wait_for_phrase(inbox, Worker(True), queue.Queue(), 1), phrase)


if __name__ == "__main__":
    unittest.main()
