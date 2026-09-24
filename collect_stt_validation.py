"""Interactive validation capture. --list and --help need no audio/ML imports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import sys
import threading
import time
from datetime import datetime, timezone
from uuid import uuid4
import wave


ROOT = Path(__file__).resolve().parent
PLAN = ROOT / "docs" / "STT_VALIDATION_PLAN.md"
OUTPUT_ROOT = ROOT / "data" / "stt_validation" / "pilot_01"


def read_prompts(path: Path = PLAN) -> list[tuple[str, str, str]]:
    rows = re.findall(
        r"^\| ((?:BG|EN|MX)\d{2}) \| (BG|EN|MIXED) \| (.+?) \|$",
        path.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    expected = [f"{prefix}{index:02d}" for prefix in ("BG", "EN", "MX")
                for index in range(1, 9)]
    if [row[0] for row in rows] != expected:
        raise ValueError("Планът трябва да съдържа точно BG01–08, EN01–08 и MX01–08.")
    for prompt_id, label, text in rows:
        if label != {"BG": "BG", "EN": "EN", "MX": "MIXED"}[prompt_id[:2]] or not text.strip():
            raise ValueError(f"Невалидна фраза: {prompt_id}")
    return rows


def append_event(path: Path, event: dict) -> None:
    """Append-only journal; a captured event survives interrupted review."""
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def save_audio(path: Path, blocks: tuple[bytes, ...]) -> str:
    pcm = b"".join(blocks)
    if not pcm or len(pcm) % 2:
        raise ValueError("Невалидни PCM16 аудиоданни.")
    # Exclusive creation: even a filename collision cannot overwrite a WAV.
    with path.open("xb") as stream:
        with wave.open(stream, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(pcm)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(path.read_bytes()).hexdigest()


def play_audio(sd, audio, rate) -> None:
    import numpy as np

    duration = len(audio) / rate
    samples = np.asarray(audio, dtype=np.float32)
    tone_samples = max(1, round(rate * 0.15))
    t = np.arange(tone_samples) / rate
    envelope = np.hanning(tone_samples)
    start_tone = (0.12 * np.sin(2 * np.pi * 880 * t) * envelope).astype(np.float32)
    end_samples = max(1, round(rate * 0.30))
    end_time = np.arange(end_samples) / rate
    end_tone = (0.20 * np.sin(2 * np.pi * 1200 * end_time)
                * np.hanning(end_samples)).astype(np.float32)
    gap = np.zeros(round(rate * 0.15), dtype=np.float32)
    # Playback-only markers. The stored WAV and its SHA256 remain unchanged.
    playback = np.concatenate((start_tone, gap, samples, gap,
                               end_tone, gap, end_tone, gap))
    print("Един тон = начало на WAV; два високи тона = край на WAV.", flush=True)
    print(f"▶ НАЧАЛО НА ПРОСЛУШВАНЕТО — {duration:.2f} s", flush=True)
    sd.play(playback, samplerate=rate, blocking=True)
    print("■ КРАЙ НА ПРОСЛУШВАНЕТО", flush=True)


def required_text(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Въведете непразен текст.")


def wait_for_phrase(inbox, worker, failures, timeout):
    deadline = time.monotonic() + timeout
    while True:
        if not failures.empty():
            raise RuntimeError("Грешка при аудиозапис.") from failures.get_nowait()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Не е получена wake-потвърдена фраза навреме.")
        try:
            return inbox.get(timeout=min(0.2, remaining))
        except queue.Empty:
            if not worker.is_alive():
                raise RuntimeError("Capture процесът спря без фраза.")


def collect(args, prompts) -> None:
    # Only an actual recording invocation imports audio and model dependencies.
    import sounddevice as sd
    import soundfile as sf
    from app.speech.capture.aurora_capture import AuroraCapture

    microphone = dict(sd.query_devices(args.device, "input"))
    speaker = args.speaker or required_text("Псевдоним на говорителя: ")
    environment = args.environment or required_text("Среда (например тиха стая): ")
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid4().hex
    session = OUTPUT_ROOT / session_id
    session.mkdir(parents=True, exist_ok=False)
    journal = session / "manifest.jsonl"
    append_event(journal, {
        "event": "session", "schema_version": 1, "session_id": session_id,
        "speaker": speaker, "environment": environment, "microphone": microphone,
        "device": args.device, "timeout_seconds": args.timeout,
        "plan_sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest(),
        "prompts": prompts, "created_at": datetime.now(timezone.utc).isoformat(),
        "capture": "AuroraCapture", "sample_rate": 16000,
    })
    print(f"Сесия: {session}")
    print("Зарежда се wake моделът. Финален STT и действия не се изпълняват.")
    inbox = queue.Queue(maxsize=1)
    failures = queue.Queue()

    def on_phrase(phrase):
        try:
            inbox.put_nowait(phrase)
        except queue.Full:
            failures.put(RuntimeError("Получена е допълнителна фраза; сесията се прекратява."))

    capture = None
    worker = None
    active_attempt = None
    try:
        capture = AuroraCapture(device=args.device, on_phrase=on_phrase, verbose=False)
        capture.pause()

        def run_capture():
            try:
                capture.run()
            except Exception as exc:
                failures.put(exc)

        worker = threading.Thread(target=run_capture, name="validation-capture", daemon=True)
        worker.start()
        for prompt_id, label, prompted_text in prompts:
            while True:
                print(f"\n{prompt_id} [{label}]\n{prompted_text}")
                if input("Enter за един опит; Q за край: ").strip().lower() == "q":
                    return
                active_attempt = uuid4().hex
                append_event(journal, {
                    "event": "attempt", "attempt_id": active_attempt, "prompt_id": prompt_id,
                    "speech_label": label, "prompted_text": prompted_text,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                })
                print("Говорете веднъж след този надпис; изчакайте резултата.", flush=True)
                capture.resume()
                phrase = wait_for_phrase(inbox, worker, failures, args.timeout)
                capture.pause()
                filename = f"{prompt_id}_{active_attempt}.wav"
                digest = save_audio(session / filename, phrase.blocks)
                append_event(journal, {
                    "event": "captured", "attempt_id": active_attempt,
                    "filename": filename, "sha256": digest,
                    "duration_seconds": phrase.duration_seconds, "rms": phrase.rms,
                    "wake_text": phrase.wake_text,
                })
                print(f"Запис: {phrase.duration_seconds:.2f} s, RMS {phrase.rms:.4f}")
                print("Прослушайте цялата фраза, включително началото и края.")
                audio, rate = sf.read(session / filename, dtype="float32")
                play_audio(sd, audio, rate)
                while True:
                    choice = input("A приемане / R прослушване / X отхвърляне / Q край: ").strip().lower()
                    if choice == "r":
                        play_audio(sd, audio, rate)
                        continue
                    if choice not in {"a", "x", "q"}:
                        continue
                    reference = ""
                    reason = ""
                    if choice == "a":
                        reference = input("Реално произнесен текст (Enter = точно подканата): ").strip() or prompted_text
                        actual_label = required_text("Език на речта BG / EN / MIXED: ").upper()
                        while actual_label not in {"BG", "EN", "MIXED"}:
                            actual_label = required_text("Въведете BG / EN / MIXED: ").upper()
                    else:
                        actual_label = ""
                        reason = required_text("Причина за отхвърляне: ") if choice == "x" else "review_interrupted"
                    append_event(journal, {
                        "event": "review", "attempt_id": active_attempt,
                        "status": {"a": "accepted", "x": "rejected", "q": "unreviewed"}[choice],
                        "reference_text": reference, "speech_label": actual_label, "reason": reason,
                        "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    })
                    active_attempt = None
                    break
                if choice == "q":
                    return
                if choice == "a":
                    break
        print("Избраните фрази са приети. Финалният STT се изпълнява отделно.")
    except (Exception, KeyboardInterrupt) as exc:
        append_event(journal, {
            "event": "error", "attempt_id": active_attempt,
            "status": "timeout" if isinstance(exc, TimeoutError) else "interrupted_or_error",
            "error": repr(exc),
        })
        raise
    finally:
        if capture is not None:
            capture.stop()
        sd.stop()
        if worker is not None:
            worker.join(timeout=5)
        append_event(journal, {
            "event": "session_end", "ended_at": datetime.now(timezone.utc).isoformat(),
            "capture_thread_alive": worker.is_alive() if worker else False,
        })
        print(f"Запазени данни: {session}\nЗатворете процеса преди финален STT.")


def main() -> None:
    # Windows redirected output may default to cp1252, which cannot encode BG.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and not stream.isatty():
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Отделен BG/EN/MIXED validation collector.")
    parser.add_argument("--list", action="store_true", help="Само показва фразите; без микрофон или модели.")
    parser.add_argument("--device", type=int, default=1)
    parser.add_argument("--speaker", help="Псевдоним на говорителя.")
    parser.add_argument("--environment", help="Описание на средата.")
    parser.add_argument("--start", help="Начален ID при продължаване в нова сесия.")
    parser.add_argument("--count", type=int, default=24)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    if args.count < 1 or not 5 <= args.timeout <= 600:
        parser.error("count трябва да е положителен; timeout трябва да е между 5 и 600 s.")
    prompts = read_prompts()
    if args.start:
        ids = [row[0] for row in prompts]
        if args.start not in ids:
            parser.error("Непознат начален ID.")
        prompts = prompts[ids.index(args.start):]
    prompts = prompts[:args.count]
    if args.list:
        for row in prompts:
            print(" | ".join(row))
        return
    collect(args, prompts)


if __name__ == "__main__":
    main()
