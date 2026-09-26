from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


CSV_PATH = Path(
    "data/language_dataset/ctc_analysis.csv"
)


@dataclass(frozen=True)
class Sample:
    sample: int
    filename: str
    label: str
    prompt: str
    delta: float


@dataclass(frozen=True)
class MixedRule:
    bg_boundary: float
    en_boundary: float

    def predict(
        self,
        sample: Sample,
    ) -> str:
        if sample.delta <= self.bg_boundary:
            return "BG"

        if sample.delta >= self.en_boundary:
            return "EN"

        return "MIXED"

    def describe(self) -> str:
        return (
            f"BG    : delta <= {self.bg_boundary:+.6f}\n"
            f"MIXED : {self.bg_boundary:+.6f} < delta "
            f"< {self.en_boundary:+.6f}\n"
            f"EN    : delta >= {self.en_boundary:+.6f}"
        )


def load_samples() -> list[Sample]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Missing CSV: {CSV_PATH}"
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

    samples: list[Sample] = []

    for row in rows:
        samples.append(
            Sample(
                sample=int(row["sample"]),
                filename=row["filename"],
                label=(
                    row["ground_truth"]
                    .strip()
                    .upper()
                ),
                prompt=(
                    row["prompted_text"]
                    .strip()
                ),
                delta=float(
                    row["entropy_delta"]
                ),
            )
        )

    return samples


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
            counters.get(key, 0)
            + 1
        )

        counters[key] = occurrence

        if occurrence == 1:
            first.append(sample)

        elif occurrence == 2:
            second.append(sample)

        else:
            raise RuntimeError(
                "Expected exactly two repetitions "
                f"for {key!r}; got "
                f"occurrence {occurrence}."
            )

    incomplete = [
        key
        for key, count
        in counters.items()
        if count != 2
    ]

    if incomplete:
        raise RuntimeError(
            "Incomplete repetition pairs: "
            + repr(incomplete)
        )

    return first, second


def midpoint_candidates(
    values: list[float],
) -> list[float]:
    unique = sorted(set(values))

    if len(unique) < 2:
        return unique

    result: list[float] = []

    gap_first = (
        unique[1]
        - unique[0]
    )

    result.append(
        unique[0]
        - gap_first / 2.0
    )

    for left, right in zip(
        unique,
        unique[1:],
    ):
        result.append(
            (left + right) / 2.0
        )

    gap_last = (
        unique[-1]
        - unique[-2]
    )

    result.append(
        unique[-1]
        + gap_last / 2.0
    )

    return result


def evaluate(
    samples: list[Sample],
    rule: MixedRule,
) -> dict[str, float | int]:
    direct_total = 0
    direct_correct = 0
    direct_wrong = 0
    mixed = 0

    bg_direct = 0
    bg_correct = 0
    bg_wrong = 0
    bg_mixed = 0

    en_direct = 0
    en_correct = 0
    en_wrong = 0
    en_mixed = 0

    for sample in samples:
        prediction = rule.predict(
            sample
        )

        if prediction == "MIXED":
            mixed += 1

            if sample.label == "BG":
                bg_mixed += 1
            else:
                en_mixed += 1

            continue

        direct_total += 1

        correct = (
            prediction
            == sample.label
        )

        if correct:
            direct_correct += 1
        else:
            direct_wrong += 1

        if sample.label == "BG":
            bg_direct += 1

            if correct:
                bg_correct += 1
            else:
                bg_wrong += 1

        elif sample.label == "EN":
            en_direct += 1

            if correct:
                en_correct += 1
            else:
                en_wrong += 1

    total = len(samples)

    coverage = (
        direct_total / total
        if total
        else 0.0
    )

    direct_accuracy = (
        direct_correct / direct_total
        if direct_total
        else 0.0
    )

    bg_direct_accuracy = (
        bg_correct / bg_direct
        if bg_direct
        else 1.0
    )

    en_direct_accuracy = (
        en_correct / en_direct
        if en_direct
        else 1.0
    )

    return {
        "total": total,
        "direct_total": direct_total,
        "direct_correct": direct_correct,
        "direct_wrong": direct_wrong,
        "mixed": mixed,
        "coverage": coverage,
        "direct_accuracy": direct_accuracy,

        "bg_direct": bg_direct,
        "bg_correct": bg_correct,
        "bg_wrong": bg_wrong,
        "bg_mixed": bg_mixed,
        "bg_direct_accuracy": (
            bg_direct_accuracy
        ),

        "en_direct": en_direct,
        "en_correct": en_correct,
        "en_wrong": en_wrong,
        "en_mixed": en_mixed,
        "en_direct_accuracy": (
            en_direct_accuracy
        ),
    }


