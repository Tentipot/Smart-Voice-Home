import time
from pathlib import Path

import torch
from speechbrain.inference.classifiers import EncoderClassifier


MODEL_NAME = "speechbrain/lang-id-voxlingua107-ecapa"

AUDIO_DIR = Path(
    "D:/AssistantServer/data/stt_benchmark"
)

TESTS = [
    *[(number, "bg") for number in range(1, 11)],
    *[(number, "en") for number in range(11, 21)],
]


def find_label_index(
    classifier: EncoderClassifier,
    language_code: str,
) -> int:
    encoder = classifier.hparams.label_encoder

    for index in range(107):
        label = encoder.decode_torch(
            torch.tensor([index])
        )[0]

        code = label.split(":", 1)[0].strip()

        if code == language_code:
            return index

    raise RuntimeError(
        f"Language not found: {language_code}"
    )


def main() -> None:
    print("Loading LID model...")

    load_start = time.perf_counter()

    classifier = EncoderClassifier.from_hparams(
        source=MODEL_NAME,
        savedir="models/lid-voxlingua107-ecapa",
        run_opts={
            "device": "cuda",
        },
    )

    if torch.cuda.is_available():
        torch.cuda.synchronize()

    load_seconds = (
        time.perf_counter() - load_start
    )

    bg_index = find_label_index(
        classifier,
        "bg",
    )

    en_index = find_label_index(
        classifier,
        "en",
    )

    print()
    print(f"Load: {load_seconds:.3f} s")
    print(f"BG index: {bg_index}")
    print(f"EN index: {en_index}")
    print()

    print(
        "ID  EXP  PRED        "
        "BG SCORE   EN SCORE   "
        "BG-EN      TIME"
    )

    print("-" * 72)

    correct_top1 = 0
    correct_bg_en = 0
    total_inference = 0.0

    for number, expected in TESTS:
        audio_path = AUDIO_DIR / (
            f"test_{number:03d}.wav"
        )

        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Missing audio file: {audio_path}"
            )

        if torch.cuda.is_available():
            torch.cuda.synchronize()

        start = time.perf_counter()

        result = classifier.classify_file(
    audio_path.as_posix()
        )

        if torch.cuda.is_available():
            torch.cuda.synchronize()

        elapsed = (
            time.perf_counter() - start
        )

        total_inference += elapsed

        scores = result[0][0]
        predicted_label = result[3][0]

        predicted_code = predicted_label.split(
            ":",
            1,
        )[0].strip()

        bg_score = float(
            scores[bg_index].item()
        )

        en_score = float(
            scores[en_index].item()
        )

        margin = bg_score - en_score

        bg_en_prediction = (
            "bg"
            if bg_score > en_score
            else "en"
        )

        if predicted_code == expected:
            correct_top1 += 1

        if bg_en_prediction == expected:
            correct_bg_en += 1

        print(
            f"{number:03d} "
            f"{expected:>4} "
            f"{predicted_code:>8} "
            f"{bg_score:10.4f} "
            f"{en_score:10.4f} "
            f"{margin:9.4f} "
            f"{elapsed:7.3f}s"
        )

    print("-" * 72)
    print()

    total = len(TESTS)

    print(
        "Top-1 correct: "
        f"{correct_top1}/{total} "
        f"({correct_top1 / total:.1%})"
    )

    print(
        "BG-vs-EN correct: "
        f"{correct_bg_en}/{total} "
        f"({correct_bg_en / total:.1%})"
    )

    print(
        "Total inference: "
        f"{total_inference:.3f} s"
    )

    print(
        "Average: "
        f"{total_inference / total:.3f} s"
    )


if __name__ == "__main__":
    main()