import argparse
import gc
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
from app.speech.stt.language_resolver import LanguageResolver
from app.speech.stt.router import SttRouter
from app.speech.stt.service import SttService
from app.speech.stt.whisper_engine import WhisperSttEngine


BG_AUDIO = Path("data/language_dataset/bg_001_20260923_212640_017014.wav")
EN_AUDIO = Path("data/language_dataset/en_002_20260923_212654_840062.wav")


def synchronize():
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def report_gpu(label):
    status = get_gpu_status()

    if status.get("available"):
        print(
            f"{label}: VRAM used="
            f"{status['vram_used_mb']} MB",
            flush=True,
        )
    else:
        print(
            f"{label}: GPU status unavailable: {status!r}",
            flush=True,
        )


class TimedEvidenceProvider:
    def __init__(self, provider):
        self.provider = provider
        self.last_seconds = None

    def analyze_file(self, audio_path):
        start = time.perf_counter()

        try:
            evidence = self.provider.analyze_file(audio_path)
            self.last_evidence = evidence
            return evidence
        finally:
            self.last_seconds = (
                time.perf_counter() - start
            )


class TimedResolver:
    def __init__(self, resolver):
        self.resolver = resolver
        self.last_seconds = None
        self.last_resolution = None

    def resolve_evidence(self, evidence):
        start = time.perf_counter()

        try:
            resolution = self.resolver.resolve_evidence(
                evidence
            )
            self.last_resolution = resolution
            return resolution
        finally:
            self.last_seconds = (
                time.perf_counter() - start
            )


class TimedRouter:
    def __init__(self, router):
        self.router = router
        self.last_seconds = None

    def transcribe_file(self, audio_path, *, policy):
        start = time.perf_counter()

        try:
            result = self.router.transcribe_file(
                audio_path,
                policy=policy,
            )
            synchronize()
            return result
        finally:
            self.last_seconds = (
                time.perf_counter() - start
            )


def run_case(
    label,
    audio_path,
    service,
    evidence_provider,
    resolver,
    router,
):
    evidence_provider.last_seconds = None
    resolver.last_seconds = None
    resolver.last_resolution = None
    router.last_seconds = None

    synchronize()
    start = time.perf_counter()

    result = service.transcribe_file(audio_path)

    synchronize()
    total_seconds = time.perf_counter() - start

    resolution = resolver.last_resolution
    evidence = evidence_provider.last_evidence

    print(
        f"CTC entropy: BG={evidence.bulgarian.non_blank_entropy:.6f}, "
        f"EN={evidence.english.non_blank_entropy:.6f}, "
        f"delta={evidence.entropy_delta:.6f}",
        flush=True,
    )
    print(
        f"CTC boundaries: BG <= {resolver.resolver.CTC_BG_BOUNDARY:.3f}, "
        f"EN >= {resolver.resolver.CTC_EN_BOUNDARY:.3f}",
        flush=True,
    )

    print(f"\n--- {label} ---", flush=True)
    print(
        f"CTC CPU: "
        f"{evidence_provider.last_seconds:.3f} s",
        flush=True,
    )
    print(
        f"LanguageResolver: "
        f"{resolver.last_seconds:.6f} s",
        flush=True,
    )
    print(
        f"STT via router: "
        f"{router.last_seconds:.3f} s",
        flush=True,
    )
    print(
        f"TOTAL STT SERVICE: "
        f"{total_seconds:.3f} s",
        flush=True,
    )
    print(
        f"Resolved policy: "
        f"{resolution.policy!r}",
        flush=True,
    )
    print(
        f"Resolution reason: "
        f"{resolution.reason!r}",
        flush=True,
    )
    print(
        f"STT engine: {result.engine!r}; model: {result.model!r}",
        flush=True,
    )
    print(
        f"STT language: {result.language!r}; "
        f"confidence: {result.language_confidence!r}",
        flush=True,
    )
    print(
        f"STT metadata: {result.metadata!r}",
        flush=True,
    )
    print(
        f"Transcription: {result.text!r}",
        flush=True,
    )

    report_gpu("After command")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audio",
        type=Path,
        help="Run one STT case on the specified WAV file.",
    )
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable.")

    if args.audio is not None:
        cases = (("Live capture", args.audio),)
    else:
        cases = (
            ("BG first", BG_AUDIO),
            ("EN first", EN_AUDIO),
            ("BG warm", BG_AUDIO),
            ("EN warm", EN_AUDIO),
        )

    for _, audio_path in cases:
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)

    manager = ModelManager()
    handles = {}

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
        factory=lambda: WhisperSttEngine(
            compute_type="int8_float16",
        ),
        lifecycle=CTranslate2ModelLifecycle(),
    )

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.CTC_LANGUAGE,
            backend=ModelBackend.PYTORCH,
            estimated_vram_mb=0,
        ),
        factory=lambda: CtcLanguageEvidenceProvider(
            device="cpu",
            dtype=torch.float32,
        ),
        lifecycle=PyTorchModelLifecycle(),
    )

    print(
        "=== STT SERVICE LATENCY: "
        "CTC CPU + BUZZ/WHISPER GPU ===",
        flush=True,
    )
    report_gpu("Baseline")

    try:
        for model_id in (
            ModelId.WHISPER_LARGE_V3,
            ModelId.BUZZ_BG,
            ModelId.CTC_LANGUAGE,
        ):
            start = time.perf_counter()

            handles[model_id] = manager.acquire(
                model_id
            )

            print(
                f"Loaded {model_id}: "
                f"{time.perf_counter() - start:.3f} s",
                flush=True,
            )
            report_gpu("After load")

        evidence_provider = TimedEvidenceProvider(
            handles[ModelId.CTC_LANGUAGE].resource
        )

        resolver = TimedResolver(
            LanguageResolver()
        )

        router = TimedRouter(
            SttRouter(
                bulgarian_engine=(
                    handles[ModelId.BUZZ_BG].resource
                ),
                english_engine=(
                    handles[
                        ModelId.WHISPER_LARGE_V3
                    ].resource
                ),
                mixed_engine=(
                    handles[
                        ModelId.WHISPER_LARGE_V3
                    ].resource
                ),
            )
        )

        service = SttService(
            evidence_provider=evidence_provider,
            language_resolver=resolver,
            router=router,
        )

        for label, audio_path in cases:
            run_case(
                label,
                audio_path,
                service,
                evidence_provider,
                resolver,
                router,
            )

    finally:
        print("\n=== CLEANUP ===", flush=True)

        # Remove references held by service and diagnostic wrappers.
        for name in (
            "service",
            "router",
            "resolver",
            "evidence_provider",
        ):
            if name in locals():
                del locals()[name]

        for handle in handles.values():
            try:
                handle.release()
            except Exception as exc:
                print(
                    f"Release error: {exc!r}",
                    flush=True,
                )

        handles.clear()

        for model_id in (
            ModelId.CTC_LANGUAGE,
            ModelId.BUZZ_BG,
            ModelId.WHISPER_LARGE_V3,
        ):
            try:
                manager.unload(model_id)
                print(
                    f"Unloaded: {model_id}",
                    flush=True,
                )
            except Exception as exc:
                print(
                    f"Unload error: {model_id}: {exc!r}",
                    flush=True,
                )

        gc.collect()
        torch.cuda.empty_cache()
        synchronize()
        report_gpu("After cleanup")


if __name__ == "__main__":
    main()