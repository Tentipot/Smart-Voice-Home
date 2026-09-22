import gc
import threading
import time
from pathlib import Path

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


BG_AUDIO = Path("data/stt_benchmark/test_031.wav")
EN_AUDIO = Path("data/stt_benchmark/test_041.wav")
LONG_AUDIO = Path("data/stt_benchmark/diagnostic_32s.wav")

SAMPLE_INTERVAL = 0.05
MIN_FREE_MB = 700
TOTAL_VRAM_MB = 8192


def synchronize():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def used_mb():
    status = get_gpu_status()

    if not status.get("available"):
        raise RuntimeError(f"GPU status unavailable: {status!r}")

    return int(status["vram_used_mb"])


def report(label):
    used = used_mb()
    free = TOTAL_VRAM_MB - used

    print(
        f"{label}: used={used} MB, "
        f"estimated_free={free} MB",
        flush=True,
    )

    return free


def measure(label, operation):
    stop = threading.Event()
    samples = []

    def sampler():
        while not stop.is_set():
            try:
                samples.append(used_mb())
            except Exception as exc:
                print(
                    f"{label}: sampler error: {exc!r}",
                    flush=True,
                )
                break

            stop.wait(SAMPLE_INTERVAL)

    synchronize()
    before = used_mb()

    thread = threading.Thread(
        target=sampler,
        daemon=True,
    )
    thread.start()

    start = time.perf_counter()

    try:
        result = operation()
        synchronize()
    finally:
        elapsed = time.perf_counter() - start
        stop.set()
        thread.join(timeout=2.0)

    after = used_mb()
    peak = max([before, after, *samples])

    print(
        f"{label}: time={elapsed:.3f}s, "
        f"before={before} MB, "
        f"after={after} MB, "
        f"observed_peak={peak} MB, "
        f"estimated_free_at_peak={TOTAL_VRAM_MB - peak} MB",
        flush=True,
    )

    return result


def enough_memory(label):
    free = report(f"Before {label}")

    if free < MIN_FREE_MB:
        print(
            f"SKIP {label}: estimated free VRAM "
            f"{free} MB < {MIN_FREE_MB} MB",
            flush=True,
        )
        return False

    return True


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    for path in (BG_AUDIO, EN_AUDIO, LONG_AUDIO):
        if not path.is_file():
            raise FileNotFoundError(path)

    manager = ModelManager()

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.WHISPER_LARGE_V3,
            backend=ModelBackend.CTRANSLATE2,
            estimated_vram_mb=3913,
        ),
        factory=lambda: WhisperSttEngine(
            compute_type="int8_float16",
        ),
        lifecycle=CTranslate2ModelLifecycle(),
    )

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

    handles = {}
    print("=== TRIPLE GPU RESIDENCY ===", flush=True)
    report("Baseline")

    try:
        # Load the two larger models first.
        handles[ModelId.WHISPER_LARGE_V3] = measure(
            "Load Whisper",
            lambda: manager.acquire(
                ModelId.WHISPER_LARGE_V3
            ),
        )

        handles[ModelId.BUZZ_BG] = measure(
            "Load Buzz",
            lambda: manager.acquire(ModelId.BUZZ_BG),
        )

        # Check memory before attempting the third model.
        if not enough_memory("CTC load"):
            print(
                "STOP: insufficient reserve for third model.",
                flush=True,
            )
            return

        # CTC previously needed approximately 1.2 GB to load.
        if TOTAL_VRAM_MB - used_mb() < 1800:
            print(
                "STOP: less than 1800 MB available "
                "before CTC load.",
                flush=True,
            )
            return

        handles[ModelId.CTC_LANGUAGE] = measure(
            "Load CTC",
            lambda: manager.acquire(ModelId.CTC_LANGUAGE),
        )

        report("All three models loaded")

        # Do not start inference if the remaining reserve is small.
        if not enough_memory("short inference"):
            print(
                "STOP: all three loaded, "
                "but inference was not attempted.",
                flush=True,
            )
            return

        ctc = handles[ModelId.CTC_LANGUAGE].resource
        buzz = handles[ModelId.BUZZ_BG].resource
        whisper = handles[ModelId.WHISPER_LARGE_V3].resource

        evidence = measure(
            "CTC BG short",
            lambda: ctc.analyze_file(BG_AUDIO),
        )
        print(f"CTC BG evidence: {evidence!r}", flush=True)

        if not enough_memory("Buzz BG short"):
            return

        bg_result = measure(
            "Buzz BG short",
            lambda: buzz.transcribe_file(
                BG_AUDIO,
                language="bg",
            ),
        )
        print(f"Buzz BG text: {bg_result.text!r}", flush=True)

        if not enough_memory("Whisper EN short"):
            return

        en_result = measure(
            "Whisper EN short",
            lambda: whisper.transcribe_file(
                EN_AUDIO,
                language="en",
            ),
        )
        print(f"Whisper EN text: {en_result.text!r}", flush=True)

        # Longer inference can require additional temporary VRAM.
        # Require a larger reserve than for short commands.
        if TOTAL_VRAM_MB - used_mb() < 1200:
            print(
                "SKIP 32s diagnostic: "
                "less than 1200 MB estimated free VRAM.",
                flush=True,
            )
            return

        long_result = measure(
            "Whisper 32s diagnostic",
            lambda: whisper.transcribe_file(
                LONG_AUDIO,
                language="en",
            ),
        )
        print(
            f"Whisper 32s text: {long_result.text!r}",
            flush=True,
        )

        report("All three resident after inference")

    except torch.cuda.OutOfMemoryError as exc:
        print(
            f"CUDA OOM: {exc!r}",
            flush=True,
        )

    finally:
        print("=== CLEANUP ===", flush=True)

        for handle in handles.values():
            try:
                handle.release()
            except Exception as exc:
                print(f"Release error: {exc!r}", flush=True)

        handles.clear()

        for model_id in (
            ModelId.CTC_LANGUAGE,
            ModelId.BUZZ_BG,
            ModelId.WHISPER_LARGE_V3,
        ):
            try:
                manager.unload(model_id)
                print(f"Unloaded: {model_id}", flush=True)
            except Exception as exc:
                print(
                    f"Unload error for {model_id}: {exc!r}",
                    flush=True,
                )

        gc.collect()
        torch.cuda.empty_cache()
        synchronize()
        report("After cleanup")


if __name__ == "__main__":
    main()