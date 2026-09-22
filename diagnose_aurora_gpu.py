from __future__ import annotations

import argparse
import queue
import re
import threading
import time
import unicodedata
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf
import webrtcvad

from app.speech.stt.whisper_engine import WhisperSttEngine


SAMPLE_RATE = 16000

REQUESTED_BLOCK_MS = 100
REQUESTED_BLOCK_SAMPLES = (
    SAMPLE_RATE * REQUESTED_BLOCK_MS // 1000
)

PRE_ROLL_SECONDS = 1.2

END_SILENCE_SECONDS = 1.2
MAX_PHRASE_SECONDS = 20.0
MIN_PHRASE_SECONDS = 0.5

VAD_FRAME_MS = 20
VAD_BLOCK_MIN_RATIO = 0.60

START_WINDOW_BLOCKS = 4
START_REQUIRED_VOICED = 3

WAKE_CHECK_INTERVAL_SECONDS = 0.5
MIN_WAKE_AUDIO_SECONDS = 1.5
MAX_WAKE_PREFIX_SECONDS = 4.0

WAKE_RMS_THRESHOLD = 0.008

OUTPUT_DIR = Path(
    "data/command_capture/wakeword_gpu"
)

WAKE_WORDS = {
    "\u0430\u0443\u0440\u043e\u0440\u0430",
    "aurora",
    "\u0623\u0648\u0631\u0648\u0631\u0627",
    "\u0623\u0631\u0648\u0631",
    "\u0623\u0648\u0631\u0648\u0631",
}

WAKE_PREFIXES = (
    "\u0430\u0443\u0440\u043e\u0440\u0430",
    "aurora",
)


def normalize_text(text: str) -> str:
    text = unicodedata.normalize(
        "NFKC",
        text,
    ).casefold()

    return re.sub(
        r"[^\w]+",
        " ",
        text,
        flags=re.UNICODE,
    ).strip()


def contains_wake(text: str) -> bool:
    words = normalize_text(text).split()

    if any(
        word in WAKE_WORDS
        for word in words
    ):
        return True

    return any(
        word.startswith(WAKE_PREFIXES)
        for word in words
    )


def pcm_sample_count(audio: bytes) -> int:
    return len(audio) // 2


def blocks_sample_count(
    blocks: list[bytes] | deque[bytes],
) -> int:
    return sum(
        pcm_sample_count(block)
        for block in blocks
    )


def blocks_duration(
    blocks: list[bytes] | deque[bytes],
) -> float:
    return (
        blocks_sample_count(blocks)
        / SAMPLE_RATE
    )


def pcm_to_float(audio: bytes) -> np.ndarray:
    return (
        np.frombuffer(
            audio,
            dtype=np.int16,
        ).astype(np.float32)
        / 32768.0
    )


def blocks_rms(
    blocks: list[bytes] | deque[bytes],
) -> float:
    if not blocks:
        return 0.0

    samples = pcm_to_float(
        b"".join(blocks)
    )

    if samples.size == 0:
        return 0.0

    return float(
        np.sqrt(
            np.mean(samples * samples)
        )
    )


def save_wav(
    path: Path,
    blocks: list[bytes],
) -> float:
    audio = b"".join(blocks)
    samples = pcm_to_float(audio)

    sf.write(
        str(path),
        samples,
        SAMPLE_RATE,
        subtype="PCM_16",
    )

    return len(samples) / SAMPLE_RATE


def first_seconds(
    blocks: list[bytes],
    seconds: float,
) -> list[bytes]:
    wanted_samples = int(
        seconds * SAMPLE_RATE
    )

    result: list[bytes] = []
    total = 0

    for block in blocks:
        result.append(block)
        total += pcm_sample_count(block)

        if total >= wanted_samples:
            break

    return result


@dataclass
class Phrase:
    phrase_id: int

    blocks: list[bytes] = field(
        default_factory=list
    )

    outstanding_checks: int = 0

    finished: bool = False
    wake_detected: bool = False
    wake_text: str = ""
    saved: bool = False

    last_check_samples: int = 0

    # Largest prefix duration that has already been submitted.
    last_submitted_prefix_samples: int = 0

    # Once the maximum prefix has been submitted, periodic
    # wake checking for this phrase is permanently finished.
    max_prefix_submitted: bool = False


