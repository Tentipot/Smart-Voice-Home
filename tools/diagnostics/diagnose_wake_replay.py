"""Replay WAV files through AuroraCapture as if they came from the microphone.

Exercises the real capture path (VAD onset, growing-prefix wake checks in the
worker thread, phrase end, delivery or discard) with a chosen wake detector,
without a microphone and without assistant actions. Blocks are fed at real
time (100 ms per block) so wake-check timing matches live use.

Each file is preceded by 1.0 s and followed by 2.0 s of digital silence.

Side effects: loads the selected wake detector model; writes one JSONL report
(exclusive create).

Run from the repository root:
    .\\.venv\\Scripts\\python.exe -B -m tools.diagnostics.diagnose_wake_replay --detector ctc
"""

import argparse
import json
import os
import threading
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

from app.speech.capture.aurora_capture import BLOCK_SAMPLES, AuroraCapture, CapturedPhrase
from app.speech.capture.wake_detector import create_wake_detector
from tools.diagnostics.diagnose_vram_residency import first_accepted_cases


ROOT = Path(__file__).resolve().parents[2]
BLOCK_SECONDS = BLOCK_SAMPLES / 16000
SILENCE_BLOCK = bytes(BLOCK_SAMPLES * 2)


def wav_blocks(path: Path) -> list[bytes]:
    with wave.open(str(path), "rb") as reader:
        frames = reader.readframes(reader.getnframes())
    size = BLOCK_SAMPLES * 2
    blocks = [frames[offset:offset + size] for offset in range(0, len(frames), size)]
    if blocks and len(blocks[-1]) < size:
        blocks[-1] = blocks[-1] + bytes(size - len(blocks[-1]))
    return blocks


class CountingDetector:
    def __init__(self, detector) -> None:
        self.detector = detector
        self.name = detector.name
        self.calls: list[float] = []

    def detect(self, audio):
        started = time.perf_counter()
        decision = self.detector.detect(audio)
        self.calls.append(time.perf_counter() - started)
        return decision


def replay(capture: AuroraCapture, detector: CountingDetector, path: Path, delivered: list) -> dict:
    capture.resume()
    delivered.clear()
    detector.calls.clear()
    blocks = [SILENCE_BLOCK] * 10 + wav_blocks(path) + [SILENCE_BLOCK] * 20
    speech_end = None

    for index, block in enumerate(blocks):
        capture.process_wake_results()
        capture.process_audio_block(block)
        if index == len(blocks) - 21:
            speech_end = time.perf_counter()
        time.sleep(BLOCK_SECONDS)

    deadline = time.perf_counter() + 30
    while time.perf_counter() < deadline:
        capture.process_wake_results()
        if delivered or (not capture.phrases and capture.active_phrase_id is None):
            break
        time.sleep(0.05)

    phrase: CapturedPhrase | None = delivered[0][0] if delivered else None
    return {
        "file": str(path.relative_to(ROOT)),
        "delivered": phrase is not None,
        "wake_text": phrase.wake_text if phrase else "",
        "delivery_after_file_end_seconds": (
            round(delivered[0][1] - speech_end, 2) if delivered else None
        ),
        "detector_calls": len(detector.calls),
        "detector_median_seconds": (
            round(sorted(detector.calls)[len(detector.calls) // 2], 3) if detector.calls else None
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--detector", default="ctc", choices=("ctc", "whisper"))
    parser.add_argument("--negatives", type=int, default=20, help="test_061.. files without wake word")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / (
            "WAKE_REPLAY_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".jsonl"
        ),
    )
    args = parser.parse_args()

    positives = [case["audio"] for case in first_accepted_cases(
        ROOT / "data" / "stt_validation" / "pilot_01"
    ).values()]
    negatives = [
        ROOT / "data" / "stt_benchmark" / f"test_{number:03d}.wav"
        for number in range(61, 61 + args.negatives)
    ]

    detector = CountingDetector(create_wake_detector(args.detector))
    delivered: list[tuple[CapturedPhrase, float]] = []
    capture = AuroraCapture(
        on_phrase=lambda phrase: delivered.append((phrase, time.perf_counter())),
        verbose=False,
        wake_detector=detector,
    )
    worker = threading.Thread(target=capture.wake_worker, daemon=True)
    worker.start()

    rows = [{"event": "start", "utc": datetime.now(timezone.utc).isoformat(), "detector": args.detector}]
    for label, files in ((1, positives), (0, negatives)):
        for path in files:
            row = {"event": "file", "label": label, **replay(capture, detector, path, delivered)}
            rows.append(row)
            print(
                f"{'WAKE' if label else 'NONE'} {Path(row['file']).name[:28]:<28} "
                f"delivered={row['delivered']!s:<5} after_end={row['delivery_after_file_end_seconds']} "
                f"calls={row['detector_calls']} det={row['detector_median_seconds']} "
                f"{row['wake_text']}",
                flush=True,
            )

    capture.stop()
    worker.join(timeout=5)

    files = [row for row in rows if row["event"] == "file"]
    positives_hit = [row for row in files if row["label"] == 1 and row["delivered"]]
    delays = sorted(row["delivery_after_file_end_seconds"] for row in positives_hit)
    summary = {
        "event": "summary",
        "detected": len(positives_hit),
        "positives": sum(row["label"] == 1 for row in files),
        "false_accepts": sum(row["label"] == 0 and row["delivered"] for row in files),
        "negatives": sum(row["label"] == 0 for row in files),
        "delivery_median_seconds": delays[len(delays) // 2] if delays else None,
        "delivery_max_seconds": delays[-1] if delays else None,
    }
    rows.append(summary)

    with args.output.open("x", encoding="utf-8") as report:
        for row in rows:
            report.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(json.dumps(summary, ensure_ascii=False))
    print(f"Report: {args.output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
