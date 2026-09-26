import argparse
import queue
import tempfile
import threading
import time
from dataclasses import asdict
from pathlib import Path

from app.resources.model_types import ModelId
from app.speech.capture.aurora_capture import AuroraCapture, CapturedPhrase
from app.speech.stt.composition import create_stt_runtime
from collect_language_dataset import save_phrase


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Live AuroraCapture -> production STT diagnostic. "
            "No assistant actions are executed."
        )
    )
    parser.add_argument("--device", type=int, default=1)
    args = parser.parse_args()

    phrase_queue: queue.Queue[CapturedPhrase] = queue.Queue(maxsize=1)

    def on_phrase(phrase: CapturedPhrase) -> None:
        try:
            phrase_queue.put_nowait(phrase)
        except queue.Full:
            print(
                "[LIVE STT] Phrase discarded while STT is busy.",
                flush=True,
            )

    print("=== LIVE PRODUCTION STT ===", flush=True)
    print("Creating production STT runtime...", flush=True)

    runtime = create_stt_runtime()

    capture = AuroraCapture(
        device=args.device,
        on_phrase=on_phrase,
        verbose=True,
    )

    capture_thread = threading.Thread(
        target=capture.run,
        name="live-production-stt",
        daemon=True,
    )

    print("Ready. Say the wake word and any command.", flush=True)
    print("No assistant actions will be executed.", flush=True)
    print("Press Ctrl+C to stop.\n", flush=True)

    capture_thread.start()

    try:
        while True:
            try:
                phrase = phrase_queue.get(timeout=0.5)

            except queue.Empty:
                if not capture_thread.is_alive():
                    raise RuntimeError(
                        "AuroraCapture stopped unexpectedly."
                    )
                continue

            print("\n=== CAPTURE ===", flush=True)
            print(
                f"Duration: {phrase.duration_seconds:.2f} s",
                flush=True,
            )
            print(
                f"RMS: {phrase.rms:.4f}",
                flush=True,
            )
            print(
                f"Wake ASR: {phrase.wake_text!r}",
                flush=True,
            )

            temp_path: Path | None = None

            try:
                with tempfile.NamedTemporaryFile(
                    prefix="aurora_live_",
                    suffix=".wav",
                    delete=False,
                ) as temp_file:
                    temp_path = Path(temp_file.name)

                save_phrase(temp_path, phrase)

                print(
                    "\n=== PRODUCTION STT ===",
                    flush=True,
                )

                started = time.perf_counter()

                transcription = (
                    runtime.service.transcribe_with_evidence(
                        temp_path
                    )
                )

                elapsed = time.perf_counter() - started
                result = transcription.result

                print(
                    f"CTC evidence: "
                    f"{asdict(transcription.evidence)}",
                    flush=True,
                )

                print(
                    "Route: "
                    f"{transcription.resolution.policy.mode.value}",
                    flush=True,
                )

                print(
                    "Resolution reason: "
                    f"{transcription.resolution.reason}",
                    flush=True,
                )

                print(
                    f"Engine: {result.engine}",
                    flush=True,
                )

                print(
                    f"Model: {result.model}",
                    flush=True,
                )

                print(
                    f"Language: {result.language}",
                    flush=True,
                )

                print(
                    "Language confidence: "
                    f"{result.language_confidence}",
                    flush=True,
                )

                print(
                    f"Transcript: {result.text}",
                    flush=True,
                )

                print(
                    f"STT time: {elapsed:.2f} s",
                    flush=True,
                )

            except Exception as exc:
                print(
                    "\n[LIVE STT ERROR] "
                    f"{type(exc).__name__}: {exc}",
                    flush=True,
                )

            finally:
                if (
                    temp_path is not None
                    and temp_path.exists()
                ):
                    try:
                        temp_path.unlink()

                    except OSError as exc:
                        print(
                            "[WARNING] Could not delete "
                            f"temporary WAV: {exc}",
                            flush=True,
                        )

                #
                # AuroraCapture intentionally pauses before
                # handing CapturedPhrase to the consumer.
                # Live operation must explicitly resume it
                # after the phrase has been processed.
                #
                capture.resume()

            print(
                "\nReady for next command.",
                flush=True,
            )

    except KeyboardInterrupt:
        print(
            "\nStopping live STT diagnostic...",
            flush=True,
        )

    finally:
        capture.stop()

        capture_thread.join(timeout=5.0)

        if capture_thread.is_alive():
            print(
                "[WARNING] Capture thread did not stop "
                "within 5 seconds.",
                flush=True,
            )

        for model_id in (
            ModelId.CTC_LANGUAGE,
            ModelId.BUZZ_BG,
            ModelId.WHISPER_LARGE_V3,
        ):
            try:
                if runtime.model_manager.is_loaded(model_id):
                    runtime.model_manager.unload(model_id)

            except Exception as exc:
                print(
                    "[WARNING] Could not unload "
                    f"{model_id}: {exc}",
                    flush=True,
                )

    print(
        "Live STT diagnostic finished.",
        flush=True,
    )


if __name__ == "__main__":
    main()