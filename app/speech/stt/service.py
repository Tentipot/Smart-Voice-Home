from pathlib import Path

from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)
from app.speech.stt.language_evidence import (
    LanguageEvidence,
)
from app.speech.stt.language_resolver import (
    LanguageResolution,
    LanguageResolver,
)
from app.speech.stt.result import SttResult
from app.speech.stt.router import SttRouter


class SttService:
    """
    Orchestrates automatic language evidence, language resolution,
    STT routing, and transcription.

    Responsibilities:
    - obtain paired BG/EN acoustic language evidence
    - resolve that evidence into LanguagePolicy
    - route the request through SttRouter
    - return the normalized SttResult

    This service does NOT:
    - create or load STT engines
    - manage model lifecycle or GPU resources
    - execute assistant intents
    - expose HTTP endpoints
    - perform mixed-language entity resolution

    All model-owning dependencies are injected by the caller so that
    model lifecycle can later be controlled by a dedicated resource
    or model manager.
    """

    def __init__(
        self,
        *,
        evidence_provider: CtcLanguageEvidenceProvider,
        language_resolver: LanguageResolver,
        router: SttRouter,
    ) -> None:
        self._evidence_provider = evidence_provider
        self._language_resolver = language_resolver
        self._router = router

    def analyze_language(
        self,
        audio_path: Path,
    ) -> tuple[
        LanguageEvidence,
        LanguageResolution,
    ]:
        """
        Analyze one audio file and resolve its language policy.

        The acoustic evidence is returned together with the resolution
        so that it is not discarded after routing and can later be used
        by higher-level intent/entity resolution.
        """

        evidence = self._evidence_provider.analyze_file(
            audio_path
        )

        resolution = (
            self._language_resolver.resolve_evidence(
                evidence
            )
        )

        return evidence, resolution

    def transcribe_file(
        self,
        audio_path: Path,
    ) -> SttResult:
        """
        Automatically resolve the language policy and transcribe
        one audio file through SttRouter.
        """

        _, resolution = self.analyze_language(
            audio_path
        )

        return self._router.transcribe_file(
            audio_path,
            policy=resolution.policy,
        )