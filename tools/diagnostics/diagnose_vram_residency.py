"""VRAM residency diagnostic for the live STT latency question.

Replays accepted pilot_01 WAV files through the production STT runtime in
three phases, without a microphone and without assistant actions:

  A  production runtime only (Buzz GPU, Whisper int8_float16 GPU, CTC CPU)
  B  A + a second Whisper large-v3 float16 instance configured exactly like
     AuroraCapture's wake model (app/speech/capture/aurora_capture.py), idle
  C  B + concurrent wake-style transcriptions on 1.5-4.0 s prefixes, as the
     live wake worker does while production STT runs

Measures per-command STT time, NVML dedicated VRAM (100 ms samples) and the
Windows "GPU Process Memory" dedicated/shared usage of this process. Shared
usage growth means VRAM spilled into system RAM.

Side effects: loads models onto the GPU, writes temporary prefix WAVs to the
system temp directory, writes one JSONL report (exclusive create).

Run from the repository root:
    .\\.venv\\Scripts\\python.exe -B -m tools.diagnostics.diagnose_vram_residency
"""

import argparse
import json
import os
import subprocess
import tempfile
import threading
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

from app.resources.model_types import ModelId
from app.resources.system_monitor import get_gpu_status
from app.speech.stt.composition import create_stt_runtime
from app.speech.stt.whisper_engine import WhisperSttEngine


ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "stt_validation" / "pilot_01"
WAKE_PREFIXES = (1.5, 2.0, 2.5, 3.0, 3.5, 4.0)
DEFAULT_PROMPTS = ("BG01", "BG03", "BG05", "EN01", "EN03", "EN05", "MX01", "MX03")


def first_accepted_cases(data_root: Path) -> dict[str, dict]:
    """Return the earliest accepted recording per prompt_id."""
    cases: dict[str, dict] = {}

    for manifest in sorted(data_root.rglob("manifest.jsonl")):
        attempts, captured = {}, {}

        for line in manifest.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            attempt_id = event.get("attempt_id")

            if event.get("event") == "attempt":
                attempts[attempt_id] = event
            elif event.get("event") == "captured":
                captured[attempt_id] = manifest.parent / event["filename"]
            elif (
                event.get("event") == "review"
                and event.get("status") == "accepted"
                and attempt_id in captured
            ):
                prompt_id = attempts[attempt_id]["prompt_id"]
                cases.setdefault(
                    prompt_id,
                    {
                        "prompt_id": prompt_id,
                        "audio": captured[attempt_id],
                        "reference_text": event.get("reference_text", ""),
                    },
                )

    return cases


def write_prefix(source: Path, seconds: float, target: Path) -> Path:
    with wave.open(str(source), "rb") as reader:
        params = reader.getparams()
        frames = reader.readframes(int(params.framerate * seconds))

    with wave.open(str(target), "wb") as writer:
        writer.setparams(params)
        writer.writeframes(frames)

    return target


def windows_process_gpu_memory(pid: int) -> dict[str, float] | None:
    """Dedicated/shared GPU memory of one process from Windows counters (MB)."""
    script = (
        "$ErrorActionPreference='Stop';"
        f"$c=Get-Counter '\\GPU Process Memory(pid_{pid}_*)\\Dedicated Usage',"
        f"'\\GPU Process Memory(pid_{pid}_*)\\Shared Usage';"
        "$d=($c.CounterSamples|?{$_.Path -like '*dedicated usage'}|Measure-Object CookedValue -Sum).Sum;"
        "$s=($c.CounterSamples|?{$_.Path -like '*shared usage'}|Measure-Object CookedValue -Sum).Sum;"
        "Write-Output \"$d $s\""
    )

    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=15,
        )
        dedicated, shared = completed.stdout.split()
        return {
            "dedicated_mb": float(dedicated) / 2**20,
            "shared_mb": float(shared) / 2**20,
        }
    except (ValueError, subprocess.SubprocessError, OSError):
        return None


class NvmlSampler:
    """Background NVML sampler; tracks peak dedicated VRAM per window."""

    def __init__(self, interval: float = 0.1) -> None:
        self.interval = interval
        self.peak_mb = 0
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            gpu = get_gpu_status()
            if gpu.get("available"):
                with self._lock:
                    self.peak_mb = max(self.peak_mb, gpu["vram_used_mb"])
            self._stop.wait(self.interval)

    def start(self) -> None:
        self._thread.start()

    def take_peak(self) -> int:
        with self._lock:
            peak, self.peak_mb = self.peak_mb, 0
        return peak

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)


class WakeLoad:
    """Continuously runs wake-style prefix transcriptions on another thread."""

    def __init__(self, engine: WhisperSttEngine, prefixes: list[Path]) -> None:
        self.engine = engine
        self.prefixes = prefixes
        self.calls: list[float] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        index = 0
        while not self._stop.is_set():
            started = time.perf_counter()
            self.engine.transcribe_file(
                self.prefixes[index % len(self.prefixes)],
                language=None,
            )
            self.calls.append(time.perf_counter() - started)
            index += 1
            self._stop.wait(0.5)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=30)


