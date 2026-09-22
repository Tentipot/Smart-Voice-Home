from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)


DATASET_DIR = Path("data/language_dataset")
MANIFEST_PATH = DATASET_DIR / "manifest.csv"
OUTPUT_PATH = DATASET_DIR / "ctc_analysis.csv"

GREEN_BOLD = "\033[1;92m"
CYAN_BOLD = "\033[1;96m"
YELLOW_BOLD = "\033[1;93m"
RED_BOLD = "\033[1;91m"
RESET = "\033[0m"


METRICS = (
    "mean_non_blank_confidence",
    "min_non_blank_confidence",
    "non_blank_entropy",
    "uncertain_non_blank_ratio",
    "blank_prediction_ratio",
    "mean_blank_probability",
    "non_blank_token_rate",
)


def get_value(
    obj: Any,
    name: str,
) -> Any:
    if isinstance(obj, dict):
        return obj[name]

    return getattr(obj, name)


def evidence_to_dict(
    evidence: Any,
) -> dict[str, float]:
    if is_dataclass(evidence):
        raw = asdict(evidence)

    elif isinstance(evidence, dict):
        raw = evidence

    else:
        raw = {
            name: getattr(evidence, name)
            for name in METRICS
        }

    return {
        name: float(raw[name])
        for name in METRICS
    }


def current_mode_from_delta(
    delta: float,
) -> str:
    if delta < 0.0:
        return "BG"

    if delta > 0.0:
        return "EN"

    return "MIX"


def fmt(
    value: float,
) -> str:
    return f"{value:+.6f}"


def percentile(
    values: list[float],
    fraction: float,
) -> float:
    if not values:
        return math.nan

    ordered = sorted(values)

    if len(ordered) == 1:
        return ordered[0]

    position = (
        (len(ordered) - 1)
        * fraction
    )

    low = math.floor(position)
    high = math.ceil(position)

    if low == high:
        return ordered[low]

    weight = position - low

    return (
        ordered[low]
        * (1.0 - weight)
        + ordered[high]
        * weight
    )


def print_distribution(
    label: str,
    values: list[float],
) -> None:
    if not values:
        print(
            f"{label}: no samples"
        )
        return

    print(
        f"{label}: "
        f"n={len(values)} "
        f"min={fmt(min(values))} "
        f"p25={fmt(percentile(values, 0.25))} "
        f"median={fmt(statistics.median(values))} "
        f"p75={fmt(percentile(values, 0.75))} "
        f"max={fmt(max(values))} "
        f"mean={fmt(statistics.mean(values))}"
    )


def load_manifest() -> list[dict[str, str]]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Manifest not found: "
            f"{MANIFEST_PATH}"
        )

    with MANIFEST_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    if not rows:
        raise RuntimeError(
            "Manifest is empty."
        )

    return rows


def validate_manifest(
    rows: list[dict[str, str]],
) -> None:
    filenames: set[str] = set()

    for row_number, row in enumerate(
        rows,
        start=2,
    ):
        filename = (
            row.get(
                "filename",
                "",
            )
            .strip()
        )

        label = (
            row.get(
                "label",
                "",
            )
            .strip()
            .upper()
        )

        prompted_text = (
            row.get(
                "prompted_text",
                "",
            )
            .strip()
        )

        if not filename:
            raise RuntimeError(
                f"Manifest row {row_number}: "
                f"missing filename."
            )

        if filename in filenames:
            raise RuntimeError(
                f"Duplicate filename in "
                f"manifest: {filename}"
            )

        filenames.add(
            filename
        )

        if label not in {
            "BG",
            "EN",
        }:
            raise RuntimeError(
                f"Manifest row {row_number}: "
                f"invalid label {label!r}"
            )

        if not prompted_text:
            raise RuntimeError(
                f"Manifest row {row_number}: "
                f"missing prompted_text."
            )

        wav_path = (
            DATASET_DIR
            / filename
        )

        if not wav_path.exists():
            raise FileNotFoundError(
                f"WAV from manifest "
                f"does not exist: "
                f"{wav_path}"
            )

    wav_files = {
        path.name
        for path in DATASET_DIR.glob(
            "*.wav"
        )
    }

    extra_wavs = (
        wav_files
        - filenames
    )

    missing_wavs = (
        filenames
        - wav_files
    )

    if extra_wavs:
        raise RuntimeError(
            "WAV files not present in "
            "manifest: "
            + ", ".join(
                sorted(extra_wavs)
            )
        )

    if missing_wavs:
        raise RuntimeError(
            "Manifest files missing from "
            "dataset: "
            + ", ".join(
                sorted(missing_wavs)
            )
        )


