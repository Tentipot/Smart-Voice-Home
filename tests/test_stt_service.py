from pathlib import Path

from app.speech.stt.base import SttEngine
from app.speech.stt.language_evidence import (
    CtcLanguageMetrics,
    LanguageEvidence,
)
from app.speech.stt.language_resolver import (
    LanguageResolver,
)
from app.speech.stt.result import SttResult
from app.speech.stt.router import SttRouter
from app.speech.stt.service import SttService


TEST_AUDIO_PATH = Path("fake_audio.wav")


class FakeEvidenceProvider:
    def __init__(
        self,
        evidence: LanguageEvidence,
    ) -> None:
        self._evidence = evidence
        self.calls = 0

    def analyze_file(
        self,
        audio_path: Path,
    ) -> LanguageEvidence:
        assert audio_path == TEST_AUDIO_PATH

        self.calls += 1

        return self._evidence


class FakeSttEngine(SttEngine):
    def __init__(
        self,
        *,
        name: str,
        transcript: str,
    ) -> None:
        self._name = name
        self._transcript = transcript
        self.calls: list[
            tuple[Path, str | None]
        ] = []

    @property
    def engine_name(self) -> str:
        return self._name

    @property
    def model_name(self) -> str:
        return f"{self._name}-model"

    def transcribe_file(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> SttResult:
        self.calls.append(
            (
                audio_path,
                language,
            )
        )

        return SttResult(
            text=self._transcript,
            language=language,
            engine=self.engine_name,
            model=self.model_name,
        )


def make_metrics(
    *,
    entropy: float,
) -> CtcLanguageMetrics:
    return CtcLanguageMetrics(
        mean_non_blank_confidence=0.90,
        min_non_blank_confidence=0.70,
        non_blank_entropy=entropy,
        uncertain_non_blank_ratio=0.10,
        blank_prediction_ratio=0.50,
        mean_blank_probability=0.50,
        non_blank_token_rate=0.50,
    )


def make_evidence(
    *,
    bg_entropy: float,
    en_entropy: float,
) -> LanguageEvidence:
    return LanguageEvidence(
        bulgarian=make_metrics(
            entropy=bg_entropy,
        ),
        english=make_metrics(
            entropy=en_entropy,
        ),
    )


def make_service(
    evidence: LanguageEvidence,
) -> tuple[
    SttService,
    FakeEvidenceProvider,
    FakeSttEngine,
    FakeSttEngine,
    FakeSttEngine,
]:
    evidence_provider = FakeEvidenceProvider(
        evidence
    )

    bg_engine = FakeSttEngine(
        name="fake-bg",
        transcript="ROUTED-BG",
    )

    en_engine = FakeSttEngine(
        name="fake-en",
        transcript="ROUTED-EN",
    )

    mixed_engine = FakeSttEngine(
        name="fake-mixed",
        transcript="ROUTED-MIXED",
    )

    router = SttRouter(
        bulgarian_engine=bg_engine,
        english_engine=en_engine,
        mixed_engine=mixed_engine,
    )

    service = SttService(
        evidence_provider=evidence_provider,
        language_resolver=LanguageResolver(),
        router=router,
    )

    return (
        service,
        evidence_provider,
        bg_engine,
        en_engine,
        mixed_engine,
    )


def test_bulgarian_routing() -> None:
    evidence = make_evidence(
        bg_entropy=0.10,
        en_entropy=0.20,
    )

    (
        service,
        provider,
        bg_engine,
        en_engine,
        mixed_engine,
    ) = make_service(
        evidence
    )

    result = service.transcribe_file(
        TEST_AUDIO_PATH
    )

    assert provider.calls == 1

    assert result.text == "ROUTED-BG"
    assert result.language == "bg"
    assert result.engine == "fake-bg"

    assert bg_engine.calls == [
        (
            TEST_AUDIO_PATH,
            "bg",
        )
    ]

    assert en_engine.calls == []
    assert mixed_engine.calls == []

    print("BG ROUTING: PASS")


def test_english_routing() -> None:
    evidence = make_evidence(
        bg_entropy=0.20,
        en_entropy=0.10,
    )

    (
        service,
        provider,
        bg_engine,
        en_engine,
        mixed_engine,
    ) = make_service(
        evidence
    )

    result = service.transcribe_file(
        TEST_AUDIO_PATH
    )

    assert provider.calls == 1

    assert result.text == "ROUTED-EN"
    assert result.language == "en"
    assert result.engine == "fake-en"

    assert bg_engine.calls == []

    assert en_engine.calls == [
        (
            TEST_AUDIO_PATH,
            "en",
        )
    ]

    assert mixed_engine.calls == []

    print("EN ROUTING: PASS")


def test_language_evidence_is_preserved() -> None:
    evidence = make_evidence(
        bg_entropy=0.10,
        en_entropy=0.20,
    )

    (
        service,
        provider,
        _,
        _,
        _,
    ) = make_service(
        evidence
    )

    (
        returned_evidence,
        resolution,
    ) = service.analyze_language(
        TEST_AUDIO_PATH
    )

    assert provider.calls == 1

    assert returned_evidence is evidence

    assert (
        returned_evidence.entropy_delta
        == evidence.entropy_delta
    )

    assert resolution.policy.mode.value == "bg"
    assert resolution.detected_language == "bg"

    print("EVIDENCE PRESERVATION: PASS")


def main() -> None:
    print()
    print("=" * 60)
    print("STT SERVICE INTEGRATION TEST")
    print("=" * 60)
    print()

    test_bulgarian_routing()
    test_english_routing()
    test_language_evidence_is_preserved()

    print()
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()