def snapshot(label: str, sampler: NvmlSampler) -> dict:
    gpu = get_gpu_status()
    row = {
        "event": "snapshot",
        "label": label,
        "vram_used_mb": gpu.get("vram_used_mb"),
        "vram_total_mb": gpu.get("vram_total_mb"),
        "nvml_peak_mb": sampler.take_peak(),
        "process_gpu_memory": windows_process_gpu_memory(os.getpid()),
    }
    print(
        f"[{label}] VRAM used={row['vram_used_mb']} MB "
        f"peak={row['nvml_peak_mb']} MB "
        f"process={row['process_gpu_memory']}",
        flush=True,
    )
    return row


def run_phase(name: str, service, cases: list[dict], sampler: NvmlSampler) -> list[dict]:
    rows = []
    service.transcribe_with_evidence(cases[0]["audio"])  # warm-up, not counted
    sampler.take_peak()

    for case in cases:
        started = time.perf_counter()
        report = service.transcribe_with_evidence(case["audio"])
        elapsed = time.perf_counter() - started
        row = {
            "event": "command",
            "phase": name,
            "prompt_id": case["prompt_id"],
            "route": report.resolution.policy.mode.value,
            "elapsed_seconds": round(elapsed, 3),
            "stt_inference_seconds": report.result.inference_seconds,
            "nvml_peak_mb": sampler.take_peak(),
            "text": report.result.text,
        }
        print(
            f"  {name} {case['prompt_id']} route={row['route']:<6} "
            f"{elapsed:6.2f} s  peak={row['nvml_peak_mb']} MB",
            flush=True,
        )
        rows.append(row)

    return rows


def summarize(rows: list[dict]) -> dict[str, dict]:
    summary = {}
    for phase in ("A", "B", "C"):
        times = sorted(
            row["elapsed_seconds"]
            for row in rows
            if row.get("event") == "command" and row["phase"] == phase
        )
        if times:
            summary[phase] = {
                "n": len(times),
                "median_seconds": times[len(times) // 2],
                "max_seconds": times[-1],
            }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--prompts", nargs="*", default=list(DEFAULT_PROMPTS))
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / (
            "VRAM_RESIDENCY_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + ".jsonl"
        ),
    )
    args = parser.parse_args()

    available = first_accepted_cases(DATA)
    cases = [available[prompt] for prompt in args.prompts]
    rows: list[dict] = [
        {
            "event": "start",
            "utc": datetime.now(timezone.utc).isoformat(),
            "pid": os.getpid(),
            "prompts": args.prompts,
            "audio": [str(case["audio"].relative_to(ROOT)) for case in cases],
        }
    ]

    sampler = NvmlSampler()
    sampler.start()
    rows.append(snapshot("baseline", sampler))

    runtime = create_stt_runtime()
    manager = runtime.model_manager
    for model_id in (ModelId.CTC_LANGUAGE, ModelId.BUZZ_BG, ModelId.WHISPER_LARGE_V3):
        with manager.acquire(model_id):
            pass
    rows.append(snapshot("production_loaded", sampler))

    print("\nPhase A: production runtime only", flush=True)
    rows += run_phase("A", runtime.service, cases, sampler)
    rows.append(snapshot("after_A", sampler))

    print("\nLoading wake Whisper (large-v3, float16, beam 1) ...", flush=True)
    wake = WhisperSttEngine(
        model_name="large-v3",
        device="cuda",
        compute_type="float16",
        beam_size=1,
    )
    rows.append(snapshot("wake_loaded", sampler))

    print("\nPhase B: + idle wake Whisper", flush=True)
    rows += run_phase("B", runtime.service, cases, sampler)
    rows.append(snapshot("after_B", sampler))

    with tempfile.TemporaryDirectory(prefix="vram_wake_") as temp_dir:
        prefixes = [
            write_prefix(
                case["audio"],
                seconds,
                Path(temp_dir) / f"{case['prompt_id']}_{seconds}.wav",
            )
            for case in cases[:2]
            for seconds in WAKE_PREFIXES
        ]
        load = WakeLoad(wake, prefixes)
        load.start()
        print("\nPhase C: + concurrent wake checks", flush=True)
        try:
            rows += run_phase("C", runtime.service, cases, sampler)
        finally:
            load.stop()
        rows.append(
            {
                "event": "wake_load",
                "calls": len(load.calls),
                "call_seconds": [round(value, 3) for value in load.calls],
            }
        )
        rows.append(snapshot("after_C", sampler))

    sampler.stop()
    summary = summarize(rows)
    rows.append({"event": "summary", **summary})

    with args.output.open("x", encoding="utf-8") as report:
        for row in rows:
            report.write(json.dumps(row, ensure_ascii=False) + "\n")

    print("\n=== SUMMARY ===")
    for phase, values in summary.items():
        print(
            f"{phase}: median {values['median_seconds']:.2f} s, "
            f"max {values['max_seconds']:.2f} s (n={values['n']})"
        )
    print(f"Report: {args.output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
