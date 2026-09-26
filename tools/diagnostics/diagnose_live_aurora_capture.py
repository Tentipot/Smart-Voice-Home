import argparse
import queue
import threading
from datetime import datetime
from pathlib import Path

from app.speech.capture.aurora_capture import (
    AuroraCapture,
    CapturedPhrase,
)
from tools.datasets.collect_language_dataset import save_phrase


OUTPUT_DIR = Path("data/command_capture/live_stt_diagnostic")

# Match collect_language_dataset.py console formatting.
GREEN_BOLD = "\033[1;92m"
RESET = "\033[0m"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture one live Aurora phrase without executing actions."
    )
    parser.add_argument("--device", type=int, default=1)
    args = parser.parse_args()

    phrase_queue: queue.Queue[CapturedPhrase] = queue.Queue(maxsize=1)

    def on_phrase(phrase: CapturedPhrase) -> None:
        try:
            phrase_queue.put_nowait(phrase)
        except queue.Full:
            print("[DIAGNOSTIC] Extra phrase discarded.", flush=True)

    capture = AuroraCapture(
        device=args.device,
        on_phrase=on_phrase,
        verbose=True,
    )

    capture_thread = threading.Thread(
        target=capture.run,
        name="live-aurora-diagnostic",
        daemon=True,
    )

    print("=== LIVE AURORA CAPTURE DIAGNOSTIC ===", flush=True)
    print("Say the wake word and one command.", flush=True)
    print("No STT routing or assistant actions will execute.", flush=True)

    capture_thread.start()

    try:
        while True:
            try:
                phrase = phrase_queue.get(timeout=0.5)
                break
            except queue.Empty:
                if not capture_thread.is_alive():
                    raise RuntimeError(
                        "AuroraCapture stopped before delivering a phrase."
                    )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_path = OUTPUT_DIR / f"aurora_{timestamp}.wav"

        save_phrase(output_path, phrase)

        print(f"\n{GREEN_BOLD}=== CAPTURED PHRASE ==={RESET}", flush=True)
        print(f"{GREEN_BOLD}Audio: {output_path.resolve()}{RESET}", flush=True)
        print(f"Duration: {phrase.duration_seconds:.2f}s", flush=True)
        print(f"RMS: {phrase.rms:.4f}", flush=True)
        print(f"Wake ASR: {phrase.wake_text!r}", flush=True)

    finally:
        capture.stop()
        capture_thread.join(timeout=5.0)

        if capture_thread.is_alive():
            print(
                "[WARNING] Capture thread did not stop within 5 seconds.",
                flush=True,
            )

    print(
        "\nCapture diagnostic finished. "
        "Run STT separately after this Python process exits.",
        flush=True,
    )


if __name__ == "__main__":
    main()
