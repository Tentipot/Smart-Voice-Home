import threading
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"

OUTPUT_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "stt_benchmark"
)


TESTS = [
    # ============================================================
    # Bulgarian only
    # ============================================================
    (
        61,
        "BG",
        "Намали звука на четиридесет процента",
    ),
    (
        62,
        "BG",
        "Заглуши звука на телевизора",
    ),
    (
        63,
        "BG",
        "Включи осветлението в коридора",
    ),
    (
        64,
        "BG",
        "Изключи лампата в спалнята",
    ),
    (
        65,
        "BG",
        "Продължи музиката на телевизора",
    ),
    (
        66,
        "BG",
        "Върни една песен назад",
    ),
    (
        67,
        "BG",
        "Увеличи звука на този телефон",
    ),
    (
        68,
        "BG",
        "Настрой звука на осемдесет процента",
    ),
    (
        69,
        "BG",
        "Спри песента на телевизора",
    ),
    (
        70,
        "BG",
        "Включи лампата в хола",
    ),

    # ============================================================
    # English only
    # ============================================================
    (
        71,
        "EN",
        "Lower the volume to forty percent",
    ),
    (
        72,
        "EN",
        "Mute the TV",
    ),
    (
        73,
        "EN",
        "Turn on the hallway light",
    ),
    (
        74,
        "EN",
        "Turn off the bedroom light",
    ),
    (
        75,
        "EN",
        "Continue the music on the TV",
    ),
    (
        76,
        "EN",
        "Go back one song",
    ),
    (
        77,
        "EN",
        "Turn up the volume on this phone",
    ),
    (
        78,
        "EN",
        "Set the volume to eighty percent",
    ),
    (
        79,
        "EN",
        "Stop the song on the TV",
    ),
    (
        80,
        "EN",
        "Turn on the living room light",
    ),
]


def save_wav(
    file_path: Path,
    audio: np.ndarray,
) -> None:
    with wave.open(str(file_path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio.tobytes())


def record_until_enter() -> tuple[np.ndarray, float]:
    chunks: list[np.ndarray] = []
    stop_event = threading.Event()

    def audio_callback(
        indata,
        frames,
        time_info,
        status,
    ) -> None:
        if status:
            print(
                f"\nAudio status: {status}",
                flush=True,
            )

        chunks.append(indata.copy())

    def wait_for_enter() -> None:
        input()
        stop_event.set()

    print()
    print("RECORDING NOW!")
    print("Speak naturally.")
    print("Press ENTER when you have finished.")
    print()

    start_time = time.perf_counter()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype=DTYPE,
        callback=audio_callback,
    ):
        stop_thread = threading.Thread(
            target=wait_for_enter,
            daemon=True,
        )

        stop_thread.start()

        while not stop_event.is_set():
            time.sleep(0.01)

    if not chunks:
        raise RuntimeError(
            "No audio samples were recorded."
        )

    audio = np.concatenate(
        chunks,
        axis=0,
    )

    actual_duration_seconds = (
        len(audio) / SAMPLE_RATE
    )

    return audio, actual_duration_seconds


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("Assistant STT Validation Recorder")
    print("=================================")
    print()
    print(f"Sample rate : {SAMPLE_RATE} Hz")
    print(f"Channels    : {CHANNELS}")
    print("Format      : 16-bit PCM WAV")
    print("Recording   : manual START / STOP")
    print(f"Tests       : {len(TESTS)}")
    print()
    print("HOW IT WORKS:")
    print()
    print("1. Read the command on screen.")
    print("2. Press ENTER when ready.")
    print("3. Recording starts IMMEDIATELY.")
    print("4. Speak naturally.")
    print("5. Press ENTER again when finished.")
    print("6. The WAV file is saved immediately.")
    print()
    print("There is NO 1-second countdown.")
    print("There is NO fixed 8-second recording.")
    print()
    print("Files test_061.wav ... test_080.wav")
    print("will be created/replaced.")
    print()

    input(
        "Press ENTER to begin the validation corpus..."
    )

    total_tests = len(TESTS)

    for index, (
        test_number,
        category,
        text,
    ) in enumerate(
        TESTS,
        start=1,
    ):
        filename = f"test_{test_number:03d}.wav"
        file_path = OUTPUT_DIR / filename

        print()
        print("=" * 72)
        print(
            f"TEST {test_number:03d}  "
            f"({index}/{total_tests})"
        )
        print(f"Category: {category}")
        print("=" * 72)
        print()
        print("COMMAND:")
        print()
        print(text)
        print()
        print(
            "Press ENTER when ready. "
            "Recording will start immediately."
        )

        input()

        audio, duration_seconds = (
            record_until_enter()
        )

        save_wav(
            file_path,
            audio,
        )

        print()
        print("Recording finished.")
        print(
            f"Duration: {duration_seconds:.2f} s"
        )
        print(f"Saved: {file_path}")

        if index != total_tests:
            print()
            input(
                "Press ENTER to show the next command..."
            )

    print()
    print("=" * 72)
    print("VALIDATION RECORDING COMPLETE")
    print("=" * 72)
    print()
    print(f"Recorded {total_tests} files.")
    print(f"Location: {OUTPUT_DIR}")
    print()


if __name__ == "__main__":
    main()