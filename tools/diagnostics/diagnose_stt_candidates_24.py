"""Compare STT candidates over the accepted pilot_01 corpus.

Diagnostic only.

This script:
- never executes assistant commands;
- does not change production routing or thresholds;
- uses the accepted pilot_01 recordings;
- validates them through run_stt_validation.accepted_cases();
- keeps Buzz and Whisper resident simultaneously once loaded;
- compares:
    * existing production result;
    * Buzz forced Bulgarian;
    * Whisper AUTO;
    * Whisper forced Bulgarian;
    * Whisper forced English;
- records WER, timings, GPU state, and ModelManager state;
- explicitly unloads models only during final cleanup.

The existing production validation JSONL is treated as the baseline.
"""

import argparse
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import torch

from app.resources.ctranslate2_model_lifecycle import (
    CTranslate2ModelLifecycle,
)
from app.resources.model_manager import ModelManager
from app.resources.model_types import (
    ModelBackend,
    ModelDescriptor,
    ModelId,
)
from app.resources.pytorch_model_lifecycle import (
    PyTorchModelLifecycle,
)
from app.resources.system_monitor import get_gpu_status
from app.speech.stt.buzzasr_engine import BuzzAsrSttEngine
from app.speech.stt.whisper_engine import WhisperSttEngine
from tools.validation.run_stt_validation import (
    DEFAULT_DATA,
    ROOT,
    accepted_cases,
    word_errors,
)


DEFAULT_BASELINE = (
    ROOT
    / "docs"
    / "STT_VALIDATION_PRODUCTION_24.jsonl"
)

DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "STT_CANDIDATES_24.jsonl"
)


def emit(out, record: dict) -> None:
    out.write(
        json.dumps(
            record,
            ensure_ascii=False,
            default=str,
        )
        + "\n"
    )
    out.flush()


def load_baseline(path: Path) -> dict[str, dict]:
    if not path.is_file():
        raise FileNotFoundError(path)

    cases: dict[str, dict] = {}

    for line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        if not line.strip():
            continue

        row = json.loads(line)

        if row.get("event") != "case":
            continue

        if row.get("status") != "ok":
            raise ValueError(
                "Baseline contains failed case: "
                f"{row.get('prompt_id')}"
            )

        prompt_id = row["prompt_id"]

        if prompt_id in cases:
            raise ValueError(
                f"Duplicate baseline case: {prompt_id}"
            )

        cases[prompt_id] = row

    if not cases:
        raise ValueError(
            f"No successful cases in baseline: {path}"
        )

    return cases


def validate_baseline(
    cases: list[dict],
    baseline: dict[str, dict],
) -> None:
    accepted_ids = {
        case["prompt_id"]
        for case in cases
    }

    baseline_ids = set(baseline)

    if accepted_ids != baseline_ids:
        missing = sorted(
            accepted_ids - baseline_ids
        )
        extra = sorted(
            baseline_ids - accepted_ids
        )

        raise ValueError(
            "Baseline/corpus ID mismatch. "
            f"Missing={missing}; extra={extra}"
        )

    for case in cases:
        old = baseline[case["prompt_id"]]

        for field in (
            "sha256",
            "attempt_id",
            "reference_text",
        ):
            if old.get(field) != case.get(field):
                raise ValueError(
                    "Baseline/input mismatch for "
                    f"{case['prompt_id']}: {field}"
                )


def resource_state(
    manager: ModelManager,
) -> dict[str, dict]:
    result: dict[str, dict] = {}

    for model_id in (
        ModelId.BUZZ_BG,
        ModelId.WHISPER_LARGE_V3,
    ):
        result[model_id.value] = {
            "loaded": manager.is_loaded(
                model_id
            ),
            "leases": manager.active_leases(
                model_id
            ),
        }

    return result


def gpu_state() -> dict:
    return get_gpu_status()


