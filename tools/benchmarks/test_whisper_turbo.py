import time
from pathlib import Path

from faster_whisper import WhisperModel


MODEL_NAME = "large-v3-turbo"

AUDIO_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "stt_benchmark"
    / "test_001.wav"
)


def main() -> None:
    print()
    print("Assistant STT - Whisper large-v3-turbo Test")
    print("-------------------------------------------")
    print(f"Model : {MODEL_NAME}")
    print(f"Audio : {AUDIO_FILE}")
    print()

    if not AUDIO_FILE.exists():
        raise FileNotFoundError(f"Audio file not found: {AUDIO_FILE}")

    print("Loading model...")

    load_start = time.perf_counter()

    model = WhisperModel(
        MODEL_NAME,
        device="cuda",
        compute_type="float16",
    )

    load_seconds = time.perf_counter() - load_start

    print(f"Model loaded in {load_seconds:.2f} s")
    print()
    print("Transcribing...")

    inference_start = time.perf_counter()

    segments, info = model.transcribe(
        str(AUDIO_FILE),
        beam_size=5,
        vad_filter=False,
    )

    # faster-whisper returns a generator.
    # Converting it to a list forces the actual transcription to run.
    segments = list(segments)

    inference_seconds = time.perf_counter() - inference_start

    transcript = "".join(segment.text for segment in segments).strip()

    print()
    print("========== RESULT ==========")
    print()
    print(f"Transcript : {transcript}")
    print(f"Language   : {info.language}")
    print(f"Lang prob  : {info.language_probability:.4f}")
    print(f"Inference  : {inference_seconds:.3f} s")
    print()
    print("============================")
    print()


if __name__ == "__main__":
    main()