def write_analysis_csv(
    results: list[dict[str, Any]],
) -> None:
    fieldnames = [
        "sample",
        "filename",
        "ground_truth",
        "prompted_text",
        "duration_seconds",
        "rms",
        "wake_text",
        "current_prediction",
        "current_correct",
        "entropy_delta",
    ]

    for prefix in (
        "bg",
        "en",
    ):
        for metric in METRICS:
            fieldnames.append(
                f"{prefix}_{metric}"
            )

    with OUTPUT_PATH.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for result in results:
            writer.writerow(
                {
                    name: result.get(
                        name,
                        "",
                    )
                    for name in fieldnames
                }
            )


def print_current_rule_summary(
    results: list[dict[str, Any]],
) -> None:
    print()
    print(
        CYAN_BOLD
        + "=== CURRENT ZERO-BOUNDARY RULE ==="
        + RESET
    )

    total = len(results)

    correct = sum(
        1
        for row in results
        if row["current_correct"]
    )

    print(
        f"Overall: "
        f"{correct}/{total} "
        f"correct "
        f"({100.0 * correct / total:.1f}%)"
    )

    for label in (
        "BG",
        "EN",
    ):
        subset = [
            row
            for row in results
            if row["ground_truth"]
            == label
        ]

        if not subset:
            print(
                f"{label}: "
                f"no samples in this run"
            )
            continue

        subset_correct = sum(
            1
            for row in subset
            if row["current_correct"]
        )

        accuracy = (
            100.0
            * subset_correct
            / len(subset)
        )

        print(
            f"{label}: "
            f"{subset_correct}/"
            f"{len(subset)} "
            f"correct "
            f"({accuracy:.1f}%)"
        )

    print()
    print(
        "Confusion:"
    )

    for truth in (
        "BG",
        "EN",
    ):
        subset = [
            row
            for row in results
            if row["ground_truth"]
            == truth
        ]

        if not subset:
            print(
                f"Truth {truth}: "
                f"no samples"
            )
            continue

        predicted_bg = sum(
            1
            for row in subset
            if row[
                "current_prediction"
            ]
            == "BG"
        )

        predicted_en = sum(
            1
            for row in subset
            if row[
                "current_prediction"
            ]
            == "EN"
        )

        predicted_mix = sum(
            1
            for row in subset
            if row[
                "current_prediction"
            ]
            == "MIX"
        )

        print(
            f"Truth {truth}: "
            f"pred BG={predicted_bg}, "
            f"pred EN={predicted_en}, "
            f"pred MIX={predicted_mix}"
        )


