from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SttResult:
    """
    Normalized result returned by every STT engine.

    Assistant Core should consume this object instead of depending
    on model-specific return types.
    """

    text: str

    language: str | None = None
    language_confidence: float | None = None

    duration_seconds: float | None = None
    inference_seconds: float | None = None

    engine: str | None = None
    model: str | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )