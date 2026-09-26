from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


CSV_PATH = Path(
    "data/language_dataset/ctc_analysis.csv"
)

GREEN_BOLD = "\033[1;92m"
CYAN_BOLD = "\033[1;96m"
YELLOW_BOLD = "\033[1;93m"
RED_BOLD = "\033[1;91m"
RESET = "\033[0m"


EXCLUDED_COLUMNS = {
    "sample",
    "filename",
    "ground_truth",
    "prompted_text",
    "duration_seconds",
    "rms",
    "wake_text",
    "current_prediction",
    "current_correct",
}


@dataclass(frozen=True)
class Sample:
    sample: int
    filename: str
    label: str
    prompt: str
    features: dict[str, float]


@dataclass(frozen=True)
class ThresholdRule:
    feature: str
    threshold: float
    bg_when_less: bool

    def predict(
        self,
        sample: Sample,
    ) -> str:
        value = sample.features[
            self.feature
        ]

        if self.bg_when_less:
            return (
                "BG"
                if value < self.threshold
                else "EN"
            )

        return (
            "BG"
            if value > self.threshold
            else "EN"
        )

    def describe(self) -> str:
        operator = (
            "<"
            if self.bg_when_less
            else ">"
        )

        return (
            f"BG if {self.feature} "
            f"{operator} "
            f"{self.threshold:.9f}; "
            f"otherwise EN"
        )


@dataclass(frozen=True)
class PairRule:
    first: ThresholdRule
    second: ThresholdRule
    use_and: bool

    def predict(
        self,
        sample: Sample,
    ) -> str:
        first_bg = (
            self.first.predict(sample)
            == "BG"
        )

        second_bg = (
            self.second.predict(sample)
            == "BG"
        )

        if self.use_and:
            is_bg = (
                first_bg
                and second_bg
            )
        else:
            is_bg = (
                first_bg
                or second_bg
            )

        return (
            "BG"
            if is_bg
            else "EN"
        )

    def describe(self) -> str:
        joiner = (
            " AND "
            if self.use_and
            else " OR "
        )

        first_op = (
            "<"
            if self.first.bg_when_less
            else ">"
        )

        second_op = (
            "<"
            if self.second.bg_when_less
            else ">"
        )

        return (
            "BG if ("
            f"{self.first.feature} "
            f"{first_op} "
            f"{self.first.threshold:.9f}"
            ")"
            f"{joiner}"
            "("
            f"{self.second.feature} "
            f"{second_op} "
            f"{self.second.threshold:.9f}"
            "); otherwise EN"
        )


def load_samples() -> list[Sample]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Missing analysis CSV: "
            f"{CSV_PATH}"
        )

    with CSV_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(
            csv.DictReader(file)
        )

    if not rows:
        raise RuntimeError(
            "ctc_analysis.csv is empty."
        )

    feature_names = [
        name
        for name in rows[0].keys()
        if name not in EXCLUDED_COLUMNS
    ]

    samples: list[Sample] = []

    for row in rows:
        features = {
            name: float(row[name])
            for name in feature_names
        }

        samples.append(
            Sample(
                sample=int(
                    row["sample"]
                ),
                filename=row[
                    "filename"
                ],
                label=row[
                    "ground_truth"
                ].strip().upper(),
                prompt=row[
                    "prompted_text"
                ].strip(),
                features=features,
            )
        )

    return samples


def candidate_thresholds(
    values: list[float],
) -> list[float]:
    unique = sorted(
        set(values)
    )

    if not unique:
        return []

    if len(unique) == 1:
        value = unique[0]

        epsilon = max(
            abs(value) * 1e-6,
            1e-9,
        )

        return [
            value - epsilon,
            value + epsilon,
        ]

    thresholds: list[float] = []

    first_gap = (
        unique[1]
        - unique[0]
    )

    thresholds.append(
        unique[0]
        - first_gap / 2.0
    )

    for left, right in zip(
        unique,
        unique[1:],
    ):
        thresholds.append(
            (
                left
                + right
            )
            / 2.0
        )

    last_gap = (
        unique[-1]
        - unique[-2]
    )

    thresholds.append(
        unique[-1]
        + last_gap / 2.0
    )

    return thresholds


def confusion(
    samples: list[Sample],
    predictor: Callable[
        [Sample],
        str,
    ],
) -> tuple[int, int, int, int]:
    bg_ok = 0
    bg_wrong = 0
    en_ok = 0
    en_wrong = 0

    for sample in samples:
        prediction = predictor(
            sample
        )

        if sample.label == "BG":
            if prediction == "BG":
                bg_ok += 1
            else:
                bg_wrong += 1

        elif sample.label == "EN":
            if prediction == "EN":
                en_ok += 1
            else:
                en_wrong += 1

        else:
            raise RuntimeError(
                f"Unexpected label: "
                f"{sample.label}"
            )

    return (
        bg_ok,
        bg_wrong,
        en_ok,
        en_wrong,
    )


