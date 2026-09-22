from __future__ import annotations

import argparse
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import sounddevice as sd
import torch
import webrtcvad

from app.speech.stt.ctc_evidence_provider import (
    CtcLanguageEvidenceProvider,
)
from app.speech.stt.language_resolver import LanguageResolver


SAMPLE_RATE = 16000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000

PREROLL_SECONDS = 0.30
END_SILENCE_SECONDS = 0.90
MAX_RECORD_SECONDS = 12.0

START_WINDOW_FRAMES = 8
START_REQUIRED_VOICED = 4

# A capture below either limit is rejected and the same
# test is repeated. These limits are deliberately conservative.
MIN_VALID_DURATION_SECONDS = 1.20
MIN_VALID_RMS = 0.008

TESTS = [
    ("BG", "Аурора, намали звука"),
    ("BG", "Аурора, увеличи звука"),
    ("BG", "Аурора, колко е часът"),
    ("BG", "Аурора, отвори браузъра"),
    ("BG", "Аурора, пусни музика"),
    ("EN", "Aurora, turn down the volume"),
    ("EN", "Aurora, turn up the volume"),
    ("EN", "Aurora, what time is it"),
    ("EN", "Aurora, open the browser"),
    ("EN", "Aurora, play some music"),
]


@dataclass
class TestResult:
    number: int
    expected: str
    phrase: str
    duration: float
    rms: float
    delta: float
    current: str
    bg_entropy: float
    en_entropy: float
    bg_confidence: float
    en_confidence: float


def pcm_rms(pcm: bytes) -> float:
    if not pcm:
        return 0.0

    samples = np.frombuffer(
        pcm,
        dtype=np.int16,
    ).astype(np.float32)

    if samples.size == 0:
        return 0.0

    samples /= 32768.0

    return float(
        np.sqrt(np.mean(samples * samples))
    )


def write_pcm16_wav(
    path: Path,
    pcm: bytes,
) -> float:
    sample_count = len(pcm) // 2

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(pcm)

    return sample_count / SAMPLE_RATE


def record_phrase(
    *,
    device: int,
    vad: webrtcvad.Vad,
) -> bytes:
    preroll_max_frames = max(
        1,
        int(
            PREROLL_SECONDS
            * 1000
            / FRAME_MS
        ),
    )

    end_silence_frames = max(
        1,
        int(
            END_SILENCE_SECONDS
            * 1000
            / FRAME_MS
        ),
    )

    max_frames = max(
        1,
        int(
            MAX_RECORD_SECONDS
            * 1000
            / FRAME_MS
        ),
    )

    preroll: list[bytes] = []
    start_votes: list[bool] = []

    recording = False
    recorded: list[bytes] = []
    silence_frames = 0

    print("Listening...", flush=True)

    with sd.RawInputStream(
        device=device,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SAMPLES,
    ) as stream:
        while True:
            data, overflowed = stream.read(
                FRAME_SAMPLES
            )

            if overflowed:
                print(
                    "[WARN] Microphone overflow.",
                    flush=True,
                )

            frame = bytes(data)

            if len(frame) != FRAME_SAMPLES * 2:
                continue

            voiced = vad.is_speech(
                frame,
                SAMPLE_RATE,
            )

            if not recording:
                preroll.append(frame)

                if len(preroll) > preroll_max_frames:
                    preroll.pop(0)

                start_votes.append(voiced)

                if len(start_votes) > START_WINDOW_FRAMES:
                    start_votes.pop(0)

                if (
                    len(start_votes)
                    == START_WINDOW_FRAMES
                    and sum(start_votes)
                    >= START_REQUIRED_VOICED
                ):
                    recording = True
                    recorded = list(preroll)
                    silence_frames = 0

                    print(
                        "Speech detected — keep speaking...",
                        flush=True,
                    )

                continue

            recorded.append(frame)

            if voiced:
                silence_frames = 0
            else:
                silence_frames += 1

            if silence_frames >= end_silence_frames:
                break

            if len(recorded) >= max_frames:
                print(
                    "[WARN] Maximum recording duration reached.",
                    flush=True,
                )
                break

    pcm = b"".join(recorded)

    # Keep only a short natural tail after speech.
    keep_tail_frames = int(
        0.20 * 1000 / FRAME_MS
    )

    if silence_frames > keep_tail_frames:
        remove_frames = (
            silence_frames - keep_tail_frames
        )

        remove_bytes = (
            remove_frames
            * FRAME_SAMPLES
            * 2
        )

        if remove_bytes < len(pcm):
            pcm = pcm[:-remove_bytes]

    return pcm