def print_delta_summary(
    results: list[dict[str, Any]],
) -> None:
    print()
    print(
        CYAN_BOLD
        + "=== ENTROPY DELTA DISTRIBUTION ==="
        + RESET
    )

    bg_values = [
        row["entropy_delta"]
        for row in results
        if row["ground_truth"]
        == "BG"
    ]

    en_values = [
        row["entropy_delta"]
        for row in results
        if row["ground_truth"]
        == "EN"
    ]

    print_distribution(
        "BG",
        bg_values,
    )

    print_distribution(
        "EN",
        en_values,
    )

    if not bg_values or not en_values:
        print()
        print(
            YELLOW_BOLD
            + "Both BG and EN samples are "
            + "required for separation analysis."
            + RESET
        )
        return

    bg_max = max(
        bg_values
    )

    en_min = min(
        en_values
    )

    print()

    print(
        f"BG maximum delta: "
        f"{fmt(bg_max)}"
    )

    print(
        f"EN minimum delta: "
        f"{fmt(en_min)}"
    )

    if bg_max < en_min:
        midpoint = (
            bg_max
            + en_min
        ) / 2.0

        print(
            GREEN_BOLD
            + "CLEAN SEPARATION EXISTS."
            + RESET
        )

        print(
            f"Gap: "
            f"{en_min - bg_max:.6f}"
        )

        print(
            f"Midpoint candidate: "
            f"{midpoint:+.6f}"
        )

        print(
            "This is diagnostic only; "
            "LanguageResolver has NOT "
            "been changed."
        )

    else:
        overlap = (
            bg_max
            - en_min
        )

        print(
            YELLOW_BOLD
            + "BG/EN DELTA RANGES OVERLAP."
            + RESET
        )

        print(
            f"Overlap span: "
            f"{overlap:.6f}"
        )

        print(
            "A single entropy-delta "
            "threshold cannot perfectly "
            "separate this dataset."
        )


def print_metric_separation(
    results: list[dict[str, Any]],
) -> None:
    print()
    print(
        CYAN_BOLD
        + "=== FEATURE MEDIANS BY LANGUAGE ==="
        + RESET
    )

    bg_rows = [
        row
        for row in results
        if row["ground_truth"]
        == "BG"
    ]

    en_rows = [
        row
        for row in results
        if row["ground_truth"]
        == "EN"
    ]

    if not bg_rows or not en_rows:
        print(
            YELLOW_BOLD
            + "Both BG and EN samples are "
            + "required for feature comparison."
            + RESET
        )
        return

    print(
        "Positive DIFF means BG median "
        "is larger than EN median."
    )

    print()

    feature_names: list[str] = [
        "entropy_delta",
    ]

    for prefix in (
        "bg",
        "en",
    ):
        for metric in METRICS:
            feature_names.append(
                f"{prefix}_{metric}"
            )

    comparisons: list[
        tuple[
            float,
            str,
            float,
            float,
        ]
    ] = []

    for feature in feature_names:
        bg_values = [
            float(row[feature])
            for row in bg_rows
        ]

        en_values = [
            float(row[feature])
            for row in en_rows
        ]

        bg_median = (
            statistics.median(
                bg_values
            )
        )

        en_median = (
            statistics.median(
                en_values
            )
        )

        pooled = (
            statistics.pstdev(
                bg_values
                + en_values
            )
        )

        if pooled > 0.0:
            normalized_difference = (
                abs(
                    bg_median
                    - en_median
                )
                / pooled
            )
        else:
            normalized_difference = 0.0

        comparisons.append(
            (
                normalized_difference,
                feature,
                bg_median,
                en_median,
            )
        )

    comparisons.sort(
        reverse=True
    )

    for (
        score,
        feature,
        bg_median,
        en_median,
    ) in comparisons:
        difference = (
            bg_median
            - en_median
        )

        print(
            f"{feature:38s} "
            f"BG={bg_median:.6f} "
            f"EN={en_median:.6f} "
            f"DIFF={difference:+.6f} "
            f"SEP={score:.3f}"
        )


