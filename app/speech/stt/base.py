from abc import ABC, abstractmethod
from pathlib import Path

from app.speech.stt.result import SttResult


class SttEngine(ABC):
    """
    Common interface for speech-to-text engines.

    Implementations may use GPU, CPU, local models, remote services,
    or other inference backends.

    Assistant Core must depend on this interface rather than on a
    specific STT implementation.
    """

    @property
    @abstractmethod
    def engine_name(self) -> str:
        """
        Stable identifier for the STT engine implementation.
        """
        raise NotImplementedError

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Human-readable model identifier.
        """
        raise NotImplementedError

    @abstractmethod
    def transcribe_file(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> SttResult:
        """
        Transcribe an audio file.

        language:
            Optional language hint such as "bg" or "en".
            None means that the engine may perform automatic
            language handling when supported.

        Returns:
            A normalized SttResult.
        """
        raise NotImplementedError