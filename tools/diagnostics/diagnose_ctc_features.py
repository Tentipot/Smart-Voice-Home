from __future__ import annotations

import argparse
from pathlib import Path

import torch

from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)
from app.speech.stt.language_resolver import LanguageResolver


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "directory",
        nargs="?",
        type=Path,
        default=Path(
            "data/command_capture/wakeword_gpu"
        ),
    )

    args = parser.parse_args()

    directory = args.directory.resolve()

    if not directory.is_dir():
        raise NotADirectoryError(directory)

    files = sorted(
        directory.glob("command_full_*.wav")
    )

    if not files:
        raise RuntimeError(
            f"No command_full_*.wav files in {directory}"
        )

    print(
        f"Found {len(files)} captured phrase(s)."
    )
    print("Loading paired BG/EN CTC models...")

    provider = CtcLanguageEvidenceProvider(
        device="cuda",
        dtype=torch.float16,
    )

    resolver = LanguageResolver()

    print()
    print(
        "FILE | "
        "DELTA | "
        "BG_ENT | EN_ENT | "
        "BG_CONF | EN_CONF | "
        "BG_MIN | EN_MIN | "
        "BG_UNCERT | EN_UNCERT | "
        "BG_RATE | EN_RATE | "
        "CURRENT"
    )

    print("-" * 180)

    for index, path in enumerate(files, start=1):
        evidence = provider.analyze_file(path)

        bg = evidence.bulgarian
        en = evidence.english

        resolution = resolver.resolve_evidence(
            evidence
        )

        print(
            f"{index:02d} {path.name} | "
            f"{evidence.entropy_delta:+.6f} | "
            f"{bg.non_blank_entropy:.6f} | "
            f"{en.non_blank_entropy:.6f} | "
            f"{bg.mean_non_blank_confidence:.6f} | "
            f"{en.mean_non_blank_confidence:.6f} | "
            f"{bg.min_non_blank_confidence:.6f} | "
            f"{en.min_non_blank_confidence:.6f} | "
            f"{bg.uncertain_non_blank_ratio:.6f} | "
            f"{en.uncertain_non_blank_ratio:.6f} | "
            f"{bg.non_blank_token_rate:.6f} | "
            f"{en.non_blank_token_rate:.6f} | "
            f"{resolution.policy.mode.value}"
        )

    print()
    print("Done.")
    print(
        "Do not change LanguageResolver from these "
        "results yet; first label the recordings BG/EN."
    )


if __name__ == "__main__":
    main()