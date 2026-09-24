import time
import wave
import os
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

from app.speech.stt.base import SttEngine
from app.speech.stt.result import SttResult


class BuzzAsrSttEngine(SttEngine):
    """
    Bulgarian STT engine backed by BuzzASR/bulgarian.

    This engine is intended for Bulgarian speech.
    The model is loaded once and reused for subsequent requests.
    """

    def __init__(
        self,
        model_name: str | None = None,
        *,
        device: str = "cuda",
        dtype: torch.dtype = torch.float16,
    ) -> None:
        configured_name = model_name or os.getenv(
            "SMART_VOICE_BUZZASR_MODEL",
            "BuzzASR/bulgarian",
        )
        self._model_name = configured_name
        local_files_only = Path(configured_name).is_dir()
        self._device = device
        self._dtype = dtype

        load_start = time.perf_counter()

        self._processor = AutoProcessor.from_pretrained(
            configured_name,
            local_files_only=local_files_only,
        )

        self._model = (
            AutoModelForSpeechSeq2Seq.from_pretrained(
                configured_name,
                dtype=dtype,
                low_cpu_mem_usage=True,
                use_safetensors=True,
                local_files_only=local_files_only,
            )
        )

        self._model.to(device)
        self._model.eval()

        if device == "cuda":
            torch.cuda.synchronize()

        self._load_seconds = (
            time.perf_counter() - load_start
        )

    @property
    def engine_name(self) -> str:
        return "buzzasr-transformers"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def load_seconds(self) -> float:
        return self._load_seconds

    def transcribe_file(
        self,
        audio_path: Path,
        *,
        language: str | None = None,
    ) -> SttResult:
        audio_path = Path(audio_path)

        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        if language not in (None, "bg"):
            raise ValueError(
                "BuzzAsrSttEngine supports Bulgarian only. "
                f"Requested language: {language!r}"
            )

        audio, duration_seconds = self._load_wav(
            audio_path
        )

        inputs = self._processor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
            return_attention_mask=True,
        )

        model_inputs = {
            key: value.to(
                device=self._device,
                dtype=(
                    self._dtype
                    if value.dtype.is_floating_point
                    else value.dtype
                ),
            )
            for key, value in inputs.items()
        }

        if self._device == "cuda":
            torch.cuda.synchronize()

        start = time.perf_counter()

        with torch.inference_mode():
            generated_ids = self._model.generate(
                **model_inputs,
                max_new_tokens=128,
            )

        if self._device == "cuda":
            torch.cuda.synchronize()

        inference_seconds = (
            time.perf_counter() - start
        )

        text = self._processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        return SttResult(
            text=text,
            language="bg",
            language_confidence=None,
            duration_seconds=duration_seconds,
            inference_seconds=inference_seconds,
            engine=self.engine_name,
            model=self.model_name,
            metadata={
                "requested_language": language,
                "device": self._device,
                "dtype": str(self._dtype),
            },
        )

    @staticmethod
    def _load_wav(
        audio_path: Path,
    ) -> tuple[np.ndarray, float]:
        """
        Load 16 kHz mono 16-bit PCM WAV without TorchCodec.
        """

        with wave.open(
            str(audio_path),
            "rb",
        ) as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frame_count = wav_file.getnframes()
            frames = wav_file.readframes(
                frame_count
            )

        if channels != 1:
            raise ValueError(
                f"{audio_path.name}: expected mono audio, "
                f"got {channels} channels"
            )

        if sample_width != 2:
            raise ValueError(
                f"{audio_path.name}: expected 16-bit PCM, "
                f"got {sample_width * 8}-bit"
            )

        if sample_rate != 16000:
            raise ValueError(
                f"{audio_path.name}: expected 16000 Hz, "
                f"got {sample_rate} Hz"
            )

        audio = np.frombuffer(
            frames,
            dtype=np.int16,
        ).astype(np.float32)

        audio /= 32768.0

        duration_seconds = (
            frame_count / float(sample_rate)
        )

        return audio, duration_seconds
