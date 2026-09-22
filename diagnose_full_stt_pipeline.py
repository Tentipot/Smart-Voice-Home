from __future__ import annotations

import argparse
import gc
from pathlib import Path

import torch

from app.speech.stt.buzzasr_engine import BuzzAsrSttEngine
from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)
from app.speech.stt.language_resolver import LanguageResolver
from app.speech.stt.router import SttRouter
from app.speech.stt.service import SttService
from app.speech.stt.whisper_engine import WhisperSttEngine


def cuda_status(label: str) -> None:
    if not torch.cuda.is_available():
        print(f"[CUDA] {label}: unavailable")
        return

    free_bytes, total_bytes = torch.cuda.mem_get_info()

    gib = 1024 ** 3

    print(
        f"[CUDA] {label}: "
        f"{free_bytes / gib:.2f} GiB free / "
        f"{total_bytes / gib:.2f} GiB total"
    )


def print_metrics(name: str, metrics) -> None:
    print(f"\n[{name}]")

    print(
        "mean_non_blank_confidence = "
        f"{metrics.mean_non_blank_confidence:.6f}"
    )
    print(
        "min_non_blank_confidence  = "
        f"{metrics.min_non_blank_confidence:.6f}"
    )
    print(
        "non_blank_entropy         = "
        f"{metrics.non_blank_entropy:.6f}"
    )
    print(
        "uncertain_non_blank_ratio = "
        f"{metrics.uncertain_non_blank_ratio:.6f}"
    )
    print(
        "blank_prediction_ratio    = "
        f"{metrics.blank_prediction_ratio:.6f}"
    )
    print(
        "mean_blank_probability    = "
        f"{metrics.mean_blank_probability:.6f}"
    )
    print(
        "non_blank_token_rate      = "
        f"{metrics.non_blank_token_rate:.6f}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "audio",
        type=Path,
        nargs="?",
        default=Path(
            "data/command_capture/wakeword_gpu/"
            "command_full_20260922_131658_961533.wav"
        ),
    )

    args = parser.parse_args()

    audio_path = args.audio.resolve()

    if not audio_path.is_file():
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    print("=== FULL STT PIPELINE DIAGNOSTIC ===")
    print(f"Audio: {audio_path}")
    print("No assistant action will be executed.")

    cuda_status("before models")

    print("\nLoading paired BG/EN CTC models...")

    evidence_provider = CtcLanguageEvidenceProvider(
        device="cuda",
        dtype=torch.float16,
    )

    resolver = LanguageResolver()

    cuda_status("after CTC load")

    print("\nAnalyzing language evidence...")

    evidence = evidence_provider.analyze_file(
        audio_path
    )

    print_metrics(
        "CTC BG",
        evidence.bulgarian,
    )

    print_metrics(
        "CTC EN",
        evidence.english,
    )

    print(
        "\nentropy_delta = "
        f"{evidence.entropy_delta:+.6f}"
    )

    resolution = resolver.resolve_evidence(
        evidence
    )

    print("\n=== CURRENT RESOLVER ===")
    print(
        f"policy.mode = "
        f"{resolution.policy.mode.value}"
    )
    print(
        f"reason = "
        f"{resolution.reason.value}"
    )
    print(
        f"detected_language = "
        f"{resolution.detected_language!r}"
    )

    # The CTC provider owns two large CUDA models.
    # Release it before loading Buzz + Whisper so this
    # diagnostic remains practical on an 8 GiB GPU.
    del evidence_provider

    gc.collect()

    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    cuda_status(
        "after releasing CTC / before STT engines"
    )

    print("\nLoading Buzz BG...")

    buzz = BuzzAsrSttEngine(
        device="cuda",
        dtype=torch.float16,
    )

    print("Loading Whisper large-v3...")

    whisper = WhisperSttEngine(
        model_name="large-v3",
        device="cuda",
        compute_type="float16",
        beam_size=1,
    )

    router = SttRouter(
        bulgarian_engine=buzz,
        english_engine=whisper,
        mixed_engine=whisper,
    )

    # SttService normally owns the evidence step too.
    # We already performed it above so we can print the
    # exact evidence before releasing the two CTC models.
    #
    # Therefore route the already-resolved policy directly.
    print("\n=== ROUTED STT ===")
    print(
        f"Routing with current policy: "
        f"{resolution.policy.mode.value}"
    )

    result = router.transcribe_file(
        audio_path,
        policy=resolution.policy,
    )

    print(f"Text: {result.text!r}")
    print(f"Language: {result.language!r}")
    print(f"Engine: {result.engine}")
    print(f"Model: {result.model}")
    print(
        f"Audio duration: "
        f"{result.duration_seconds:.2f}s"
    )
    print(
        f"Inference time: "
        f"{result.inference_seconds:.2f}s"
    )

    print("\n=== CONTROL: FORCED BUZZ BG ===")

    bg_result = buzz.transcribe_file(
        audio_path,
        language="bg",
    )

    print(f"Text: {bg_result.text!r}")
    print(f"Language: {bg_result.language!r}")
    print(f"Engine: {bg_result.engine}")
    print(f"Model: {bg_result.model}")
    print(
        f"Inference time: "
        f"{bg_result.inference_seconds:.2f}s"
    )

    print("\n=== COMPARISON ===")

    if resolution.policy.mode.value == "bg":
        print(
            "Current resolver selected BG. "
            "Routed result should therefore use Buzz."
        )
    else:
        print(
            "Current resolver did NOT select BG. "
            "Compare the routed transcript against "
            "the forced Buzz BG transcript."
        )

    print(
        "\nNo intent/action was executed."
    )


if __name__ == "__main__":
    main()