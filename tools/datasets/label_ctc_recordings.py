from __future__ import annotations

import csv
import sys
from pathlib import Path

import sounddevice as sd
import soundfile as sf


CAPTURE_DIR = Path(
    "data/command_capture/wakeword_gpu"
)

OUTPUT_CSV = Path(
    "data/command_capture/ctc_language_labels.csv"
)

VALID_LABELS = {
    "b": "BG",
    "e": "EN",
    "n": "NOISE_OTHER",
}


def find_recordings() -> list[Path]:
    return sorted(
        CAPTURE_DIR.glob("command_full_*.wav")
    )


def load_existing_labels() -> dict[str, str]:
    if not OUTPUT_CSV.is_file():
        return {}

    labels: dict[str, str] = {}

    with OUTPUT_CSV.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            filename = (
                row.get("filename", "").strip()
            )

            label = (
                row.get("label", "").strip()
            )

            if filename and label:
                labels[filename] = label

    return labels


def save_labels(
    recordings: list[Path],
    labels: dict[str, str],
) -> None:
    OUTPUT_CSV.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with OUTPUT_CSV.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.writer(file)

        writer.writerow(
            [
                "filename",
                "label",
            ]
        )

        for path in recordings:
            label = labels.get(
                path.name
            )

            if label is None:
                continue

            writer.writerow(
                [
                    path.name,
                    label,
                ]
            )


def play_recording(
    path: Path,
) -> tuple[float, int]:
    audio, sample_rate = sf.read(
        str(path),
        dtype="float32",
        always_2d=False,
    )

    if audio.ndim != 1:
        raise ValueError(
            f"{path.name}: expected mono WAV"
        )

    duration = (
        len(audio) / sample_rate
    )

    print(
        f"\nPlaying {duration:.2f}s..."
    )

    sd.stop()

    sd.play(
        audio,
        samplerate=sample_rate,
        blocking=True,
    )

    return duration, sample_rate


def print_controls() -> None:
    print()
    print("Choose label:")
    print("  B = Bulgarian")
    print("  E = English")
    print("  N = Noise / Other / unusable")
    print("  R = Replay")
    print("  S = Skip for now")
    print("  Q = Save and quit")


def main() -> None:
    recordings = find_recordings()

    if not recordings:
        print(
            f"No command_full_*.wav files found in "
            f"{CAPTURE_DIR.resolve()}"
        )
        sys.exit(1)

    labels = load_existing_labels()

    print("=== CTC LANGUAGE LABELER ===")
    print(
        f"Found {len(recordings)} recording(s)."
    )
    print(
        f"Labels file: {OUTPUT_CSV.resolve()}"
    )

    if labels:
        print(
            f"Existing labels loaded: "
            f"{len(labels)}"
        )

    print()
    print("Labels:")
    print("  B = Bulgarian")
    print("  E = English")
    print(
        "  N = Noise / Other / unusable"
    )
    print()
    print(
        "R replays the current WAV."
    )
    print(
        "S leaves it unlabeled."
    )
    print(
        "Q saves progress and exits."
    )

    for index, path in enumerate(
        recordings,
        start=1,
    ):
        existing = labels.get(
            path.name
        )

        print()
        print("=" * 72)
        print(
            f"[{index:02d}/{len(recordings):02d}] "
            f"{path.name}"
        )

        if existing:
            print(
                f"Existing label: {existing}"
            )

        while True:
            try:
                play_recording(path)

            except Exception as exc:
                print(
                    f"[PLAYBACK ERROR] "
                    f"{type(exc).__name__}: {exc}"
                )

                print(
                    "Label it N if the file itself "
                    "is unusable, or S to skip."
                )

            print_controls()

            choice = input(
                "Label [B/E/N/R/S/Q]: "
            ).strip().lower()

            if choice == "r":
                continue

            if choice == "q":
                save_labels(
                    recordings,
                    labels,
                )

                print(
                    f"\nSaved: "
                    f"{OUTPUT_CSV.resolve()}"
                )

                print(
                    f"Labeled: "
                    f"{len(labels)}/"
                    f"{len(recordings)}"
                )

                return

            if choice == "s":
                print(
                    f"Skipped: {path.name}"
                )
                break

            if choice in VALID_LABELS:
                label = VALID_LABELS[
                    choice
                ]

                labels[path.name] = label

                save_labels(
                    recordings,
                    labels,
                )

                print(
                    f"Saved label: "
                    f"{label}"
                )

                break

            print(
                "Invalid key. "
                "Use B, E, N, R, S, or Q."
            )

    save_labels(
        recordings,
        labels,
    )

    print()
    print("=" * 72)
    print("LABELING COMPLETE")
    print(
        f"Saved: {OUTPUT_CSV.resolve()}"
    )

    bg_count = sum(
        label == "BG"
        for label in labels.values()
    )

    en_count = sum(
        label == "EN"
        for label in labels.values()
    )

    noise_count = sum(
        label == "NOISE_OTHER"
        for label in labels.values()
    )

    print(
        f"BG:          {bg_count}"
    )
    print(
        f"EN:          {en_count}"
    )
    print(
        f"NOISE/OTHER: {noise_count}"
    )
    print(
        f"TOTAL:       {len(labels)}"
    )

    print()
    print("=== LABEL TABLE ===")

    for index, path in enumerate(
        recordings,
        start=1,
    ):
        label = labels.get(
            path.name,
            "UNLABELED",
        )

        print(
            f"{index:02d} "
            f"{label:12s} "
            f"{path.name}"
        )


if __name__ == "__main__":
    main()