
import gc
import time
import weakref

import torch

from app.resources.model_manager import ModelManager
from app.resources.model_types import (
    ModelBackend,
    ModelDescriptor,
    ModelId,
)
from app.resources.pytorch_model_lifecycle import (
    PyTorchModelLifecycle,
)
from app.resources.system_monitor import get_gpu_status
from app.speech.stt.buzzasr_engine import BuzzAsrSttEngine


MODEL_ID = ModelId.BUZZ_BG
SETTLE_SECONDS = 2.0


def get_vram_used_mb() -> int:
    gpu = get_gpu_status()

    if not gpu.get("available"):
        raise RuntimeError(
            "NVIDIA GPU status is unavailable: "
            f"{gpu.get('reason', 'unknown reason')}"
        )

    return int(gpu["vram_used_mb"])


def settle() -> None:
    torch.cuda.synchronize()
    time.sleep(SETTLE_SECONDS)


def measure(label: str, baseline_mb: int) -> int:
    settle()

    used_mb = get_vram_used_mb()
    delta_mb = used_mb - baseline_mb

    print(
        f"{label:<28} "
        f"used={used_mb:>5} MB  "
        f"delta={delta_mb:>+5} MB",
        flush=True,
    )

    return used_mb


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    print()
    print("=" * 72)
    print("BUZZASR MODEL MANAGER GPU LIFECYCLE DIAGNOSTIC")
    print("=" * 72)
    print()
    print("NVML measures total GPU VRAM usage.")
    print("Deltas are relative to the initial baseline.")
    print("Avoid other GPU-intensive applications during the test.")
    print()

    baseline_mb = get_vram_used_mb()

    print(
        f"{'BASELINE':<28} "
        f"used={baseline_mb:>5} MB  "
        f"delta={0:>+5} MB"
    )

    factory_calls = 0

    def factory() -> BuzzAsrSttEngine:
        nonlocal factory_calls

        factory_calls += 1

        print(
            f"\nLoading Buzz generation {factory_calls}...",
            flush=True,
        )

        return BuzzAsrSttEngine()

    manager = ModelManager()

    manager.register(
        descriptor=ModelDescriptor(
            model_id=MODEL_ID,
            backend=ModelBackend.PYTORCH,
            estimated_vram_mb=3323,
        ),
        factory=factory,
        lifecycle=PyTorchModelLifecycle(),
    )

    print()
    print("Acquiring Buzz for the first time...")

    load_start = time.perf_counter()

    first_handle = manager.acquire(MODEL_ID)

    first_load_seconds = time.perf_counter() - load_start

    first_ref = weakref.ref(first_handle.resource)

    assert factory_calls == 1
    assert manager.active_leases(MODEL_ID) == 1

    loaded_mb = measure(
        "FIRST ACQUIRE",
        baseline_mb,
    )

    print(
        f"First acquire time: {first_load_seconds:.3f} s"
    )

    first_handle.release()

    assert manager.active_leases(MODEL_ID) == 0
    assert first_ref() is not None

    resident_mb = measure(
        "AFTER LEASE RELEASE",
        baseline_mb,
    )

    print()
    print("Acquiring the resident Buzz model again...")

    reuse_start = time.perf_counter()

    second_handle = manager.acquire(MODEL_ID)

    reuse_seconds = time.perf_counter() - reuse_start

    assert second_handle.resource is first_ref()
    assert factory_calls == 1

    reused_mb = measure(
        "RESIDENT REUSE",
        baseline_mb,
    )

    print(
        f"Resident acquire time: {reuse_seconds:.6f} s"
    )

    second_handle.release()

    assert manager.active_leases(MODEL_ID) == 0

    print()
    print("Explicitly unloading Buzz through ModelManager...")

    unload_start = time.perf_counter()

    unloaded = manager.unload(MODEL_ID)

    unload_seconds = time.perf_counter() - unload_start

    assert unloaded is True
    assert manager.is_loaded(MODEL_ID) is False

    gc.collect()

    resource_destroyed = first_ref() is None

    after_unload_mb = measure(
        "AFTER MANAGER UNLOAD",
        baseline_mb,
    )

    print(
        f"Manager unload time: {unload_seconds:.3f} s"
    )
    print(
        f"Python engine object destroyed: {resource_destroyed}"
    )

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print()

    print(f"Factory calls             : {factory_calls}")
    print(f"First load delta          : {loaded_mb - baseline_mb:+d} MB")
    print(f"After lease release       : {resident_mb - baseline_mb:+d} MB")
    print(f"After resident reuse      : {reused_mb - baseline_mb:+d} MB")
    print(f"After manager unload      : {after_unload_mb - baseline_mb:+d} MB")
    print(f"Released from loaded state: {loaded_mb - after_unload_mb:+d} MB")
    print(f"Engine object destroyed   : {resource_destroyed}")

    print()
    print(
        "Note: total GPU usage can include CUDA runtime state "
        "and unrelated GPU activity."
    )

    if not resource_destroyed:
        raise AssertionError(
            "Buzz engine is still referenced after manager unload."
        )

    print()
    print("BUZZ MODEL MANAGER DIAGNOSTIC COMPLETED")


if __name__ == "__main__":
    main()