@dataclass
class WakeJob:
    phrase_id: int
    blocks: list[bytes]
    is_final: bool


@dataclass
class WakeResult:
    phrase_id: int
    is_final: bool
    text: str
    language: str
    elapsed: float
    error: str = ""


class AuroraDiagnostic:
    def __init__(
        self,
        device: int,
    ):
        self.device = device

        self.audio_queue: queue.Queue[bytes] = (
            queue.Queue(maxsize=200)
        )

        self.wake_queue: queue.Queue[WakeJob] = (
            queue.Queue(maxsize=8)
        )

        self.result_queue: queue.Queue[WakeResult] = (
            queue.Queue()
        )

        self.stop_event = threading.Event()

        self.whisper = WhisperSttEngine(
            model_name="large-v3",
            device="cuda",
            compute_type="float16",
            beam_size=1,
        )

        self.vad = webrtcvad.Vad(1)

        self.pre_roll: deque[bytes] = deque()

        self.start_votes: deque[bool] = deque(
            maxlen=START_WINDOW_BLOCKS
        )

        self.phrases: dict[int, Phrase] = {}

        self.next_phrase_id = 1
        self.active_phrase_id: int | None = None

        self.silence_samples = 0

        self.actual_callback_samples: int | None = None

    def microphone_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):
        if status:
            print(f"[MIC] {status}")

        block = bytes(indata)

        actual_samples = pcm_sample_count(
            block
        )

        if self.actual_callback_samples is None:
            self.actual_callback_samples = (
                actual_samples
            )

            print(
                "[MIC FORMAT] "
                f"requested_frames="
                f"{REQUESTED_BLOCK_SAMPLES} "
                f"callback_frames={frames} "
                f"pcm_samples={actual_samples} "
                f"duration="
                f"{actual_samples / SAMPLE_RATE:.3f}s"
            )

        try:
            self.audio_queue.put_nowait(
                block
            )

        except queue.Full:
            print(
                "[MIC] Audio queue full; "
                "block dropped"
            )

    def block_speech_ratio(
        self,
        block: bytes,
    ) -> float:
        frame_samples = (
            SAMPLE_RATE
            * VAD_FRAME_MS
            // 1000
        )

        frame_bytes = frame_samples * 2

        votes = 0
        frames = 0

        for offset in range(
            0,
            len(block),
            frame_bytes,
        ):
            frame = block[
                offset:offset + frame_bytes
            ]

            if len(frame) != frame_bytes:
                continue

            frames += 1

            if self.vad.is_speech(
                frame,
                SAMPLE_RATE,
            ):
                votes += 1

        if frames == 0:
            return 0.0

        return votes / frames

    def block_contains_speech(
        self,
        block: bytes,
    ) -> tuple[bool, float]:
        ratio = self.block_speech_ratio(
            block
        )

        return (
            ratio >= VAD_BLOCK_MIN_RATIO,
            ratio,
        )

    def trim_pre_roll(self):
        max_samples = int(
            PRE_ROLL_SECONDS
            * SAMPLE_RATE
        )

        while (
            len(self.pre_roll) > 1
            and blocks_sample_count(
                self.pre_roll
            ) > max_samples
        ):
            self.pre_roll.popleft()

    def update_pre_roll(
        self,
        block: bytes,
    ):
        self.pre_roll.append(block)
        self.trim_pre_roll()

    def submit_wake_check(
        self,
        phrase: Phrase,
        blocks: list[bytes],
        is_final: bool,
    ) -> bool:
        if phrase.wake_detected:
            return False

        job = WakeJob(
            phrase_id=phrase.phrase_id,
            blocks=list(blocks),
            is_final=is_final,
        )

        try:
            if is_final:
                self.wake_queue.put(
                    job,
                    timeout=2.0,
                )
            else:
                self.wake_queue.put_nowait(
                    job
                )

        except queue.Full:
            print(
                f"[WAKE] phrase="
                f"{phrase.phrase_id} "
                f"final={is_final} "
                "queue full"
            )
            return False

        phrase.outstanding_checks += 1
        return True

    def wake_worker(self):
        while not self.stop_event.is_set():
            try:
                job = self.wake_queue.get(
                    timeout=0.2
                )

            except queue.Empty:
                continue

            temp_path = (
                OUTPUT_DIR
                / (
                    f"_wake_{job.phrase_id}_"
                    f"{time.monotonic_ns()}.wav"
                )
            )

            started = time.perf_counter()

            try:
                save_wav(
                    temp_path,
                    job.blocks,
                )

                result = (
                    self.whisper.transcribe_file(
                        temp_path,
                        language=None,
                    )
                )

                self.result_queue.put(
                    WakeResult(
                        phrase_id=job.phrase_id,
                        is_final=job.is_final,
                        text=result.text,
                        language=result.language,
                        elapsed=(
                            time.perf_counter()
                            - started
                        ),
                    )
                )

            except Exception as exc:
                self.result_queue.put(
                    WakeResult(
                        phrase_id=job.phrase_id,
                        is_final=job.is_final,
                        text="",
                        language="",
                        elapsed=(
                            time.perf_counter()
                            - started
                        ),
                        error=(
                            f"{type(exc).__name__}: "
                            f"{exc}"
                        ),
                    )
                )

            finally:
                try:
                    temp_path.unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass

                self.wake_queue.task_done()

    def save_confirmed_phrase(
        self,
        phrase: Phrase,
    ):
        if (
            phrase.saved
            or not phrase.finished
        ):
            return

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        path = (
            OUTPUT_DIR
            / f"command_full_{timestamp}.wav"
        )

        ram_duration = blocks_duration(
            phrase.blocks
        )

        wav_duration = save_wav(
            path,
            phrase.blocks,
        )

        phrase.saved = True

        print(
            f"[CAPTURE] Saved: {path}"
        )

        print(
            "[DURATION] "
            f"RAM={ram_duration:.2f}s "
            f"WAV={wav_duration:.2f}s "
            f"samples="
            f"{blocks_sample_count(phrase.blocks)}"
        )

        print(
            f"[FULL RMS] "
            f"{blocks_rms(phrase.blocks):.4f}"
        )

        print(
            f"[WAKE TEXT] "
            f"{phrase.wake_text!r}"
        )

        print(
            "[READY FOR STT] "
            "Full phrase saved. "
            "No action executed."
        )

    def process_wake_results(self):
        while True:
            try:
                result = (
                    self.result_queue
                    .get_nowait()
                )

            except queue.Empty:
                break

            phrase = self.phrases.get(
                result.phrase_id
            )

            if phrase is None:
                self.result_queue.task_done()
                continue

            phrase.outstanding_checks = max(
                0,
                phrase.outstanding_checks - 1,
            )

            if result.error:
                print(
                    f"[WAKE ERROR] "
                    f"phrase={result.phrase_id} "
                    f"final={result.is_final} "
                    f"{result.error}"
                )

            else:
                detected = contains_wake(
                    result.text
                )

                print(
                    f"[WAKE ASR] "
                    f"phrase={result.phrase_id} "
                    f"final={result.is_final} "
                    f"text={result.text!r} "
                    f"language={result.language} "
                    f"elapsed={result.elapsed:.2f}s "
                    f"wake={detected}"
                )

                if (
                    detected
                    and not phrase.wake_detected
                ):
                    phrase.wake_detected = True
                    phrase.wake_text = (
                        result.text
                    )

                    print(
                        "*** AURORA DETECTED — "
                        "KEEP FULL PHRASE ***"
                    )

                if (
                    phrase.wake_detected
                    and phrase.finished
                ):
                    self.save_confirmed_phrase(
                        phrase
                    )

            if (
                phrase.finished
                and phrase.outstanding_checks == 0
            ):
                if not phrase.wake_detected:
                    print(
                        f"[DISCARD] "
                        f"Phrase "
                        f"{phrase.phrase_id}: "
                        "wake not confirmed"
                    )

                del self.phrases[
                    phrase.phrase_id
                ]

            self.result_queue.task_done()

    def start_phrase(self):
        phrase_id = self.next_phrase_id
        self.next_phrase_id += 1

        initial_blocks = list(
            self.pre_roll
        )

        phrase = Phrase(
            phrase_id=phrase_id,
            blocks=initial_blocks,
        )

        self.phrases[
            phrase_id
        ] = phrase

        self.active_phrase_id = (
            phrase_id
        )

        self.silence_samples = 0
        self.start_votes.clear()

        print(
            f"[VAD] Candidate started: "
            f"phrase={phrase_id} "
            f"preroll="
            f"{blocks_duration(initial_blocks):.2f}s "
            f"rms="
            f"{blocks_rms(initial_blocks):.4f}"
        )

    def maybe_check_wake(
        self,
        phrase: Phrase,
    ):
        if phrase.wake_detected:
            return

        if phrase.max_prefix_submitted:
            return

        total_samples = blocks_sample_count(
            phrase.blocks
        )

        total_seconds = (
            total_samples / SAMPLE_RATE
        )

        if (
            total_seconds
            < MIN_WAKE_AUDIO_SECONDS
        ):
            return

        interval_samples = int(
            WAKE_CHECK_INTERVAL_SECONDS
            * SAMPLE_RATE
        )

        if (
            total_samples
            - phrase.last_check_samples
            < interval_samples
        ):
            return

        phrase.last_check_samples = (
            total_samples
        )

        max_prefix_samples = int(
            MAX_WAKE_PREFIX_SECONDS
            * SAMPLE_RATE
        )

        prefix_samples = min(
            total_samples,
            max_prefix_samples,
        )

        # Never submit the same prefix twice.
        if (
            prefix_samples
            <= phrase.last_submitted_prefix_samples
        ):
            return

        prefix_seconds = (
            prefix_samples / SAMPLE_RATE
        )

        prefix = first_seconds(
            phrase.blocks,
            prefix_seconds,
        )

        rms = blocks_rms(
            prefix
        )

        if rms < WAKE_RMS_THRESHOLD:
            print(
                f"[WAKE SKIP] "
                f"phrase={phrase.phrase_id} "
                f"prefix="
                f"{blocks_duration(prefix):.2f}s "
                f"rms={rms:.4f}"
            )

            # Mark this prefix as considered even when skipped,
            # otherwise the same low-energy prefix could be
            # reconsidered repeatedly.
            phrase.last_submitted_prefix_samples = (
                prefix_samples
            )

            if (
                prefix_samples
                >= max_prefix_samples
            ):
                phrase.max_prefix_submitted = True

            return

        if self.submit_wake_check(
            phrase,
            prefix,
            is_final=False,
        ):
            phrase.last_submitted_prefix_samples = (
                prefix_samples
            )

            if (
                prefix_samples
                >= max_prefix_samples
            ):
                phrase.max_prefix_submitted = True

            print(
                f"[WAKE CHECK] "
                f"phrase={phrase.phrase_id} "
                f"prefix="
                f"{blocks_duration(prefix):.2f}s "
                f"rms={rms:.4f}"
            )

    def finish_phrase(
        self,
        reason: str,
    ):
        phrase_id = (
            self.active_phrase_id
        )

        if phrase_id is None:
            return

        phrase = self.phrases[
            phrase_id
        ]

        phrase.finished = True

        self.active_phrase_id = None
        self.silence_samples = 0
        self.start_votes.clear()

        duration = blocks_duration(
            phrase.blocks
        )

        rms = blocks_rms(
            phrase.blocks
        )

        print(
            f"[VAD] Candidate ended: "
            f"phrase={phrase_id} "
            f"duration={duration:.2f}s "
            f"rms={rms:.4f} "
            f"reason={reason}"
        )

        if duration < MIN_PHRASE_SECONDS:
            if (
                phrase.outstanding_checks
                == 0
            ):
                print(
                    f"[DISCARD] Phrase "
                    f"{phrase_id}: "
                    "too short"
                )

                del self.phrases[
                    phrase_id
                ]

            self.pre_roll.clear()
            return

        if phrase.wake_detected:
            self.save_confirmed_phrase(
                phrase
            )

        else:
            max_prefix_samples = int(
                MAX_WAKE_PREFIX_SECONDS
                * SAMPLE_RATE
            )

            available_prefix_samples = min(
                blocks_sample_count(
                    phrase.blocks
                ),
                max_prefix_samples,
            )

            # Submit a final prefix only when it contains audio
            # that has NOT already been submitted.
            need_final_check = (
                available_prefix_samples
                > phrase.last_submitted_prefix_samples
            )

            if need_final_check:
                final_seconds = (
                    available_prefix_samples
                    / SAMPLE_RATE
                )

                final_prefix = first_seconds(
                    phrase.blocks,
                    final_seconds,
                )

                submitted = (
                    self.submit_wake_check(
                        phrase,
                        final_prefix,
                        is_final=True,
                    )
                )

                if submitted:
                    phrase.last_submitted_prefix_samples = (
                        available_prefix_samples
                    )

                    print(
                        f"[FINAL CHECK] "
                        f"phrase={phrase_id} "
                        f"prefix="
                        f"{blocks_duration(final_prefix):.2f}s"
                    )

            elif (
                phrase.outstanding_checks == 0
            ):
                print(
                    f"[DISCARD] Phrase "
                    f"{phrase_id}: "
                    "wake not confirmed"
                )

                del self.phrases[
                    phrase_id
                ]

        self.pre_roll.clear()

    def process_audio_block(
        self,
        block: bytes,
    ):
        self.process_wake_results()

        voiced, speech_ratio = (
            self.block_contains_speech(
                block
            )
        )

        block_samples = (
            pcm_sample_count(block)
        )

        if self.active_phrase_id is None:
            self.update_pre_roll(
                block
            )

            self.start_votes.append(
                voiced
            )

            should_start = (
                len(self.start_votes)
                == START_WINDOW_BLOCKS
                and sum(self.start_votes)
                >= START_REQUIRED_VOICED
            )

            if not should_start:
                return

            print(
                "[VAD ONSET] "
                f"speech_ratio="
                f"{speech_ratio:.2f} "
                f"votes="
                f"{sum(self.start_votes)}/"
                f"{START_WINDOW_BLOCKS}"
            )

            # Current block is already inside pre_roll.
            self.start_phrase()

            phrase = self.phrases[
                self.active_phrase_id
            ]

        else:
            phrase = self.phrases[
                self.active_phrase_id
            ]

            phrase.blocks.append(
                block
            )

        if voiced:
            self.silence_samples = 0
        else:
            self.silence_samples += (
                block_samples
            )

        if not phrase.wake_detected:
            self.maybe_check_wake(
                phrase
            )

        silence_seconds = (
            self.silence_samples
            / SAMPLE_RATE
        )

        phrase_seconds = blocks_duration(
            phrase.blocks
        )

        if (
            silence_seconds
            >= END_SILENCE_SECONDS
        ):
            self.finish_phrase(
                "vad_end"
            )

        elif (
            phrase_seconds
            >= MAX_PHRASE_SECONDS
        ):
            self.finish_phrase(
                "max_duration"
            )

    def run(self):
        OUTPUT_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        print(
            "Loading Whisper large-v3 on GPU..."
        )

        worker = threading.Thread(
            target=self.wake_worker,
            name="aurora-wake-worker",
            daemon=True,
        )

        worker.start()

        print(
            f"Microphone: device {self.device}"
        )

        print(
            "Continuous mic + 1.2s ring buffer."
        )

        print(
            "VAD creates candidates."
        )

        print(
            "Wake checks: growing prefix "
            "1.5s -> 2.0s -> 2.5s -> "
            "3.0s -> 3.5s -> 4.0s."
        )

        print(
            "Each prefix is submitted at most once."
        )

        print(
            "After 4.0s there are NO repeated "
            "periodic wake checks."
        )

        print(
            "Say naturally: "
            "'Аурора, намали звука'."
        )

        print(
            "No commands will be executed."
        )

        print(
            "Ctrl+C to stop."
        )

        try:
            with sd.RawInputStream(
                device=self.device,
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=(
                    REQUESTED_BLOCK_SAMPLES
                ),
                callback=(
                    self.microphone_callback
                ),
            ):
                while (
                    not self.stop_event.is_set()
                ):
                    try:
                        block = (
                            self.audio_queue.get(
                                timeout=0.1
                            )
                        )

                    except queue.Empty:
                        self.process_wake_results()
                        continue

                    try:
                        self.process_audio_block(
                            block
                        )

                    finally:
                        self.audio_queue.task_done()

        except KeyboardInterrupt:
            print(
                "\nStopping..."
            )

        finally:
            self.stop_event.set()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--device",
        type=int,
        default=1,
    )

    args = parser.parse_args()

    AuroraDiagnostic(
        device=args.device,
    ).run()


if __name__ == "__main__":
    main()