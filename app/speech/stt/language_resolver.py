from dataclasses import dataclass
from enum import Enum

from app.speech.stt.language_evidence import (
    LanguageEvidence,
)
from app.speech.stt.language_policy import (
    LanguagePolicy,
)


class LanguageResolutionReason(str, Enum):
    ENGLISH_DETECTED = "english_detected"
    BULGARIAN_DETECTED = "bulgarian_detected"
    BULGARIAN_FAMILY_FALLBACK = "bulgarian_family_fallback"

    CTC_BULGARIAN_EVIDENCE = "ctc_bulgarian_evidence"
    CTC_ENGLISH_EVIDENCE = "ctc_english_evidence"
    CTC_AMBIGUOUS_EVIDENCE = "ctc_ambiguous_evidence"

    MIXED_EVIDENCE = "mixed_evidence"
    UNKNOWN_FALLBACK = "unknown_fallback"


@dataclass(frozen=True, slots=True)
class LanguageResolution:
    policy: LanguagePolicy
    reason: LanguageResolutionReason
    detected_language: str | None
    detected_confidence: float | None


class LanguageResolver:
    """
    Resolves language evidence into the assistant's supported
    STT language policy.

    Current user language profile:
        Bulgarian
        English

    Primary routing signal:
        paired BG/EN CTC acoustic evidence

    entropy_delta:
        Bulgarian non-blank entropy
        minus
        English non-blank entropy

    Calibrated routing policy:

        delta <= 0.003
            -> Bulgarian

        0.003 < delta < 0.043
            -> Mixed / ambiguous

        delta >= 0.043
            -> English

    The ambiguity zone prevents weak CTC evidence from forcing
    the audio into the wrong language-specific STT engine.

    These boundaries were calibrated against the local
    production-like BG/EN command dataset.

    This class does not execute commands.
    """

    CTC_BG_BOUNDARY = 0.003
    CTC_EN_BOUNDARY = 0.043

    BULGARIAN_FAMILY_FALLBACK_LANGUAGES = frozenset(
        {
            "ru",
            "uk",
            "be",
            "mk",
            "sr",
            "hr",
            "bs",
            "sl",
            "cs",
            "sk",
            "pl",
        }
    )

    def resolve_evidence(
        self,
        evidence: LanguageEvidence,
    ) -> LanguageResolution:
        """
        Resolve paired BG/EN CTC evidence.

        Strong Bulgarian evidence:
            entropy_delta <= CTC_BG_BOUNDARY

        Strong English evidence:
            entropy_delta >= CTC_EN_BOUNDARY

        Evidence between the calibrated boundaries is deliberately
        classified as MIXED instead of forcing a language-specific
        STT engine.
        """

        entropy_delta = evidence.entropy_delta

        if entropy_delta <= self.CTC_BG_BOUNDARY:
            return LanguageResolution(
                policy=LanguagePolicy.bulgarian(),
                reason=(
                    LanguageResolutionReason
                    .CTC_BULGARIAN_EVIDENCE
                ),
                detected_language="bg",
                detected_confidence=None,
            )

        if entropy_delta >= self.CTC_EN_BOUNDARY:
            return LanguageResolution(
                policy=LanguagePolicy.english(),
                reason=(
                    LanguageResolutionReason
                    .CTC_ENGLISH_EVIDENCE
                ),
                detected_language="en",
                detected_confidence=None,
            )

        return LanguageResolution(
            policy=LanguagePolicy.mixed(),
            reason=(
                LanguageResolutionReason
                .CTC_AMBIGUOUS_EVIDENCE
            ),
            detected_language=None,
            detected_confidence=None,
        )

    def resolve_detected_language(
        self,
        detected_language: str | None,
        confidence: float | None = None,
    ) -> LanguageResolution:
        language = self._normalize_language(
            detected_language
        )

        if language == "en":
            return LanguageResolution(
                policy=LanguagePolicy.english(),
                reason=(
                    LanguageResolutionReason
                    .ENGLISH_DETECTED
                ),
                detected_language=language,
                detected_confidence=confidence,
            )

        if language == "bg":
            return LanguageResolution(
                policy=LanguagePolicy.bulgarian(),
                reason=(
                    LanguageResolutionReason
                    .BULGARIAN_DETECTED
                ),
                detected_language=language,
                detected_confidence=confidence,
            )

        if (
            language
            in self.BULGARIAN_FAMILY_FALLBACK_LANGUAGES
        ):
            return LanguageResolution(
                policy=LanguagePolicy.bulgarian(),
                reason=(
                    LanguageResolutionReason
                    .BULGARIAN_FAMILY_FALLBACK
                ),
                detected_language=language,
                detected_confidence=confidence,
            )

        return LanguageResolution(
            policy=LanguagePolicy.bulgarian(),
            reason=(
                LanguageResolutionReason
                .UNKNOWN_FALLBACK
            ),
            detected_language=language,
            detected_confidence=confidence,
        )

    def resolve_mixed(
        self,
    ) -> LanguageResolution:
        return LanguageResolution(
            policy=LanguagePolicy.mixed(),
            reason=(
                LanguageResolutionReason
                .MIXED_EVIDENCE
            ),
            detected_language=None,
            detected_confidence=None,
        )

    @staticmethod
    def _normalize_language(
        language: str | None,
    ) -> str | None:
        if language is None:
            return None

        normalized = (
            language
            .strip()
            .lower()
        )

        if not normalized:
            return None

        return normalized