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


BG_MODEL_NAME = "anuragshas/wav2vec2-large-xls-r-300m-bg"
EN_MODEL_NAME = "jonatasgrosman/wav2vec2-large-xlsr-53-english"

AUDIO_DIR = Path("D:/AssistantServer/data/stt_benchmark")

DEVICE = "cuda"
DTYPE = torch.float16


def load_wav(
    audio_path: Path,
) -> tuple[np.ndarray, float]:
    with wave.open(str(audio_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        frames = wav_file.readframes(frame_count)

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

    duration_seconds = frame_count / float(sample_rate)

    return audio, duration_seconds


def expected_track(number: int) -> str:
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

    max_probabilities, predicted_ids = probabilities.max(
        dim=-1
    )

    blank_probabilities = probabilities[
        ...,
        blank_token_id
    ]

    non_blank_mask = predicted_ids != blank_token_id

    blank_prediction_ratio = (
        (~non_blank_mask)
        .float()
        .mean()
        .item()
    )

    mean_blank_probability = (
        blank_probabilities.mean().item()
    )

    non_blank_confidences = max_probabilities[
        non_blank_mask
    ]

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
    max_entropy = math.log(vocabulary_size)

    normalized_entropy = entropy / max_entropy

    mean_entropy = normalized_entropy.mean().item()

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

    non_blank_count = non_blank_mask.sum().item()

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

    non_blank_token_rate = (
        non_blank_count
        / predicted_ids.numel()
    )

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
        "non_blank_token_rate":
            non_blank_token_rate,
    }


def load_ctc_model(
    model_name: str,
) -> tuple[
    Wav2Vec2FeatureExtractor,
    Wav2Vec2CTCTokenizer,
    AutoModelForCTC,
    int,
]:
    feature_extractor = (
        Wav2Vec2FeatureExtractor.from_pretrained(
            model_name
        )
    )

    tokenizer = (
        Wav2Vec2CTCTokenizer.from_pretrained(
            model_name
        )
    )

    model = AutoModelForCTC.from_pretrained(
        model_name,
        dtype=DTYPE,
        low_cpu_mem_usage=True,
    )

    model.to(DEVICE)
    model.eval()

    blank_token_id = tokenizer.pad_token_id

    if blank_token_id is None:
        raise RuntimeError(
            f"{model_name}: tokenizer has no "
            "pad_token_id."
        )

    return (
        feature_extractor,
        tokenizer,
        model,
        blank_token_id,
    )


def run_model(
    audio: np.ndarray,
    feature_extractor: Wav2Vec2FeatureExtractor,
    tokenizer: Wav2Vec2CTCTokenizer,
    model: AutoModelForCTC,
    blank_token_id: int,
) -> tuple[
    str,
    dict[str, float],
    float,
]:
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

    return (
        transcript,
        metrics,
        inference_seconds,
    )


def calculate_deltas(
    bg: dict[str, float],
    en: dict[str, float],
) -> dict[str, float]:
    return {
        "confidence_delta":
            bg["mean_non_blank_confidence"]
            - en["mean_non_blank_confidence"],

        "min_confidence_delta":
            bg["min_non_blank_confidence"]
            - en["min_non_blank_confidence"],

        "entropy_delta":
            bg["non_blank_entropy"]
            - en["non_blank_entropy"],

        "uncertain_delta":
            bg["uncertain_non_blank_ratio"]
            - en["uncertain_non_blank_ratio"],

        "blank_ratio_delta":
            bg["blank_prediction_ratio"]
            - en["blank_prediction_ratio"],

        "blank_probability_delta":
            bg["mean_blank_probability"]
            - en["mean_blank_probability"],

        "token_rate_delta":
            bg["non_blank_token_rate"]
            - en["non_blank_token_rate"],
    }


def print_group_summary(
    track: str,
    rows: list[dict[str, float]],
) -> None:
    print()
    print(track)
    print("-" * 80)

    names = (
        "confidence_delta",
        "min_confidence_delta",
        "entropy_delta",
        "uncertain_delta",
        "blank_ratio_delta",
        "blank_probability_delta",
        "token_rate_delta",
    )

    for name in names:
        values = [
            row[name]
            for row in rows
        ]

        average = sum(values) / len(values)
        minimum = min(values)
        maximum = max(values)

        print(
            f"{name:<26} "
            f"avg={average:+.4f}  "
            f"min={minimum:+.4f}  "
            f"max={maximum:+.4f}"
        )


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available."
        )

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    print("=" * 80)
    print("PAIRWISE BG CTC vs EN CTC")
    print("=" * 80)
    print()

    print("Loading BG CTC...")
    bg_load_start = time.perf_counter()

    (
        bg_feature_extractor,
        bg_tokenizer,
        bg_model,
        bg_blank_id,
    ) = load_ctc_model(
        BG_MODEL_NAME
    )

    torch.cuda.synchronize()

    bg_load_seconds = (
        time.perf_counter()
        - bg_load_start
    )

    print(
        f"BG loaded in "
        f"{bg_load_seconds:.3f} s"
    )

    print(
        f"BG vocabulary: "
        f"{len(bg_tokenizer)}"
    )

    print()
    print("Loading EN CTC...")

    en_load_start = time.perf_counter()

    (
        en_feature_extractor,
        en_tokenizer,
        en_model,
        en_blank_id,
    ) = load_ctc_model(
        EN_MODEL_NAME
    )

    torch.cuda.synchronize()

    en_load_seconds = (
        time.perf_counter()
        - en_load_start
    )

    print(
        f"EN loaded in "
        f"{en_load_seconds:.3f} s"
    )

    print(
        f"EN vocabulary: "
        f"{len(en_tokenizer)}"
    )

    print()
    print(
        "CUDA allocated with both models: "
        f"{torch.cuda.memory_allocated() / 1024**3:.3f} GB"
    )

    print(
        "CUDA reserved with both models: "
        f"{torch.cuda.memory_reserved() / 1024**3:.3f} GB"
    )

    print()
    print("=" * 80)
    print("30-FILE PAIRWISE ANALYSIS")
    print("=" * 80)

    groups: dict[
        str,
        list[dict[str, float]],
    ] = {
        "BG": [],
        "EN": [],
        "MIXED": [],
    }

    total_audio = 0.0
    total_bg_inference = 0.0
    total_en_inference = 0.0

    for number in range(1, 31):
        audio_path = AUDIO_DIR / (
            f"test_{number:03d}.wav"
        )

        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Missing audio file: "
                f"{audio_path}"
            )

        track = expected_track(number)

        audio, duration_seconds = load_wav(
            audio_path
        )

        (
            bg_text,
            bg_metrics,
            bg_seconds,
        ) = run_model(
            audio,
            bg_feature_extractor,
            bg_tokenizer,
            bg_model,
            bg_blank_id,
        )

        (
            en_text,
            en_metrics,
            en_seconds,
        ) = run_model(
            audio,
            en_feature_extractor,
            en_tokenizer,
            en_model,
            en_blank_id,
        )

        deltas = calculate_deltas(
            bg_metrics,
            en_metrics,
        )

        groups[track].append(
            deltas
        )

        total_audio += duration_seconds
        total_bg_inference += bg_seconds
        total_en_inference += en_seconds

        print()
        print(
            f"{number:03d} [{track}]"
        )

        print(
            f"BG TEXT : {bg_text}"
        )

        print(
            f"EN TEXT : {en_text}"
        )

        print(
            "BG NB confidence : "
            f"{bg_metrics['mean_non_blank_confidence']:.4f}"
        )

        print(
            "EN NB confidence : "
            f"{en_metrics['mean_non_blank_confidence']:.4f}"
        )

        print(
            "BG NB entropy    : "
            f"{bg_metrics['non_blank_entropy']:.4f}"
        )

        print(
            "EN NB entropy    : "
            f"{en_metrics['non_blank_entropy']:.4f}"
        )

        print(
            "BG uncertain     : "
            f"{bg_metrics['uncertain_non_blank_ratio']:.4f}"
        )

        print(
            "EN uncertain     : "
            f"{en_metrics['uncertain_non_blank_ratio']:.4f}"
        )

        print(
            "DELTA confidence : "
            f"{deltas['confidence_delta']:+.4f}"
        )

        print(
            "DELTA entropy    : "
            f"{deltas['entropy_delta']:+.4f}"
        )

        print(
            "DELTA uncertain  : "
            f"{deltas['uncertain_delta']:+.4f}"
        )

        print(
            "DELTA blank ratio: "
            f"{deltas['blank_ratio_delta']:+.4f}"
        )

        print(
            "DELTA token rate : "
            f"{deltas['token_rate_delta']:+.4f}"
        )

        print(
            f"TIME BG/EN       : "
            f"{bg_seconds:.3f} / "
            f"{en_seconds:.3f} s"
        )

    print()
    print("=" * 80)
    print("GROUP DELTA DISTRIBUTIONS")
    print()
    print(
        "All deltas are BG minus EN."
    )
    print(
        "Do NOT interpret their sign as a "
        "classifier without calibration."
    )
    print("=" * 80)

    for track in (
        "BG",
        "EN",
        "MIXED",
    ):
        print_group_summary(
            track,
            groups[track],
        )

    print()
    print("=" * 80)
    print("PERFORMANCE")
    print("=" * 80)

    total_ctc_inference = (
        total_bg_inference
        + total_en_inference
    )

    print(
        f"Total audio              : "
        f"{total_audio:.3f} s"
    )

    print(
        f"BG inference total       : "
        f"{total_bg_inference:.3f} s"
    )

    print(
        f"EN inference total       : "
        f"{total_en_inference:.3f} s"
    )

    print(
        f"Combined CTC inference   : "
        f"{total_ctc_inference:.3f} s"
    )

    print(
        f"Combined average / file  : "
        f"{total_ctc_inference / 30:.3f} s"
    )

    print(
        f"Combined RTF             : "
        f"{total_ctc_inference / total_audio:.4f}"
    )

    print(
        "Peak CUDA allocated     : "
        f"{torch.cuda.max_memory_allocated() / 1024**3:.3f} GB"
    )

    print(
        "CUDA reserved           : "
        f"{torch.cuda.memory_reserved() / 1024**3:.3f} GB"
    )

    print("=" * 80)


if __name__ == "__main__":
    main()