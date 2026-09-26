import os
from dataclasses import dataclass
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
from app.speech.stt.buzzasr_engine import BuzzAsrSttEngine
from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)
from app.speech.stt.language_resolver import LanguageResolver
from app.speech.stt.managed import (
    ManagedLanguageEvidenceProvider,
    ManagedSttEngine,
)
from app.speech.stt.router import SttRouter
from app.speech.stt.service import SttService
from app.speech.stt.whisper_engine import WhisperSttEngine


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True, slots=True)
class SttRuntime:
    service: SttService
    model_manager: ModelManager


def create_stt_runtime() -> SttRuntime:
    manager = ModelManager()

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.BUZZ_BG,
            backend=ModelBackend.PYTORCH,
            estimated_vram_mb=3323,
        ),
        factory=lambda: BuzzAsrSttEngine(
            model_name=os.getenv(
                "SMART_VOICE_BUZZASR_MODEL",
                str(ROOT / "models" / "buzzasr-bulgarian"),
            ),
        ),
        lifecycle=PyTorchModelLifecycle(),
    )

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.WHISPER_LARGE_V3,
            backend=ModelBackend.CTRANSLATE2,
            estimated_vram_mb=3913,
        ),
        factory=lambda: WhisperSttEngine(
            model_name=os.getenv(
                "SMART_VOICE_WHISPER_MODEL",
                str(ROOT / "models" / "faster-whisper-large-v3"),
            ),
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
            bg_model_name=os.getenv(
                "SMART_VOICE_CTC_BG_MODEL",
                str(ROOT / "models" / "wav2vec2-bg"),
            ),
            en_model_name=os.getenv(
                "SMART_VOICE_CTC_EN_MODEL",
                str(ROOT / "models" / "wav2vec2-en"),
            ),
            device="cpu",
            dtype=torch.float32,
        ),
        lifecycle=PyTorchModelLifecycle(),
    )

    evidence_provider = ManagedLanguageEvidenceProvider(manager)

    buzz_engine = ManagedSttEngine(
        manager,
        ModelId.BUZZ_BG,
    )

    whisper_engine = ManagedSttEngine(
        manager,
        ModelId.WHISPER_LARGE_V3,
    )

    router = SttRouter(
        bulgarian_engine=buzz_engine,
        english_engine=whisper_engine,
        mixed_engine=whisper_engine,
    )

    service = SttService(
        evidence_provider=evidence_provider,
        language_resolver=LanguageResolver(),
        router=router,
    )

    return SttRuntime(
        service=service,
        model_manager=manager,
    )
