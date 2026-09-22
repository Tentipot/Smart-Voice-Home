from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path

import torch

from app.speech.stt.buzzasr_engine import BuzzAsrSttEngine
from app.speech.stt.ctc_evidence_provider import CtcLanguageEvidenceProvider
from app.speech.stt.language_resolver import LanguageResolver


DEFAULT_AUDIO = Path(
    r"data\command_capture\wakeword_gpu"
    r"\command_full_20260922_124403_026821.wav"
)


def print_metric(name: str, metrics) -> None:
    print(f"\n[{name}]")
    print(
        "  mean_non_blank_confidence = "
        f"{metrics.mean_non_blank_confidence:.6f}"
    )
    print(
        "  min_non_blank_confidence  = "
        f"{metrics.min_non_blank_confidence:.6f}"
    )
    print(
        "  non_blank_entropy         = "
        f"{metrics.non_blank_entropy:.6f}"
    )
    print(
        "  uncertain_non_blank_ratio = "
        f"{metrics.uncertain_non_blank_ratio:.6f}"
    )
    print(
        "  blank_prediction_ratio    = "
        f"{metrics.blank_prediction_ratio:.6f}"
    )
    print(
        "  mean_blank_probability    = "
        f"{metrics.mean_blank_probability:.6f}"
    )
    print(
        "  non_blank_token_rate      = "
        f"{metrics.non_blank_token_rate:.6f}"
    )


def print_vram(label: str) -> None:
    free_bytes, total_bytes = torch.cuda.mem_get_info()

    print(
        f"[CUDA] {label}: "
        f"{free_bytes / 1024**3:.2f} GiB free / "
        f"{total_bytes / 1024**3:.2f} GiB total"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose CTC language routing and independently test "
            "Bulgarian BuzzASR. No assistant actions are executed."
        )
    )
    parser.add_argument(
        "audio",
        nargs="?",
        type=Path,
        default=DEFAULT_AUDIO,
        help="16 kHz mono PCM16 WAV file",
    )
    args = parser.parse_args()

    audio_path = args.audio.resolve()

    print("=== STT PIPELINE DIAGNOSTIC ===")
    print(f"Audio: {audio_path}")
    print("No assistant action will be executed.")

    if not audio_path.is_file():
        print(f"\n[ERROR] Audio file not found: {audio_path}")
        return 2

    if not torch.cuda.is_available():
        print("\n[ERROR] CUDA is not available to PyTorch.")
        return 3

    print(f"\n[CUDA] GPU: {torch.cuda.get_device_name(0)}")
    print_vram("before CTC")

    print("\n[1/3] Loading BG + EN CTC evidence models...")

    evidence_provider = CtcLanguageEvidenceProvider(
        device="cuda",
        dtype=torch.float16,
    )

    print("[2/3] Analyzing language evidence...")

    evidence = evidence_provider.analyze_file(audio_path)

    print_metric("CTC BG", evidence.bulgarian)
    print_metric("CTC EN", evidence.english)

    print("\n[CTC COMPARISON]")
    print(f"  entropy_delta = {evidence.entropy_delta:+.6f}")

    resolver = LanguageResolver()
    resolution = resolver.resolve_evidence(evidence)

    print("\n[CURRENT LANGUAGE RESOLUTION]")
    print(f"  policy.mode         = {resolution.policy.mode.value}")
    print(f"  reason              = {resolution.reason.value}")
    print(
        "  detected_language   = "
        f"{resolution.detected_language!r}"
    )
    print(
        "  detected_confidence = "
        f"{resolution.detected_confidence!r}"
    )

    print(
        "\n[DIAGNOSTIC OVERRIDE]"
        "\nCurrent router decision is shown above."
        "\nFor this diagnostic ONLY, Buzz BG will now transcribe"
        "\nthe same full WAV regardless of the CTC decision."
    )

    # Release both CTC models before loading Buzz.
    del evidence_provider
    gc.collect()
    torch.cuda.empty_cache()

    print_vram("after releasing CTC / before Buzz")

    print("\n[3/3] Loading BuzzASR/bulgarian...")

    buzz = BuzzAsrSttEngine(
        device="cuda",
        dtype=torch.float16,
    )

    print(
        "[BUZZ] Forced BG diagnostic transcription "
        "of the full captured phrase..."
    )

    result = buzz.transcribe_file(
        audio_path,
        language="bg",
    )

    print("\n=== FORCED BUZZ BG RESULT ===")
    print(f"Text: {result.text!r}")
    print(f"Language: {result.language!r}")
    print(f"Engine: {result.engine}")
    print(f"Model: {result.model}")
    print(f"Audio duration: {result.duration_seconds:.2f}s")
    print(f"Inference time: {result.inference_seconds:.2f}s")
    print(f"Metadata: {result.metadata}")

    print("\n=== COMPARISON ===")
    print(
        "CTC router selected: "
        f"{resolution.policy.mode.value!r}"
    )
    print(
        "Buzz was forced to BG only for diagnosis; "
        "the production resolver was NOT changed."
    )
    print("No assistant intent/action was executed.")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        raise SystemExit(130)
    except Exception as exc:
        print(
            f"\n[FATAL] {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        raise