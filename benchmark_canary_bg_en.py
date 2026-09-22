import time
import wave
from pathlib import Path

import torch
import nemo.collections.asr as nemo_asr


MODEL_NAME = "nvidia/canary-1b-v2"

BENCHMARK_DIR = (
    Path(__file__).resolve().parent
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


def transcribe_candidate(
    model,
    file_path: Path,
    language: str,
) -> tuple[str, float]:
    torch.cuda.synchronize()

    start = time.perf_counter()

    output = model.transcribe(
        [str(file_path)],
        source_lang=language,
        target_lang=language,
        pnc="yes",
    )

    torch.cuda.synchronize()

    inference_seconds = time.perf_counter() - start

    if not output:
        transcript = ""
    elif hasattr(output[0], "text"):
        transcript = output[0].text
    else:
        transcript = str(output[0])

    return transcript.strip(), inference_seconds


def main() -> None:
    print()
    print("Assistant STT Benchmark - Canary 1B v2")
    print("BG + EN candidate experiment")
    print("=======================================")
    print()

    for filename, _ in TESTS:
        file_path = BENCHMARK_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Benchmark file not found: {file_path}"
            )

    print(f"Model : {MODEL_NAME}")
    print("GPU   : CUDA")
    print("Modes : bg->bg and en->en")
    print()
    print("Loading model...")

    load_start = time.perf_counter()

    model = nemo_asr.models.ASRModel.from_pretrained(
        model_name=MODEL_NAME,
        map_location="cuda",
    )

    model.eval()

    torch.cuda.synchronize()

    load_seconds = time.perf_counter() - load_start

    print()
    print(f"Model loaded in {load_seconds:.2f} s")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(
        "VRAM allocated after load: "
        f"{torch.cuda.memory_allocated(0) / 1024**3:.2f} GB"
    )
    print(
        "VRAM reserved after load : "
        f"{torch.cuda.memory_reserved(0) / 1024**3:.2f} GB"
    )
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

        bg_text, bg_time = transcribe_candidate(
            model,
            file_path,
            "bg",
        )

        en_text, en_time = transcribe_candidate(
            model,
            file_path,
            "en",
        )

        results.append(
            {
                "index": index,
                "filename": filename,
                "expected": expected_text,
                "audio": audio_duration,
                "bg_text": bg_text,
                "bg_time": bg_time,
                "en_text": en_text,
                "en_time": en_time,
            }
        )

    print()
    print("========================================")
    print("CANARY 1B V2 - BG + EN RESULTS")
    print("========================================")

    total_audio = 0.0
    total_bg_time = 0.0
    total_en_time = 0.0

    for result in results:
        total_audio += result["audio"]
        total_bg_time += result["bg_time"]
        total_en_time += result["en_time"]

        bg_rtf = (
            result["bg_time"] / result["audio"]
            if result["audio"] > 0
            else 0.0
        )

        en_rtf = (
            result["en_time"] / result["audio"]
            if result["audio"] > 0
            else 0.0
        )

        print()
        print(
            f"TEST {result['index']} - "
            f"{result['filename']}"
        )
        print(f"Expected : {result['expected']}")
        print(f"Audio    : {result['audio']:.3f} s")
        print()

        print("BG candidate")
        print(f"Transcript : {result['bg_text']}")
        print(f"Inference  : {result['bg_time']:.3f} s")
        print(f"RTF        : {bg_rtf:.3f}")
        print()

        print("EN candidate")
        print(f"Transcript : {result['en_text']}")
        print(f"Inference  : {result['en_time']:.3f} s")
        print(f"RTF        : {en_rtf:.3f}")

    total_combined = total_bg_time + total_en_time

    bg_overall_rtf = (
        total_bg_time / total_audio
        if total_audio > 0
        else 0.0
    )

    en_overall_rtf = (
        total_en_time / total_audio
        if total_audio > 0
        else 0.0
    )

    combined_rtf = (
        total_combined / total_audio
        if total_audio > 0
        else 0.0
    )

    print()
    print("----------------------------------------")
    print(f"Total audio        : {total_audio:.3f} s")
    print(f"Total BG inference : {total_bg_time:.3f} s")
    print(f"Total EN inference : {total_en_time:.3f} s")
    print(f"BG overall RTF     : {bg_overall_rtf:.3f}")
    print(f"EN overall RTF     : {en_overall_rtf:.3f}")
    print(f"Combined inference : {total_combined:.3f} s")
    print(f"Combined RTF       : {combined_rtf:.3f}")
    print("----------------------------------------")
    print()


if __name__ == "__main__":
    main()