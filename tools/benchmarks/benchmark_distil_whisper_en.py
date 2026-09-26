import time
import wave
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor


MODEL_NAME = "distil-whisper/distil-large-v3.5"

BASE_DIR = Path(__file__).resolve().parents[2]
AUDIO_DIR = BASE_DIR / "data" / "stt_benchmark"


TESTS = [
    (11, "Set the volume to twenty percent"),
    (12, "Turn off the living room light"),
    (13, "Turn up the volume"),
    (14, "Stop the music"),
    (15, "Continue the music"),
    (16, "Play Metallica Enter Sandman on Spotify"),
    (17, "Play Dr. Dre Still D.R.E. on Spotify"),
    (18, "Play Guns N' Roses November Rain"),
    (19, "Turn on the kitchen light"),
    (20, "Restart the song"),
]


def get_audio_duration(file_path: Path) -> float:
    with wave.open(str(file_path), "rb") as wav_file:
        return wav_file.getnframes() / float(
            wav_file.getframerate()
        )


def load_audio(file_path: Path) -> np.ndarray:
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


def transcribe_file(
    model,
    processor,
    file_path: Path,
) -> tuple[str, float]:

    audio = load_audio(file_path)

    inputs = processor(
        audio,
        sampling_rate=16000,
        return_tensors="pt",
        return_attention_mask=True,
    )

    inputs = {
        key: value.to(
            device="cuda",
            dtype=(
                torch.float16
                if value.dtype.is_floating_point
                else value.dtype
            ),
        )
        for key, value in inputs.items()
    }

    torch.cuda.synchronize()
    start = time.perf_counter()

    with torch.inference_mode():
        generated_ids = model.generate(
            **inputs,
            max_new_tokens=128,
        )

    torch.cuda.synchronize()
    elapsed = time.perf_counter() - start

    transcript = processor.batch_decode(
        generated_ids,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )[0].strip()

    return transcript, elapsed


def main() -> None:
    print()
    print("=" * 78)
    print("DISTIL-WHISPER LARGE-V3.5 - EN BENCHMARK")
    print("=" * 78)
    print()

    print(f"Model : {MODEL_NAME}")
    print(f"Tests : {len(TESTS)}")
    print("Track : English only")
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

        for file_path in missing_files:
            print(file_path)

        return

    print("Corpus: OK")
    print()

    # ------------------------------------------------------------
    # GPU
    # ------------------------------------------------------------

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA GPU is not available."
        )

    print(
        f"GPU: {torch.cuda.get_device_name(0)}"
    )
    print()

    # ------------------------------------------------------------
    # Load processor
    # ------------------------------------------------------------

    print("Loading processor...")

    processor = AutoProcessor.from_pretrained(
        MODEL_NAME,
    )

    # ------------------------------------------------------------
    # Load model
    # ------------------------------------------------------------

    print("Loading model...")

    load_start = time.perf_counter()

    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        MODEL_NAME,
        dtype=torch.float16,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )

    model.to("cuda")
    model.eval()

    torch.cuda.synchronize()

    load_time = (
        time.perf_counter()
        - load_start
    )

    print(
        f"Model load time: {load_time:.3f} s"
    )

    allocated_gb = (
        torch.cuda.memory_allocated()
        / 1024**3
    )

    reserved_gb = (
        torch.cuda.memory_reserved()
        / 1024**3
    )

    print(
        "CUDA allocated after load: "
        f"{allocated_gb:.3f} GB"
    )

    print(
        "CUDA reserved after load : "
        f"{reserved_gb:.3f} GB"
    )

    print()

    # ------------------------------------------------------------
    # Warm-up — test 011, not counted
    # ------------------------------------------------------------

    warmup_file = (
        AUDIO_DIR
        / "test_011.wav"
    )

    print("Warming up...")

    warmup_text, warmup_time = (
        transcribe_file(
            model,
            processor,
            warmup_file,
        )
    )

    print(
        f"Warm-up transcript: {warmup_text}"
    )

    print(
        f"Warm-up time      : "
        f"{warmup_time:.3f} s"
    )

    print("Warm-up is NOT counted.")
    print()

    torch.cuda.reset_peak_memory_stats()

    # ------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------

    total_audio = 0.0
    total_inference = 0.0

    print("=" * 78)
    print("ENGLISH TESTS 011-020")
    print("=" * 78)

    for test_number, expected in TESTS:
        file_path = (
            AUDIO_DIR
            / f"test_{test_number:03d}.wav"
        )

        audio_duration = get_audio_duration(
            file_path
        )

        transcript, elapsed = (
            transcribe_file(
                model,
                processor,
                file_path,
            )
        )

        total_audio += audio_duration
        total_inference += elapsed

        print()
        print("-" * 78)
        print(f"TEST {test_number:03d}")
        print("-" * 78)
        print(f"EXPECTED : {expected}")
        print(f"DISTIL   : {transcript}")
        print(f"TIME     : {elapsed:.3f} s")

    # ------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------

    peak_allocated_gb = (
        torch.cuda.max_memory_allocated()
        / 1024**3
    )

    peak_reserved_gb = (
        torch.cuda.max_memory_reserved()
        / 1024**3
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

    print(
        f"Total inference     : "
        f"{total_inference:.3f} s"
    )

    if TESTS:
        print(
            "Average inference   : "
            f"{total_inference / len(TESTS):.3f} s"
        )

    if total_audio > 0:
        print(
            "RTF                 : "
            f"{total_inference / total_audio:.3f}"
        )

    print(
        "Peak CUDA allocated : "
        f"{peak_allocated_gb:.3f} GB"
    )

    print(
        "Peak CUDA reserved  : "
        f"{peak_reserved_gb:.3f} GB"
    )

    print()
    print("=" * 78)
    print(
        "DISTIL-WHISPER EN BENCHMARK COMPLETE"
    )
    print("=" * 78)
    print()


if __name__ == "__main__":
    main()