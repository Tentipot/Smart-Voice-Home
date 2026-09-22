import csv
import time
from pathlib import Path

import torch

from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)
from app.speech.stt.language_evidence import (
    LanguageEvidence,
)


ROOT_DIR = Path(__file__).resolve().parent

AUDIO_DIR = (
    ROOT_DIR
    / "data"
    / "stt_benchmark"
)

OUTPUT_PATH = (
    ROOT_DIR
    / "data"
    / "stt_ctc_pure_40.csv"
)


TESTS = [
    *[(number, "BG") for number in range(31, 41)],
    *[(number, "EN") for number in range(41, 51)],
    *[(number, "BG") for number in range(61, 71)],
    *[(number, "EN") for number in range(71, 81)],
]


CSV_FIELDS = [
    "test",
    "expected",
    "route",
    "correct",
    "confidence_delta",
    "min_confidence_delta",
    "entropy_delta",
    "uncertain_delta",
    "blank_ratio_delta",
    "blank_probability_delta",
    "token_rate_delta",
    "bg_mean_non_blank_confidence",
    "en_mean_non_blank_confidence",
    "bg_min_non_blank_confidence",
    "en_min_non_blank_confidence",
    "bg_non_blank_entropy",
    "en_non_blank_entropy",
    "bg_uncertain_non_blank_ratio",
    "en_uncertain_non_blank_ratio",
    "bg_blank_prediction_ratio",
    "en_blank_prediction_ratio",
    "bg_mean_blank_probability",
    "en_mean_blank_probability",
    "bg_non_blank_token_rate",
    "en_non_blank_token_rate",
]


def route_from_entropy_delta(
    entropy_delta: float,
) -> str:
    """
    Frozen diagnostic rule.

    This is the same rule used by the previous
    CTC routing validation:

        entropy_delta < 0 -> BG
        entropy_delta > 0 -> EN
        entropy_delta = 0 -> AMBIGUOUS

    No threshold is tuned here.
    """

    if entropy_delta < 0.0:
        return "BG"

    if entropy_delta > 0.0:
        return "EN"

    return "AMBIGUOUS"


def evidence_to_row(
    test_number: int,
    expected: str,
    evidence: LanguageEvidence,
) -> dict[str, object]:
    bg = evidence.bulgarian
    en = evidence.english

    route = route_from_entropy_delta(
        evidence.entropy_delta
    )

    return {
        "test": test_number,
        "expected": expected,
        "route": route,
        "correct": route == expected,
        "confidence_delta":
            evidence.confidence_delta,
        "min_confidence_delta":
            evidence.min_confidence_delta,
        "entropy_delta":
            evidence.entropy_delta,
        "uncertain_delta":
            evidence.uncertain_delta,
        "blank_ratio_delta":
            evidence.blank_ratio_delta,
        "blank_probability_delta":
            evidence.blank_probability_delta,
        "token_rate_delta":
            evidence.token_rate_delta,
        "bg_mean_non_blank_confidence":
            bg.mean_non_blank_confidence,
        "en_mean_non_blank_confidence":
            en.mean_non_blank_confidence,
        "bg_min_non_blank_confidence":
            bg.min_non_blank_confidence,
        "en_min_non_blank_confidence":
            en.min_non_blank_confidence,
        "bg_non_blank_entropy":
            bg.non_blank_entropy,
        "en_non_blank_entropy":
            en.non_blank_entropy,
        "bg_uncertain_non_blank_ratio":
            bg.uncertain_non_blank_ratio,
        "en_uncertain_non_blank_ratio":
            en.uncertain_non_blank_ratio,
        "bg_blank_prediction_ratio":
            bg.blank_prediction_ratio,
        "en_blank_prediction_ratio":
            en.blank_prediction_ratio,
        "bg_mean_blank_probability":
            bg.mean_blank_probability,
        "en_mean_blank_probability":
            en.mean_blank_probability,
        "bg_non_blank_token_rate":
            bg.non_blank_token_rate,
        "en_non_blank_token_rate":
            en.non_blank_token_rate,
    }


