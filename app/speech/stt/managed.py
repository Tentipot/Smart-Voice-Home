from pathlib import Path

from app.resources.model_manager import ModelManager
from app.resources.model_types import ModelId
from app.speech.stt.base import SttEngine
from app.speech.stt.language_evidence import LanguageEvidence
from app.speech.stt.result import SttResult


class ManagedLanguageEvidenceProvider:
    """
    Provides language evidence through a temporary ModelManager lease.

    Releasing the lease does not unload the CTC resource. Residency and
    explicit unload remain ModelManager concerns.
    """

    def __init__(self, manager: ModelManager) -> None:
        self._manager = manager

    def analyze_file(self, audio_path: Path) -> LanguageEvidence:
        with self._manager.acquire(ModelId.CTC_LANGUAGE) as provider:
            return provider.analyze_file(audio_path)


class ManagedSttEngine(SttEngine):
    """
    Delegates transcription to a ModelManager-owned STT engine.

    Each transcription holds a temporary lease. The underlying resource
    may remain resident after the lease is released.
    """

    def __init__(
        self,
        manager: ModelManager,
        model_id: ModelId,
    ) -> None:
        if model_id not in (
            ModelId.BUZZ_BG,
            ModelId.WHISPER_LARGE_V3,
        ):
            raise ValueError(
                f"Unsupported managed STT model: {model_id}"
            )

        self._manager = manager
        self._model_id = model_id

    @property
    def engine_name(self) -> str:
        with self._manager.acquire(self._model_id) as engine:
            return engine.engine_name

    @property
    def model_name(self) -> str:
        with self._manager.acquire(self._model_id) as engine:
            return engine.model_name

    def transcribe_file(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> SttResult:
        with self._manager.acquire(self._model_id) as engine:
            return engine.transcribe_file(
                audio_path,
                language=language,
            )
