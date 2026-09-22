import gc
import threading
import time
from pathlib import Path

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
from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)


AUDIO_DIR = Path("data/stt_benchmark")
BG_AUDIO = AUDIO_DIR / "test_031.wav"
EN_AUDIO = AUDIO_DIR / "test_041.wav"
LONG_AUDIO = AUDIO_DIR / "diagnostic_32s.wav"

SAMPLE_INTERVAL_SECONDS = 0.05


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


def report_vram(label: str) -> None:
    used = gpu_used_mb()
    print(f"{label}: VRAM used={used} MB", flush=True)


def run_measured(label: str, operation):
    stop_event = threading.Event()
    samples = []
    sampler_errors = []

    def sample_gpu() -> None:
        while not stop_event.is_set():
            try:
                samples.append(gpu_used_mb())
            except Exception as exc:
                sampler_errors.append(repr(exc))
                break

            stop_event.wait(SAMPLE_INTERVAL_SECONDS)

    synchronize()
    before_mb = gpu_used_mb()

    sampler = threading.Thread(
        target=sample_gpu,
        daemon=True,
    )
    sampler.start()

    start = time.perf_counter()

    try:
        result = operation()
        synchronize()
    finally:
        elapsed = time.perf_counter() - start
        stop_event.set()
        sampler.join(timeout=2.0)

    after_mb = gpu_used_mb()
    observed_peak_mb = max(
        [before_mb, after_mb, *samples]
    )

    print(
        f"{label}: "
        f"time={elapsed:.3f}s, "
        f"before={before_mb} MB, "
        f"after={after_mb} MB, "
        f"observed_peak={observed_peak_mb} MB",
        flush=True,
    )

    if sampler_errors:
        print(
            f"{label}: sampler_errors={sampler_errors!r}",
            flush=True,
        )

    return result


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    for audio_path in (BG_AUDIO, EN_AUDIO, LONG_AUDIO):
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)

    manager = ModelManager()

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
            model_id=ModelId.CTC_LANGUAGE,
            backend=ModelBackend.PYTORCH,
            estimated_vram_mb=1314,
        ),
        factory=CtcLanguageEvidenceProvider,
        lifecycle=PyTorchModelLifecycle(),
    )

    buzz_handle = None
    ctc_handle = None

    print("=== BUZZ + CTC GPU RESIDENCY ===", flush=True)
    report_vram("Baseline")

    try:
        buzz_handle = run_measured(
            "Load Buzz",
            lambda: manager.acquire(ModelId.BUZZ_BG),
        )
        report_vram("After Buzz load")

        ctc_handle = run_measured(
            "Load CTC",
            lambda: manager.acquire(ModelId.CTC_LANGUAGE),
        )
        report_vram("After CTC load")

        buzz = buzz_handle.resource
        ctc = ctc_handle.resource

        ctc_bg = run_measured(
            "CTC BG short",
            lambda: ctc.analyze_file(BG_AUDIO),
        )
        print(f"CTC BG evidence: {ctc_bg!r}", flush=True)

        buzz_bg = run_measured(
            "Buzz BG short #1",
            lambda: buzz.transcribe_file(
                BG_AUDIO,
                language="bg",
            ),
        )
        print(
            f"Buzz BG text #1: {buzz_bg.text!r}",
            flush=True,
        )

        ctc_en = run_measured(
            "CTC EN short",
            lambda: ctc.analyze_file(EN_AUDIO),
        )
        print(f"CTC EN evidence: {ctc_en!r}", flush=True)

        buzz_bg_again = run_measured(
            "Buzz BG short #2",
            lambda: buzz.transcribe_file(
                BG_AUDIO,
                language="bg",
            ),
        )
        print(
            f"Buzz BG text #2: {buzz_bg_again.text!r}",
            flush=True,
        )

        buzz_long = run_measured(
            "Buzz BG 32s diagnostic",
            lambda: buzz.transcribe_file(
                LONG_AUDIO,
                language="bg",
            ),
        )
        print(
            f"Buzz 32s text: {buzz_long.text!r}",
            flush=True,
        )

        report_vram("Both models resident after inference")

    finally:
        print("=== CLEANUP ===", flush=True)

        if ctc_handle is not None:
            ctc_handle.release()
            ctc_handle = None

        if buzz_handle is not None:
            buzz_handle.release()
            buzz_handle = None

        for model_id in (
            ModelId.CTC_LANGUAGE,
            ModelId.BUZZ_BG,
        ):
            try:
                manager.unload(model_id)
                print(f"Unloaded: {model_id}", flush=True)
            except Exception as exc:
                print(
                    f"Unload failed for {model_id}: {exc!r}",
                    flush=True,
                )

        gc.collect()
        torch.cuda.empty_cache()
        synchronize()
        report_vram("After cleanup")


if __name__ == "__main__":
    main()