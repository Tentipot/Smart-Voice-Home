from pathlib import Path

from app.speech.stt.base import SttEngine
from app.speech.stt.language_policy import (
    LanguagePolicy,
    SttLanguageMode,
)
from app.speech.stt.result import SttResult


class SttRouter:
    """
    Routes an STT request to the appropriate engine according
    to LanguagePolicy.

    The router does not know implementation details of the
    underlying models. It depends only on SttEngine.
    """

    def __init__(
        self,
        *,
        bulgarian_engine: SttEngine,
        english_engine: SttEngine,
        mixed_engine: SttEngine,
    ) -> None:
        self._bulgarian_engine = bulgarian_engine
        self._english_engine = english_engine
        self._mixed_engine = mixed_engine

    def transcribe_file(
        self,
        audio_path: Path,
        *,
        policy: LanguagePolicy,
    ) -> SttResult:
        """
        Route one audio file according to the supplied policy.

        AUTO is intentionally not resolved here yet.
        Automatic BG / EN / MIXED classification will be a
        separate policy component.
        """

        mode = policy.mode

        if mode == SttLanguageMode.BULGARIAN:
            return self._bulgarian_engine.transcribe_file(
                audio_path,
                language="bg",
            )

        if mode == SttLanguageMode.ENGLISH:
            return self._english_engine.transcribe_file(
                audio_path,
                language="en",
            )

        if mode == SttLanguageMode.MIXED:
            return self._mixed_engine.transcribe_file(
                audio_path,
                language=None,
            )

        if mode == SttLanguageMode.AUTO:
            raise ValueError(
                "AUTO language policy must be resolved to "
                "BULGARIAN, ENGLISH, or MIXED before STT routing."
            )

        raise ValueError(
            f"Unsupported STT language mode: {mode!r}"
        )