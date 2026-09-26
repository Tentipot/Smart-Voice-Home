import time
import wave
from pathlib import Path

from faster_whisper import WhisperModel


MODEL_NAME = "large-v3"

BENCHMARK_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "stt_benchmark"
)

TESTS = [
    (
        "test_001.wav",
        "Пусни Metallica Enter Sandman в Spotify",
    ),
    (
        "test_002.wav",
        "Пусни Dr. Dre Still D.R.E. в Spotify",
    ),
    (
        "test_003.wav",
        "Пусни Guns N' Roses November Rain",
    ),
    (
        "test_004.wav",
        "Намали звука на двадесет процента",
    ),
    (
        "test_005.wav",
        "Изключи лампата в хола",
    ),
]


def get_audio_duration(file_path: Path) -> float:
    with wave.open(str(file_path), "rb") as wav_file:
        frames = wav_file.getnframes()
        sample_rate = wav_file.getframerate()

    return frames / float(sample_rate)


def main() -> None:
    print()
    print("Assistant STT Benchmark - Whisper large-v3")
    print("==========================================")
    print()

    for filename, _ in TESTS:
        file_path = BENCHMARK_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Benchmark file not found: {file_path}"
            )

    print(f"Model : {MODEL_NAME}")
    print("Device: CUDA")
    print("Compute type: float16")
    print()
    print("Loading model...")

    load_start = time.perf_counter()

    model = WhisperModel(
        MODEL_NAME,
        device="cuda",
        compute_type="float16",
    )

    load_seconds = time.perf_counter() - load_start

    print()
    print(f"Model loaded in {load_seconds:.2f} s")
    print()
    print("Running benchmark...")
    print()

    results = []

    for index, (filename, expected_text) in enumerate(
        TESTS,
        start=1,
    ):
        file_path = BENCHMARK_DIR / filename
        audio_duration = get_audio_duration(file_path)

        start = time.perf_counter()

        segments, info = model.transcribe(
            str(file_path),
            beam_size=5,
            vad_filter=False,
        )

        # Actual faster-whisper inference happens
        # while the generator is consumed.
        segments = list(segments)

        inference_seconds = time.perf_counter() - start

        transcript = "".join(
            segment.text for segment in segments
        ).strip()

        rtf = (
            inference_seconds / audio_duration
            if audio_duration > 0
            else 0.0
        )

        results.append(
            {
                "index": index,
                "filename": filename,
                "expected": expected_text,
                "transcript": transcript,
                "language": info.language,
                "language_probability": (
                    info.language_probability
                ),
                "audio": audio_duration,
                "inference": inference_seconds,
                "rtf": rtf,
            }
        )

    print()
    print("========================================")
    print("WHISPER LARGE-V3 BENCHMARK RESULTS")
    print("========================================")

    total_audio = 0.0
    total_inference = 0.0

    for result in results:
        total_audio += result["audio"]
        total_inference += result["inference"]

        print()
        print(
            f"TEST {result['index']} - "
            f"{result['filename']}"
        )
        print(f"Expected   : {result['expected']}")
        print(f"Transcript : {result['transcript']}")
        print(f"Language   : {result['language']}")
        print(
            f"Lang prob  : "
            f"{result['language_probability']:.4f}"
        )
        print(
            f"Audio      : "
            f"{result['audio']:.3f} s"
        )
        print(
            f"Inference  : "
            f"{result['inference']:.3f} s"
        )
        print(
            f"RTF        : "
            f"{result['rtf']:.3f}"
        )

    overall_rtf = (
        total_inference / total_audio
        if total_audio > 0
        else 0.0
    )

    print()
    print("----------------------------------------")
    print(f"Total audio     : {total_audio:.3f} s")
    print(
        f"Total inference : "
        f"{total_inference:.3f} s"
    )
    print(f"Overall RTF     : {overall_rtf:.3f}")
    print("----------------------------------------")
    print()


if __name__ == "__main__":
    main()