import gc
import time

import torch

from app.resources.system_monitor import (
    get_gpu_status,
)
from app.speech.stt.buzzasr_engine import (
    BuzzAsrSttEngine,
)


SETTLE_SECONDS = 2.0


def get_vram_used_mb() -> int:
    gpu = get_gpu_status()

    if not gpu.get("available"):
        raise RuntimeError(
            "NVIDIA GPU status is unavailable: "
            f"{gpu.get('reason', 'unknown reason')}"
        )

    return int(
        gpu["vram_used_mb"]
    )


def print_measurement(
    label: str,
    *,
    baseline_mb: int,
) -> int:
    used_mb = get_vram_used_mb()
    delta_mb = used_mb - baseline_mb

    print(
        f"{label:<28} "
        f"used={used_mb:>5} MB  "
        f"delta={delta_mb:>+5} MB"
    )

    return used_mb


def settle() -> None:
    time.sleep(
        SETTLE_SECONDS
    )


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available."
        )

    print()
    print("=" * 72)
    print("BUZZASR SAME-PROCESS GPU LIFECYCLE DIAGNOSTIC")
    print("=" * 72)
    print()
    print(
        "NVML measures total GPU VRAM usage."
    )
    print(
        "Delta values are relative to the baseline "
        "measured by this process."
    )
    print()

    settle()

    baseline_mb = get_vram_used_mb()

    print(
        f"{'BASELINE':<28} "
        f"used={baseline_mb:>5} MB  "
        f"delta={0:>+5} MB"
    )

    print()
    print(
        "Loading BuzzAsrSttEngine..."
    )
    print()

    load_start = time.perf_counter()

    engine = BuzzAsrSttEngine()

    torch.cuda.synchronize()

    load_seconds = (
        time.perf_counter()
        - load_start
    )

    settle()

    loaded_mb = print_measurement(
        "BUZZ ENGINE LOADED",
        baseline_mb=baseline_mb,
    )

    print()
    print(
        f"Engine load time: "
        f"{load_seconds:.3f} s"
    )

    print()
    print(
        "Deleting engine and collecting "
        "Python objects..."
    )
    print()

    del engine

    gc.collect()

    settle()

    after_gc_mb = print_measurement(
        "AFTER DEL + GC",
        baseline_mb=baseline_mb,
    )

    print()
    print(
        "Clearing PyTorch CUDA cache..."
    )
    print()

    torch.cuda.empty_cache()

    torch.cuda.synchronize()

    gc.collect()

    settle()

    after_cache_mb = print_measurement(
        "AFTER EMPTY_CACHE",
        baseline_mb=baseline_mb,
    )

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print()

    load_delta_mb = (
        loaded_mb - baseline_mb
    )

    retained_after_gc_mb = (
        after_gc_mb - baseline_mb
    )

    retained_after_cache_mb = (
        after_cache_mb - baseline_mb
    )

    released_after_gc_mb = (
        loaded_mb - after_gc_mb
    )

    released_after_cache_mb = (
        loaded_mb - after_cache_mb
    )

    print(
        f"Load delta              : "
        f"{load_delta_mb:+d} MB"
    )

    print(
        f"Released after del + GC : "
        f"{released_after_gc_mb:+d} MB"
    )

    print(
        f"Retained after del + GC : "
        f"{retained_after_gc_mb:+d} MB"
    )

    print(
        f"Released after cache    : "
        f"{released_after_cache_mb:+d} MB"
    )

    print(
        f"Retained after cache    : "
        f"{retained_after_cache_mb:+d} MB"
    )

    print()
    print(
        "Interpretation:"
    )
    print(
        "- 'Load delta' estimates the additional total "
        "VRAM while BuzzASR is resident."
    )
    print(
        "- 'Retained after del + GC' shows what remains "
        "before explicit PyTorch cache cleanup."
    )
    print(
        "- 'Retained after cache' shows what remains "
        "after torch.cuda.empty_cache()."
    )
    print(
        "- Small non-zero differences can come from "
        "CUDA runtime state or unrelated GPU activity."
    )

    print()


if __name__ == "__main__":
    main()