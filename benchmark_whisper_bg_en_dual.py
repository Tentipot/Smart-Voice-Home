import time
import wave
from pathlib import Path

from faster_whisper import WhisperModel


MODEL_NAME = "large-v3"

BASE_DIR = Path(__file__).resolve().parent
AUDIO_DIR = BASE_DIR / "data" / "stt_benchmark"


TESTS = [
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


def transcribe_file(
    model: WhisperModel,
    file_path: Path,
    language: str,
) -> tuple[str, float]:

    start = time.perf_counter()

    segments, _ = model.transcribe(
        str(file_path),

        # Diagnostic test:
        # force ONLY the selected language.
        language=language,

        task="transcribe",
        beam_size=5,
        temperature=0.0,
        condition_on_previous_text=False,
        vad_filter=False,
    )

    # Inference actually happens when the generator
    # is consumed.
    segments = list(segments)

    elapsed = time.perf_counter() - start

    transcript = " ".join(
        segment.text.strip()
        for segment in segments
        if segment.text.strip()
    ).strip()

    return transcript, elapsed


def main() -> None:
    print()
    print("=" * 78)
    print("WHISPER LARGE-V3 - FORCED BG vs FORCED EN")
    print("=" * 78)
    print()
    print(f"Model : {MODEL_NAME}")
    print("Pass 1: forced Bulgarian")
    print("Pass 2: forced English")
    print("AUTO language detection: DISABLED")
    print(f"Tests : {len(TESTS)}")
    print()

    # ------------------------------------------------------------
    # Check corpus
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

    print(f"Model load time: {load_time:.3f} s")
    print()

    # ------------------------------------------------------------
    # Warm up BOTH language paths.
    # Neither result is counted.
    # ------------------------------------------------------------

    warmup_file = AUDIO_DIR / "test_001.wav"

    print("Warming up Bulgarian path...")

    _, bg_warmup = transcribe_file(
        model,
        warmup_file,
        "bg",
    )

    print(f"BG warm-up: {bg_warmup:.3f} s")

    print("Warming up English path...")

    _, en_warmup = transcribe_file(
        model,
        warmup_file,
        "en",
    )

    print(f"EN warm-up: {en_warmup:.3f} s")

    print("Warm-up results are NOT counted.")
    print()

    # ------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------

    total_audio = 0.0
    total_bg_time = 0.0
    total_en_time = 0.0

    print("=" * 78)
    print("DUAL-LANGUAGE DIAGNOSTIC")
    print("=" * 78)

    for test_number, category, expected in TESTS:
        file_path = (
            AUDIO_DIR
            / f"test_{test_number:03d}.wav"
        )

        audio_duration = get_audio_duration(
            file_path
        )

        bg_text, bg_time = transcribe_file(
            model,
            file_path,
            "bg",
        )

        en_text, en_time = transcribe_file(
            model,
            file_path,
            "en",
        )

        total_audio += audio_duration
        total_bg_time += bg_time
        total_en_time += en_time

        print()
        print("-" * 78)
        print(
            f"TEST {test_number:03d} | "
            f"{category}"
        )
        print("-" * 78)

        print(f"EXPECTED : {expected}")
        print()
        print(f"BG PASS  : {bg_text}")
        print(f"BG TIME  : {bg_time:.3f} s")
        print()
        print(f"EN PASS  : {en_text}")
        print(f"EN TIME  : {en_time:.3f} s")

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print()

    print(f"Model load : {load_time:.3f} s")
    print()

    print(
        f"Audio corpus       : "
        f"{total_audio:.3f} s"
    )

    print(
        f"Forced BG total    : "
        f"{total_bg_time:.3f} s"
    )

    print(
        f"Forced EN total    : "
        f"{total_en_time:.3f} s"
    )

    dual_total = (
        total_bg_time
        + total_en_time
    )

    print(
        f"Both passes total  : "
        f"{dual_total:.3f} s"
    )

    print()

    if len(TESTS) > 0:
        print(
            "Average BG pass     : "
            f"{total_bg_time / len(TESTS):.3f} s"
        )

        print(
            "Average EN pass     : "
            f"{total_en_time / len(TESTS):.3f} s"
        )

        print(
            "Average dual pass   : "
            f"{dual_total / len(TESTS):.3f} s"
        )

    print()

    if total_audio > 0:
        print(
            "BG RTF              : "
            f"{total_bg_time / total_audio:.3f}"
        )

        print(
            "EN RTF              : "
            f"{total_en_time / total_audio:.3f}"
        )

        print(
            "Dual-pass RTF       : "
            f"{dual_total / total_audio:.3f}"
        )

    print()
    print("=" * 78)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()