def score_rule(
    samples: list[Sample],
    predictor: Callable[
        [Sample],
        str,
    ],
) -> tuple[
    float,
    float,
    int,
    int,
]:
    (
        bg_ok,
        bg_wrong,
        en_ok,
        en_wrong,
    ) = confusion(
        samples,
        predictor,
    )

    bg_total = (
        bg_ok
        + bg_wrong
    )

    en_total = (
        en_ok
        + en_wrong
    )

    bg_accuracy = (
        bg_ok / bg_total
        if bg_total
        else 0.0
    )

    en_accuracy = (
        en_ok / en_total
        if en_total
        else 0.0
    )

    balanced_accuracy = (
        bg_accuracy
        + en_accuracy
    ) / 2.0

    total_errors = (
        bg_wrong
        + en_wrong
    )

    worst_language_errors = max(
        bg_wrong,
        en_wrong,
    )

    return (
        balanced_accuracy,
        min(
            bg_accuracy,
            en_accuracy,
        ),
        -worst_language_errors,
        -total_errors,
    )


def feature_names(
    samples: list[Sample],
) -> list[str]:
    if not samples:
        return []

    return sorted(
        samples[0].features.keys()
    )


def best_single_rule(
    train: list[Sample],
) -> ThresholdRule:
    best_rule: (
        ThresholdRule
        | None
    ) = None

    best_score: (
        tuple[
            float,
            float,
            int,
            int,
        ]
        | None
    ) = None

    for feature in feature_names(
        train
    ):
        values = [
            sample.features[
                feature
            ]
            for sample in train
        ]

        for threshold in (
            candidate_thresholds(
                values
            )
        ):
            for bg_when_less in (
                True,
                False,
            ):
                rule = ThresholdRule(
                    feature=feature,
                    threshold=threshold,
                    bg_when_less=(
                        bg_when_less
                    ),
                )

                score = score_rule(
                    train,
                    rule.predict,
                )

                if (
                    best_score is None
                    or score > best_score
                ):
                    best_score = score
                    best_rule = rule

    if best_rule is None:
        raise RuntimeError(
            "Could not find a "
            "single-feature rule."
        )

    return best_rule


def top_threshold_rules(
    train: list[Sample],
    per_feature: int = 4,
) -> list[ThresholdRule]:
    result: list[
        ThresholdRule
    ] = []

    for feature in feature_names(
        train
    ):
        candidates: list[
            tuple[
                tuple[
                    float,
                    float,
                    int,
                    int,
                ],
                ThresholdRule,
            ]
        ] = []

        values = [
            sample.features[
                feature
            ]
            for sample in train
        ]

        for threshold in (
            candidate_thresholds(
                values
            )
        ):
            for bg_when_less in (
                True,
                False,
            ):
                rule = ThresholdRule(
                    feature=feature,
                    threshold=threshold,
                    bg_when_less=(
                        bg_when_less
                    ),
                )

                candidates.append(
                    (
                        score_rule(
                            train,
                            rule.predict,
                        ),
                        rule,
                    )
                )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        result.extend(
            rule
            for _, rule
            in candidates[
                :per_feature
            ]
        )

    return result


def best_pair_rule(
    train: list[Sample],
) -> PairRule:
    base_rules = (
        top_threshold_rules(
            train,
            per_feature=4,
        )
    )

    best_rule: (
        PairRule
        | None
    ) = None

    best_score: (
        tuple[
            float,
            float,
            int,
            int,
        ]
        | None
    ) = None

    for index, first in enumerate(
        base_rules
    ):
        for second in (
            base_rules[
                index + 1:
            ]
        ):
            if (
                first.feature
                == second.feature
            ):
                continue

            for use_and in (
                True,
                False,
            ):
                rule = PairRule(
                    first=first,
                    second=second,
                    use_and=use_and,
                )

                score = score_rule(
                    train,
                    rule.predict,
                )

                if (
                    best_score is None
                    or score > best_score
                ):
                    best_score = score
                    best_rule = rule

    if best_rule is None:
        raise RuntimeError(
            "Could not find a "
            "two-feature rule."
        )

    return best_rule


def print_evaluation(
    title: str,
    samples: list[Sample],
    predictor: Callable[
        [Sample],
        str,
    ],
) -> None:
    (
        bg_ok,
        bg_wrong,
        en_ok,
        en_wrong,
    ) = confusion(
        samples,
        predictor,
    )

    total = len(samples)

    correct = (
        bg_ok
        + en_ok
    )

    bg_total = (
        bg_ok
        + bg_wrong
    )

    en_total = (
        en_ok
        + en_wrong
    )

    print(
        f"{title}: "
        f"{correct}/{total} "
        f"({100.0 * correct / total:.1f}%)"
    )

    print(
        f"    BG: "
        f"{bg_ok}/{bg_total} "
        f"correct, "
        f"{bg_wrong} wrong"
    )

    print(
        f"    EN: "
        f"{en_ok}/{en_total} "
        f"correct, "
        f"{en_wrong} wrong"
    )


