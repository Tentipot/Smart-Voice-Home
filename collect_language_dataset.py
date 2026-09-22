from __future__ import annotations

import argparse
import csv
import queue
import threading
from datetime import datetime
from pathlib import Path

import sounddevice as sd
import soundfile as sf

from app.speech.capture.aurora_capture import (
    CapturedPhrase,
    AuroraCapture,
    SAMPLE_RATE,
    pcm_to_float,
)


DATASET_DIR = Path("data/language_dataset")
MANIFEST_PATH = DATASET_DIR / "manifest.csv"

MIN_ACCEPT_SECONDS = 1.5
MAX_ACCEPT_SECONDS = 8.0
MIN_ACCEPT_RMS = 0.008

# ANSI console formatting.
GREEN_BOLD = "\033[1;92m"
RESET = "\033[0m"


BG_PHRASES = (
    "Аурора, намали звука",
    "Аурора, увеличи звука",
    "Аурора, колко е часът",
    "Аурора, отвори браузъра",
    "Аурора, пусни музика",
    "Аурора, спри музиката",
    "Аурора, затвори браузъра",
    "Аурора, какво е времето",
    "Аурора, пусни следващата песен",
    "Аурора, върни предишната песен",
)

EN_PHRASES = (
    "Aurora, turn down the volume",
    "Aurora, turn up the volume",
    "Aurora, what time is it",
    "Aurora, open the browser",
    "Aurora, play some music",
    "Aurora, stop the music",
    "Aurora, close the browser",
    "Aurora, what is the weather",
    "Aurora, play the next song",
    "Aurora, play the previous song",
)


def phrase_to_audio(
    phrase: CapturedPhrase,
):
    return pcm_to_float(
        b"".join(phrase.blocks)
    )


def play_phrase(
    phrase: CapturedPhrase,
) -> None:
    audio = phrase_to_audio(phrase)

    sd.stop()

    print(
        "[PLAYBACK] Playing captured WAV...",
        flush=True,
    )

    sd.play(
        audio,
        samplerate=SAMPLE_RATE,
        blocking=True,
    )

    print(
        "[PLAYBACK] Finished.",
        flush=True,
    )


def save_phrase(
    path: Path,
    phrase: CapturedPhrase,
) -> None:
    audio = phrase_to_audio(phrase)

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    sf.write(
        str(path),
        audio,
        SAMPLE_RATE,
        subtype="PCM_16",
    )


