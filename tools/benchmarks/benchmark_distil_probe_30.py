import time
import wave
from pathlib import Path

import numpy as np
import torch
from transformers import (
    AutoModelForSpeechSeq2Seq,
    AutoProcessor,
)


MODEL_NAME = "distil-whisper/distil-large-v3.5"

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


def expected_track(
    number: int,
) -> str:
    if number <= 10:
        return "BG"

    if number <= 20:
        return "EN"

    return "MIXED"


def main() -> None:
    print("Loading Distil-Whisper probe...")
    print(f"Model: {MODEL_NAME}")
    print()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

    load_start = time.perf_counter()

    processor = AutoProcessor.from_pretrained(
        MODEL_NAME,
    )

    model = AutoModelForSpeechSeq2Seq.from_pretrained(
        MODEL_NAME,
        dtype=DTYPE,
        low_cpu_mem_usage=True,
        use_safetensors=True,
    )

    model.to(DEVICE)
    model.eval()

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    load_seconds = (
        time.perf_counter() - load_start
    )

    print(
        f"Load: {load_seconds:.3f} s"
    )

    if torch.cuda.is_available():
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
    print("DISTIL-WHISPER 30-FILE AUTO PROBE")
    print("=" * 80)

    total_inference = 0.0
    total_audio = 0.0

    for number in range(1, 31):
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

        inputs = processor(
            audio,
            sampling_rate=16000,
            return_tensors="pt",
            return_attention_mask=True,
        )

        model_inputs = {
            key: value.to(
                device=DEVICE,
                dtype=(
                    DTYPE
                    if value.dtype.is_floating_point
                    else value.dtype
                ),
            )
            for key, value in inputs.items()
        }

        if torch.cuda.is_available():
            torch.cuda.synchronize()

        start = time.perf_counter()

        with torch.inference_mode():
            generated_ids = model.generate(
                **model_inputs,
                max_new_tokens=128,
            )

        if torch.cuda.is_available():
            torch.cuda.synchronize()

        inference_seconds = (
            time.perf_counter() - start
        )

        text = processor.batch_decode(
            generated_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0].strip()

        total_inference += inference_seconds
        total_audio += duration_seconds

        print()
        print(
            f"{number:03d} "
            f"[{expected_track(number)}]"
        )

        print(
            f"TIME : {inference_seconds:.3f} s"
        )

        print(
            f"TEXT : {text}"
        )

    print()
    print("=" * 80)

    average = total_inference / 30
    rtf = total_inference / total_audio

    print(
        f"Total audio     : {total_audio:.3f} s"
    )

    print(
        f"Total inference : {total_inference:.3f} s"
    )

    print(
        f"Average         : {average:.3f} s"
    )

    print(
        f"RTF             : {rtf:.3f}"
    )

    if torch.cuda.is_available():
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