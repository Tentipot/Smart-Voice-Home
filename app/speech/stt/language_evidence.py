from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CtcLanguageMetrics:
    """
    Acoustic metrics produced by one language-specific CTC model.

    These values are evidence only. They do not decide which language
    the utterance belongs to.
    """

    mean_non_blank_confidence: float
    min_non_blank_confidence: float
    non_blank_entropy: float
    uncertain_non_blank_ratio: float
    blank_prediction_ratio: float
    mean_blank_probability: float
    non_blank_token_rate: float


@dataclass(frozen=True, slots=True)
class LanguageEvidence:
    """
    Paired acoustic evidence from the Bulgarian and English CTC models.

    Delta convention:

        delta = Bulgarian metric - English metric

    No thresholds or language-routing decisions belong in this class.
    It is intentionally a neutral evidence container.
    """

    bulgarian: CtcLanguageMetrics
    english: CtcLanguageMetrics

    @property
    def confidence_delta(self) -> float:
        return (
            self.bulgarian.mean_non_blank_confidence
            - self.english.mean_non_blank_confidence
        )

    @property
    def min_confidence_delta(self) -> float:
        return (
            self.bulgarian.min_non_blank_confidence
            - self.english.min_non_blank_confidence
        )

    @property
    def entropy_delta(self) -> float:
        return (
            self.bulgarian.non_blank_entropy
            - self.english.non_blank_entropy
        )

    @property
    def uncertain_delta(self) -> float:
        return (
            self.bulgarian.uncertain_non_blank_ratio
            - self.english.uncertain_non_blank_ratio
        )

    @property
    def blank_ratio_delta(self) -> float:
        return (
            self.bulgarian.blank_prediction_ratio
            - self.english.blank_prediction_ratio
        )

    @property
    def blank_probability_delta(self) -> float:
        return (
            self.bulgarian.mean_blank_probability
            - self.english.mean_blank_probability
        )

    @property
    def token_rate_delta(self) -> float:
        return (
            self.bulgarian.non_blank_token_rate
            - self.english.non_blank_token_rate
        )