import time
import wave
from pathlib import Path

import numpy as np
import torch
from faster_whisper import WhisperModel
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoProcessor,
)

from app.speech.stt.language_resolver import (
    LanguageResolver,
)


BUZZ_MODEL_NAME = "BuzzASR/bulgarian"
WHISPER_MODEL_NAME = "large-v3"

BASE_DIR = Path(__file__).resolve().parents[2]
AUDIO_DIR = BASE_DIR / "data" / "stt_benchmark"


TESTS = [
    (31, "BG", "Намали звука на тридесет процента"),
    (32, "BG", "Включи осветлението в спалнята"),
    (33, "BG", "Изключи лампата в кухнята"),
    (34, "BG", "Спри музиката на този телефон"),
    (35, "BG", "Продължи песента"),
    (36, "BG", "Пусни предишната песен"),
    (37, "BG", "Увеличи звука на телевизора"),
    (38, "BG", "Настрой звука на седемдесет процента"),
    (39, "BG", "Рестартирай текущата песен"),
    (40, "BG", "Изключи осветлението в хола"),

    (41, "EN", "Set the volume to thirty percent"),
    (42, "EN", "Turn on the bedroom light"),
    (43, "EN", "Turn off the kitchen light"),
    (44, "EN", "Stop the music on this phone"),
    (45, "EN", "Continue the current song"),
    (46, "EN", "Play the previous song"),
    (47, "EN", "Turn up the volume on the TV"),
    (48, "EN", "Set the volume to seventy percent"),
    (49, "EN", "Restart the current song"),
    (50, "EN", "Turn off the living room light"),

    (51, "MIXED", "Пусни AC/DC Highway to Hell"),
    (
        52,
        "MIXED",
        "Пусни Metallica Enter Sandman в Spotify",
    ),
    (
        53,
        "MIXED",
        "Намери ми акумулаторен винтоверт "
        "на Bosch с две батерии",
    ),
    (
        54,
        "MIXED",
        "Пусни The Expanse в Stremio",
    ),
    (
        55,
        "MIXED",
        "Стартирай климатика Gree спалня",
    ),
    (
        56,
        "MIXED",
        "Пусни Guns N' Roses November Rain",
    ),
    (
        57,
        "MIXED",
        "Намери ми телевизор Samsung с OLED дисплей",
    ),
    (
        58,
        "MIXED",
        "Пусни Dr. Dre Still D.R.E. в Spotify",
    ),
    (
        59,
        "MIXED",
        "Намери ми лаптоп Lenovo ThinkPad "
        "с шестнадесет гигабайта памет",
    ),
    (
        60,
        "MIXED",
        "Пусни Guardians of the Galaxy "
        "на телевизора в хола",
    ),
]


def get_audio_duration(
    file_path: Path,
) -> float:
    with wave.open(str(file_path), "rb") as wav_file:
        frames = wav_file.getnframes()
        sample_rate = wav_file.getframerate()

    return frames / float(sample_rate)


