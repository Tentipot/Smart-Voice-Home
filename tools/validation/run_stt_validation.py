"""Run production STT over accepted pilot_01 recordings.

This runner reports measurements only.
It does not parse or execute commands.

The STT service and ModelManager are created through the production
composition root so validation exercises the same STT wiring used by
the application.
"""

import argparse
import hashlib
import json
import os
import subprocess
import time
import unicodedata
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import torch

from app.commands.semantic_review import SemanticReviewer
from app.resources.model_types import ModelId
from app.resources.system_monitor import get_gpu_status
from app.speech.stt.composition import create_stt_runtime
from app.speech.stt.language_resolver import LanguageResolver


ROOT = Path(__file__).resolve().parents[2]

DEFAULT_DATA = (
    ROOT
    / "data"
    / "stt_validation"
    / "pilot_01"
)

DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / (
        "STT_VALIDATION_"
        + datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
        + ".jsonl"
    )
)


def word_errors(reference, hypothesis):
    def words(text):
        text = unicodedata.normalize(
            "NFC",
            text,
        ).lower()

        return "".join(
            character
            for character in text
            if not unicodedata.category(
                character
            ).startswith("P")
        ).split()

    reference_words = words(reference)
    hypothesis_words = words(hypothesis)

    if not reference_words:
        raise ValueError("Empty reference")

    row = list(
        range(len(hypothesis_words) + 1)
    )

    for index, reference_word in enumerate(
        reference_words,
        1,
    ):
        new_row = [index]

        for column, hypothesis_word in enumerate(
            hypothesis_words,
            1,
        ):
            new_row.append(
                min(
                    new_row[-1] + 1,
                    row[column] + 1,
                    row[column - 1]
                    + (
                        reference_word
                        != hypothesis_word
                    ),
                )
            )

        row = new_row

    errors = row[-1]

    return {
        "errors": errors,
        "reference_words": len(
            reference_words
        ),
        "wer": (
            errors
            / len(reference_words)
        ),
    }


def accepted_cases(data_root: Path):
    attempts = {}
    captured = {}
    accepted = {}

    for manifest in sorted(
        data_root.rglob("manifest.jsonl")
    ):
        for line in manifest.read_text(
            encoding="utf-8"
        ).splitlines():
            event = json.loads(line)

            attempt_id = event.get(
                "attempt_id"
            )

            if event.get("event") == "attempt":
                attempts[attempt_id] = event

            elif event.get("event") == "captured":
                captured[attempt_id] = (
                    (
                        manifest.parent
                        / event["filename"]
                    ).resolve(),
                    event,
                )

            elif event.get("event") == "review":
                accepted[attempt_id] = event

    cases = []

    for attempt_id, review in accepted.items():
        if review.get("status") != "accepted":
            continue

        if (
            attempt_id not in captured
            or attempt_id not in attempts
        ):
            raise ValueError(
                "Incomplete attempt: "
                f"{attempt_id}"
            )

        audio, capture = captured[
            attempt_id
        ]

        if (
            not audio.is_relative_to(
                data_root.resolve()
            )
            or not audio.is_file()
        ):
            raise FileNotFoundError(
                "accepted attempt has no WAV: "
                f"{attempt_id}"
            )

        digest = hashlib.sha256(
            audio.read_bytes()
        ).hexdigest()

        if digest != capture["sha256"]:
            raise ValueError(
                f"SHA256 mismatch: {audio}"
            )

        attempt = attempts.get(
            attempt_id,
            {},
        )

        if not review.get(
            "reference_text",
            "",
        ).strip():
            raise ValueError(
                "Missing reference: "
                f"{attempt_id}"
            )

        cases.append(
            {
                "attempt_id": attempt_id,
                "audio": audio,
                "sha256": digest,
                **attempt,
                **review,
            }
        )

    ids = [
        case["prompt_id"]
        for case in cases
    ]

    if len(ids) != len(set(ids)):
        raise ValueError(
            "Multiple accepted recordings "
            "for a prompt; select before "
            "evaluation"
        )

    return sorted(
        cases,
        key=lambda item: item["prompt_id"],
    )


def resource_state(manager):
    return {
        model_id.value: {
            "loaded": manager.is_loaded(
                model_id
            ),
            "leases": manager.active_leases(
                model_id
            ),
        }
        for model_id in (
            ModelId.CTC_LANGUAGE,
            ModelId.BUZZ_BG,
            ModelId.WHISPER_LARGE_V3,
        )
    }


