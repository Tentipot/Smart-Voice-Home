import time
import wave
from pathlib import Path

from faster_whisper import WhisperModel


MODEL_NAME = "large-v3"

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "data" / "stt_benchmark"


TESTS = [
    # Bulgarian
    (1, "BG", "Намали звука на двадесет процента"),
    (2, "BG", "Изключи лампата в хола"),
    (3, "BG", "Увеличи звука"),
    (4, "BG", "Спри музиката"),
    (5, "BG", "Продължи музиката"),
    (6, "BG", "Пусни следващата песен"),
    (7, "BG", "Върни предишната песен"),
    (8, "BG", "Рестартирай песента"),
    (9, "BG", "Включи лампата в кухнята"),
    (10, "BG", "Настрой звука на петдесет процента"),

    # English
    (11, "EN", "Set the volume to twenty percent"),
    (12, "EN", "Turn off the living room light"),
    (13, "EN", "Turn up the volume"),
    (14, "EN", "Stop the music"),
    (15, "EN", "Continue the music"),
    (16, "EN", "Play Metallica Enter Sandman on Spotify"),
    (17, "EN", "Play Dr. Dre Still D.R.E. on Spotify"),
    (18, "EN", "Play Guns N' Roses November Rain"),
    (19, "EN", "Turn on the kitchen light"),
    (20, "EN", "Restart the song"),

    # Bulgarian + English
    (
        21,
        "BG+EN",
        "Пусни Metallica Enter Sandman в Spotify",
    ),
    (
        22,
        "BG+EN",
        "Play Guns N' Roses и увеличи звука на двадесет процента",
    ),
    (
        23,
        "BG+EN",
        "Пусни Dr. Dre Still D.R.E. and set the volume to fifty percent",
    ),
    (
        24,
        "BG+EN",
        "Set the volume на тридесет процента и продължи музиката",
    ),
    (
        25,
        "BG+EN",
        "Отвори YouTube на Samsung TV and play the latest video",
    ),
    (
        26,
        "BG+EN",
        "Play Metallica Enter Sandman и после намали звука",
    ),
    (
        27,
        "BG+EN",
        "Пусни следващата song and turn up the volume",
    ),
    (
        28,
        "BG+EN",
        "Turn on лампата в хола и изключи kitchen light",
    ),
    (
        29,
        "BG+EN",
        "Спри music on Samsung TV и продължи на този телефон",
    ),
    (
        30,
        "BG+EN",
        "Play the next song и след това рестартирай песента",
    ),
]


def get_audio_duration(file_path: Path) -> float:
    with wave.open(str(file_path), "rb") as wav_file:
        frames = wav_file.getnframes()
        sample_rate = wav_file.getframerate()

    return frames / float(sample_rate)


def transcribe_file(model, file_path: Path):
    segments, info = model.transcribe(
        str(file_path),

        # IMPORTANT:
        # language=None means Whisper automatic language detection.
        language=None,

        task="transcribe",

        beam_size=5,

        temperature=0.0,

        condition_on_previous_text=False,

        vad_filter=False,
    )

    # faster-whisper returns a generator.
    # The actual inference happens while consuming it.
    segments = list(segments)

    transcript = " ".join(
        segment.text.strip()
        for segment in segments
        if segment.text.strip()
    ).strip()

    return transcript, info


