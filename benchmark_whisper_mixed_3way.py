import time
import wave
from pathlib import Path

from faster_whisper import WhisperModel


MODEL_NAME = "large-v3"

BASE_DIR = Path(__file__).resolve().parent
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


def transcribe(
    model: WhisperModel,
    file_path: Path,
    language: str | None,
) -> tuple[str, float, str, float]:

    start = time.perf_counter()

    segments, info = model.transcribe(
        str(file_path),
        language=language,
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

    detected_language = info.language or "unknown"
    language_probability = info.language_probability or 0.0

    return (
        transcript,
        elapsed,
        detected_language,
        language_probability,
    )


def print_result(
    label: str,
    transcript: str,
    elapsed: float,
    language: str,
    probability: float,
) -> None:

    print(f"{label:<8} : {transcript}")
    print(
        f"{'':8}   LANG={language} "
        f"PROB={probability:.4f} "
        f"TIME={elapsed:.3f} s"
    )


def main() -> None:
    print()
    print("=" * 78)
    print("WHISPER LARGE-V3 - MIXED 3-WAY DIAGNOSTIC")
    print("=" * 78)
    print()

    print(f"Model : {MODEL_NAME}")
    print(f"Tests : {len(TESTS)}")
    print("Track : BG+EN mixed")
    print()
    print("Pass A: AUTO")
    print("Pass B: forced Bulgarian")
    print("Pass C: forced English")
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
    #
    # Use all three modes once so that none of the measured
    # passes gets an unfair first-inference penalty.
    # ------------------------------------------------------------

    warmup_file = (
        AUDIO_DIR
        / "test_021.wav"
    )

    print("Warming up AUTO...")

    (
        warm_auto,
        warm_auto_time,
        warm_auto_lang,
        warm_auto_prob,
    ) = transcribe(
        model,
        warmup_file,
        None,
    )

    print_result(
        "AUTO",
        warm_auto,
        warm_auto_time,
        warm_auto_lang,
        warm_auto_prob,
    )

    print()

    print("Warming up BG...")

    (
        warm_bg,
        warm_bg_time,
        warm_bg_lang,
        warm_bg_prob,
    ) = transcribe(
        model,
        warmup_file,
        "bg",
    )

    print_result(
        "BG",
        warm_bg,
        warm_bg_time,
        warm_bg_lang,
        warm_bg_prob,
    )

    print()

    print("Warming up EN...")

    (
        warm_en,
        warm_en_time,
        warm_en_lang,
        warm_en_prob,
    ) = transcribe(
        model,
        warmup_file,
        "en",
    )

    print_result(
        "EN",
        warm_en,
        warm_en_time,
        warm_en_lang,
        warm_en_prob,
    )

    print()
    print("Warm-ups are NOT counted.")
    print()

    # ------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------

    total_audio = 0.0

    total_auto = 0.0
    total_bg = 0.0
    total_en = 0.0

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

        # --------------------------------------------------------
        # AUTO
        # --------------------------------------------------------

        (
            auto_text,
            auto_time,
            auto_lang,
            auto_prob,
        ) = transcribe(
            model,
            file_path,
            None,
        )

        # --------------------------------------------------------
        # Forced Bulgarian
        # --------------------------------------------------------

        (
            bg_text,
            bg_time,
            bg_lang,
            bg_prob,
        ) = transcribe(
            model,
            file_path,
            "bg",
        )

        # --------------------------------------------------------
        # Forced English
        # --------------------------------------------------------

        (
            en_text,
            en_time,
            en_lang,
            en_prob,
        ) = transcribe(
            model,
            file_path,
            "en",
        )

        total_audio += audio_duration

        total_auto += auto_time
        total_bg += bg_time
        total_en += en_time

        print()
        print("-" * 78)
        print(f"TEST {test_number:03d}")
        print("-" * 78)

        print(f"EXPECTED : {expected}")
        print()

        print_result(
            "AUTO",
            auto_text,
            auto_time,
            auto_lang,
            auto_prob,
        )

        print()

        print_result(
            "BG",
            bg_text,
            bg_time,
            bg_lang,
            bg_prob,
        )

        print()

        print_result(
            "EN",
            en_text,
            en_time,
            en_lang,
            en_prob,
        )

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    total_3way = (
        total_auto
        + total_bg
        + total_en
    )

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    print()

    print(
        f"Model load          : "
        f"{load_time:.3f} s"
    )

    print(
        f"Audio corpus        : "
        f"{total_audio:.3f} s"
    )

    print()

    print(
        f"AUTO total          : "
        f"{total_auto:.3f} s"
    )

    print(
        f"AUTO average        : "
        f"{total_auto / len(TESTS):.3f} s"
    )

    print(
        f"AUTO RTF            : "
        f"{total_auto / total_audio:.3f}"
    )

    print()

    print(
        f"Forced BG total     : "
        f"{total_bg:.3f} s"
    )

    print(
        f"Forced BG average   : "
        f"{total_bg / len(TESTS):.3f} s"
    )

    print(
        f"Forced BG RTF       : "
        f"{total_bg / total_audio:.3f}"
    )

    print()

    print(
        f"Forced EN total     : "
        f"{total_en:.3f} s"
    )

    print(
        f"Forced EN average   : "
        f"{total_en / len(TESTS):.3f} s"
    )

    print(
        f"Forced EN RTF       : "
        f"{total_en / total_audio:.3f}"
    )

    print()

    print(
        f"3-way total         : "
        f"{total_3way:.3f} s"
    )

    print(
        f"3-way per command   : "
        f"{total_3way / len(TESTS):.3f} s"
    )

    print(
        f"3-way combined RTF  : "
        f"{total_3way / total_audio:.3f}"
    )

    print()

    print("=" * 78)
    print("WHISPER MIXED 3-WAY DIAGNOSTIC COMPLETE")
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()