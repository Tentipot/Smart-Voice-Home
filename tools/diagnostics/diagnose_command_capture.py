import argparse
import queue
import time
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf


SAMPLE_RATE = 16000
BLOCK_MS = 20
BLOCK_SIZE = SAMPLE_RATE * BLOCK_MS // 1000

START_TIMEOUT_S = 3.0
END_SILENCE_S = 0.70
MAX_SPEECH_S = 20.0

PRE_ROLL_S = 0.30
POST_ROLL_S = 0.20

NOISE_CALIBRATION_S = 1.0

# Начални стойности за диагностика, не окончателен VAD.
MIN_RMS_THRESHOLD = 0.008
NOISE_MULTIPLIER = 3.0
START_CONFIRM_BLOCKS = 3

OUTPUT_DIR = Path("data/command_capture")


def rms(samples: np.ndarray) -> float:
    samples64 = samples.astype(np.float64, copy=False)
    return float(np.sqrt(np.mean(samples64 * samples64)))


def parse_args():
    parser = argparse.ArgumentParser(
        description="Diagnostic microphone command capture."
    )
    parser.add_argument(
        "--device",
        type=int,
        default=2,
        help="Input device index from sounddevice.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="Optional fixed RMS threshold.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    device = sd.query_devices(args.device, "input")

    if device["max_input_channels"] < 1:
        raise RuntimeError(
            f"Device {args.device} has no input channels."
        )

    print("=== COMMAND CAPTURE DIAGNOSTIC ===", flush=True)
    print(f"Device: {args.device} - {device['name']}", flush=True)
    print(f"Sample rate: {SAMPLE_RATE} Hz", flush=True)
    print(f"Block: {BLOCK_MS} ms", flush=True)
    print(f"Start timeout: {START_TIMEOUT_S:.2f} s", flush=True)
    print(f"End silence: {END_SILENCE_S:.2f} s", flush=True)
    print(f"Max speech: {MAX_SPEECH_S:.1f} s", flush=True)
    print(
        "\nThis test does not execute commands.",
        flush=True,
    )

    audio_queue = queue.Queue()
    stream_errors = []

    def callback(indata, frames, time_info, status):
        if status:
            stream_errors.append(str(status))

        audio_queue.put(
            (
                time.perf_counter(),
                indata[:, 0].copy(),
            )
        )

    pre_roll_blocks = max(
        1,
        round(PRE_ROLL_S * SAMPLE_RATE / BLOCK_SIZE),
    )

    post_roll_blocks = max(
        1,
        round(POST_ROLL_S * SAMPLE_RATE / BLOCK_SIZE),
    )

    end_silence_blocks = max(
        1,
        round(END_SILENCE_S * SAMPLE_RATE / BLOCK_SIZE),
    )

    calibration_blocks = max(
        1,
        round(NOISE_CALIBRATION_S * SAMPLE_RATE / BLOCK_SIZE),
    )

    start_timeout_blocks = max(
        1,
        round(START_TIMEOUT_S * SAMPLE_RATE / BLOCK_SIZE),
    )

    max_speech_blocks = max(
        1,
        round(MAX_SPEECH_S * SAMPLE_RATE / BLOCK_SIZE),
    )

    print(
        "\nStarting microphone. Keep quiet during calibration.",
        flush=True,
    )

    with sd.InputStream(
        device=args.device,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        blocksize=BLOCK_SIZE,
        callback=callback,
    ):
        noise_levels = []

        for _ in range(calibration_blocks):
            _, block = audio_queue.get()
            noise_levels.append(rms(block))

        noise_floor = float(np.median(noise_levels))

        if args.threshold is None:
            threshold = max(
                MIN_RMS_THRESHOLD,
                noise_floor * NOISE_MULTIPLIER,
            )
        else:
            threshold = args.threshold

        if threshold <= 0:
            raise ValueError(
                "RMS threshold must be greater than zero."
            )

        print(
            f"Noise floor RMS: {noise_floor:.5f}",
            flush=True,
        )
        print(
            f"Speech threshold RMS: {threshold:.5f}",
            flush=True,
        )
        print(
            "\nReady. Speak your command NOW.",
            flush=True,
        )

        pre_roll = deque(maxlen=pre_roll_blocks)

        recorded = []
        state = "WAITING"

        wait_blocks = 0
        consecutive_voice_blocks = 0
        speech_blocks = 0
        silence_blocks = 0

        first_speech_time = None
        last_voice_time = None
        capture_end_time = None
        stop_reason = None

        while True:
            block_time, block = audio_queue.get()

            level = rms(block)
            voiced = level >= threshold

            if state == "WAITING":
                pre_roll.append(block)
                wait_blocks += 1

                if voiced:
                    consecutive_voice_blocks += 1
                else:
                    consecutive_voice_blocks = 0

                if (
                    consecutive_voice_blocks
                    >= START_CONFIRM_BLOCKS
                ):
                    state = "RECORDING"

                    recorded.extend(pre_roll)

                    first_speech_time = block_time
                    last_voice_time = block_time

                    speech_blocks = len(pre_roll)
                    silence_blocks = 0

                    print(
                        "\nSpeech detected. Recording...",
                        flush=True,
                    )

                    continue

                if wait_blocks >= start_timeout_blocks:
                    stop_reason = "NO_SPEECH"
                    capture_end_time = block_time
                    break

            elif state == "RECORDING":
                recorded.append(block)
                speech_blocks += 1

                if voiced:
                    last_voice_time = block_time
                    silence_blocks = 0
                else:
                    silence_blocks += 1

                if silence_blocks >= end_silence_blocks:
                    stop_reason = "END_SILENCE"
                    capture_end_time = block_time
                    break

                if speech_blocks >= max_speech_blocks:
                    stop_reason = "MAX_DURATION"
                    capture_end_time = block_time
                    break

    print("\n=== RESULT ===", flush=True)
    print(f"Stop reason: {stop_reason}", flush=True)

    if stream_errors:
        print(
            f"Stream warnings: {stream_errors[:5]!r}",
            flush=True,
        )

    if stop_reason == "NO_SPEECH":
        print("No command was recorded.", flush=True)
        return

    # Запазваме само малка част от крайната тишина.
    trailing_silence_to_remove = max(
        0,
        silence_blocks - post_roll_blocks,
    )

    if trailing_silence_to_remove:
        recorded = recorded[:-trailing_silence_to_remove]

    audio = np.concatenate(recorded).astype(
        np.float32,
        copy=False,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    filename = (
        "command_"
        + datetime.now().strftime("%Y%m%d_%H%M%S")
        + ".wav"
    )

    output_path = OUTPUT_DIR / filename

    sf.write(
        output_path,
        audio,
        SAMPLE_RATE,
        subtype="PCM_16",
    )

    duration_s = len(audio) / SAMPLE_RATE

    print(
        f"Saved audio: {output_path.resolve()}",
        flush=True,
    )
    print(
        f"Saved duration: {duration_s:.3f} s",
        flush=True,
    )

    if (
        first_speech_time is not None
        and last_voice_time is not None
        and capture_end_time is not None
    ):
        print(
            "Detected last voice -> capture stopped: "
            f"{capture_end_time - last_voice_time:.3f} s",
            flush=True,
        )

    print(
        "NOTE: This measures the RMS detector's last voiced "
        "block, not the exact acoustic end of speech.",
        flush=True,
    )


if __name__ == "__main__":
    main()