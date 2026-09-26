
import argparse
import queue
import time
import wave
from collections import deque
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import webrtcvad


SAMPLE_RATE = 16000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_BYTES = FRAME_SAMPLES * 2

DEFAULT_DEVICE = 1  # Trust GXT 232

PRE_ROLL_S = 0.30
POST_ROLL_S = 0.20
MAX_COMMAND_S = 20.0
MIN_COMMAND_S = 0.50

OUTPUT_DIR = Path("data/command_capture/webrtc")


def frame_count(seconds):
    return max(1, round(seconds * 1000 / FRAME_MS))


def parse_args():
    parser = argparse.ArgumentParser(
        description="WebRTC VAD diagnostic with manual arming."
    )
    parser.add_argument(
        "--device",
        type=int,
        default=DEFAULT_DEVICE,
    )
    parser.add_argument(
        "--mode",
        type=int,
        choices=(0, 1, 2, 3),
        default=1,
    )
    parser.add_argument(
        "--start-timeout",
        type=float,
        default=15.0,
    )
    parser.add_argument(
        "--end-silence",
        type=float,
        default=1.2,
    )
    return parser.parse_args()


def signal_stats(frames):
    if not frames:
        return 0.0, 0.0

    audio = np.frombuffer(
        b"".join(frames),
        dtype="<i2",
    ).astype(np.float64)

    if audio.size == 0:
        return 0.0, 0.0

    peak = float(np.max(np.abs(audio))) / 32768.0
    rms = float(np.sqrt(np.mean(audio * audio))) / 32768.0

    return peak, rms


def save_wav(path, frames):
    path.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(b"".join(frames))


def main():
    args = parse_args()

    if args.start_timeout <= 0:
        raise ValueError("--start-timeout must be positive.")

    if args.end_silence <= 0:
        raise ValueError("--end-silence must be positive.")

    device = sd.query_devices(args.device, "input")

    sd.check_input_settings(
        device=args.device,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
    )

    vad = webrtcvad.Vad(args.mode)

    pre_roll_count = frame_count(PRE_ROLL_S)
    post_roll_count = frame_count(POST_ROLL_S)
    start_timeout_count = frame_count(args.start_timeout)
    end_silence_count = frame_count(args.end_silence)
    max_command_count = frame_count(MAX_COMMAND_S)
    min_command_count = frame_count(MIN_COMMAND_S)

    # За начало изискваме поне 5 VAD-положителни порции
    # в прозорец от 8 порции (160 ms).
    start_window_count = 8
    start_required_votes = 5

    audio_queue = queue.Queue(maxsize=500)
    warnings = []
    dropped_frames = [0]

    def callback(indata, frames, time_info, status):
        if status:
            warnings.append(str(status))

        frame = bytes(indata)

        if frames != FRAME_SAMPLES or len(frame) != FRAME_BYTES:
            warnings.append(
                f"Unexpected frame: {frames} samples, "
                f"{len(frame)} bytes"
            )
            return

        try:
            audio_queue.put_nowait(
                (time.perf_counter(), frame)
            )
        except queue.Full:
            dropped_frames[0] += 1

    print("=== WEBRTC VAD DIAGNOSTIC V2 ===")
    print(f"Device: {args.device} - {device['name']}")
    print(f"Sample rate: {SAMPLE_RATE} Hz")
    print(f"Frame: {FRAME_MS} ms")
    print(f"VAD mode: {args.mode}")
    print(f"Start timeout: {args.start_timeout:.2f} s")
    print(f"End silence: {args.end_silence:.2f} s")
    print(f"Max command: {MAX_COMMAND_S:.1f} s")

    print(
        "\nPrepare your command. "
        "The microphone is NOT listening yet."
    )

    input("Press ENTER when ready to speak...")

    pre_roll = deque(maxlen=pre_roll_count)
    start_votes = deque(maxlen=start_window_count)

    recorded = []
    state = "WAITING"

    wait_count = 0
    command_count = 0
    silence_count = 0

    last_voice_time = None
    stop_time = None
    stop_reason = None

    with sd.RawInputStream(
        device=args.device,
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SAMPLES,
        callback=callback,
    ):
        print(
            "\nREADY — you have "
            f"{args.start_timeout:.0f} seconds to start.",
            flush=True,
        )

        while True:
            frame_time, frame = audio_queue.get()

            is_speech = vad.is_speech(
                frame,
                SAMPLE_RATE,
            )

            if state == "WAITING":
                pre_roll.append(frame)
                start_votes.append(is_speech)
                wait_count += 1

                if (
                    len(start_votes) == start_window_count
                    and sum(start_votes) >= start_required_votes
                ):
                    state = "RECORDING"

                    recorded.extend(pre_roll)
                    command_count = len(recorded)
                    silence_count = 0

                    if is_speech:
                        last_voice_time = frame_time

                    print(
                        "Speech confirmed. Recording...",
                        flush=True,
                    )
                    continue

                if wait_count >= start_timeout_count:
                    stop_reason = "NO_SPEECH"
                    stop_time = frame_time
                    break

            else:
                recorded.append(frame)
                command_count += 1

                if is_speech:
                    last_voice_time = frame_time
                    silence_count = 0
                else:
                    silence_count += 1

                # Не приключваме от кратък шум или единична дума,
                # преди да има поне 500 ms запис.
                if (
                    command_count >= min_command_count
                    and silence_count >= end_silence_count
                ):
                    stop_reason = "END_SILENCE"
                    stop_time = frame_time
                    break

                if command_count >= max_command_count:
                    stop_reason = "MAX_DURATION"
                    stop_time = frame_time
                    break

    print("\n=== RESULT ===")
    print(f"Stop reason: {stop_reason}")

    if warnings:
        print(f"Stream warnings: {warnings[:5]!r}")

    if dropped_frames[0]:
        print(f"Dropped frames: {dropped_frames[0]}")

    if stop_reason == "NO_SPEECH":
        print("No command was recorded.")
        return

    # При крайна тишина запазваме последните 200 ms,
    # но не изрязваме реалната реч.
    if stop_reason == "END_SILENCE":
        remove_count = max(
            0,
            silence_count - post_roll_count,
        )

        if remove_count:
            recorded = recorded[:-remove_count]

    if not recorded:
        print("ERROR: Recorded audio is empty.")
        return

    peak, audio_rms = signal_stats(recorded)

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    output_path = (
        OUTPUT_DIR / f"command_{timestamp}.wav"
    )

    save_wav(output_path, recorded)

    saved_duration = (
        len(recorded) * FRAME_MS / 1000.0
    )

    print(
        f"Saved audio: {output_path.resolve()}"
    )
    print(
        f"Saved duration: {saved_duration:.3f} s"
    )
    print(f"Peak: {peak:.5f}")
    print(f"RMS: {audio_rms:.5f}")

    if (
        last_voice_time is not None
        and stop_time is not None
    ):
        print(
            "Last VAD-positive frame -> capture stopped: "
            f"{stop_time - last_voice_time:.3f} s"
        )

    if saved_duration < MIN_COMMAND_S:
        print(
            "WARNING: Recording is too short "
            "for a reliable command."
        )

    if peak < 0.001:
        print(
            "WARNING: Recorded signal is extremely quiet."
        )

    print(
        "NOTE: VAD timing is not an exact acoustic "
        "speech-end measurement."
    )


if __name__ == "__main__":
    main()