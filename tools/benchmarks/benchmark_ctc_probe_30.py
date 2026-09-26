import math
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


def expected_track(
    number: int,
) -> str:
    if number <= 10:
        return "BG"

    if number <= 20:
        return "EN"

    return "MIXED"


def calculate_metrics(
    logits: torch.Tensor,
    blank_token_id: int,
) -> dict[str, float]:
    probabilities = torch.softmax(
        logits.float(),
        dim=-1,
    )

    max_probabilities, predicted_ids = (
        probabilities.max(dim=-1)
    )

    blank_probabilities = probabilities[
        ...,
        blank_token_id
    ]

    non_blank_mask = (
        predicted_ids != blank_token_id
    )

    blank_prediction_ratio = (
        (~non_blank_mask)
        .float()
        .mean()
        .item()
    )

    mean_blank_probability = (
        blank_probabilities.mean().item()
    )

    non_blank_confidences = (
        max_probabilities[non_blank_mask]
    )

    if non_blank_confidences.numel() > 0:
        mean_non_blank_confidence = (
            non_blank_confidences.mean().item()
        )

        min_non_blank_confidence = (
            non_blank_confidences.min().item()
        )
    else:
        mean_non_blank_confidence = 0.0
        min_non_blank_confidence = 0.0

    safe_probabilities = probabilities.clamp_min(
        1e-12
    )

    entropy = -(
        safe_probabilities
        * safe_probabilities.log()
    ).sum(dim=-1)

    vocabulary_size = probabilities.shape[-1]

    max_entropy = math.log(
        vocabulary_size
    )

    normalized_entropy = (
        entropy / max_entropy
    )

    mean_entropy = (
        normalized_entropy.mean().item()
    )

    if non_blank_mask.any():
        non_blank_entropy = (
            normalized_entropy[
                non_blank_mask
            ]
            .mean()
            .item()
        )
    else:
        non_blank_entropy = 1.0

    uncertain_non_blank_mask = (
        non_blank_mask
        & (max_probabilities < 0.70)
    )

    non_blank_count = (
        non_blank_mask.sum().item()
    )

    uncertain_non_blank_count = (
        uncertain_non_blank_mask.sum().item()
    )

    if non_blank_count > 0:
        uncertain_non_blank_ratio = (
            uncertain_non_blank_count
            / non_blank_count
        )
    else:
        uncertain_non_blank_ratio = 1.0

    return {
        "blank_prediction_ratio":
            blank_prediction_ratio,
        "mean_blank_probability":
            mean_blank_probability,
        "mean_non_blank_confidence":
            mean_non_blank_confidence,
        "min_non_blank_confidence":
            min_non_blank_confidence,
        "mean_entropy":
            mean_entropy,
        "non_blank_entropy":
            non_blank_entropy,
        "uncertain_non_blank_ratio":
            uncertain_non_blank_ratio,
    }


def main() -> None:
    print("Loading Bulgarian CTC probe...")
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

    blank_token_id = tokenizer.pad_token_id

    if blank_token_id is None:
        raise RuntimeError(
            "Tokenizer has no pad_token_id; "
            "cannot determine CTC blank token."
        )

    print(
        f"Load: {load_seconds:.3f} s"
    )

    print(
        f"Vocabulary size: {len(tokenizer)}"
    )

    print(
        f"CTC blank token ID: {blank_token_id}"
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
    print("BULGARIAN CTC 30-FILE ACOUSTIC PROBE")
    print("=" * 80)

    total_inference = 0.0
    total_audio = 0.0

    group_metrics: dict[
        str,
        list[dict[str, float]],
    ] = {
        "BG": [],
        "EN": [],
        "MIXED": [],
    }

    for number in range(1, 31):
        audio_path = AUDIO_DIR / (
            f"test_{number:03d}.wav"
        )

        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Missing audio file: {audio_path}"
            )

        track = expected_track(
            number
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

        predicted_ids = torch.argmax(
            logits,
            dim=-1,
        )

        transcript = tokenizer.batch_decode(
            predicted_ids
        )[0].strip()

        metrics = calculate_metrics(
            logits,
            blank_token_id,
        )

        group_metrics[
            track
        ].append(metrics)

        total_inference += inference_seconds
        total_audio += duration_seconds

        print()
        print(
            f"{number:03d} [{track}]"
        )

        print(
            f"TIME       : "
            f"{inference_seconds:.3f} s"
        )

        print(
            f"TEXT       : {transcript}"
        )

        print(
            "BLANK RATIO: "
            f"{metrics['blank_prediction_ratio']:.4f}"
        )

        print(
            "BLANK PROB : "
            f"{metrics['mean_blank_probability']:.4f}"
        )

        print(
            "NB CONF    : "
            f"{metrics['mean_non_blank_confidence']:.4f}"
        )

        print(
            "NB MIN CONF: "
            f"{metrics['min_non_blank_confidence']:.4f}"
        )

        print(
            "ENTROPY    : "
            f"{metrics['mean_entropy']:.4f}"
        )

        print(
            "NB ENTROPY : "
            f"{metrics['non_blank_entropy']:.4f}"
        )

        print(
            "NB UNC <.70: "
            f"{metrics['uncertain_non_blank_ratio']:.4f}"
        )

    print()
    print("=" * 80)
    print("GROUP AVERAGES")
    print("=" * 80)

    metric_names = (
        "blank_prediction_ratio",
        "mean_blank_probability",
        "mean_non_blank_confidence",
        "min_non_blank_confidence",
        "mean_entropy",
        "non_blank_entropy",
        "uncertain_non_blank_ratio",
    )

    for track in (
        "BG",
        "EN",
        "MIXED",
    ):
        values = group_metrics[
            track
        ]

        print()
        print(track)

        for metric_name in metric_names:
            average_value = sum(
                item[metric_name]
                for item in values
            ) / len(values)

            print(
                f"  {metric_name:<28}: "
                f"{average_value:.4f}"
            )

    print()
    print("=" * 80)

    average = total_inference / 30
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