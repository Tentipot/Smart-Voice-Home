import gc
import threading
import time
from pathlib import Path

import torch

from app.resources.system_monitor import get_gpu_status
from app.speech.stt.buzzasr_engine import BuzzAsrSttEngine
from app.speech.stt.whisper_engine import WhisperSttEngine


AUDIO_PATH = Path("data/stt_benchmark/diagnostic_32s.wav")

# Do not attempt to load Buzz if the available VRAM is already low.
MIN_FREE_BEFORE_BUZZ_MB = 4000

# Approximate sampling interval for the observed VRAM peak.
SAMPLE_INTERVAL_SECONDS = 0.05


def gpu_memory() -> tuple[int, int]:
    status = get_gpu_status()

    if not status.get("available"):
        raise RuntimeError(
            f"GPU status unavailable: {status!r}"
        )

    used = int(status["vram_used_mb"])
    total = 8192  # RTX 3070 in this machine

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


def transcribe_with_peak(
    label: str,
    engine: object,
    language: str,
    baseline_mb: int,
) -> None:
    stop_event = threading.Event()
    peak_used_mb = [gpu_memory()[0]]
    monitor_errors = []

    def monitor_memory() -> None:
        while not stop_event.wait(SAMPLE_INTERVAL_SECONDS):
            try:
                used, _ = gpu_memory()
                peak_used_mb[0] = max(peak_used_mb[0], used)
            except Exception as exc:
                monitor_errors.append(str(exc))
                return

    monitor = threading.Thread(
        target=monitor_memory,
        name="vram-monitor",
        daemon=True,
    )

    synchronize()
    start = time.perf_counter()
    monitor.start()

    try:
        result = engine.transcribe_file(
            AUDIO_PATH,
            language=language,
        )
        synchronize()
        elapsed = time.perf_counter() - start
    finally:
        stop_event.set()
        monitor.join()

    used_after, _ = gpu_memory()
    peak_used_mb[0] = max(peak_used_mb[0], used_after)

    print(f"{label}: {elapsed:.3f} s", flush=True)
    print(f"  Text: {result.text}", flush=True)
    print(
        f"  Observed peak VRAM: {peak_used_mb[0]} MB",
        flush=True,
    )

    if monitor_errors:
        print(
            f"  VRAM monitor warning: {monitor_errors[0]}",
            flush=True,
        )

    print_memory(f"After {label}", baseline_mb)


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    if not AUDIO_PATH.is_file():
        raise FileNotFoundError(AUDIO_PATH)

    whisper = None
    buzz = None

    synchronize()
    baseline_mb, _ = gpu_memory()

    print("=" * 72)
    print("DUAL STT — 32-SECOND AUDIO DIAGNOSTIC")
    print(f"Audio: {AUDIO_PATH}")
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
                "SKIP: insufficient free VRAM before Buzz load "
                f"({free_mb} MB).",
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

        transcribe_with_peak(
            "BG 32-second inference",
            buzz,
            "bg",
            baseline_mb,
        )

        transcribe_with_peak(
            "EN 32-second inference",
            whisper,
            "en",
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