def print_errors(
    results: list[dict[str, Any]],
) -> None:
    errors = [
        row
        for row in results
        if not row["current_correct"]
    ]

    print()
    print(
        CYAN_BOLD
        + "=== CURRENT RULE ERRORS ==="
        + RESET
    )

    if not errors:
        print(
            GREEN_BOLD
            + "No errors."
            + RESET
        )
        return

    for row in errors:
        print(
            f"{row['sample']:02d} "
            f"truth={row['ground_truth']} "
            f"pred={row['current_prediction']} "
            f"delta="
            f"{row['entropy_delta']:+.6f} "
            f"{row['filename']}"
        )

        print(
            f"    "
            f"{row['prompted_text']}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Optional number of manifest "
            "samples to analyze."
        ),
    )

    args = parser.parse_args()

    rows = load_manifest()

    validate_manifest(
        rows
    )

    if args.limit is not None:
        if args.limit < 1:
            raise ValueError(
                "--limit must be >= 1"
            )

        rows = rows[
            : args.limit
        ]

    print(
        GREEN_BOLD
        + "=== CTC LANGUAGE DATASET ANALYSIS ==="
        + RESET
    )

    print(
        f"Dataset: "
        f"{DATASET_DIR.resolve()}"
    )

    print(
        f"Samples: {len(rows)}"
    )

    print()
    print(
        "Loading paired BG + EN CTC "
        "models..."
    )

    provider = (
        CtcLanguageEvidenceProvider()
    )

    print(
        GREEN_BOLD
        + "CTC models ready."
        + RESET
    )

    print()

    results: list[
        dict[str, Any]
    ] = []

    for index, row in enumerate(
        rows,
        start=1,
    ):
        filename = (
            row["filename"]
            .strip()
        )

        label = (
            row["label"]
            .strip()
            .upper()
        )

        wav_path = (
            DATASET_DIR
            / filename
        )

        print(
            CYAN_BOLD
            + f"[{index:02d}/{len(rows):02d}] "
            + f"{label} "
            + RESET
            + filename,
            flush=True,
        )

        evidence = (
            provider.analyze_file(
                wav_path
            )
        )

        bg = evidence_to_dict(
            get_value(
                evidence,
                "bulgarian",
            )
        )

        en = evidence_to_dict(
            get_value(
                evidence,
                "english",
            )
        )

        entropy_delta = (
            bg[
                "non_blank_entropy"
            ]
            - en[
                "non_blank_entropy"
            ]
        )

        current_prediction = (
            current_mode_from_delta(
                entropy_delta
            )
        )

        current_correct = (
            current_prediction
            == label
        )

        if current_correct:
            status = (
                GREEN_BOLD
                + "OK"
                + RESET
            )
        else:
            status = (
                RED_BOLD
                + "WRONG"
                + RESET
            )

        print(
            f"    delta="
            f"{entropy_delta:+.6f} "
            f"current="
            f"{current_prediction} "
            f"{status}"
        )

        result: dict[
            str,
            Any,
        ] = {
            "sample": index,
            "filename": filename,
            "ground_truth": label,
            "prompted_text": (
                row[
                    "prompted_text"
                ]
            ),
            "duration_seconds": (
                row.get(
                    "duration_seconds",
                    "",
                )
            ),
            "rms": row.get(
                "rms",
                "",
            ),
            "wake_text": row.get(
                "wake_text",
                "",
            ),
            "current_prediction": (
                current_prediction
            ),
            "current_correct": (
                current_correct
            ),
            "entropy_delta": (
                entropy_delta
            ),
        }

        for metric in METRICS:
            result[
                f"bg_{metric}"
            ] = bg[metric]

            result[
                f"en_{metric}"
            ] = en[metric]

        results.append(
            result
        )

    write_analysis_csv(
        results
    )

    print_current_rule_summary(
        results
    )

    print_delta_summary(
        results
    )

    print_metric_separation(
        results
    )

    print_errors(
        results
    )

    print()
    print(
        GREEN_BOLD
        + "=== ANALYSIS COMPLETE ==="
        + RESET
    )

    print(
        f"CSV: "
        f"{OUTPUT_PATH.resolve()}"
    )

    print()
    print(
        YELLOW_BOLD
        + "No LanguageResolver code "
        + "was changed."
        + RESET
    )


if __name__ == "__main__":
    main()