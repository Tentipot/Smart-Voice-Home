
import gc
import time
import weakref
from pathlib import Path
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


AUDIO_DIR = Path("data/stt_benchmark")

TEST_CASES = (
    (ModelId.BUZZ_BG, "test_031.wav", "bg"),
    (ModelId.WHISPER_LARGE_V3, "test_041.wav", "en"),
    (ModelId.CTC_LANGUAGE, "test_031.wav", None),
)


def synchronize() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def gpu_used_mb() -> int:
    status = get_gpu_status()

    if not status.get("available"):
        raise RuntimeError(
            f"GPU status unavailable: {status!r}"
        )

    return int(status["vram_used_mb"])


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


def process_audio(
    manager: ModelManager,
    model_id: ModelId,
    audio_path: Path,
    language: str | None,
    label: str,
) -> float:
    handle = manager.acquire(model_id)

    try:
        synchronize()
        start = time.perf_counter()

        if model_id == ModelId.CTC_LANGUAGE:
            evidence = handle.resource.analyze_file(
                audio_path
            )
            output: Any = evidence
        else:
            result = handle.resource.transcribe_file(
                audio_path,
                language=language,
            )
            output = result.text

        synchronize()
        elapsed = time.perf_counter() - start

        print(
            f"{label:<24} {elapsed:>8.3f} s",
            flush=True,
        )
        print(f"  Output: {output}", flush=True)

        return elapsed

    finally:
        handle.release()


def run_case(
    manager: ModelManager,
    model_id: ModelId,
    filename: str,
    language: str | None,
    baseline_mb: int,
) -> None:
    audio_path = AUDIO_DIR / filename

    if not audio_path.is_file():
        raise FileNotFoundError(audio_path)

    print()
    print("=" * 72)
    print(f"MODEL: {model_id.value}")
    print(f"AUDIO: {audio_path}")
    print("=" * 72, flush=True)

    synchronize()
    start = time.perf_counter()
    handle = manager.acquire(model_id)
    synchronize()
    cold_load = time.perf_counter() - start

    resource_ref = weakref.ref(handle.resource)

    handle.release()

    print(f"Cold load: {cold_load:.3f} s")
    print(
        f"VRAM after load: "
        f"{gpu_used_mb() - baseline_mb:+d} MB",
        flush=True,
    )

    first = process_audio(
        manager,
        model_id,
        audio_path,
        language,
        "First inference",
    )

    second = process_audio(
        manager,
        model_id,
        audio_path,
        language,
        "Resident inference",
    )

    synchronize()
    start = time.perf_counter()
    unloaded = manager.unload(model_id)
    synchronize()
    unload_time = time.perf_counter() - start

    gc.collect()

    if not unloaded:
        raise AssertionError(
            f"Model was not loaded: {model_id.value}"
        )

    if resource_ref() is not None:
        raise AssertionError(
            f"Resource retained: {model_id.value}"
        )

    print(f"Unload: {unload_time:.3f} s")
    print(
        f"VRAM after unload: "
        f"{gpu_used_mb() - baseline_mb:+d} MB",
        flush=True,
    )

    synchronize()
    start = time.perf_counter()
    reloaded_handle = manager.acquire(model_id)
    synchronize()
    reload_time = time.perf_counter() - start

    reloaded_handle.release()

    print(f"Reload: {reload_time:.3f} s")

    after_reload = process_audio(
        manager,
        model_id,
        audio_path,
        language,
        "Inference after reload",
    )

    synchronize()
    final_start = time.perf_counter()
    manager.unload(model_id)
    synchronize()
    final_unload = time.perf_counter() - final_start

    gc.collect()

    print()
    print(f"Cold first command: {cold_load + first:.3f} s")
    print(f"Resident command:   {second:.3f} s")
    print(
        f"Reloaded command:   "
        f"{reload_time + after_reload:.3f} s"
    )
    print(f"Final unload:       {final_unload:.3f} s")
    print(
        f"Final VRAM delta:   "
        f"{gpu_used_mb() - baseline_mb:+d} MB",
        flush=True,
    )


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    manager = ModelManager()
    register_models(manager)

    synchronize()
    baseline_mb = gpu_used_mb()

    print("=" * 72)
    print("STT COMMAND LATENCY DIAGNOSTIC")
    print(f"Baseline VRAM: {baseline_mb} MB")
    print("=" * 72, flush=True)

    for model_id, filename, language in TEST_CASES:
        run_case(
            manager,
            model_id,
            filename,
            language,
            baseline_mb,
        )

    print()
    print("STT COMMAND LATENCY DIAGNOSTIC COMPLETED")


if __name__ == "__main__":
    main()