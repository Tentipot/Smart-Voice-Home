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

FIRST_TEST = 51
LAST_TEST = 60

SEGMENT_COUNT = 16


EXPECTED_COMMANDS = {
    51: "Пусни AC/DC Highway to Hell",
    52: "Пусни Metallica Enter Sandman в Spotify",
    53: "Намери ми акумулаторен винтоверт на Bosch с две батерии",
    54: "Пусни The Expanse в Stremio",
    55: "Стартирай климатика Gree спалня",
    56: "Пусни Guns N' Roses November Rain",
    57: "Намери ми телевизор Samsung с OLED дисплей",
    58: "Пусни Dr. Dre Still D.R.E. в Spotify",
    59: "Намери ми лаптоп Lenovo ThinkPad с шестнадесет гигабайта памет",
    60: "Пусни Guardians of the Galaxy на телевизора в хола",
}


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
            f"{model_name}: tokenizer has no pad_token_id."
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
) -> tuple[
    str,
    torch.Tensor,
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
        logits = model(input_values).logits

    torch.cuda.synchronize()

    inference_seconds = time.perf_counter() - start

    predicted_ids = torch.argmax(
        logits,
        dim=-1,
    )

    transcript = tokenizer.batch_decode(
        predicted_ids
    )[0].strip()

    return (
        transcript,
        logits[0].float().cpu(),
        inference_seconds,
    )


def segment_metrics(
    logits: torch.Tensor,
    blank_token_id: int,
    segment_count: int,
) -> list[dict[str, float]]:
    probabilities = torch.softmax(
        logits,
        dim=-1,
    )

    total_frames = probabilities.shape[0]

    boundaries = np.linspace(
        0,
        total_frames,
        segment_count + 1,
        dtype=int,
    )

    results: list[dict[str, float]] = []

    vocabulary_size = probabilities.shape[-1]
    max_entropy = math.log(vocabulary_size)

    for segment_index in range(segment_count):
        start = int(boundaries[segment_index])
        end = int(boundaries[segment_index + 1])

        if end <= start:
            end = min(
                start + 1,
                total_frames,
            )

        segment = probabilities[start:end]

        max_probabilities, predicted_ids = (
            segment.max(dim=-1)
        )

        non_blank_mask = (
            predicted_ids != blank_token_id
        )

        non_blank_count = int(
            non_blank_mask.sum().item()
        )

        frame_count = int(
            segment.shape[0]
        )

        if non_blank_count > 0:
            non_blank_confidence = (
                max_probabilities[
                    non_blank_mask
                ]
                .mean()
                .item()
            )

            safe_segment = segment.clamp_min(
                1e-12
            )

            entropy = -(
                safe_segment
                * safe_segment.log()
            ).sum(dim=-1)

            normalized_entropy = (
                entropy / max_entropy
            )

            non_blank_entropy = (
                normalized_entropy[
                    non_blank_mask
                ]
                .mean()
                .item()
            )

            uncertain_ratio = (
                (
                    max_probabilities[
                        non_blank_mask
                    ] < 0.70
                )
                .float()
                .mean()
                .item()
            )
        else:
            non_blank_confidence = 0.0
            non_blank_entropy = 1.0
            uncertain_ratio = 1.0

        token_rate = (
            non_blank_count / frame_count
            if frame_count > 0
            else 0.0
        )

        results.append(
            {
                "confidence":
                    non_blank_confidence,
                "entropy":
                    non_blank_entropy,
                "uncertain":
                    uncertain_ratio,
                "token_rate":
                    token_rate,
                "non_blank_count":
                    float(non_blank_count),
                "frame_count":
                    float(frame_count),
            }
        )

    return results


def safe_delta(
    bg_value: float,
    en_value: float,
) -> float:
    return bg_value - en_value


def evidence_symbol(
    confidence_delta: float,
    entropy_delta: float,
    bg_non_blank: float,
    en_non_blank: float,
) -> str:
    if (
        bg_non_blank == 0
        and en_non_blank == 0
    ):
        return "."

    bg_votes = 0
    en_votes = 0

    if confidence_delta > 0:
        bg_votes += 1
    elif confidence_delta < 0:
        en_votes += 1

    if entropy_delta < 0:
        bg_votes += 1
    elif entropy_delta > 0:
        en_votes += 1

    if bg_votes == 2:
        return "B"

    if en_votes == 2:
        return "E"

    return "?"


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available."
        )

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()

    print("=" * 88)
    print("SEGMENT-LEVEL HOLD-OUT VALIDATION — MIXED 051-060")
    print("=" * 88)
    print()
    print(
        "IMPORTANT: Same 16-segment diagnostic method "
        "used for 021-030."
    )
    print(
        "B/E/?/. is diagnostic evidence only."
    )
    print(
        "Do NOT tune thresholds from this hold-out corpus."
    )
    print()

    print("Loading BG CTC...")

    (
        bg_feature_extractor,
        bg_tokenizer,
        bg_model,
        bg_blank_id,
    ) = load_ctc_model(
        BG_MODEL_NAME
    )

    print("Loading EN CTC...")

    (
        en_feature_extractor,
        en_tokenizer,
        en_model,
        en_blank_id,
    ) = load_ctc_model(
        EN_MODEL_NAME
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

    total_bg_seconds = 0.0
    total_en_seconds = 0.0
    total_audio_seconds = 0.0

    for number in range(
        FIRST_TEST,
        LAST_TEST + 1,
    ):
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

        (
            bg_text,
            bg_logits,
            bg_seconds,
        ) = run_model(
            audio,
            bg_feature_extractor,
            bg_tokenizer,
            bg_model,
        )

        (
            en_text,
            en_logits,
            en_seconds,
        ) = run_model(
            audio,
            en_feature_extractor,
            en_tokenizer,
            en_model,
        )

        bg_segments = segment_metrics(
            bg_logits,
            bg_blank_id,
            SEGMENT_COUNT,
        )

        en_segments = segment_metrics(
            en_logits,
            en_blank_id,
            SEGMENT_COUNT,
        )

        total_audio_seconds += duration_seconds
        total_bg_seconds += bg_seconds
        total_en_seconds += en_seconds

        print()
        print("=" * 88)
        print(
            f"{number:03d}  "
            f"duration={duration_seconds:.3f}s  "
            f"BG={bg_seconds:.3f}s  "
            f"EN={en_seconds:.3f}s"
        )
        print("=" * 88)

        print()
        print("EXPECTED:")
        print(
            EXPECTED_COMMANDS[number]
        )

        print()
        print(
            f"BG TEXT: {bg_text}"
        )

        print(
            f"EN TEXT: {en_text}"
        )

        print()
        print(
            "SEG   TIME(s)       "
            "BGconf  ENconf   "
            "dCONF    "
            "BGent   ENent    "
            "dENT     "
            "BGtok  ENtok   EV"
        )

        print("-" * 88)

        symbols: list[str] = []

        for index in range(SEGMENT_COUNT):
            bg = bg_segments[index]
            en = en_segments[index]

            confidence_delta = safe_delta(
                bg["confidence"],
                en["confidence"],
            )

            entropy_delta = safe_delta(
                bg["entropy"],
                en["entropy"],
            )

            symbol = evidence_symbol(
                confidence_delta,
                entropy_delta,
                bg["non_blank_count"],
                en["non_blank_count"],
            )

            symbols.append(symbol)

            start_time = (
                duration_seconds
                * index
                / SEGMENT_COUNT
            )

            end_time = (
                duration_seconds
                * (index + 1)
                / SEGMENT_COUNT
            )

            print(
                f"{index + 1:02d}    "
                f"{start_time:4.1f}-{end_time:4.1f}    "
                f"{bg['confidence']:.3f}   "
                f"{en['confidence']:.3f}   "
                f"{confidence_delta:+.3f}   "
                f"{bg['entropy']:.3f}   "
                f"{en['entropy']:.3f}   "
                f"{entropy_delta:+.3f}   "
                f"{bg['token_rate']:.3f}  "
                f"{en['token_rate']:.3f}   "
                f"{symbol}"
            )

        print()
        print(
            "EVIDENCE TIMELINE: "
            + "".join(symbols)
        )

        print(
            "Legend: "
            "B=both simple metrics favor BG, "
            "E=both favor EN, "
            "?=disagreement, "
            ".=no non-blank evidence"
        )

    print()
    print("=" * 88)
    print("PERFORMANCE")
    print("=" * 88)

    combined_seconds = (
        total_bg_seconds
        + total_en_seconds
    )

    print(
        f"Total mixed audio: "
        f"{total_audio_seconds:.3f} s"
    )

    print(
        f"BG total         : "
        f"{total_bg_seconds:.3f} s"
    )

    print(
        f"EN total         : "
        f"{total_en_seconds:.3f} s"
    )

    print(
        f"Combined total   : "
        f"{combined_seconds:.3f} s"
    )

    print(
        f"Average / file   : "
        f"{combined_seconds / 10:.3f} s"
    )

    print(
        f"Combined RTF     : "
        f"{combined_seconds / total_audio_seconds:.4f}"
    )

    print(
        "Peak CUDA allocated: "
        f"{torch.cuda.max_memory_allocated() / 1024**3:.3f} GB"
    )

    print(
        "CUDA reserved      : "
        f"{torch.cuda.memory_reserved() / 1024**3:.3f} GB"
    )

    print("=" * 88)


if __name__ == "__main__":
    main()