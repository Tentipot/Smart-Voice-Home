import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from run_stt_validation import accepted_cases, word_errors


class ValidationTests(unittest.TestCase):
    def test_word_errors(self):
        self.assertEqual(word_errors('НЕ, спирай!', 'не спирай')['errors'], 0)
        self.assertEqual(word_errors('a b c', 'a x c')['errors'], 1)
        self.assertEqual(word_errors('a b', 'a')['errors'], 1)
        self.assertEqual(word_errors('a', 'a b')['errors'], 1)
        self.assertEqual(word_errors('é', 'e\u0301')['errors'], 0)
        self.assertEqual(word_errors('не спирай', 'спирай')['errors'], 1)

    def test_integrity_and_review_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio = root / 'sample.wav'
            audio.write_bytes(b'test audio')
            events = [
                {'event': 'attempt', 'attempt_id': 'one', 'prompt_id': 'BG01'},
                {'event': 'captured', 'attempt_id': 'one', 'filename': audio.name,
                 'sha256': hashlib.sha256(audio.read_bytes()).hexdigest()},
                {'event': 'review', 'attempt_id': 'one', 'status': 'accepted',
                 'reference_text': 'тест', 'speech_label': 'BG'},
            ]
            journal = root / 'manifest.jsonl'
            def save():
                journal.write_text('\n'.join(json.dumps(x) for x in events), encoding='utf-8')
            save()
            self.assertEqual(len(accepted_cases(root)), 1)
            audio.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'SHA256'):
                accepted_cases(root)
            events.append({'event': 'review', 'attempt_id': 'one', 'status': 'rejected'})
            save()
            self.assertEqual(accepted_cases(root), [])


if __name__ == '__main__':
    unittest.main()