def register_models(
    manager: ModelManager,
) -> None:
    buzz_model = os.getenv(
        "SMART_VOICE_BUZZASR_MODEL",
        str(
            ROOT
            / "models"
            / "buzzasr-bulgarian"
        ),
    )

    whisper_model = os.getenv(
        "SMART_VOICE_WHISPER_MODEL",
        str(
            ROOT
            / "models"
            / "faster-whisper-large-v3"
        ),
    )

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.BUZZ_BG,
            backend=ModelBackend.PYTORCH,
            estimated_vram_mb=3323,
        ),
        factory=lambda: BuzzAsrSttEngine(
            model_name=buzz_model,
        ),
        lifecycle=PyTorchModelLifecycle(),
    )

    manager.register(
        descriptor=ModelDescriptor(
            model_id=ModelId.WHISPER_LARGE_V3,
            backend=ModelBackend.CTRANSLATE2,
            estimated_vram_mb=3913,
        ),
        factory=lambda: WhisperSttEngine(
            model_name=whisper_model,
            compute_type="int8_float16",
        ),
        lifecycle=CTranslate2ModelLifecycle(),
    )


def transcribe_candidate(
    manager: ModelManager,
    model_id: ModelId,
    audio_path: Path,
    *,
    language: str | None,
) -> dict:
    gpu_before = gpu_state()

    start = time.perf_counter()

    with manager.acquire(model_id) as engine:
        result = engine.transcribe_file(
            audio_path,
            language=language,
        )

    elapsed = (
        time.perf_counter() - start
    )

    return {
        "text": result.text,
        "language": result.language,
        "language_confidence": (
            result.language_confidence
        ),
        "engine": result.engine,
        "model": result.model,
        "inference_seconds": (
            result.inference_seconds
        ),
        "elapsed_seconds": elapsed,
        "metadata": result.metadata,
        "gpu_before": gpu_before,
        "gpu_after": gpu_state(),
        "resources_after": resource_state(
            manager
        ),
    }


