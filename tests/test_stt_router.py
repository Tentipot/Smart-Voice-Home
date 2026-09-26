from pathlib import Path

from app.speech.stt import (
    LanguagePolicy,
    SttEngine,
    SttResult,
    SttRouter,
)


class FakeSttEngine(SttEngine):
    """
    Lightweight fake engine used only to verify routing logic.
    """

    def __init__(
        self,
        name: str,
    ) -> None:
        self._name = name

    @property
    def engine_name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return "fake-model"

    def transcribe_file(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> SttResult:
        return SttResult(
            text=f"handled-by-{self._name}",
            language=language,
            engine=self.engine_name,
            model=self.model_name,
            metadata={
                "audio_path": str(audio_path),
                "requested_language": language,
            },
        )


def main() -> None:
    bg_engine = FakeSttEngine(
        "fake-bg",
    )

    en_engine = FakeSttEngine(
        "fake-en",
    )

    mixed_engine = FakeSttEngine(
        "fake-mixed",
    )

    router = SttRouter(
        bulgarian_engine=bg_engine,
        english_engine=en_engine,
        mixed_engine=mixed_engine,
    )

    fake_audio = Path(
        "example.wav"
    )

    print("=" * 70)
    print("STT ROUTER TEST")
    print("=" * 70)
    print()

    bg_result = router.transcribe_file(
        fake_audio,
        policy=LanguagePolicy.bulgarian(),
    )

    print(
        "BG    :",
        bg_result.text,
        "| language =",
        bg_result.language,
    )

    en_result = router.transcribe_file(
        fake_audio,
        policy=LanguagePolicy.english(),
    )

    print(
        "EN    :",
        en_result.text,
        "| language =",
        en_result.language,
    )

    mixed_result = router.transcribe_file(
        fake_audio,
        policy=LanguagePolicy.mixed(),
    )

    print(
        "MIXED :",
        mixed_result.text,
        "| language =",
        mixed_result.language,
    )

    print()

    print("Testing AUTO rejection...")

    try:
        router.transcribe_file(
            fake_audio,
            policy=LanguagePolicy.auto(),
        )

    except ValueError as error:
        print(
            "AUTO  : correctly rejected"
        )
        print(
            "        ",
            error,
        )

    else:
        raise RuntimeError(
            "AUTO should have been rejected."
        )

    print()
    print("=" * 70)
    print("STT ROUTER TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()