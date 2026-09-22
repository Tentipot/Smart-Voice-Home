import gc
import time
from pathlib import Path

import torch

from app.resources.system_monitor import get_gpu_status
from app.speech.stt.buzzasr_engine import BuzzAsrSttEngine
from app.speech.stt.whisper_engine import WhisperSttEngine


BG_AUDIO = Path("data/stt_benchmark/test_031.wav")
EN_AUDIO = Path("data/stt_benchmark/test_041.wav")

# Conservative pre-load check. This is not a guarantee against
# transient CUDA allocation peaks.
MIN_FREE_BEFORE_BUZZ_MB = 4000


def gpu_memory() -> tuple[int, int]:
    status = get_gpu_status()

    if not status.get("available"):
        raise RuntimeError(
            f"GPU status unavailable: {status!r}"
        )

    used = int(status["vram_used_mb"])

    # RTX 3070 in this test machine: 8192 MiB.
    total = 8192
    return used, total - used


def synchronize() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def print_memory(label: str, baseline_mb: int) -> None:
    used, free = gpu_memory()

    print(
        f"{label}: "
        f"used={used} MB, "
        f"free={free} MB, "
        f"delta={used - baseline_mb:+d} MB",
        flush=True,
    )


def transcribe(
    label: str,
    engine: object,
    audio_path: Path,
    language: str,
    baseline_mb: int,
) -> None:
    synchronize()
    start = time.perf_counter()

    result = engine.transcribe_file(
        audio_path,
        language=language,
    )

    synchronize()
    elapsed = time.perf_counter() - start

    print(
        f"{label}: {elapsed:.3f} s",
        flush=True,
    )
    print(f"  Text: {result.text}", flush=True)
    print_memory(f"After {label}", baseline_mb)


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    for audio_path in (BG_AUDIO, EN_AUDIO):
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)

    whisper = None
    buzz = None

    synchronize()
    baseline_mb, _ = gpu_memory()

    print("=" * 72)
    print("DUAL STT RESIDENCY DIAGNOSTIC")
    print("=" * 72, flush=True)
    print_memory("Baseline", baseline_mb)

    try:
        print("\nLoading Whisper int8_float16...", flush=True)
        start = time.perf_counter()

        whisper = WhisperSttEngine(
            model_name="large-v3",
            device="cuda",
            compute_type="int8_float16",
        )

        synchronize()
        print(
            f"Whisper load: {time.perf_counter() - start:.3f} s",
            flush=True,
        )
        print_memory("After Whisper load", baseline_mb)

        _, free_mb = gpu_memory()

        if free_mb < MIN_FREE_BEFORE_BUZZ_MB:
            print(
                "SKIP: insufficient free VRAM "
                f"before Buzz load ({free_mb} MB).",
                flush=True,
            )
            return

        print("\nLoading Buzz...", flush=True)
        start = time.perf_counter()

        buzz = BuzzAsrSttEngine()

        synchronize()
        print(
            f"Buzz load: {time.perf_counter() - start:.3f} s",
            flush=True,
        )
        print_memory("After Buzz load", baseline_mb)

        print("\nBoth models are resident.", flush=True)

        transcribe(
            "BG inference 1",
            buzz,
            BG_AUDIO,
            "bg",
            baseline_mb,
        )

        transcribe(
            "EN inference",
            whisper,
            EN_AUDIO,
            "en",
            baseline_mb,
        )

        transcribe(
            "BG inference 2",
            buzz,
            BG_AUDIO,
            "bg",
            baseline_mb,
        )

    finally:
        print("\nCleaning up...", flush=True)

        buzz = None
        whisper = None

        gc.collect()
        torch.cuda.empty_cache()
        gc.collect()

        print_memory("After cleanup", baseline_mb)

    print("=" * 72)
    print("DIAGNOSTIC COMPLETED", flush=True)


if __name__ == "__main__":
    main()