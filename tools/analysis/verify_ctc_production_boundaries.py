from __future__ import annotations

import csv
from pathlib import Path


CSV_PATH = Path(
    "data/language_dataset/ctc_analysis.csv"
)

BG_BOUNDARY = 0.003
EN_BOUNDARY = 0.043


def predict(delta: float) -> str:
    if delta <= BG_BOUNDARY:
        return "BG"

    if delta >= EN_BOUNDARY:
        return "EN"

    return "MIXED"


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Missing CSV: {CSV_PATH}"
        )

    with CSV_PATH.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = list(csv.DictReader(file))

    if len(rows) != 40:
        raise RuntimeError(
            f"Expected 40 samples, found {len(rows)}."
        )

    bg_count = sum(
        1
        for row in rows
        if row["ground_truth"].strip().upper() == "BG"
    )

    en_count = sum(
        1
        for row in rows
        if row["ground_truth"].strip().upper() == "EN"
    )

    if bg_count != 20 or en_count != 20:
        raise RuntimeError(
            f"Expected 20 BG + 20 EN; "
            f"found {bg_count} BG + {en_count} EN."
        )

    direct = 0
    correct = 0
    wrong = 0
    mixed = 0

    stats = {
        "BG": {
            "direct": 0,
            "correct": 0,
            "wrong": 0,
            "mixed": 0,
        },
        "EN": {
            "direct": 0,
            "correct": 0,
            "wrong": 0,
            "mixed": 0,
        },
    }

    wrong_rows = []
    mixed_rows = []

    print(
        "=== VERIFY PRODUCTION CTC BOUNDARIES ==="
    )

    print()
    print(
        f"BG    : delta <= {BG_BOUNDARY:+.6f}"
    )
    print(
        f"MIXED : {BG_BOUNDARY:+.6f} < delta "
        f"< {EN_BOUNDARY:+.6f}"
    )
    print(
        f"EN    : delta >= {EN_BOUNDARY:+.6f}"
    )

    print()
    print(
        "Per-sample verification:"
    )

    for row in rows:
        truth = (
            row["ground_truth"]
            .strip()
            .upper()
        )

        delta = float(
            row["entropy_delta"]
        )

        result = predict(delta)

        filename = row["filename"]
        prompt = row["prompted_text"]

        if result == "MIXED":
            mixed += 1
            stats[truth]["mixed"] += 1

            mixed_rows.append(
                (
                    truth,
                    delta,
                    filename,
                    prompt,
                )
            )

            status = "MIXED"

        else:
            direct += 1
            stats[truth]["direct"] += 1

            if result == truth:
                correct += 1
                stats[truth]["correct"] += 1
                status = "OK"

            else:
                wrong += 1
                stats[truth]["wrong"] += 1
                status = "WRONG"

                wrong_rows.append(
                    (
                        truth,
                        result,
                        delta,
                        filename,
                        prompt,
                    )
                )

        print(
            f"{int(row['sample']):02d} "
            f"truth={truth} "
            f"delta={delta:+.6f} "
            f"route={result:5s} "
            f"{status}"
        )

    print()
    print(
        "=" * 72
    )
    print(
        "SUMMARY"
    )
    print(
        "=" * 72
    )

    coverage = (
        100.0 * direct / len(rows)
    )

    direct_accuracy = (
        100.0 * correct / direct
        if direct
        else 0.0
    )

    print(
        f"Total             : {len(rows)}"
    )
    print(
        f"Direct decisions  : {direct}/"
        f"{len(rows)} ({coverage:.1f}% coverage)"
    )
    print(
        f"MIXED             : {mixed}"
    )
    print(
        f"Direct correct    : {correct}"
    )
    print(
        f"Direct WRONG      : {wrong}"
    )
    print(
        f"Direct accuracy   : {direct_accuracy:.1f}%"
    )

    print()

    for label in ("BG", "EN"):
        item = stats[label]

        print(
            f"{label}: "
            f"direct={item['direct']} "
            f"correct={item['correct']} "
            f"wrong={item['wrong']} "
            f"mixed={item['mixed']}"
        )

    print()
    print(
        "MIXED SAMPLES"
    )
    print(
        "-" * 72
    )

    if not mixed_rows:
        print(
            "None."
        )
    else:
        for (
            truth,
            delta,
            filename,
            prompt,
        ) in mixed_rows:
            print(
                f"{truth} "
                f"{delta:+.6f} "
                f"{filename}"
            )
            print(
                f"    {prompt}"
            )

    print()
    print(
        "CONFIDENTLY MISROUTED SAMPLES"
    )
    print(
        "-" * 72
    )

    if not wrong_rows:
        print(
            "None."
        )
    else:
        for (
            truth,
            result,
            delta,
            filename,
            prompt,
        ) in wrong_rows:
            print(
                f"truth={truth} "
                f"route={result} "
                f"delta={delta:+.6f} "
                f"{filename}"
            )
            print(
                f"    {prompt}"
            )

    print()
    print(
        "=" * 72
    )

    if wrong == 0:
        print(
            "RESULT: PASS"
        )
        print(
            "Rounded boundaries produced "
            "zero confident misroutes."
        )
    else:
        print(
            "RESULT: FAIL"
        )
        print(
            "Do NOT use these boundaries "
            "in LanguageResolver."
        )

    print(
        "=" * 72
    )

    print()
    print(
        "No production code was changed."
    )


if __name__ == "__main__":
    main()