def run_case(case, service, manager):
    started = time.perf_counter()

    transcription = (
        service.transcribe_with_evidence(
            case["audio"]
        )
    )

    result = transcription.result

    elapsed = (
        time.perf_counter()
        - started
    )

    return {
        "attempt_id": case["attempt_id"],
        "sha256": case["sha256"],
        "status": "ok",
        "ctc": asdict(
            transcription.evidence
        ),
        "entropy_delta": (
            transcription.evidence.entropy_delta
        ),
        "route": (
            transcription
            .resolution
            .policy
            .mode
            .value
        ),
        "resolution_reason": (
            transcription.resolution.reason
        ),
        "gpu_after": get_gpu_status(),
        "resource_state_after": (
            resource_state(manager)
        ),
        "word_error": word_errors(
            case["reference_text"],
            result.text,
        ),
        "semantic_review": asdict(
            SemanticReviewer().review(
                result.text
            )
        ),
        "reference_semantic_review": (
            "pending_manual_review"
        ),
        "prompt_id": case["prompt_id"],
        "speech_label": (
            case["speech_label"]
        ),
        "reference_text": (
            case["reference_text"]
        ),
        "audio": str(
            case["audio"].relative_to(
                ROOT
            )
        ),
        "engine": result.engine,
        "model": result.model,
        "language": result.language,
        "language_confidence": (
            result.language_confidence
        ),
        "text": result.text,
        "metadata": result.metadata,
        "elapsed_seconds": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run production STT validation "
            "over accepted pilot_01 WAV files."
        )
    )

    parser.add_argument(
        "--data-root",
        type=Path,
        default=DEFAULT_DATA,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help=(
            "Optional limit for a smoke run; "
            "0 means all accepted cases."
        ),
    )

    args = parser.parse_args()

    if args.limit < 0:
        parser.error(
            "--limit must be nonnegative"
        )

    cases = accepted_cases(
        args.data_root
    )

    if args.limit:
        cases = cases[:args.limit]

    if not cases:
        raise RuntimeError(
            "No accepted validation cases found."
        )

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable; "
            "pilot configuration requires "
            "GPU STT."
        )

    # Fail locally rather than contacting a hub
    # if any required model is missing.
    for env, folder in (
        (
            "BUZZASR",
            "buzzasr-bulgarian",
        ),
        (
            "CTC_BG",
            "wav2vec2-bg",
        ),
        (
            "CTC_EN",
            "wav2vec2-en",
        ),
        (
            "WHISPER",
            "faster-whisper-large-v3",
        ),
    ):
        path = Path(
            os.getenv(
                f"SMART_VOICE_{env}_MODEL",
                str(
                    ROOT
                    / "models"
                    / folder
                ),
            )
        ).resolve()

        if not path.is_dir():
            raise FileNotFoundError(
                f"Local model required: {path}"
            )

        os.environ[
            f"SMART_VOICE_{env}_MODEL"
        ] = str(path)

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ[
        "TRANSFORMERS_OFFLINE"
    ] = "1"

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Exclusive creation happens before
    # production runtime/model loading.
    with args.output.open(
        "x",
        encoding="utf-8",
        newline="\n",
    ) as stream:
        runtime = None
        service = None
        manager = None

        completed = 0
        failed = 0
        cleanup_errors = []

        def emit(record):
            stream.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    default=str,
                )
                + "\n"
            )
            stream.flush()

        emit(
            {
                "event": "start",
                "gpu": get_gpu_status(),
                "head": subprocess.check_output(
                    [
                        "git",
                        "rev-parse",
                        "HEAD",
                    ],
                    cwd=ROOT,
                    text=True,
                ).strip(),
                "planned": len(cases),
                "thresholds": [
                    LanguageResolver
                    .CTC_BG_BOUNDARY,
                    LanguageResolver
                    .CTC_EN_BOUNDARY,
                ],
            }
        )

        try:
            runtime = create_stt_runtime()
            service = runtime.service
            manager = (
                runtime.model_manager
            )

            emit(
                {
                    "event": (
                        "runtime_created"
                    ),
                    "resources": (
                        resource_state(
                            manager
                        )
                    ),
                }
            )

            for index, case in enumerate(
                cases,
                1,
            ):
                print(
                    (
                        f"[{index}/"
                        f"{len(cases)}] "
                        f"{case['prompt_id']}: "
                        f"{case['audio'].name}"
                    ),
                    flush=True,
                )

                try:
                    record = run_case(
                        case,
                        service,
                        manager,
                    )

                    completed += 1

                except Exception as exc:
                    failed += 1

                    record = {
                        "prompt_id": (
                            case["prompt_id"]
                        ),
                        "status": "error",
                        "error": repr(exc),
                        "sha256": (
                            case["sha256"]
                        ),
                    }

                    if manager is not None:
                        record[
                            "resource_state_after_error"
                        ] = resource_state(
                            manager
                        )

                emit(
                    {
                        "event": "case",
                        "first_inference": (
                            index == 1
                        ),
                        **record,
                    }
                )

        finally:
            service = None
            runtime = None

            if manager is not None:
                for model_id in (
                    ModelId.CTC_LANGUAGE,
                    ModelId.BUZZ_BG,
                    ModelId.WHISPER_LARGE_V3,
                ):
                    try:
                        if manager.is_loaded(
                            model_id
                        ):
                            manager.unload(
                                model_id
                            )

                    except Exception as exc:
                        cleanup_errors.append(
                            (
                                f"{model_id.value}: "
                                f"{exc!r}"
                            )
                        )

            emit(
                {
                    "event": "end",
                    "completed": completed,
                    "failed": failed,
                    "planned": len(cases),
                    "gpu": get_gpu_status(),
                    "cleanup_errors": (
                        cleanup_errors
                    ),
                }
            )

            print(
                (
                    f"Completed {completed}; "
                    f"failed {failed}; "
                    f"planned {len(cases)}"
                ),
                flush=True,
            )

    if failed or cleanup_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()