def print_errors(
    samples: list[Sample],
    predictor: Callable[
        [Sample],
        str,
    ],
) -> None:
    errors = [
        (
            sample,
            predictor(sample),
        )
        for sample in samples
        if predictor(sample)
        != sample.label
    ]

    if not errors:
        print(
            GREEN_BOLD
            + "    No test errors."
            + RESET
        )
        return

    for sample, prediction in errors:
        print(
            RED_BOLD
            + "    WRONG "
            + RESET
            + f"truth={sample.label} "
            + f"pred={prediction} "
            + f"{sample.filename}"
        )

        print(
            f"        "
            f"{sample.prompt}"
        )


def split_by_repetition(
    samples: list[Sample],
) -> tuple[
    list[Sample],
    list[Sample],
]:
    counters: dict[
        tuple[str, str],
        int,
    ] = {}

    first: list[Sample] = []
    second: list[Sample] = []

    for sample in samples:
        key = (
            sample.label,
            sample.prompt,
        )

        occurrence = (
            counters.get(
                key,
                0,
            )
            + 1
        )

        counters[key] = (
            occurrence
        )

        if occurrence == 1:
            first.append(
                sample
            )

        elif occurrence == 2:
            second.append(
                sample
            )

        else:
            raise RuntimeError(
                "Expected exactly two "
                "recordings per "
                "language/prompt pair. "
                f"Found occurrence "
                f"{occurrence} for "
                f"{key!r}."
            )

    incomplete = [
        key
        for key, count
        in counters.items()
        if count != 2
    ]

    if incomplete:
        raise RuntimeError(
            "Dataset does not contain "
            "exactly two repetitions for: "
            + repr(incomplete)
        )

    return (
        first,
        second,
    )


def evaluate_fold(
    *,
    name: str,
    train: list[Sample],
    test: list[Sample],
) -> None:
    print()
    print(
        CYAN_BOLD
        + f"=== {name} ==="
        + RESET
    )

    print(
        f"Train: {len(train)} "
        f"samples"
    )

    print(
        f"Test : {len(test)} "
        f"samples"
    )

    single = best_single_rule(
        train
    )

    print()
    print(
        YELLOW_BOLD
        + "BEST SINGLE-FEATURE RULE"
        + RESET
    )

    print(
        single.describe()
    )

    print_evaluation(
        "TRAIN",
        train,
        single.predict,
    )

    print_evaluation(
        "TEST ",
        test,
        single.predict,
    )

    print_errors(
        test,
        single.predict,
    )

    pair = best_pair_rule(
        train
    )

    print()
    print(
        YELLOW_BOLD
        + "BEST TWO-FEATURE RULE"
        + RESET
    )

    print(
        pair.describe()
    )

    print_evaluation(
        "TRAIN",
        train,
        pair.predict,
    )

    print_evaluation(
        "TEST ",
        test,
        pair.predict,
    )

    print_errors(
        test,
        pair.predict,
    )


def evaluate_zero_rule(
    samples: list[Sample],
) -> None:
    def predict(
        sample: Sample,
    ) -> str:
        return (
            "BG"
            if sample.features[
                "entropy_delta"
            ] < 0.0
            else "EN"
        )

    print()
    print(
        CYAN_BOLD
        + "=== BASELINE: CURRENT RULE ==="
        + RESET
    )

    print(
        "BG if entropy_delta < 0; "
        "otherwise EN"
    )

    print_evaluation(
        "ALL",
        samples,
        predict,
    )


def main() -> None:
    samples = load_samples()

    if len(samples) != 40:
        print(
            YELLOW_BOLD
            + f"WARNING: expected 40 "
            + f"samples, found "
            + f"{len(samples)}."
            + RESET
        )

    labels = {
        sample.label
        for sample in samples
    }

    if labels != {
        "BG",
        "EN",
    }:
        raise RuntimeError(
            f"Expected BG and EN labels; "
            f"found {sorted(labels)}"
        )

    first, second = (
        split_by_repetition(
            samples
        )
    )

    print(
        GREEN_BOLD
        + "=== OFFLINE CTC RULE SEARCH ==="
        + RESET
    )

    print(
        f"Source: "
        f"{CSV_PATH.resolve()}"
    )

    print(
        f"Samples: {len(samples)}"
    )

    print(
        f"Repetition A: "
        f"{len(first)}"
    )

    print(
        f"Repetition B: "
        f"{len(second)}"
    )

    print()
    print(
        "No CTC models are loaded."
    )

    print(
        "No production code is changed."
    )

    evaluate_zero_rule(
        samples
    )

    evaluate_fold(
        name=(
            "FOLD 1: "
            "TRAIN REPETITION A / "
            "TEST REPETITION B"
        ),
        train=first,
        test=second,
    )

    evaluate_fold(
        name=(
            "FOLD 2: "
            "TRAIN REPETITION B / "
            "TEST REPETITION A"
        ),
        train=second,
        test=first,
    )

    print()
    print(
        GREEN_BOLD
        + "=== RULE SEARCH COMPLETE ==="
        + RESET
    )

    print()
    print(
        "Interpretation:"
    )

    print(
        "A useful production rule should "
        "generalize in BOTH fold directions."
    )

    print(
        "A rule that is perfect on TRAIN "
        "but weak on TEST is overfitting."
    )

    print(
        "We will not change "
        "LanguageResolver until these "
        "held-out results are inspected."
    )


if __name__ == "__main__":
    main()