def rule_score(
    samples: list[Sample],
    rule: MixedRule,
) -> tuple[
    int,
    float,
    float,
    float,
]:
    result = evaluate(
        samples,
        rule,
    )

    wrong = int(
        result["direct_wrong"]
    )

    coverage = float(
        result["coverage"]
    )

    bg_accuracy = float(
        result["bg_direct_accuracy"]
    )

    en_accuracy = float(
        result["en_direct_accuracy"]
    )

    worst_accuracy = min(
        bg_accuracy,
        en_accuracy,
    )

    direct_accuracy = float(
        result["direct_accuracy"]
    )

    # Priority:
    #
    # 1. Avoid confident wrong routing.
    # 2. Maximize worst-language reliability.
    # 3. Maximize overall direct accuracy.
    # 4. Among equally safe rules, maximize coverage.
    #
    # Negative wrong count means fewer errors
    # sorts higher.

    return (
        -wrong,
        worst_accuracy,
        direct_accuracy,
        coverage,
    )


def find_best_rule(
    train: list[Sample],
) -> MixedRule:
    values = [
        sample.delta
        for sample in train
    ]

    candidates = midpoint_candidates(
        values
    )

    if not candidates:
        raise RuntimeError(
            "No boundary candidates."
        )

    best_rule: MixedRule | None = None
    best_score: (
        tuple[
            int,
            float,
            float,
            float,
        ]
        | None
    ) = None

    for bg_boundary in candidates:
        for en_boundary in candidates:
            if (
                bg_boundary
                >= en_boundary
            ):
                continue

            rule = MixedRule(
                bg_boundary=bg_boundary,
                en_boundary=en_boundary,
            )

            score = rule_score(
                train,
                rule,
            )

            if (
                best_score is None
                or score > best_score
            ):
                best_score = score
                best_rule = rule

    if best_rule is None:
        raise RuntimeError(
            "Could not find MIXED-zone rule."
        )

    return best_rule


def print_result(
    title: str,
    samples: list[Sample],
    rule: MixedRule,
) -> None:
    result = evaluate(
        samples,
        rule,
    )

    print(title)

    print(
        f"  Direct decisions : "
        f"{result['direct_total']}/"
        f"{result['total']} "
        f"({100.0 * float(result['coverage']):.1f}% coverage)"
    )

    print(
        f"  MIXED            : "
        f"{result['mixed']}"
    )

    print(
        f"  Direct correct   : "
        f"{result['direct_correct']}"
    )

    print(
        f"  Direct WRONG     : "
        f"{result['direct_wrong']}"
    )

    if int(
        result["direct_total"]
    ):
        print(
            f"  Direct accuracy  : "
            f"{100.0 * float(result['direct_accuracy']):.1f}%"
        )

    print(
        f"  BG: direct="
        f"{result['bg_direct']} "
        f"correct={result['bg_correct']} "
        f"wrong={result['bg_wrong']} "
        f"mixed={result['bg_mixed']}"
    )

    print(
        f"  EN: direct="
        f"{result['en_direct']} "
        f"correct={result['en_correct']} "
        f"wrong={result['en_wrong']} "
        f"mixed={result['en_mixed']}"
    )


def print_wrong_direct(
    samples: list[Sample],
    rule: MixedRule,
) -> None:
    wrong = []

    for sample in samples:
        prediction = rule.predict(
            sample
        )

        if (
            prediction != "MIXED"
            and prediction
            != sample.label
        ):
            wrong.append(
                (
                    sample,
                    prediction,
                )
            )

    if not wrong:
        print(
            "  No confidently misrouted "
            "test samples."
        )
        return

    print(
        "  Confidently misrouted:"
    )

    for sample, prediction in wrong:
        print(
            f"    {sample.filename}"
        )

        print(
            f"      truth={sample.label} "
            f"pred={prediction} "
            f"delta={sample.delta:+.6f}"
        )

        print(
            f"      {sample.prompt}"
        )


