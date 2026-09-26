import time
import wave
from pathlib import Path

from faster_whisper import WhisperModel


MODEL_NAME = "large-v3-turbo"

BASE_DIR = Path(__file__).resolve().parents[2]
AUDIO_DIR = BASE_DIR / "data" / "stt_benchmark"


TESTS = [
    (
        21,
        "Пусни Metallica Enter Sandman в Spotify",
    ),
    (
        22,
        "Play Guns N' Roses и увеличи звука на двадесет процента",
    ),
    (
        23,
        "Пусни Dr. Dre Still D.R.E. and set the volume to fifty percent",
    ),
    (
        24,
        "Set the volume на тридесет процента и продължи музиката",
    ),
    (
        25,
        "Отвори YouTube на Samsung TV and play the latest video",
    ),
    (
        26,
        "Play Metallica Enter Sandman и после намали звука",
    ),
    (
        27,
        "Пусни следващата song and turn up the volume",
    ),
    (
        28,
        "Turn on лампата в хола и изключи kitchen light",
    ),
    (
        29,
        "Спри music on Samsung TV и продължи на този телефон",
    ),
    (
        30,
        "Play the next song и след това рестартирай песента",
    ),
]


def get_audio_duration(file_path: Path) -> float:
    with wave.open(str(file_path), "rb") as wav_file:
        frames = wav_file.getnframes()
        sample_rate = wav_file.getframerate()

    return frames / float(sample_rate)


def transcribe_file(
    model: WhisperModel,
    file_path: Path,
) -> tuple[str, float, str, float]:

    start = time.perf_counter()

    segments, info = model.transcribe(
        str(file_path),

        # Important:
        # AUTO language detection for genuine BG+EN
        # code-switch testing.
        language=None,

        task="transcribe",
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
        vad_filter=False,
    )

    segments = list(segments)

    elapsed = time.perf_counter() - start

    transcript = " ".join(
        segment.text.strip()
        for segment in segments
        if segment.text.strip()
    ).strip()

    language = info.language or "unknown"
    probability = info.language_probability or 0.0

    return (
        transcript,
        elapsed,
        language,
        probability,
    )


def main() -> None:
    print()
    print("=" * 78)
    print("WHISPER LARGE-V3-TURBO - MIXED BG+EN BENCHMARK")
    print("=" * 78)
    print()

    print(f"Model : {MODEL_NAME}")
    print(f"Tests : {len(TESTS)}")
    print("Track : BG+EN mixed")
    print("Mode  : AUTO language detection")
    print()

    # ------------------------------------------------------------
    # Validate corpus
    # ------------------------------------------------------------

    missing_files = []

    for test_number, _ in TESTS:
        file_path = (
            AUDIO_DIR
            / f"test_{test_number:03d}.wav"
        )

        if not file_path.exists():
            missing_files.append(file_path)

    if missing_files:
        print("ERROR: Missing benchmark files:")
        print()

        for file_path in missing_files:
            print(file_path)

        return

    print("Corpus: OK")
    print()

    # ------------------------------------------------------------
    # Load model
    # ------------------------------------------------------------

    print("Loading model...")

    load_start = time.perf_counter()

    model = WhisperModel(
        MODEL_NAME,
        device="cuda",
        compute_type="float16",
    )

    load_time = time.perf_counter() - load_start

    print(
        f"Model load time: {load_time:.3f} s"
    )
    print()

    # ------------------------------------------------------------
    # Warm-up
    # ------------------------------------------------------------

    warmup_file = (
        AUDIO_DIR
        / "test_021.wav"
    )

    print("Warming up...")

    (
        warmup_text,
        warmup_time,
        warmup_language,
        warmup_probability,
    ) = transcribe_file(
        model,
        warmup_file,
    )

    print(
        f"Warm-up transcript : {warmup_text}"
    )
    print(
        f"Warm-up language   : "
        f"{warmup_language} "
        f"({warmup_probability:.4f})"
    )
    print(
        f"Warm-up time       : "
        f"{warmup_time:.3f} s"
    )
    print("Warm-up is NOT counted.")
    print()

    # ------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------

    total_audio = 0.0
    total_inference = 0.0

    print("=" * 78)
    print("MIXED BG+EN TESTS 021-030")
    print("=" * 78)

    for test_number, expected in TESTS:
        file_path = (
            AUDIO_DIR
            / f"test_{test_number:03d}.wav"
        )

        audio_duration = get_audio_duration(
            file_path
        )

        (
            transcript,
            elapsed,
            language,
            probability,
        ) = transcribe_file(
            model,
            file_path,
        )

        total_audio += audio_duration
        total_inference += elapsed

        print()
        print("-" * 78)
        print(f"TEST {test_number:03d}")
        print("-" * 78)

        print(f"EXPECTED : {expected}")
        print(f"TURBO    : {transcript}")
        print(
            f"LANGUAGE : "
            f"{language} "
            f"({probability:.4f})"
        )
        print(
            f"TIME     : "
            f"{elapsed:.3f} s"
        )

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print()

    print(
        f"Model load        : "
        f"{load_time:.3f} s"
    )

    print(
        f"Audio corpus      : "
        f"{total_audio:.3f} s"
    )

    print(
        f"Total inference   : "
        f"{total_inference:.3f} s"
    )

    if TESTS:
        print(
            f"Average inference : "
            f"{total_inference / len(TESTS):.3f} s"
        )

    if total_audio > 0:
        print(
            f"RTF               : "
            f"{total_inference / total_audio:.3f}"
        )

    print()
    print("=" * 78)
    print("WHISPER TURBO MIXED BENCHMARK COMPLETE")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()