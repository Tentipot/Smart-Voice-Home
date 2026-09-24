
import time
import os
import wave
from pathlib import Path

from faster_whisper import WhisperModel

from app.resources.cuda_dll import register_nvidia_dll_directories
from app.speech.stt.base import SttEngine
from app.speech.stt.result import SttResult


class WhisperSttEngine(SttEngine):
    """
    STT engine backed by faster-whisper.

    The model is loaded once when the engine instance is created
    and reused for subsequent transcription requests.
    """

    def __init__(
        self,
        model_name: str | None = None,
        *,
        device: str = "cuda",
        compute_type: str = "float16",
        beam_size: int = 5,
    ) -> None:
        self._model_name = model_name or os.getenv("SMART_VOICE_WHISPER_MODEL", "large-v3")
        self._device = device
        self._compute_type = compute_type
        self._beam_size = beam_size

        if device == "cuda":
            register_nvidia_dll_directories()

        load_start = time.perf_counter()

        self._model = WhisperModel(
            self._model_name,
            device=device,
            compute_type=compute_type,
        )

        self._load_seconds = (
            time.perf_counter() - load_start
        )

    @property
    def engine_name(self) -> str:
        return "faster-whisper"

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

        duration_seconds = self._get_wav_duration(
            audio_path
        )

        start = time.perf_counter()

        segments, info = self._model.transcribe(
            str(audio_path),
            language=language,
            task="transcribe",
            beam_size=self._beam_size,
            temperature=0.0,
            condition_on_previous_text=False,
            vad_filter=False,
        )

        # faster-whisper performs inference lazily while
        # the segments iterator is consumed.
        segments = list(segments)

        inference_seconds = (
            time.perf_counter() - start
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
            if segment.text.strip()
        ).strip()

        detected_language = (
            info.language
            if info.language
            else language
        )

        language_confidence = (
            info.language_probability
            if language is None
            else None
        )

        return SttResult(
            text=text,
            language=detected_language,
            language_confidence=language_confidence,
            duration_seconds=duration_seconds,
            inference_seconds=inference_seconds,
            engine=self.engine_name,
            model=self.model_name,
            metadata={
                "requested_language": language,
                "device": self._device,
                "compute_type": self._compute_type,
                "beam_size": self._beam_size,
            },
        )

    @staticmethod
    def _get_wav_duration(
        audio_path: Path,
    ) -> float | None:
        """
        Return WAV duration when the input is a standard WAV file.

        Duration is optional metadata, so failure to read the WAV
        header must not prevent STT inference.
        """

        try:
            with wave.open(
                str(audio_path),
                "rb",
            ) as wav_file:
                frame_count = wav_file.getnframes()
                sample_rate = wav_file.getframerate()

            if sample_rate <= 0:
                return None

            return frame_count / float(sample_rate)

        except (wave.Error, EOFError):
            return None
