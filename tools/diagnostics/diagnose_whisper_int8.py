import gc
import time
import weakref
from pathlib import Path

import torch

from app.resources.system_monitor import get_gpu_status
from app.speech.stt.whisper_engine import WhisperSttEngine


AUDIO_PATH = Path("data/stt_benchmark/test_041.wav")


def gpu_used_mb() -> int:
    status = get_gpu_status()

    if not status.get("available"):
        raise RuntimeError(
            f"GPU status unavailable: {status!r}"
        )

    return int(status["vram_used_mb"])


def free_ram_gb() -> float:
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)

    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(
        ctypes.byref(status)
    ):
        raise OSError("Cannot read Windows memory status.")

    return status.ullAvailPhys / (1024 ** 3)


def synchronize() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def print_memory(label: str, baseline_vram: int) -> None:
    used = gpu_used_mb()

    print(
        f"{label}: "
        f"VRAM used={used} MB, "
        f"VRAM delta={used - baseline_vram:+d} MB, "
        f"free RAM={free_ram_gb():.2f} GiB",
        flush=True,
    )


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    if not AUDIO_PATH.is_file():
        raise FileNotFoundError(AUDIO_PATH)

    engine = None
    engine_ref = None

    synchronize()
    baseline_vram = gpu_used_mb()

    print("=" * 72)
    print("WHISPER LARGE-V3 INT8_FLOAT16 DIAGNOSTIC")
    print(f"Audio: {AUDIO_PATH}")
    print("=" * 72, flush=True)

    print_memory("Baseline", baseline_vram)

    try:
        synchronize()
        start = time.perf_counter()

        engine = WhisperSttEngine(
            model_name="large-v3",
            device="cuda",
            compute_type="int8_float16",
        )

        synchronize()
        load_seconds = time.perf_counter() - start
        engine_ref = weakref.ref(engine)

        print(f"Load time: {load_seconds:.3f} s", flush=True)
        print_memory("After load", baseline_vram)

        for run_number in (1, 2):
            synchronize()
            start = time.perf_counter()

            result = engine.transcribe_file(
                AUDIO_PATH,
                language="en",
            )

            synchronize()
            elapsed = time.perf_counter() - start

            print(
                f"Inference {run_number}: {elapsed:.3f} s",
                flush=True,
            )
            print(f"  Text: {result.text}", flush=True)
            print_memory(
                f"After inference {run_number}",
                baseline_vram,
            )

    finally:
        engine = None
        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        gc.collect()

        print_memory("After cleanup", baseline_vram)

        if engine_ref is not None:
            print(
                f"Engine released: {engine_ref() is None}",
                flush=True,
            )

    print("=" * 72)
    print("DIAGNOSTIC COMPLETED", flush=True)


if __name__ == "__main__":
    main()