import time
import wave
from pathlib import Path

import torch
import nemo.collections.asr as nemo_asr


MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v3"

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "data" / "stt_benchmark"


TESTS = [
    # ============================================================
    # Bulgarian
    # ============================================================
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

    # ============================================================
    # English
    # ============================================================
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

    # ============================================================
    # Bulgarian + English
    # ============================================================
    (21, "BG+EN", "Пусни Metallica Enter Sandman в Spotify"),

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


def extract_text(result) -> str:
    if result is None:
        return ""

    if isinstance(result, str):
        return result.strip()

    if isinstance(result, list):
        if not result:
            return ""

        item = result[0]

        if isinstance(item, str):
            return item.strip()

        if hasattr(item, "text"):
            return str(item.text).strip()

        return str(item).strip()

    if hasattr(result, "text"):
        return str(result.text).strip()

    return str(result).strip()


def synchronize_gpu() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def main() -> None:
    print()
    print("=" * 78)
    print("PARAKEET TDT 0.6B V3 - ACCURACY BENCHMARK")
    print("=" * 78)
    print()
    print(f"Model : {MODEL_NAME}")
    print(f"Tests : {len(TESTS)}")
    print()

    # ------------------------------------------------------------
    # Validate corpus before loading the model
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

    synchronize_gpu()
    load_start = time.perf_counter()

    model = nemo_asr.models.ASRModel.from_pretrained(
        model_name=MODEL_NAME,
        map_location="cuda",
    )

    model.eval()

    synchronize_gpu()
    load_seconds = time.perf_counter() - load_start

    print(f"Model load time: {load_seconds:.3f} s")
    print()

    # ------------------------------------------------------------
    # Explicit warm-up
    #
    # test_001 is used once here, but this result is discarded.
    # test_001 is then transcribed again normally in the benchmark.
    # ------------------------------------------------------------

    warmup_file = AUDIO_DIR / "test_001.wav"

    print("GPU warm-up...")
    print(f"Warm-up file: {warmup_file.name}")

    synchronize_gpu()
    warmup_start = time.perf_counter()

    with torch.inference_mode():
        model.transcribe(
            [str(warmup_file)],
            batch_size=1,
        )

    synchronize_gpu()
    warmup_seconds = time.perf_counter() - warmup_start

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

        synchronize_gpu()
        inference_start = time.perf_counter()

        with torch.inference_mode():
            result = model.transcribe(
                [str(file_path)],
                batch_size=1,
            )

        synchronize_gpu()
        inference_seconds = (
            time.perf_counter() - inference_start
        )

        transcript = extract_text(result)

        if audio_seconds > 0:
            rtf = inference_seconds / audio_seconds
        else:
            rtf = 0.0

        total_audio_seconds += audio_seconds
        total_inference_seconds += inference_seconds

        category_stats[category]["audio"] += audio_seconds
        category_stats[category]["inference"] += inference_seconds
        category_stats[category]["count"] += 1

        print()
        print("-" * 78)
        print(
            f"TEST {test_number:03d} | "
            f"{category}"
        )
        print("-" * 78)
        print(f"Expected   : {expected}")
        print(f"Transcript : {transcript}")
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
    print(f"Total audio     : {total_audio_seconds:.3f} s")
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