"""Wake-word detectors for AuroraCapture.

Two interchangeable detectors decide whether an audio window contains the
wake word:

- CtcWakeDetector (default): CTC keyword spotting on the Bulgarian wav2vec2
  CTC model. It does not transcribe; it scores how well the keyword can be
  aligned anywhere in the window. Offline test on 2026-09-26: 69/69 wake
  phrases found, 0/80 false accepts on the held-out split
  (docs/PROJECT_HISTORY.md, tools/diagnostics/diagnose_ctc_wake_kws.py).
- WhisperWakeDetector: the previous behaviour, a Whisper large-v3 float16
  transcription followed by a text match. Kept as a fallback.

Select with SMART_VOICE_WAKE_DETECTOR=ctc|whisper (default: ctc).
"""

from __future__ import annotations

import os
import re
import tempfile
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import soundfile as sf
import torch


SAMPLE_RATE = 16000

ROOT = Path(__file__).resolve().parents[3]

DEFAULT_CTC_MODEL = ROOT / "models" / "wav2vec2-bg"

# Bulgarian CTC spellings observed for "Аурора" / English "Aurora".
DEFAULT_CTC_KEYWORDS = (
    "аурора",
    "орора",
    "аврора",
)

# Calibrated on 2026-09-26 (CPU float32): worst wake phrase 1.71,
# closest phrase without the wake word 2.15. Lower score = better match.
DEFAULT_CTC_THRESHOLD = 2.08

WAKE_WORDS = {
    "аурора",
    "aurora",
    "أورورا",
    "أرور",
    "أورور",
}

WAKE_PREFIXES = (
    "аурора",
    "aurora",
)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize(
        "NFKC",
        text,
    ).casefold()

    return re.sub(
        r"[^\w]+",
        " ",
        text,
        flags=re.UNICODE,
    ).strip()


def contains_wake(text: str) -> bool:
    words = normalize_text(text).split()

    if any(
        word in WAKE_WORDS
        for word in words
    ):
        return True

    return any(
        word.startswith(WAKE_PREFIXES)
        for word in words
    )


def keyword_deficit(
    log_probs: np.ndarray,
    tokens: list[int],
    blank: int,
) -> float:
    """
    Per-token log-probability deficit of the best CTC alignment of a
    keyword anywhere in the window (free start and end).

    The deficit is measured against the unconstrained best path over the
    same frames, so 0 means the greedy CTC output contains the keyword.
    """

    deficits = (
        log_probs.max(axis=1, keepdims=True)
        - log_probs
    )

    labels = [blank]
    for token in tokens:
        labels += [token, blank]

    cost = deficits[:, labels]
    states = len(labels)

    best = np.inf
    previous = np.full(states, np.inf)

    for frame in range(cost.shape[0]):
        current = np.full(states, np.inf)

        for state in range(states):
            candidates = [previous[state]]

            if state >= 1:
                candidates.append(previous[state - 1])

            if (
                state >= 2
                and labels[state] != blank
                and labels[state] != labels[state - 2]
            ):
                candidates.append(previous[state - 2])

            if state <= 1:
                candidates.append(0.0)

            current[state] = (
                min(candidates)
                + cost[frame, state]
            )

        best = min(
            best,
            current[-1],
            current[-2],
        )
        previous = current

    return float(best) / len(tokens)


@dataclass(frozen=True)
class WakeDecision:
    detected: bool
    text: str
    language: str = ""
    score: float | None = None


class WakeDetector(Protocol):
    name: str

    def detect(
        self,
        audio: np.ndarray,
    ) -> WakeDecision:
        ...


