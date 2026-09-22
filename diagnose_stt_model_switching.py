
import gc
import time
import weakref
from collections.abc import Callable
from typing import Any

import torch

from app.resources.ctranslate2_model_lifecycle import (
    CTranslate2ModelLifecycle,
)
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
from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)
from app.speech.stt.whisper_engine import WhisperSttEngine


SETTLE_SECONDS = 2.0


def gpu_used_mb() -> int:
    status = get_gpu_status()

    if not status.get("available"):
        raise RuntimeError(
            f"GPU status unavailable: {status!r}"
        )

    return int(status["vram_used_mb"])


def settle() -> None:
    torch.cuda.synchronize()
    time.sleep(SETTLE_SECONDS)


def measure(label: str, baseline: int) -> int:
    settle()
    used = gpu_used_mb()

    print(
        f"{label:<28} "
        f"used={used:>5} MB "
        f"delta={used - baseline:>+5} MB",
        flush=True,
    )

    return used


def register_models(manager: ModelManager) -> None:
    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.BUZZ_BG,
            backend=ModelBackend.PYTORCH,
            estimated_vram_mb=3323,
        ),
        factory=BuzzAsrSttEngine,
        lifecycle=PyTorchModelLifecycle(),
    )

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.WHISPER_LARGE_V3,
            backend=ModelBackend.CTRANSLATE2,
            estimated_vram_mb=3913,
        ),
        factory=WhisperSttEngine,
        lifecycle=CTranslate2ModelLifecycle(),
    )

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.CTC_LANGUAGE,
            backend=ModelBackend.PYTORCH,
            estimated_vram_mb=1314,
        ),
        factory=CtcLanguageEvidenceProvider,
        lifecycle=PyTorchModelLifecycle(),
    )


def run_model(
    manager: ModelManager,
    model_id: ModelId,
    baseline: int,
) -> dict[str, Any]:
    print()
    print("-" * 72)
    print(f"MODEL: {model_id.value}", flush=True)
    print("-" * 72)

    start = time.perf_counter()
    handle = manager.acquire(model_id)
    cold_seconds = time.perf_counter() - start

    resource_ref = weakref.ref(handle.resource)

    assert manager.active_leases(model_id) == 1

    loaded_mb = measure("COLD LOAD", baseline)

    handle.release()

    assert manager.active_leases(model_id) == 0

    resident_mb = measure("LEASE RELEASE", baseline)

    start = time.perf_counter()
    warm_handle = manager.acquire(model_id)
    warm_seconds = time.perf_counter() - start

    assert warm_handle.resource is resource_ref()

    warm_handle.release()

    warm_mb = measure("WARM ACQUIRE", baseline)

    start = time.perf_counter()
    assert manager.unload(model_id) is True
    unload_seconds = time.perf_counter() - start

    gc.collect()

    destroyed = resource_ref() is None

    unloaded_mb = measure("UNLOAD", baseline)

    if not destroyed:
        raise AssertionError(
            f"Resource retained after unload: {model_id.value}"
        )

    print(
        f"Cold load: {cold_seconds:.3f} s | "
        f"Warm acquire: {warm_seconds:.6f} s | "
        f"Unload: {unload_seconds:.3f} s",
        flush=True,
    )

    print(f"Resource destroyed: {destroyed}")

    return {
        "model": model_id.value,
        "cold_seconds": cold_seconds,
        "warm_seconds": warm_seconds,
        "unload_seconds": unload_seconds,
        "loaded_delta_mb": loaded_mb - baseline,
        "resident_delta_mb": resident_mb - baseline,
        "warm_delta_mb": warm_mb - baseline,
        "unloaded_delta_mb": unloaded_mb - baseline,
    }


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    manager = ModelManager()
    register_models(manager)

    print()
    print("=" * 72)
    print("STT MODEL SWITCHING: TIME + VRAM")
    print("=" * 72)
    print(
        "Models run sequentially. No audio inference is performed."
    )
    print(
        "Timing excludes the two-second VRAM settling interval."
    )
    print()

    settle()
    baseline = gpu_used_mb()

    print(f"BASELINE: {baseline} MB", flush=True)

    results: list[dict[str, Any]] = []

    sequence = (
        ModelId.BUZZ_BG,
        ModelId.WHISPER_LARGE_V3,
        ModelId.CTC_LANGUAGE,
    )

    total_start = time.perf_counter()

    for model_id in sequence:
        result = run_model(manager, model_id, baseline)
        results.append(result)

    total_wall_seconds = time.perf_counter() - total_start

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)

    for result in results:
        print()
        print(result["model"])
        print(
            f"  Cold load     : "
            f"{result['cold_seconds']:.3f} s"
        )
        print(
            f"  Warm acquire  : "
            f"{result['warm_seconds']:.6f} s"
        )
        print(
            f"  Unload        : "
            f"{result['unload_seconds']:.3f} s"
        )
        print(
            f"  Loaded VRAM   : "
            f"{result['loaded_delta_mb']:+d} MB"
        )
        print(
            f"  After unload  : "
            f"{result['unloaded_delta_mb']:+d} MB"
        )

    operation_seconds = sum(
        result["cold_seconds"]
        + result["warm_seconds"]
        + result["unload_seconds"]
        for result in results
    )

    print()
    print(
        f"Total load/acquire/unload: "
        f"{operation_seconds:.3f} s"
    )
    print(
        f"Total diagnostic wall time: "
        f"{total_wall_seconds:.3f} s"
    )
    print()
    print("STT SWITCHING DIAGNOSTIC COMPLETED")


if __name__ == "__main__":
    main()