import time
import wave
from pathlib import Path

import numpy as np
import torch
from transformers import (
    AutoModelForCTC,
    Wav2Vec2CTCTokenizer,
    Wav2Vec2FeatureExtractor,
)


MODEL_NAME = "anuragshas/wav2vec2-large-xls-r-300m-bg"

AUDIO_DIR = Path(
    "D:/AssistantServer/data/stt_benchmark"
)

DEVICE = "cuda"
DTYPE = torch.float16


def load_wav(
    audio_path: Path,
) -> tuple[np.ndarray, float]:
    with wave.open(
        str(audio_path),
        "rb",
    ) as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        frames = wav_file.readframes(
            frame_count
        )

    if channels != 1:
        raise ValueError(
            f"{audio_path.name}: expected mono, "
            f"got {channels} channels"
        )

    if sample_width != 2:
        raise ValueError(
            f"{audio_path.name}: expected 16-bit PCM, "
            f"got {sample_width * 8}-bit"
        )

    if sample_rate != 16000:
        raise ValueError(
            f"{audio_path.name}: expected 16000 Hz, "
            f"got {sample_rate} Hz"
        )

    audio = np.frombuffer(
        frames,
        dtype=np.int16,
    ).astype(np.float32)

    audio /= 32768.0

    duration_seconds = (
        frame_count / float(sample_rate)
    )

    return audio, duration_seconds


def main() -> None:
    print("Loading Bulgarian CTC model...")
    print(f"Model: {MODEL_NAME}")
    print()

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available."
        )

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    load_start = time.perf_counter()

    feature_extractor = (
        Wav2Vec2FeatureExtractor.from_pretrained(
            MODEL_NAME,
        )
    )

    tokenizer = (
        Wav2Vec2CTCTokenizer.from_pretrained(
            MODEL_NAME,
        )
    )

    model = AutoModelForCTC.from_pretrained(
        MODEL_NAME,
        dtype=DTYPE,
        low_cpu_mem_usage=True,
    )

    model.to(DEVICE)
    model.eval()

    torch.cuda.synchronize()

    load_seconds = (
        time.perf_counter() - load_start
    )

    print(
        f"Load: {load_seconds:.3f} s"
    )

    print(
        "CUDA allocated after load: "
        f"{torch.cuda.memory_allocated() / 1024**3:.3f} GB"
    )

    print(
        "CUDA reserved after load: "
        f"{torch.cuda.memory_reserved() / 1024**3:.3f} GB"
    )

    print()
    print("=" * 80)
    print("BULGARIAN CTC TEST 001-010")
    print("=" * 80)

    total_inference = 0.0
    total_audio = 0.0

    for number in range(1, 11):
        audio_path = AUDIO_DIR / (
            f"test_{number:03d}.wav"
        )

        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Missing audio file: {audio_path}"
            )

        audio, duration_seconds = load_wav(
            audio_path
        )

        inputs = feature_extractor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
        )

        input_values = inputs.input_values.to(
            device=DEVICE,
            dtype=DTYPE,
        )

        torch.cuda.synchronize()

        start = time.perf_counter()

        with torch.inference_mode():
            logits = model(
                input_values
            ).logits

        torch.cuda.synchronize()

        inference_seconds = (
            time.perf_counter() - start
        )

        probabilities = torch.softmax(
            logits.float(),
            dim=-1,
        )

        frame_confidence, predicted_ids = (
            probabilities.max(dim=-1)
        )

        transcript = tokenizer.batch_decode(
            predicted_ids
        )[0].strip()

        mean_frame_confidence = (
            frame_confidence.mean().item()
        )

        min_frame_confidence = (
            frame_confidence.min().item()
        )

        uncertain_ratio = (
            (
                frame_confidence < 0.70
            )
            .float()
            .mean()
            .item()
        )

        total_inference += inference_seconds
        total_audio += duration_seconds

        print()
        print(
            f"{number:03d} [BG]"
        )

        print(
            f"TIME       : "
            f"{inference_seconds:.3f} s"
        )

        print(
            f"TEXT       : "
            f"{transcript}"
        )

        print(
            f"MEAN CONF  : "
            f"{mean_frame_confidence:.4f}"
        )

        print(
            f"MIN CONF   : "
            f"{min_frame_confidence:.4f}"
        )

        print(
            f"UNCERT <.70: "
            f"{uncertain_ratio:.4f}"
        )

    print()
    print("=" * 80)

    average = total_inference / 10
    rtf = total_inference / total_audio

    print(
        f"Total audio     : "
        f"{total_audio:.3f} s"
    )

    print(
        f"Total inference : "
        f"{total_inference:.3f} s"
    )

    print(
        f"Average         : "
        f"{average:.3f} s"
    )

    print(
        f"RTF             : "
        f"{rtf:.3f}"
    )

    print(
        "Peak CUDA allocated: "
        f"{torch.cuda.max_memory_allocated() / 1024**3:.3f} GB"
    )

    print(
        "CUDA reserved: "
        f"{torch.cuda.memory_reserved() / 1024**3:.3f} GB"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()