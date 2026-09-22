from dataclasses import dataclass
from enum import Enum


class ModelId(str, Enum):
    """
    Stable logical identifiers for model-backed resources.

    ModelId identifies the role of a model inside the Assistant
    Platform. It is intentionally independent from model repository
    names, filesystem paths, inference backends, and devices.
    """

    CTC_LANGUAGE = "ctc_language"
    BUZZ_BG = "buzz_bg"
    WHISPER_LARGE_V3 = "whisper_large_v3"


class ModelBackend(str, Enum):
    """
    Inference backend that owns the model's runtime resources.

    Backend identity matters because different runtimes require
    different lifecycle and GPU cleanup strategies.
    """

    PYTORCH = "pytorch"
    CTRANSLATE2 = "ctranslate2"


@dataclass(frozen=True, slots=True)
class ModelDescriptor:
    """
    Static metadata describing a model-backed resource.

    estimated_vram_mb is an observed planning estimate, not a hard
    allocation guarantee. Runtime resource decisions must eventually
    use actual system/GPU measurements and an appropriate safety
    margin.
    """

    model_id: ModelId
    backend: ModelBackend
    estimated_vram_mb: int | None = None

    def __post_init__(self) -> None:
        if (
            self.estimated_vram_mb is not None
            and self.estimated_vram_mb < 0
        ):
            raise ValueError(
                "estimated_vram_mb must be "
                "non-negative or None."
            )