def main() -> None:
    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available."
        )

    missing_files = []

    for test_number, _ in TESTS:
        audio_path = (
            AUDIO_DIR
            / f"test_{test_number:03d}.wav"
        )

        if not audio_path.is_file():
            missing_files.append(
                audio_path
            )

    if missing_files:
        missing_text = "\n".join(
            str(path)
            for path in missing_files
        )

        raise FileNotFoundError(
            "Missing audio files:\n"
            f"{missing_text}"
        )

    print()
    print("=" * 72)
    print("CTC PURE-LANGUAGE EVIDENCE DATASET")
    print("=" * 72)
    print()
    print("Tests:")
    print("  031-040 -> BG")
    print("  041-050 -> EN")
    print("  061-070 -> BG")
    print("  071-080 -> EN")
    print()
    print(f"Total: {len(TESTS)}")
    print()
    print(
        "Loading paired BG/EN CTC evidence provider..."
    )
    print()

    load_start = time.perf_counter()

    provider = CtcLanguageEvidenceProvider()

    load_seconds = (
        time.perf_counter()
        - load_start
    )

    print(
        f"Models loaded in {load_seconds:.3f} s"
    )
    print()

    rows: list[dict[str, object]] = []

    analysis_start = time.perf_counter()

    for index, (
        test_number,
        expected,
    ) in enumerate(
        TESTS,
        start=1,
    ):
        audio_path = (
            AUDIO_DIR
            / f"test_{test_number:03d}.wav"
        )

        evidence = provider.analyze_file(
            audio_path
        )

        row = evidence_to_row(
            test_number=test_number,
            expected=expected,
            evidence=evidence,
        )

        rows.append(row)

        result = (
            "CORRECT"
            if row["correct"]
            else "WRONG"
        )

        print(
            f"{index:02d}/{len(TESTS)}  "
            f"test_{test_number:03d}  "
            f"expected={expected}  "
            f"route={row['route']}  "
            f"entropy_delta="
            f"{row['entropy_delta']:+.6f}  "
            f"{result}"
        )

    analysis_seconds = (
        time.perf_counter()
        - analysis_start
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDS,
        )

        writer.writeheader()
        writer.writerows(rows)

    bg_rows = [
        row
        for row in rows
        if row["expected"] == "BG"
    ]

    en_rows = [
        row
        for row in rows
        if row["expected"] == "EN"
    ]

    correct_rows = [
        row
        for row in rows
        if row["correct"]
    ]

    wrong_rows = [
        row
        for row in rows
        if not row["correct"]
    ]

    bg_correct = sum(
        1
        for row in bg_rows
        if row["correct"]
    )

    en_correct = sum(
        1
        for row in en_rows
        if row["correct"]
    )

    closest_rows = sorted(
        rows,
        key=lambda row: abs(
            float(row["entropy_delta"])
        ),
    )[:10]

    print()
    print("=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print()

    print(
        f"BG correct     : "
        f"{bg_correct}/{len(bg_rows)}"
    )

    print(
        f"EN correct     : "
        f"{en_correct}/{len(en_rows)}"
    )

    print(
        f"Total correct  : "
        f"{len(correct_rows)}/{len(rows)}"
    )

    print(
        f"Accuracy       : "
        f"{100.0 * len(correct_rows) / len(rows):.1f}%"
    )

    print()
    print(
        f"Analysis time  : "
        f"{analysis_seconds:.3f} s"
    )

    print()
    print("=" * 72)
    print("CLOSEST TO ZERO ENTROPY DELTA")
    print("=" * 72)
    print()

    for row in closest_rows:
        print(
            f"test_{int(row['test']):03d}  "
            f"expected={row['expected']}  "
            f"route={row['route']}  "
            f"entropy="
            f"{float(row['entropy_delta']):+.6f}  "
            f"conf="
            f"{float(row['confidence_delta']):+.6f}  "
            f"min_conf="
            f"{float(row['min_confidence_delta']):+.6f}  "
            f"uncertain="
            f"{float(row['uncertain_delta']):+.6f}"
        )

    if wrong_rows:
        print()
        print("=" * 72)
        print("MISROUTED SAMPLES")
        print("=" * 72)
        print()

        for row in wrong_rows:
            print(
                f"test_{int(row['test']):03d}  "
                f"expected={row['expected']}  "
                f"route={row['route']}  "
                f"entropy="
                f"{float(row['entropy_delta']):+.6f}"
            )

    print()
    print("=" * 72)
    print("CSV SAVED")
    print("=" * 72)
    print()
    print(OUTPUT_PATH)
    print()


if __name__ == "__main__":
    main()