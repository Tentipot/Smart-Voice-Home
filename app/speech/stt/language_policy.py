from dataclasses import dataclass
from enum import Enum


class SttLanguageMode(str, Enum):
    """
    High-level language modes understood by the STT layer.

    AUTO means that the language strategy is not known yet.
    MIXED means that BG+EN code-switching is expected.
    """

    AUTO = "auto"
    BULGARIAN = "bg"
    ENGLISH = "en"
    MIXED = "mixed"


@dataclass(frozen=True, slots=True)
class LanguagePolicy:
    """
    Language policy for one STT request.

    This is platform-level policy. It does not imply that every
    STT engine natively supports all of these options.
    """

    mode: SttLanguageMode

    allowed_languages: tuple[str, ...] = (
        "bg",
        "en",
    )

    preserve_original_language: bool = True

    def __post_init__(self) -> None:
        if not self.allowed_languages:
            raise ValueError(
                "allowed_languages must not be empty"
            )

        normalized = tuple(
            language.strip().lower()
            for language in self.allowed_languages
        )

        if any(
            not language
            for language in normalized
        ):
            raise ValueError(
                "allowed_languages contains "
                "an empty language code"
            )

        if len(set(normalized)) != len(normalized):
            raise ValueError(
                "allowed_languages contains "
                "duplicate language codes"
            )

        object.__setattr__(
            self,
            "allowed_languages",
            normalized,
        )

        if (
            self.mode == SttLanguageMode.BULGARIAN
            and "bg" not in normalized
        ):
            raise ValueError(
                "Bulgarian mode requires 'bg' "
                "in allowed_languages"
            )

        if (
            self.mode == SttLanguageMode.ENGLISH
            and "en" not in normalized
        ):
            raise ValueError(
                "English mode requires 'en' "
                "in allowed_languages"
            )

        if (
            self.mode == SttLanguageMode.MIXED
            and not {"bg", "en"}.issubset(normalized)
        ):
            raise ValueError(
                "Mixed BG+EN mode requires both "
                "'bg' and 'en' in allowed_languages"
            )

    @classmethod
    def bulgarian(cls) -> "LanguagePolicy":
        return cls(
            mode=SttLanguageMode.BULGARIAN,
        )

    @classmethod
    def english(cls) -> "LanguagePolicy":
        return cls(
            mode=SttLanguageMode.ENGLISH,
        )

    @classmethod
    def mixed(cls) -> "LanguagePolicy":
        return cls(
            mode=SttLanguageMode.MIXED,
        )

    @classmethod
    def auto(cls) -> "LanguagePolicy":
        return cls(
            mode=SttLanguageMode.AUTO,
        )