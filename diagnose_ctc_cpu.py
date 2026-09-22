
import time
from pathlib import Path

import torch

from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)


BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "data" / "stt_benchmark"

TEST_NUMBERS = (31, 41, 51, 61, 71)


def main() -> None:
    print("CTC CPU DIAGNOSTIC", flush=True)
    print(f"PyTorch threads: {torch.get_num_threads()}", flush=True)
    print()

    audio_paths = [
        AUDIO_DIR / f"test_{number:03d}.wav"
        for number in TEST_NUMBERS
    ]

    for audio_path in audio_paths:
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)

    print("Loading CTC models on CPU...", flush=True)

    start = time.perf_counter()

    provider = CtcLanguageEvidenceProvider(
        device="cpu",
        dtype=torch.float32,
    )

    load_seconds = time.perf_counter() - start

    print(f"Load time: {load_seconds:.3f} s", flush=True)
    print()

    for audio_path in audio_paths:
        print(f"File: {audio_path.name}", flush=True)

        for run_number in (1, 2):
            start = time.perf_counter()

            evidence = provider.analyze_file(audio_path)

            elapsed = time.perf_counter() - start

            print(
                f"  Run {run_number}: {elapsed:.3f} s",
                flush=True,
            )

            print(
                "  BG confidence: "
                f"{evidence.bulgarian.mean_non_blank_confidence:.4f}",
                flush=True,
            )

            print(
                "  EN confidence: "
                f"{evidence.english.mean_non_blank_confidence:.4f}",
                flush=True,
            )

            print(
                "  Entropy delta: "
                f"{evidence.entropy_delta:+.6f}",
                flush=True,
            )

        print()

    print("CTC CPU DIAGNOSTIC COMPLETE", flush=True)


if __name__ == "__main__":
    main()