def main() -> None:
    print()
    print("=" * 78)
    print("WHISPER LARGE-V3 - ACCURACY BENCHMARK")
    print("=" * 78)
    print()
    print(f"Model : {MODEL_NAME}")
    print("Mode  : AUTO language detection")
    print("Device: CUDA")
    print("Type  : float16")
    print(f"Tests : {len(TESTS)}")
    print()

    # ------------------------------------------------------------
    # Validate corpus
    # ------------------------------------------------------------

    missing_files = []

    for test_number, _, _ in TESTS:
        file_path = AUDIO_DIR / f"test_{test_number:03d}.wav"

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
    # Model load
    # ------------------------------------------------------------

    print("Loading model...")

    load_start = time.perf_counter()

    model = WhisperModel(
        MODEL_NAME,
        device="cuda",
        compute_type="float16",
    )

    load_seconds = time.perf_counter() - load_start

    print(f"Model load time: {load_seconds:.3f} s")
    print()

    # ------------------------------------------------------------
    # Explicit warm-up
    # ------------------------------------------------------------

    warmup_file = AUDIO_DIR / "test_001.wav"

    print("GPU warm-up...")
    print(f"Warm-up file: {warmup_file.name}")

    warmup_start = time.perf_counter()

    transcribe_file(
        model,
        warmup_file,
    )

    warmup_seconds = (
        time.perf_counter() - warmup_start
    )

    print(f"Warm-up time: {warmup_seconds:.3f} s")
    print("Warm-up result is NOT counted.")
    print()

    # ------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------

    total_audio_seconds = 0.0
    total_inference_seconds = 0.0

    category_stats = {
        "BG": {
            "audio": 0.0,
            "inference": 0.0,
            "count": 0,
        },
        "EN": {
            "audio": 0.0,
            "inference": 0.0,
            "count": 0,
        },
        "BG+EN": {
            "audio": 0.0,
            "inference": 0.0,
            "count": 0,
        },
    }

    print("=" * 78)
    print("STEADY-STATE BENCHMARK")
    print("=" * 78)

    for test_number, category, expected in TESTS:
        file_path = AUDIO_DIR / f"test_{test_number:03d}.wav"

        audio_seconds = get_audio_duration(file_path)

        inference_start = time.perf_counter()

        transcript, info = transcribe_file(
            model,
            file_path,
        )

        inference_seconds = (
            time.perf_counter() - inference_start
        )

        if audio_seconds > 0:
            rtf = inference_seconds / audio_seconds
        else:
            rtf = 0.0

        total_audio_seconds += audio_seconds
        total_inference_seconds += inference_seconds

        category_stats[category]["audio"] += audio_seconds
        category_stats[category]["inference"] += inference_seconds
        category_stats[category]["count"] += 1

        detected_language = getattr(
            info,
            "language",
            "unknown",
        )

        language_probability = getattr(
            info,
            "language_probability",
            None,
        )

        print()
        print("-" * 78)
        print(
            f"TEST {test_number:03d} | "
            f"{category}"
        )
        print("-" * 78)
        print(f"Expected   : {expected}")
        print(f"Transcript : {transcript}")
        print(
            f"Language   : {detected_language}"
        )

        if language_probability is not None:
            print(
                "Lang prob.  : "
                f"{language_probability:.4f}"
            )

        print(f"Audio      : {audio_seconds:.3f} s")
        print(f"Inference  : {inference_seconds:.3f} s")
        print(f"RTF        : {rtf:.3f}")

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print()

    print(f"Model load : {load_seconds:.3f} s")
    print(f"Warm-up    : {warmup_seconds:.3f} s")
    print()

    print(
        f"Total audio     : "
        f"{total_audio_seconds:.3f} s"
    )

    print(
        f"Total inference : "
        f"{total_inference_seconds:.3f} s"
    )

    if total_audio_seconds > 0:
        overall_rtf = (
            total_inference_seconds
            / total_audio_seconds
        )
    else:
        overall_rtf = 0.0

    print(f"Overall RTF     : {overall_rtf:.3f}")

    print()
    print("CATEGORY PERFORMANCE")
    print()

    for category in ("BG", "EN", "BG+EN"):
        stats = category_stats[category]

        if stats["audio"] > 0:
            category_rtf = (
                stats["inference"]
                / stats["audio"]
            )
        else:
            category_rtf = 0.0

        average_inference = (
            stats["inference"]
            / stats["count"]
        )

        print(
            f"{category:5} | "
            f"Tests: {stats['count']:2d} | "
            f"Inference: {stats['inference']:.3f} s | "
            f"Average: {average_inference:.3f} s | "
            f"RTF: {category_rtf:.3f}"
        )

    print()
    print("=" * 78)
    print("BENCHMARK COMPLETE")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()