def add_word_error(
    candidate: dict,
    reference_text: str,
) -> dict:
    candidate["word_error"] = word_errors(
        reference_text,
        candidate["text"],
    )

    return candidate


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__
    )

    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA,
    )

    parser.add_argument(
        "--baseline",
        type=Path,
        default=DEFAULT_BASELINE,
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
    )

    args = parser.parse_args()

    cases = accepted_cases(args.data)

    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError(
                "--limit must be greater than zero"
            )

        cases = cases[: args.limit]

    baseline_all = load_baseline(
        args.baseline
    )

    if args.limit is None:
        validate_baseline(
            cases,
            baseline_all,
        )
    else:
        for case in cases:
            old = baseline_all.get(
                case["prompt_id"]
            )

            if old is None:
                raise ValueError(
                    "Missing baseline case: "
                    f"{case['prompt_id']}"
                )

            for field in (
                "sha256",
                "attempt_id",
                "reference_text",
            ):
                if (
                    old.get(field)
                    != case.get(field)
                ):
                    raise ValueError(
                        "Baseline/input mismatch for "
                        f"{case['prompt_id']}: "
                        f"{field}"
                    )

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable."
        )

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    if args.output.exists():
        raise FileExistsError(
            "Output already exists: "
            f"{args.output}"
        )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    manager = ModelManager()
    register_models(manager)

    completed = 0
    failed = 0
    cleanup_errors: list[str] = []

    with args.output.open(
        "x",
        encoding="utf-8",
    ) as out:
        emit(
            out,
            {
                "event": "start",
                "utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "head": subprocess.check_output(
                    [
                        "git",
                        "rev-parse",
                        "HEAD",
                    ],
                    cwd=ROOT,
                    text=True,
                ).strip(),
                "script_sha256": (
                    hashlib.sha256(
                        Path(__file__).read_bytes()
                    ).hexdigest()
                ),
                "baseline": str(
                    args.baseline
                ),
                "baseline_sha256": (
                    hashlib.sha256(
                        args.baseline.read_bytes()
                    ).hexdigest()
                ),
                "planned": len(cases),
                "gpu": gpu_state(),
                "resources": resource_state(
                    manager
                ),
                "diagnostic_only": True,
                "production_routing_changed": (
                    False
                ),
                "residency_policy": (
                    "Buzz and Whisper remain "
                    "resident after first load; "
                    "explicit unload only at "
                    "final cleanup."
                ),
            },
        )

        try:
            for index, case in enumerate(
                cases,
                start=1,
            ):
                prompt_id = case[
                    "prompt_id"
                ]

                baseline = baseline_all[
                    prompt_id
                ]

                print(
                    f"[{index}/{len(cases)}] "
                    f"{prompt_id}: "
                    f"{case['audio'].name}",
                    flush=True,
                )

                row = {
                    "event": "case",
                    "prompt_id": prompt_id,
                    "speech_label": case[
                        "speech_label"
                    ],
                    "attempt_id": case[
                        "attempt_id"
                    ],
                    "sha256": case[
                        "sha256"
                    ],
                    "reference_text": case[
                        "reference_text"
                    ],
                    "audio": str(
                        case["audio"]
                    ),
                    "baseline": {
                        "route": baseline.get(
                            "route"
                        ),
                        "resolution_reason": (
                            baseline.get(
                                "resolution_reason"
                            )
                        ),
                        "text": baseline.get(
                            "text"
                        ),
                        "language": baseline.get(
                            "language"
                        ),
                        "engine": baseline.get(
                            "engine"
                        ),
                        "word_error": baseline.get(
                            "word_error"
                        ),
                    },
                }

                try:
                    buzz = transcribe_candidate(
                        manager,
                        ModelId.BUZZ_BG,
                        case["audio"],
                        language="bg",
                    )

                    row["buzz_bg"] = (
                        add_word_error(
                            buzz,
                            case[
                                "reference_text"
                            ],
                        )
                    )

                    whisper_auto = (
                        transcribe_candidate(
                            manager,
                            ModelId.WHISPER_LARGE_V3,
                            case["audio"],
                            language=None,
                        )
                    )

                    row["whisper_auto"] = (
                        add_word_error(
                            whisper_auto,
                            case[
                                "reference_text"
                            ],
                        )
                    )

                    whisper_bg = (
                        transcribe_candidate(
                            manager,
                            ModelId.WHISPER_LARGE_V3,
                            case["audio"],
                            language="bg",
                        )
                    )

                    row["whisper_bg"] = (
                        add_word_error(
                            whisper_bg,
                            case[
                                "reference_text"
                            ],
                        )
                    )

                    whisper_en = (
                        transcribe_candidate(
                            manager,
                            ModelId.WHISPER_LARGE_V3,
                            case["audio"],
                            language="en",
                        )
                    )

                    row["whisper_en"] = (
                        add_word_error(
                            whisper_en,
                            case[
                                "reference_text"
                            ],
                        )
                    )

                    row["status"] = "ok"
                    row["gpu_after_case"] = (
                        gpu_state()
                    )
                    row[
                        "resources_after_case"
                    ] = resource_state(
                        manager
                    )

                    completed += 1

                except Exception as exc:
                    row["status"] = "error"
                    row["error"] = repr(exc)
                    row["gpu_after_error"] = (
                        gpu_state()
                    )
                    row[
                        "resources_after_error"
                    ] = resource_state(
                        manager
                    )

                    failed += 1

                emit(out, row)

        finally:
            for model_id in (
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
                        f"{model_id.value}: "
                        f"{exc!r}"
                    )

            if torch.cuda.is_available():
                torch.cuda.empty_cache()

            emit(
                out,
                {
                    "event": "end",
                    "completed": completed,
                    "failed": failed,
                    "planned": len(cases),
                    "gpu": gpu_state(),
                    "resources": (
                        resource_state(
                            manager
                        )
                    ),
                    "cleanup_errors": (
                        cleanup_errors
                    ),
                },
            )

    print(
        f"Completed {completed}; "
        f"failed {failed}; "
        f"planned {len(cases)}",
        flush=True,
    )

    if failed or cleanup_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()