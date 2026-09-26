from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class SttTranscription:
    """One transcription and its routing evidence, not an approved command.

    Evidence contains aggregate acoustic metrics, not word alignment or
    semantic confidence. All fields belong to the same service invocation.
    """

    audio_path: Path
    result: SttResult
    evidence: LanguageEvidence
    resolution: LanguageResolution


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

        return self.transcribe_with_evidence(audio_path).result

    def transcribe_with_evidence(
        self,
        audio_path: Path,
    ) -> SttTranscription:
        """Preserve evidence for downstream review without a second CTC pass.

        This does not resolve entities, validate intent or authorize actions.
        No per-request state is retained on the service instance.
        """
        audio_path = Path(audio_path)
        evidence, resolution = self.analyze_language(
            audio_path
        )

        result = self._router.transcribe_file(
            audio_path,
            policy=resolution.policy,
        )
        return SttTranscription(
            audio_path=audio_path,
            result=result,
            evidence=evidence,
            resolution=resolution,
        )
