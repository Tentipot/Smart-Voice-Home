import time
import wave
from pathlib import Path

import torch
import nemo.collections.asr as nemo_asr


MODEL_NAME = "nvidia/parakeet-tdt-0.6b-v3"

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


def extract_text(result) -> str:
    if isinstance(result, tuple):
        result = result[0]

    first_result = result[0]

    if hasattr(first_result, "text"):
        return first_result.text.strip()

    return str(first_result).strip()


def main() -> None:
    print()
    print("Assistant STT Benchmark - Parakeet")
    print("==================================")
    print()

    for filename, _ in TESTS:
        file_path = BENCHMARK_DIR / filename

        if not file_path.exists():
            raise FileNotFoundError(
                f"Benchmark file not found: {file_path}"
            )

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")

    print(f"Model : {MODEL_NAME}")
    print(f"GPU   : {torch.cuda.get_device_name(0)}")
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
    print(
        "VRAM after load: "
        f"{torch.cuda.memory_allocated(0) / 1024**3:.2f} GB"
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

        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()

        start = time.perf_counter()

        with torch.inference_mode():
            result = model.transcribe(
                [str(file_path)],
                batch_size=1,
            )

        torch.cuda.synchronize()

        inference_seconds = time.perf_counter() - start

        transcript = extract_text(result)

        peak_vram_gb = (
            torch.cuda.max_memory_allocated()
            / 1024**3
        )

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
                "audio": audio_duration,
                "inference": inference_seconds,
                "rtf": rtf,
                "vram": peak_vram_gb,
            }
        )

    print()
    print("========================================")
    print("PARAKEET BENCHMARK RESULTS")
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
        print(
            f"Peak VRAM  : "
            f"{result['vram']:.2f} GB"
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