def print_mixed(
    samples: list[Sample],
    rule: MixedRule,
) -> None:
    mixed = [
        sample
        for sample in samples
        if rule.predict(sample)
        == "MIXED"
    ]

    if not mixed:
        print(
            "  No MIXED samples."
        )
        return

    print(
        "  MIXED samples:"
    )

    for sample in mixed:
        print(
            f"    {sample.label} "
            f"{sample.delta:+.6f} "
            f"{sample.filename}"
        )


def evaluate_fold(
    name: str,
    train: list[Sample],
    test: list[Sample],
) -> MixedRule:
    print()
    print(
        "=" * 72
    )

    print(name)

    print(
        "=" * 72
    )

    rule = find_best_rule(
        train
    )

    print()
    print(
        "SELECTED FROM TRAIN:"
    )

    print(
        rule.describe()
    )

    print()

    print_result(
        "TRAIN:",
        train,
        rule,
    )

    print()

    print_result(
        "HELD-OUT TEST:",
        test,
        rule,
    )

    print()

    print_wrong_direct(
        test,
        rule,
    )

    print()

    print_mixed(
        test,
        rule,
    )

    return rule


def print_fixed_rule_crosscheck(
    samples: list[Sample],
    first_rule: MixedRule,
    second_rule: MixedRule,
) -> None:
    conservative_bg = min(
        first_rule.bg_boundary,
        second_rule.bg_boundary,
    )

    conservative_en = max(
        first_rule.en_boundary,
        second_rule.en_boundary,
    )

    rule = MixedRule(
        bg_boundary=conservative_bg,
        en_boundary=conservative_en,
    )

    print()
    print(
        "=" * 72
    )

    print(
        "CONSERVATIVE INTERSECTION OF BOTH FOLDS"
    )

    print(
        "=" * 72
    )

    print()

    print(
        rule.describe()
    )

    print()

    print_result(
        "ALL 40:",
        samples,
        rule,
    )

    print()

    print_wrong_direct(
        samples,
        rule,
    )

    print()

    print_mixed(
        samples,
        rule,
    )

    print()
    print(
        "NOTE: This is still diagnostic."
    )

    print(
        "No LanguageResolver code has "
        "been modified."
    )


def main() -> None:
    samples = load_samples()

    if len(samples) != 40:
        raise RuntimeError(
            f"Expected 40 samples; "
            f"found {len(samples)}."
        )

    bg_count = sum(
        1
        for sample in samples
        if sample.label == "BG"
    )

    en_count = sum(
        1
        for sample in samples
        if sample.label == "EN"
    )

    if (
        bg_count != 20
        or en_count != 20
    ):
        raise RuntimeError(
            f"Expected 20 BG + 20 EN; "
            f"found {bg_count} BG + "
            f"{en_count} EN."
        )

    first, second = (
        split_by_repetition(
            samples
        )
    )

    print(
        "=== CTC BG / MIXED / EN ANALYSIS ==="
    )

    print(
        f"Source: {CSV_PATH.resolve()}"
    )

    print(
        f"Dataset: "
        f"{bg_count} BG + "
        f"{en_count} EN"
    )

    print(
        "Goal: reliable direct routing; "
        "uncertain cases become MIXED."
    )

    print(
        "No models are loaded."
    )

    print(
        "No production code is changed."
    )

    rule_a = evaluate_fold(
        (
            "FOLD 1 - TRAIN REPETITION A / "
            "TEST REPETITION B"
        ),
        first,
        second,
    )

    rule_b = evaluate_fold(
        (
            "FOLD 2 - TRAIN REPETITION B / "
            "TEST REPETITION A"
        ),
        second,
        first,
    )

    print_fixed_rule_crosscheck(
        samples,
        rule_a,
        rule_b,
    )

    print()
    print(
        "=== ANALYSIS COMPLETE ==="
    )


if __name__ == "__main__":
    main()