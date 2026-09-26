import time
import wave
from pathlib import Path

import sounddevice as sd


SAMPLE_RATE = 16000
CHANNELS = 1
DTYPE = "int16"
RECORD_SECONDS = 8

OUTPUT_DIR = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "stt_benchmark"
)


TESTS = [
    # ============================================================
    # Bulgarian only
    # ============================================================
    (1, "BG", "Намали звука на двадесет процента"),
    (2, "BG", "Изключи лампата в хола"),
    (3, "BG", "Увеличи звука"),
    (4, "BG", "Спри музиката"),
    (5, "BG", "Продължи музиката"),
    (6, "BG", "Пусни следващата песен"),
    (7, "BG", "Върни предишната песен"),
    (8, "BG", "Рестартирай песента"),
    (9, "BG", "Включи лампата в кухнята"),
    (10, "BG", "Настрой звука на петдесет процента"),

    # ============================================================
    # English only
    # ============================================================
    (11, "EN", "Set the volume to twenty percent"),
    (12, "EN", "Turn off the living room light"),
    (13, "EN", "Turn up the volume"),
    (14, "EN", "Stop the music"),
    (15, "EN", "Continue the music"),
    (16, "EN", "Play Metallica Enter Sandman on Spotify"),
    (17, "EN", "Play Dr. Dre Still D.R.E. on Spotify"),
    (18, "EN", "Play Guns N' Roses November Rain"),
    (19, "EN", "Turn on the kitchen light"),
    (20, "EN", "Restart the song"),

    # ============================================================
    # Bulgarian + English mixed
    # ============================================================
    (21, "BG+EN", "Пусни Metallica Enter Sandman в Spotify"),

    (
        22,
        "BG+EN",
        "Play Guns N' Roses и увеличи звука на двадесет процента",
    ),

    (
        23,
        "BG+EN",
        "Пусни Dr. Dre Still D.R.E. and set the volume to fifty percent",
    ),

    (
        24,
        "BG+EN",
        "Set the volume на тридесет процента и продължи музиката",
    ),

    (
        25,
        "BG+EN",
        "Отвори YouTube на Samsung TV and play the latest video",
    ),

    (
        26,
        "BG+EN",
        "Play Metallica Enter Sandman и после намали звука",
    ),

    (
        27,
        "BG+EN",
        "Пусни следващата song and turn up the volume",
    ),

    (
        28,
        "BG+EN",
        "Turn on лампата в хола и изключи kitchen light",
    ),

    (
        29,
        "BG+EN",
        "Спри music on Samsung TV и продължи на този телефон",
    ),

    (
        30,
        "BG+EN",
        "Play the next song и след това рестартирай песента",
    ),
]


def save_wav(file_path: Path, audio) -> None:
    with wave.open(str(file_path), "wb") as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(audio.tobytes())


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("Assistant STT Benchmark Recorder")
    print("================================")
    print()
    print(f"Sample rate : {SAMPLE_RATE} Hz")
    print(f"Channels    : {CHANNELS}")
    print(f"Recording   : {RECORD_SECONDS} seconds")
    print(f"Tests       : {len(TESTS)}")
    print()
    print("HOW IT WORKS:")
    print()
    print("1. Read the command.")
    print("2. Take as much time as you need.")
    print("3. Press ENTER when ready.")
    print("4. You get a 1-second countdown.")
    print("5. Speak naturally.")
    print()
    print("Existing test_001.wav ... test_030.wav")
    print("will be replaced as we record them.")
    print()

    input("Press ENTER to begin the benchmark...")

    for test_number, category, text in TESTS:
        filename = f"test_{test_number:03d}.wav"
        file_path = OUTPUT_DIR / filename

        print()
        print("=" * 72)
        print(
            f"TEST {test_number:03d} / "
            f"{len(TESTS):03d}"
        )
        print(f"Category: {category}")
        print("=" * 72)
        print()
        print("COMMAND:")
        print()
        print(text)
        print()
        print("Read the command first.")
        print("There is NO time limit here.")
        print()

        input("When ready, press ENTER to record...")

        print()
        print("Get ready...")
        time.sleep(1.0)

        print("RECORDING NOW!")

        audio = sd.rec(
            int(RECORD_SECONDS * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
        )

        sd.wait()

        save_wav(
            file_path,
            audio,
        )

        print()
        print("Recording finished.")
        print(f"Saved: {file_path}")

        if test_number != TESTS[-1][0]:
            print()
            input("Press ENTER to show the next command...")

    print()
    print("=" * 72)
    print("RECORDING COMPLETE")
    print("=" * 72)
    print()
    print(f"Recorded {len(TESTS)} files.")
    print(f"Location: {OUTPUT_DIR}")
    print()


if __name__ == "__main__":
    main()