def mode_name(resolution) -> str:
    return resolution.policy.mode.value.upper()


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--device",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is not available to PyTorch."
        )

    print("=== CTC BG/EN CALIBRATION ===")
    print(
        f"GPU: {torch.cuda.get_device_name(0)}"
    )
    print(f"Microphone device: {args.device}")

    print(
        "\n10 VALID recordings are required:"
        "\n  5 Bulgarian"
        "\n  5 English"
    )

    print(
        "\nIMPORTANT:"
        "\nWhen READY appears, say the displayed phrase once,"
        "\nthen stop speaking and wait for the result."
    )

    print(
        "\nInvalid/quiet captures are automatically rejected."
    )

    print(
        f"Validation: duration >= "
        f"{MIN_VALID_DURATION_SECONDS:.2f}s, "
        f"RMS >= {MIN_VALID_RMS:.4f}"
    )

    print(
        "\nNo assistant actions will be executed."
    )

    print(
        "\nLoading the two CTC models once..."
    )

    provider = CtcLanguageEvidenceProvider(
        device="cuda",
        dtype=torch.float16,
    )

    resolver = LanguageResolver()
    vad = webrtcvad.Vad(1)

    results: list[TestResult] = []

    with tempfile.TemporaryDirectory(
        prefix="aurora_ctc_calibration_"
    ) as temp_dir:
        temp_path = Path(temp_dir)

        for index, (expected, phrase) in enumerate(
            TESTS,
            start=1,
        ):
            attempt = 0

            while True:
                attempt += 1

                print("\n" + "=" * 72)
                print(
                    f"TEST {index}/{len(TESTS)} "
                    f"[expected {expected}] "
                    f"[attempt {attempt}]"
                )
                print("=" * 72)

                print("\nREADY — SAY NOW:")
                print(f'  "{phrase}"')
                print()

                pcm = record_phrase(
                    device=args.device,
                    vad=vad,
                )

                if not pcm:
                    print(
                        "\nINVALID CAPTURE: "
                        "no audio captured."
                    )
                    print(
                        "Retrying the SAME phrase..."
                    )
                    continue

                duration = (
                    len(pcm) / 2 / SAMPLE_RATE
                )

                rms = pcm_rms(pcm)

                print(
                    f"\nCaptured: "
                    f"{duration:.2f}s "
                    f"RMS={rms:.4f}"
                )

                invalid_reasons: list[str] = []

                if (
                    duration
                    < MIN_VALID_DURATION_SECONDS
                ):
                    invalid_reasons.append(
                        "too short"
                    )

                if rms < MIN_VALID_RMS:
                    invalid_reasons.append(
                        "too quiet"
                    )

                if invalid_reasons:
                    print(
                        "\n*** INVALID CAPTURE ***"
                    )

                    print(
                        "Reason: "
                        + ", ".join(
                            invalid_reasons
                        )
                    )

                    print(
                        "This recording will NOT "
                        "be included."
                    )

                    print(
                        "Retrying the SAME phrase..."
                    )

                    continue

                wav_path = (
                    temp_path
                    / f"test_{index:02d}.wav"
                )

                write_pcm16_wav(
                    wav_path,
                    pcm,
                )

                print(
                    "Capture accepted."
                )

                print(
                    "Running CTC analysis..."
                )

                evidence = provider.analyze_file(
                    wav_path
                )

                resolution = (
                    resolver.resolve_evidence(
                        evidence
                    )
                )

                delta = evidence.entropy_delta
                current = mode_name(
                    resolution
                )

                result = TestResult(
                    number=index,
                    expected=expected,
                    phrase=phrase,
                    duration=duration,
                    rms=rms,
                    delta=delta,
                    current=current,
                    bg_entropy=(
                        evidence
                        .bulgarian
                        .non_blank_entropy
                    ),
                    en_entropy=(
                        evidence
                        .english
                        .non_blank_entropy
                    ),
                    bg_confidence=(
                        evidence
                        .bulgarian
                        .mean_non_blank_confidence
                    ),
                    en_confidence=(
                        evidence
                        .english
                        .mean_non_blank_confidence
                    ),
                )

                results.append(result)

                status = (
                    "OK"
                    if current == expected
                    else "WRONG"
                )

                print("\nRESULT:")
                print(
                    f"  BG entropy = "
                    f"{result.bg_entropy:.6f}"
                )
                print(
                    f"  EN entropy = "
                    f"{result.en_entropy:.6f}"
                )
                print(
                    f"  delta      = "
                    f"{result.delta:+.6f}"
                )
                print(
                    f"  BG conf    = "
                    f"{result.bg_confidence:.6f}"
                )
                print(
                    f"  EN conf    = "
                    f"{result.en_confidence:.6f}"
                )
                print(
                    f"  current    = "
                    f"{result.current}"
                )
                print(
                    f"  expected   = "
                    f"{result.expected}"
                )
                print(
                    f"  status     = {status}"
                )

                break

    print("\n\n" + "=" * 96)
    print("FINAL CALIBRATION TABLE")
    print("=" * 96)

    print(
        f"{'#':<3} "
        f"{'EXP':<4} "
        f"{'DUR':>6} "
        f"{'RMS':>7} "
        f"{'DELTA':>11} "
        f"{'CURRENT':<8} "
        f"{'BG_ENT':>9} "
        f"{'EN_ENT':>9} "
        f"{'STATUS':<6}"
    )

    print("-" * 96)

    correct = 0

    for result in results:
        status = (
            "OK"
            if result.current == result.expected
            else "WRONG"
        )

        if status == "OK":
            correct += 1

        print(
            f"{result.number:<3} "
            f"{result.expected:<4} "
            f"{result.duration:>6.2f} "
            f"{result.rms:>7.4f} "
            f"{result.delta:>+11.6f} "
            f"{result.current:<8} "
            f"{result.bg_entropy:>9.6f} "
            f"{result.en_entropy:>9.6f} "
            f"{status:<6}"
        )

    print("-" * 96)

    print(
        f"Current zero-boundary accuracy: "
        f"{correct}/{len(results)}"
    )

    bg_deltas = [
        result.delta
        for result in results
        if result.expected == "BG"
    ]

    en_deltas = [
        result.delta
        for result in results
        if result.expected == "EN"
    ]

    if bg_deltas:
        print(
            "BG delta range: "
            f"{min(bg_deltas):+.6f} .. "
            f"{max(bg_deltas):+.6f}"
        )

    if en_deltas:
        print(
            "EN delta range: "
            f"{min(en_deltas):+.6f} .. "
            f"{max(en_deltas):+.6f}"
        )

    if bg_deltas and en_deltas:
        bg_max = max(bg_deltas)
        en_min = min(en_deltas)

        print()

        if bg_max < en_min:
            midpoint = (
                bg_max + en_min
            ) / 2.0

            print(
                "Observed VALID samples are "
                "separable by entropy_delta."
            )

            print(
                "Candidate midpoint from this "
                "sample set:"
            )

            print(
                f"  {midpoint:+.6f}"
            )

        else:
            print(
                "BG and EN delta ranges overlap."
            )

            print(
                "A single entropy_delta threshold "
                "is NOT sufficient for these samples."
            )

    print(
        "\nCalibration finished."
        "\nNo commands were executed."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())