class CtcWakeDetector:
    """Wake-word detection by CTC keyword spotting."""

    name = "ctc"

    def __init__(
        self,
        model_name: str | Path | None = None,
        *,
        device: str = "cpu",
        dtype: torch.dtype = torch.float32,
        keywords: tuple[str, ...] = DEFAULT_CTC_KEYWORDS,
        threshold: float = DEFAULT_CTC_THRESHOLD,
    ) -> None:
        from transformers import (
            AutoModelForCTC,
            Wav2Vec2CTCTokenizer,
            Wav2Vec2FeatureExtractor,
        )

        model_name = str(
            model_name
            or os.getenv(
                "SMART_VOICE_CTC_BG_MODEL",
                DEFAULT_CTC_MODEL,
            )
        )
        local = Path(model_name).is_dir()

        self._device = device
        self._dtype = dtype
        self._threshold = threshold

        self._features = Wav2Vec2FeatureExtractor.from_pretrained(
            model_name,
            local_files_only=local,
        )
        tokenizer = Wav2Vec2CTCTokenizer.from_pretrained(
            model_name,
            local_files_only=local,
        )
        self._model = AutoModelForCTC.from_pretrained(
            model_name,
            dtype=dtype,
            low_cpu_mem_usage=True,
            local_files_only=local,
        )
        self._model.to(device)
        self._model.eval()

        self._blank = tokenizer.pad_token_id
        vocab = tokenizer.get_vocab()
        self._keywords = {
            keyword: [vocab[char] for char in keyword]
            for keyword in keywords
        }

    @property
    def threshold(self) -> float:
        return self._threshold

    def log_probs(
        self,
        audio: np.ndarray,
    ) -> np.ndarray:
        inputs = self._features(
            audio,
            sampling_rate=SAMPLE_RATE,
            return_tensors="pt",
        )
        values = inputs.input_values.to(
            device=self._device,
            dtype=self._dtype,
        )

        with torch.inference_mode():
            logits = self._model(values).logits[0].float()

        return torch.log_softmax(
            logits,
            dim=-1,
        ).cpu().numpy()

    def score(
        self,
        log_probs: np.ndarray,
    ) -> tuple[str, float]:
        return min(
            (
                (
                    keyword,
                    keyword_deficit(
                        log_probs,
                        tokens,
                        self._blank,
                    ),
                )
                for keyword, tokens in self._keywords.items()
            ),
            key=lambda item: item[1],
        )

    def detect(
        self,
        audio: np.ndarray,
    ) -> WakeDecision:
        keyword, score = self.score(
            self.log_probs(audio)
        )

        return WakeDecision(
            detected=score < self._threshold,
            text=f"{keyword} score={score:.2f}",
            score=score,
        )


class WhisperWakeDetector:
    """Previous wake detection: Whisper transcription + text match."""

    name = "whisper"

    def __init__(
        self,
        temp_dir: Path | None = None,
    ) -> None:
        from app.speech.stt.whisper_engine import WhisperSttEngine

        self._whisper = WhisperSttEngine(
            model_name="large-v3",
            device="cuda",
            compute_type="float16",
            beam_size=1,
        )
        self._temp_dir = temp_dir or Path(tempfile.gettempdir()) / "aurora_wake"
        self._temp_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def detect(
        self,
        audio: np.ndarray,
    ) -> WakeDecision:
        temp_path = self._temp_dir / f"wake_{time.monotonic_ns()}.wav"

        try:
            sf.write(
                str(temp_path),
                audio,
                SAMPLE_RATE,
                subtype="PCM_16",
            )
            result = self._whisper.transcribe_file(
                temp_path,
                language=None,
            )

        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

        return WakeDecision(
            detected=contains_wake(result.text),
            text=result.text,
            language=result.language or "",
        )


def create_wake_detector(
    kind: str | None = None,
) -> WakeDetector:
    kind = (
        kind
        or os.getenv("SMART_VOICE_WAKE_DETECTOR", "ctc")
    ).strip().lower()

    if kind == "ctc":
        return CtcWakeDetector()

    if kind == "whisper":
        return WhisperWakeDetector()

    raise ValueError(
        f"Unknown wake detector: {kind!r} "
        "(expected 'ctc' or 'whisper')"
    )