def load_audio(
    file_path: Path,
) -> np.ndarray:
    with wave.open(str(file_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frames = wav_file.readframes(
            wav_file.getnframes()
        )

    if channels != 1:
        raise ValueError(
            f"{file_path.name}: expected mono audio, "
            f"got {channels} channels"
        )

    if sample_width != 2:
        raise ValueError(
            f"{file_path.name}: expected 16-bit PCM, "
            f"got {sample_width * 8}-bit"
        )

    if sample_rate != 16000:
        raise ValueError(
            f"{file_path.name}: expected 16000 Hz, "
            f"got {sample_rate} Hz"
        )

    audio = np.frombuffer(
        frames,
        dtype=np.int16,
    ).astype(np.float32)

    audio /= 32768.0

    return audio


def transcribe_buzz(
    model,
    processor,
    file_path: Path,
) -> tuple[str, float]:
    audio = load_audio(file_path)

    inputs = processor(
        audio,
        sampling_rate=16000,
        return_tensors="pt",
    )

    input_features = inputs.input_features.to(
        device="cuda",
        dtype=torch.float16,
    )

    torch.cuda.synchronize()
    start = time.perf_counter()

    with torch.inference_mode():
        generated_ids = model.generate(
            input_features,
            max_new_tokens=128,
        )

    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    transcript = processor.batch_decode(
        generated_ids,
        skip_special_tokens=True,
    )[0].strip()

    return transcript, elapsed


def transcribe_whisper(
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
    language_probability = (
        info.language_probability or 0.0
    )

    return (
        transcript,
        elapsed,
        detected_language,
        language_probability,
    )


def print_whisper_result(
    label: str,
    transcript: str,
    elapsed: float,
    language: str,
    probability: float,
) -> None:
    print(
        f"{label:<10}: {transcript}"
    )

    print(
        f"{'':10}  "
        f"LANG={language} "
        f"PROB={probability:.4f} "
        f"TIME={elapsed:.3f} s"
    )


def main() -> None:
    print()
    print("=" * 88)
    print("LANGUAGE RESOLVER VALIDATION 031-060")
    print("=" * 88)
    print()
    print(f"Buzz model    : {BUZZ_MODEL_NAME}")
    print(f"Whisper model : {WHISPER_MODEL_NAME}")
    print(f"Tests         : {len(TESTS)}")
    print()
    print("Comparison:")
    print("  BEFORE   = Whisper AUTO transcript")
    print("  RESOLVER = AUTO language -> LanguagePolicy")
    print("  AFTER    = forced BG or forced EN hypothesis")
    print()
    print(
        "No extra resolver inference is performed."
    )
    print(
        "WH AUTO, WH BG and WH EN are generated once."
    )
    print()

    missing_files = []

    for test_number, _, _ in TESTS:
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

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA GPU is not available."
        )

    print(
        f"GPU: {torch.cuda.get_device_name(0)}"
    )
    print()

    resolver = LanguageResolver()

    print("Loading Buzz processor...")

    buzz_processor = AutoProcessor.from_pretrained(
        BUZZ_MODEL_NAME,
    )

    print("Loading Buzz model...")

    buzz_load_start = time.perf_counter()

    buzz_model = (
        AutoModelForSpeechSeq2Seq.from_pretrained(
            BUZZ_MODEL_NAME,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        )
    )

    buzz_model.to("cuda")
    buzz_model.eval()

    torch.cuda.synchronize()

    buzz_load_time = (
        time.perf_counter()
        - buzz_load_start
    )

    print(
        f"Buzz load time: "
        f"{buzz_load_time:.3f} s"
    )

    print(
        "CUDA allocated after Buzz: "
        f"{torch.cuda.memory_allocated() / 1024**3:.3f} GB"
    )

    print()

    print("Loading Whisper model...")

    whisper_load_start = time.perf_counter()

    whisper_model = WhisperModel(
        WHISPER_MODEL_NAME,
        device="cuda",
        compute_type="float16",
    )

    whisper_load_time = (
        time.perf_counter()
        - whisper_load_start
    )

    print(
        f"Whisper load time: "
        f"{whisper_load_time:.3f} s"
    )

    print()

    warmup_file = (
        AUDIO_DIR
        / "test_031.wav"
    )

    print("Warming up Buzz...")

    (
        warm_buzz_text,
        warm_buzz_time,
    ) = transcribe_buzz(
        buzz_model,
        buzz_processor,
        warmup_file,
    )

    print(
        f"BUZZ       : {warm_buzz_text}"
    )
    print(
        f"             TIME={warm_buzz_time:.3f} s"
    )

    print()
    print("Warming up Whisper AUTO...")

    (
        warm_auto_text,
        warm_auto_time,
        warm_auto_lang,
        warm_auto_prob,
    ) = transcribe_whisper(
        whisper_model,
        warmup_file,
        None,
    )

    print_whisper_result(
        "WH AUTO",
        warm_auto_text,
        warm_auto_time,
        warm_auto_lang,
        warm_auto_prob,
    )

    print()
    print("Warming up Whisper BG...")

    (
        warm_bg_text,
        warm_bg_time,
        warm_bg_lang,
        warm_bg_prob,
    ) = transcribe_whisper(
        whisper_model,
        warmup_file,
        "bg",
    )

    print_whisper_result(
        "WH BG",
        warm_bg_text,
        warm_bg_time,
        warm_bg_lang,
        warm_bg_prob,
    )

    print()
    print("Warming up Whisper EN...")

    (
        warm_en_text,
        warm_en_time,
        warm_en_lang,
        warm_en_prob,
    ) = transcribe_whisper(
        whisper_model,
        warmup_file,
        "en",
    )

    print_whisper_result(
        "WH EN",
        warm_en_text,
        warm_en_time,
        warm_en_lang,
        warm_en_prob,
    )

    print()
    print("Warm-ups are NOT counted.")
    print()

    torch.cuda.reset_peak_memory_stats()

    total_audio = 0.0
    total_buzz = 0.0
    total_auto = 0.0
    total_bg = 0.0
    total_en = 0.0

    resolved_bg_count = 0
    resolved_en_count = 0

    correct_route_bg = 0
    correct_route_en = 0

    pure_bg_count = 0
    pure_en_count = 0

    detected_languages: dict[str, int] = {}

    print("=" * 88)
    print("BEFORE / AFTER RESULTS")
    print("=" * 88)

    for test_number, track, expected in TESTS:
        file_path = (
            AUDIO_DIR
            / f"test_{test_number:03d}.wav"
        )

        audio_duration = get_audio_duration(
            file_path
        )

        (
            buzz_text,
            buzz_time,
        ) = transcribe_buzz(
            buzz_model,
            buzz_processor,
            file_path,
        )

        (
            auto_text,
            auto_time,
            auto_lang,
            auto_prob,
        ) = transcribe_whisper(
            whisper_model,
            file_path,
            None,
        )

        (
            bg_text,
            bg_time,
            bg_lang,
            bg_prob,
        ) = transcribe_whisper(
            whisper_model,
            file_path,
            "bg",
        )

        (
            en_text,
            en_time,
            en_lang,
            en_prob,
        ) = transcribe_whisper(
            whisper_model,
            file_path,
            "en",
        )

        resolution = resolver.resolve_detected_language(
            auto_lang,
            auto_prob,
        )

        resolved_mode = resolution.policy.mode.value

        if resolved_mode == "en":
            resolved_text = en_text
            resolved_time = en_time
            resolved_lang = en_lang
            resolved_prob = en_prob
            resolved_bg_count_increment = 0
            resolved_en_count_increment = 1

        elif resolved_mode == "bg":
            resolved_text = bg_text
            resolved_time = bg_time
            resolved_lang = bg_lang
            resolved_prob = bg_prob
            resolved_bg_count_increment = 1
            resolved_en_count_increment = 0

        else:
            raise RuntimeError(
                "Unexpected resolver policy mode: "
                f"{resolved_mode}"
            )

        resolved_bg_count += (
            resolved_bg_count_increment
        )

        resolved_en_count += (
            resolved_en_count_increment
        )

        detected_languages[auto_lang] = (
            detected_languages.get(
                auto_lang,
                0,
            )
            + 1
        )

        if track == "BG":
            pure_bg_count += 1

            if resolved_mode == "bg":
                correct_route_bg += 1

        elif track == "EN":
            pure_en_count += 1

            if resolved_mode == "en":
                correct_route_en += 1

        total_audio += audio_duration
        total_buzz += buzz_time
        total_auto += auto_time
        total_bg += bg_time
        total_en += en_time

        print()
        print("-" * 88)
        print(
            f"TEST {test_number:03d} "
            f"[{track}] "
            f"DURATION={audio_duration:.3f} s"
        )
        print("-" * 88)

        print(
            f"EXPECTED   : {expected}"
        )

        print()

        print(
            f"BUZZ       : {buzz_text}"
        )
        print(
            f"             TIME={buzz_time:.3f} s"
        )

        print()

        print_whisper_result(
            "BEFORE",
            auto_text,
            auto_time,
            auto_lang,
            auto_prob,
        )

        print()

        print(
            f"RESOLVER   : "
            f"detected={auto_lang} "
            f"prob={auto_prob:.4f} "
            f"-> policy={resolved_mode}"
        )

        print(
            f"REASON     : "
            f"{resolution.reason.value}"
        )

        print()

        print_whisper_result(
            "AFTER",
            resolved_text,
            resolved_time,
            resolved_lang,
            resolved_prob,
        )

        print(
            f"             "
            f"SELECTED=forced-{resolved_mode}"
        )

        print()

        print_whisper_result(
            "WH BG",
            bg_text,
            bg_time,
            bg_lang,
            bg_prob,
        )

        print()

        print_whisper_result(
            "WH EN",
            en_text,
            en_time,
            en_lang,
            en_prob,
        )

    total_whisper_3way = (
        total_auto
        + total_bg
        + total_en
    )

    print()
    print("=" * 88)
    print("LANGUAGE ROUTING SUMMARY")
    print("=" * 88)
    print()

    print("AUTO detected languages:")

    for language in sorted(
        detected_languages
    ):
        print(
            f"  {language:<8}: "
            f"{detected_languages[language]}"
        )

    print()

    print(
        f"Resolver -> BG : "
        f"{resolved_bg_count}"
    )

    print(
        f"Resolver -> EN : "
        f"{resolved_en_count}"
    )

    print()

    print(
        f"Pure BG routed BG : "
        f"{correct_route_bg}/{pure_bg_count}"
    )

    print(
        f"Pure EN routed EN : "
        f"{correct_route_en}/{pure_en_count}"
    )

    pure_total = (
        pure_bg_count
        + pure_en_count
    )

    pure_correct = (
        correct_route_bg
        + correct_route_en
    )

    print(
        f"Pure routing total : "
        f"{pure_correct}/{pure_total}"
    )

    print()

    print(
        "NOTE: MIXED 051-060 are intentionally "
        "not scored as BG/EN routing correctness."
    )

    print()
    print("=" * 88)
    print("PERFORMANCE")
    print("=" * 88)
    print()

    print(
        f"Audio corpus        : "
        f"{total_audio:.3f} s"
    )

    print(
        f"Buzz total          : "
        f"{total_buzz:.3f} s"
    )

    print(
        f"Whisper AUTO total  : "
        f"{total_auto:.3f} s"
    )

    print(
        f"Whisper BG total    : "
        f"{total_bg:.3f} s"
    )

    print(
        f"Whisper EN total    : "
        f"{total_en:.3f} s"
    )

    print(
        f"Whisper 3-way total : "
        f"{total_whisper_3way:.3f} s"
    )

    print()

    print(
        "Peak CUDA allocated : "
        f"{torch.cuda.max_memory_allocated() / 1024**3:.3f} GB"
    )

    print(
        "Peak CUDA reserved  : "
        f"{torch.cuda.max_memory_reserved() / 1024**3:.3f} GB"
    )

    print()
    print("=" * 88)
    print("LANGUAGE RESOLVER VALIDATION COMPLETE")
    print("=" * 88)
    print()


if __name__ == "__main__":
    main()