import math
import wave
from pathlib import Path

import numpy as np
import torch
from transformers import (
    AutoModelForCTC,
    Wav2Vec2CTCTokenizer,
    Wav2Vec2FeatureExtractor,
)

from app.speech.stt.language_evidence import (
    CtcLanguageMetrics,
    LanguageEvidence,
)


DEFAULT_BG_MODEL_NAME = (
    "anuragshas/wav2vec2-large-xls-r-300m-bg"
)

DEFAULT_EN_MODEL_NAME = (
    "jonatasgrosman/wav2vec2-large-xlsr-53-english"
)


class CtcLanguageEvidenceProvider:
    """
    Produces paired Bulgarian/English acoustic language evidence.

    Responsibilities:
    - load the Bulgarian and English CTC models
    - validate and load 16 kHz mono 16-bit PCM WAV audio
    - run both CTC models
    - calculate acoustic metrics
    - return LanguageEvidence

    This provider does NOT:
    - decide BG / EN / MIXED
    - apply routing thresholds
    - produce the assistant's final transcript
    - execute commands
    """

    def __init__(
        self,
        bg_model_name: str = DEFAULT_BG_MODEL_NAME,
        en_model_name: str = DEFAULT_EN_MODEL_NAME,
        device: str = "cuda",
        dtype: torch.dtype = torch.float16,
    ) -> None:
        self._bg_model_name = bg_model_name
        self._en_model_name = en_model_name
        self._device = device
        self._dtype = dtype

        if (
            self._device == "cuda"
            and not torch.cuda.is_available()
        ):
            raise RuntimeError(
                "CUDA was requested but is not available."
            )

        (
            self._bg_feature_extractor,
            self._bg_tokenizer,
            self._bg_model,
            self._bg_blank_token_id,
        ) = self._load_model(
            self._bg_model_name
        )

        (
            self._en_feature_extractor,
            self._en_tokenizer,
            self._en_model,
            self._en_blank_token_id,
        ) = self._load_model(
            self._en_model_name
        )

    @property
    def bg_model_name(self) -> str:
        return self._bg_model_name

    @property
    def en_model_name(self) -> str:
        return self._en_model_name

    def analyze_file(
        self,
        audio_path: Path,
    ) -> LanguageEvidence:
        audio = self._load_wav(
            audio_path
        )

        bg_metrics = self._analyze_audio(
            audio=audio,
            feature_extractor=self._bg_feature_extractor,
            model=self._bg_model,
            blank_token_id=self._bg_blank_token_id,
        )

        en_metrics = self._analyze_audio(
            audio=audio,
            feature_extractor=self._en_feature_extractor,
            model=self._en_model,
            blank_token_id=self._en_blank_token_id,
        )

        return LanguageEvidence(
            bulgarian=bg_metrics,
            english=en_metrics,
        )

    def _load_model(
        self,
        model_name: str,
    ) -> tuple[
        Wav2Vec2FeatureExtractor,
        Wav2Vec2CTCTokenizer,
        AutoModelForCTC,
        int,
    ]:
        feature_extractor = (
            Wav2Vec2FeatureExtractor.from_pretrained(
                model_name
            )
        )

        tokenizer = (
            Wav2Vec2CTCTokenizer.from_pretrained(
                model_name
            )
        )

        model = AutoModelForCTC.from_pretrained(
            model_name,
            dtype=self._dtype,
            low_cpu_mem_usage=True,
        )

        model.to(self._device)
        model.eval()

        blank_token_id = tokenizer.pad_token_id

        if blank_token_id is None:
            raise RuntimeError(
                f"{model_name}: tokenizer has no "
                "pad_token_id."
            )

        return (
            feature_extractor,
            tokenizer,
            model,
            blank_token_id,
        )

    def _analyze_audio(
        self,
        audio: np.ndarray,
        feature_extractor: Wav2Vec2FeatureExtractor,
        model: AutoModelForCTC,
        blank_token_id: int,
    ) -> CtcLanguageMetrics:
        inputs = feature_extractor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
        )

        input_values = inputs.input_values.to(
            device=self._device,
            dtype=self._dtype,
        )

        with torch.inference_mode():
            logits = model(
                input_values
            ).logits

        return self._calculate_metrics(
            logits=logits,
            blank_token_id=blank_token_id,
        )

    @staticmethod
    def _calculate_metrics(
        logits: torch.Tensor,
        blank_token_id: int,
    ) -> CtcLanguageMetrics:
        probabilities = torch.softmax(
            logits.float(),
            dim=-1,
        )

        (
            max_probabilities,
            predicted_ids,
        ) = probabilities.max(
            dim=-1
        )

        blank_probabilities = probabilities[
            ...,
            blank_token_id,
        ]

        non_blank_mask = (
            predicted_ids != blank_token_id
        )

        blank_prediction_ratio = (
            (~non_blank_mask)
            .float()
            .mean()
            .item()
        )

        mean_blank_probability = (
            blank_probabilities
            .mean()
            .item()
        )

        non_blank_confidences = (
            max_probabilities[
                non_blank_mask
            ]
        )

        if non_blank_confidences.numel() > 0:
            mean_non_blank_confidence = (
                non_blank_confidences
                .mean()
                .item()
            )

            min_non_blank_confidence = (
                non_blank_confidences
                .min()
                .item()
            )
        else:
            mean_non_blank_confidence = 0.0
            min_non_blank_confidence = 0.0

        safe_probabilities = (
            probabilities.clamp_min(
                1e-12
            )
        )

        entropy = -(
            safe_probabilities
            * safe_probabilities.log()
        ).sum(
            dim=-1
        )

        vocabulary_size = (
            probabilities.shape[-1]
        )

        max_entropy = math.log(
            vocabulary_size
        )

        normalized_entropy = (
            entropy / max_entropy
        )

        if non_blank_mask.any():
            non_blank_entropy = (
                normalized_entropy[
                    non_blank_mask
                ]
                .mean()
                .item()
            )
        else:
            non_blank_entropy = 1.0

        uncertain_non_blank_mask = (
            non_blank_mask
            & (max_probabilities < 0.70)
        )

        non_blank_count = (
            non_blank_mask
            .sum()
            .item()
        )

        uncertain_non_blank_count = (
            uncertain_non_blank_mask
            .sum()
            .item()
        )

        if non_blank_count > 0:
            uncertain_non_blank_ratio = (
                uncertain_non_blank_count
                / non_blank_count
            )
        else:
            uncertain_non_blank_ratio = 1.0

        non_blank_token_rate = (
            non_blank_count
            / predicted_ids.numel()
        )

        return CtcLanguageMetrics(
            mean_non_blank_confidence=(
                mean_non_blank_confidence
            ),
            min_non_blank_confidence=(
                min_non_blank_confidence
            ),
            non_blank_entropy=(
                non_blank_entropy
            ),
            uncertain_non_blank_ratio=(
                uncertain_non_blank_ratio
            ),
            blank_prediction_ratio=(
                blank_prediction_ratio
            ),
            mean_blank_probability=(
                mean_blank_probability
            ),
            non_blank_token_rate=(
                non_blank_token_rate
            ),
        )

    @staticmethod
    def _load_wav(
        audio_path: Path,
    ) -> np.ndarray:
        with wave.open(
            str(audio_path),
            "rb",
        ) as wav_file:
            channels = (
                wav_file.getnchannels()
            )

            sample_width = (
                wav_file.getsampwidth()
            )

            sample_rate = (
                wav_file.getframerate()
            )

            frames = wav_file.readframes(
                wav_file.getnframes()
            )

        if channels != 1:
            raise ValueError(
                f"{audio_path.name}: expected mono, "
                f"got {channels} channels"
            )

        if sample_width != 2:
            raise ValueError(
                f"{audio_path.name}: expected "
                "16-bit PCM, "
                f"got {sample_width * 8}-bit"
            )

        if sample_rate != 16000:
            raise ValueError(
                f"{audio_path.name}: expected "
                "16000 Hz, "
                f"got {sample_rate} Hz"
            )

        audio = np.frombuffer(
            frames,
            dtype=np.int16,
        ).astype(
            np.float32
        )

        audio /= 32768.0

        return audio