import argparse
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel


SAMPLE_RATE = 16000
RECORD_SECONDS = 4.0
WAKE_WORDS = {"aurora", "аурора"}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    return " ".join(text.split())


def contains_wake_word(text: str) -> bool:
    return any(word in WAKE_WORDS for word in normalize(text).split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="large-v3")
    parser.add_argument("--device", type=int, default=1)
    args = parser.parse_args()

    output_dir = Path("data/command_capture/wakeword")
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading locally cached model...", flush=True)
    model = WhisperModel(
        args.model,
        device="cpu",
        compute_type="int8",
        local_files_only=True,
    )

    print("Model ready. Microphone device:", args.device, flush=True)

    for label in ("english", "bulgarian"):
        input(
            f"\n[{label}] Press ENTER, then say "
            "'Aurora' or 'Аурора' clearly..."
        )

        print("Recording starts NOW.", flush=True)

        audio = sd.rec(
            int(RECORD_SECONDS * SAMPLE_RATE),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=args.device,
        )
        sd.wait()

        audio = np.asarray(audio[:, 0], dtype=np.float32)

        filename = (
            f"{label}_{datetime.now():%Y%m%d_%H%M%S}.wav"
        )
        path = output_dir / filename

        sf.write(path, audio, SAMPLE_RATE)

        peak = float(np.max(np.abs(audio)))
        rms = float(np.sqrt(np.mean(audio * audio)))

        print(
            f"Saved: {path} | peak={peak:.4f} rms={rms:.4f}",
            flush=True,
        )
        print("Transcribing saved recording...", flush=True)

        start = time.perf_counter()

        segments, info = model.transcribe(
            audio,
            language=None,
            beam_size=5,
            condition_on_previous_text=False,
            vad_filter=False,
            temperature=0.0,
        )

        text = " ".join(
            segment.text for segment in segments
        ).strip()

        elapsed = time.perf_counter() - start
        detected = contains_wake_word(text)

        print(f"Language: {info.language}")
        print(f"Transcript: {text!r}")
        print(f"Wake detected: {detected}")
        print(f"Transcription time: {elapsed:.2f}s", flush=True)

    print("\nBoth tests finished. No commands executed.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