def append_manifest(
    *,
    filename: str,
    label: str,
    prompted_text: str,
    duration: float,
    rms: float,
    wake_text: str,
) -> None:
    DATASET_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    new_file = not MANIFEST_PATH.exists()

    with MANIFEST_PATH.open(
        "a",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.writer(file)

        if new_file:
            writer.writerow(
                [
                    "filename",
                    "label",
                    "prompted_text",
                    "duration_seconds",
                    "rms",
                    "wake_text",
                ]
            )

        writer.writerow(
            [
                filename,
                label,
                prompted_text,
                f"{duration:.3f}",
                f"{rms:.6f}",
                wake_text,
            ]
        )


def build_plan(
    per_language: int,
) -> list[tuple[str, str]]:
    plan: list[tuple[str, str]] = []

    for index in range(per_language):
        plan.append(
            (
                "BG",
                BG_PHRASES[
                    index % len(BG_PHRASES)
                ],
            )
        )

    for index in range(per_language):
        plan.append(
            (
                "EN",
                EN_PHRASES[
                    index % len(EN_PHRASES)
                ],
            )
        )

    return plan


def clear_phrase_queue(
    phrase_queue: queue.Queue[
        CapturedPhrase
    ],
) -> None:
    while True:
        try:
            phrase_queue.get_nowait()

        except queue.Empty:
            return

        else:
            phrase_queue.task_done()


def print_prompt_phrase(
    label: str,
    prompted_text: str,
) -> None:
    print()
    print(
        GREEN_BOLD
        + ">>> ГОВОРИ СЕГА <<<"
        + RESET,
        flush=True,
    )

    print(
        GREEN_BOLD
        + f"[{label}]  {prompted_text}"
        + RESET,
        flush=True,
    )

    print(
        GREEN_BOLD
        + "=============================="
        + RESET,
        flush=True,
    )
    print()


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--device",
        type=int,
        default=1,
    )

    parser.add_argument(
        "--per-language",
        type=int,
        default=20,
    )

    args = parser.parse_args()

    if args.per_language < 1:
        raise ValueError(
            "--per-language must be >= 1"
        )

    DATASET_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    phrase_queue: queue.Queue[
        CapturedPhrase
    ] = queue.Queue(
        maxsize=1
    )

    def on_phrase(
        phrase: CapturedPhrase,
    ) -> None:
        try:
            phrase_queue.put_nowait(
                phrase
            )

        except queue.Full:
            print(
                "[COLLECTOR] Unexpected extra "
                "phrase discarded.",
                flush=True,
            )

    capture = AuroraCapture(
        device=args.device,
        on_phrase=on_phrase,
        verbose=True,
    )

    capture_thread = threading.Thread(
        target=capture.run,
        name="language-dataset-capture",
        daemon=True,
    )

    plan = build_plan(
        args.per_language
    )

    print(
        "=== CLEAN LANGUAGE DATASET "
        "COLLECTOR ==="
    )

    print(
        f"Target: {args.per_language} BG + "
        f"{args.per_language} EN"
    )

    print()

    print(
        "Workflow:"
    )
    print(
        "  1. Say the GREEN prompted phrase."
    )
    print(
        "  2. Aurora capture finishes."
    )
    print(
        "  3. Microphone capture pauses."
    )
    print(
        "  4. The captured audio is played."
    )
    print(
        "  5. A/R/X/Q review."
    )
    print(
        "  6. Capture resumes only after "
        "your decision."
    )

    print()

    capture_thread.start()

    try:
        sample_index = 0

        while sample_index < len(plan):
            label, prompted_text = (
                plan[sample_index]
            )

            clear_phrase_queue(
                phrase_queue
            )

            capture.resume()

            print()
            print("=" * 72)

            print(
                f"SAMPLE "
                f"{sample_index + 1:02d}/"
                f"{len(plan):02d}"
            )

            print(
                f"GROUND TRUTH: {label}"
            )

            # Deliberately isolated and highlighted.
            print_prompt_phrase(
                label,
                prompted_text,
            )

            print(
                "Waiting for Aurora-confirmed "
                "capture..."
            )

            phrase = phrase_queue.get()

            print()
            print(
                "--- CAPTURE RECEIVED ---"
            )

            print(
                f"Duration: "
                f"{phrase.duration_seconds:.2f}s"
            )

            print(
                f"RMS: {phrase.rms:.4f}"
            )

            print(
                f"Wake ASR: "
                f"{phrase.wake_text!r}"
            )

            quality_ok = True

            if (
                phrase.duration_seconds
                < MIN_ACCEPT_SECONDS
            ):
                quality_ok = False
                print(
                    "[QUALITY] Too short."
                )

            if (
                phrase.duration_seconds
                > MAX_ACCEPT_SECONDS
            ):
                quality_ok = False
                print(
                    "[QUALITY] Too long."
                )

            if (
                phrase.rms
                < MIN_ACCEPT_RMS
            ):
                quality_ok = False
                print(
                    "[QUALITY] Too quiet."
                )

            if quality_ok:
                print(
                    "[QUALITY] Automatic "
                    "checks passed."
                )
            else:
                print(
                    "[QUALITY] Automatic "
                    "checks FAILED."
                )

            print(
                "[CAPTURE] Microphone is paused."
            )

            print()

            play_phrase(phrase)

            while True:
                choice = input(
                    "\n[A]ccept / "
                    "[R]eplay / "
                    "re[X]ject / "
                    "[Q]uit: "
                ).strip().lower()

                if choice == "r":
                    play_phrase(phrase)
                    continue

                if choice == "q":
                    phrase_queue.task_done()

                    print(
                        "\nStopping. Already "
                        "accepted samples remain "
                        "saved."
                    )

                    capture.stop()
                    return

                if choice == "x":
                    phrase_queue.task_done()

                    print(
                        "Rejected. The SAME sample "
                        "will be requested again."
                    )

                    break

                if choice == "a":
                    if not quality_ok:
                        confirm = input(
                            "Automatic quality "
                            "checks failed. "
                            "Accept anyway? [y/N]: "
                        ).strip().lower()

                        if confirm != "y":
                            phrase_queue.task_done()

                            print(
                                "Rejected. The SAME "
                                "sample will be "
                                "requested again."
                            )

                            break

                    timestamp = (
                        datetime.now().strftime(
                            "%Y%m%d_%H%M%S_%f"
                        )
                    )

                    filename = (
                        f"{label.lower()}_"
                        f"{sample_index + 1:03d}_"
                        f"{timestamp}.wav"
                    )

                    path = (
                        DATASET_DIR
                        / filename
                    )

                    save_phrase(
                        path,
                        phrase,
                    )

                    append_manifest(
                        filename=filename,
                        label=label,
                        prompted_text=prompted_text,
                        duration=(
                            phrase.duration_seconds
                        ),
                        rms=phrase.rms,
                        wake_text=(
                            phrase.wake_text
                        ),
                    )

                    phrase_queue.task_done()

                    print(
                        f"[SAVED] {path}"
                    )

                    sample_index += 1
                    break

                print(
                    "Use A, R, X, or Q."
                )

        print()
        print("=" * 72)
        print(
            "DATASET COMPLETE"
        )
        print(
            f"{args.per_language} BG + "
            f"{args.per_language} EN"
        )
        print(
            f"Manifest: "
            f"{MANIFEST_PATH.resolve()}"
        )

    except KeyboardInterrupt:
        print(
            "\nStopping..."
        )

    finally:
        capture.stop()


if __name__ == "__main__":
    main()