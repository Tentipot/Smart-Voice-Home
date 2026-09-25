"""Run the fixed STT diagnostic route over accepted pilot_01 recordings.

This runner reports measurements only. It does not parse or execute commands.
"""

import argparse
import json
import os
import time
import hashlib
import gc
import subprocess
import unicodedata
from datetime import datetime, timezone
from dataclasses import asdict
from pathlib import Path

import torch

from app.resources.ctranslate2_model_lifecycle import CTranslate2ModelLifecycle
from app.resources.model_manager import ModelManager
from app.resources.model_types import ModelBackend, ModelDescriptor, ModelId
from app.resources.pytorch_model_lifecycle import PyTorchModelLifecycle
from app.speech.stt.buzzasr_engine import BuzzAsrSttEngine
from app.speech.stt.ctc_evidence_provider import CtcLanguageEvidenceProvider
from app.speech.stt.language_resolver import LanguageResolver
from app.speech.stt.router import SttRouter
from app.speech.stt.service import SttService
from app.speech.stt.whisper_engine import WhisperSttEngine
from app.resources.system_monitor import get_gpu_status
from diagnose_captured_phrase_stt import TimedEvidenceProvider, TimedResolver, TimedRouter, synchronize


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "data" / "stt_validation" / "pilot_01"
DEFAULT_OUTPUT = ROOT / "docs" / ("STT_VALIDATION_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".jsonl")


def word_errors(reference, hypothesis):
    def words(text):
        text = unicodedata.normalize("NFC", text).lower()
        return "".join(c for c in text if not unicodedata.category(c).startswith("P")).split()
    a, b = words(reference), words(hypothesis)
    if not a:
        raise ValueError("Empty reference")
    row = list(range(len(b) + 1))
    for i, word in enumerate(a, 1):
        new = [i]
        for j, other in enumerate(b, 1):
            new.append(min(new[-1] + 1, row[j] + 1, row[j-1] + (word != other)))
        row = new
    return {"errors": row[-1], "reference_words": len(a), "wer": row[-1] / len(a)}


def accepted_cases(data_root: Path):
    attempts = {}
    captured = {}
    accepted = {}
    for manifest in sorted(data_root.rglob("manifest.jsonl")):
        for line in manifest.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            attempt_id = event.get("attempt_id")
            if event.get("event") == "attempt":
                attempts[attempt_id] = event
            elif event.get("event") == "captured":
                captured[attempt_id] = ((manifest.parent / event["filename"]).resolve(), event)
            elif event.get("event") == "review":
                accepted[attempt_id] = event

    cases = []
    for attempt_id, review in accepted.items():
        if review.get("status") != "accepted":
            continue
        if attempt_id not in captured or attempt_id not in attempts:
            raise ValueError(f"Incomplete attempt: {attempt_id}")
        audio, capture = captured[attempt_id]
        if not audio.is_relative_to(data_root.resolve()) or not audio.is_file():
            raise FileNotFoundError(f"accepted attempt has no WAV: {attempt_id}")
        digest = hashlib.sha256(audio.read_bytes()).hexdigest()
        if digest != capture["sha256"]:
            raise ValueError(f"SHA256 mismatch: {audio}")
        attempt = attempts.get(attempt_id, {})
        if not review.get("reference_text", "").strip():
            raise ValueError(f"Missing reference: {attempt_id}")
        cases.append({"attempt_id": attempt_id, "audio": audio, "sha256": digest, **attempt, **review})
    ids = [case["prompt_id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Multiple accepted recordings for a prompt; select before evaluation")
    return sorted(cases, key=lambda item: item["prompt_id"])


def build_service(manager, handles, loads):
    manager.register(
        descriptor=ModelDescriptor(model_id=ModelId.BUZZ_BG, backend=ModelBackend.PYTORCH, estimated_vram_mb=3323),
        factory=lambda: BuzzAsrSttEngine(
            model_name=os.getenv(
                "SMART_VOICE_BUZZASR_MODEL",
                str(ROOT / "models" / "buzzasr-bulgarian"),
            ),
        ), lifecycle=PyTorchModelLifecycle(),
    )
    manager.register(
        descriptor=ModelDescriptor(model_id=ModelId.WHISPER_LARGE_V3, backend=ModelBackend.CTRANSLATE2, estimated_vram_mb=3913),
        factory=lambda: WhisperSttEngine(
            model_name=os.getenv("SMART_VOICE_WHISPER_MODEL", str(ROOT / "models" / "faster-whisper-large-v3")),
            compute_type="int8_float16",
        ),
        lifecycle=CTranslate2ModelLifecycle(),
    )
    manager.register(
        descriptor=ModelDescriptor(model_id=ModelId.CTC_LANGUAGE, backend=ModelBackend.PYTORCH, estimated_vram_mb=0),
        factory=lambda: CtcLanguageEvidenceProvider(
            bg_model_name=os.getenv("SMART_VOICE_CTC_BG_MODEL", str(ROOT / "models" / "wav2vec2-bg")),
            en_model_name=os.getenv("SMART_VOICE_CTC_EN_MODEL", str(ROOT / "models" / "wav2vec2-en")),
            device="cpu", dtype=torch.float32,
        ),
        lifecycle=PyTorchModelLifecycle(),
    )
    for model_id in (
        ModelId.WHISPER_LARGE_V3, ModelId.BUZZ_BG, ModelId.CTC_LANGUAGE
    ):
        start = time.perf_counter()
        handles[model_id] = manager.acquire(model_id)
        synchronize()
        loads.append({"model": model_id.value, "seconds": time.perf_counter() - start, "gpu": get_gpu_status()})
    evidence = TimedEvidenceProvider(handles[ModelId.CTC_LANGUAGE].resource)
    resolver = TimedResolver(LanguageResolver())
    router = TimedRouter(SttRouter(
        bulgarian_engine=handles[ModelId.BUZZ_BG].resource,
        english_engine=handles[ModelId.WHISPER_LARGE_V3].resource,
        mixed_engine=handles[ModelId.WHISPER_LARGE_V3].resource,
    ))
    return SttService(evidence_provider=evidence, language_resolver=resolver, router=router), (evidence, resolver, router)


def run_case(case, service, probes):
    evidence, resolver, router = probes
    synchronize()
    started = time.perf_counter()
    result = service.transcribe_file(case["audio"])
    synchronize()
    elapsed = time.perf_counter() - started
    return {
        "attempt_id": case["attempt_id"],
        "sha256": case["sha256"],
        "status": "ok",
        "ctc": asdict(evidence.last_evidence),
        "entropy_delta": evidence.last_evidence.entropy_delta,
        "route": resolver.last_resolution.policy.mode.value,
        "resolution_reason": resolver.last_resolution.reason,
        "timings": {"ctc": evidence.last_seconds, "resolver": resolver.last_seconds, "stt": router.last_seconds},
        "gpu_after": get_gpu_status(),
        "word_error": word_errors(case["reference_text"], result.text),
        "semantic_review": "pending_manual_review",
        "prompt_id": case["prompt_id"],
        "speech_label": case["speech_label"],
        "reference_text": case["reference_text"],
        "audio": str(case["audio"].relative_to(ROOT)),
        "engine": result.engine,
        "model": result.model,
        "language": result.language,
        "language_confidence": result.language_confidence,
        "text": result.text,
        "metadata": result.metadata,
        "elapsed_seconds": elapsed,
    }


def main():
    parser = argparse.ArgumentParser(description="Run fixed STT validation over accepted pilot_01 WAV files.")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for a smoke run; 0 means all accepted cases.")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be nonnegative")
    cases = accepted_cases(args.data_root)
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        raise RuntimeError("No accepted validation cases found.")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; fixed pilot configuration requires GPU STT.")

    # Fail locally rather than contacting a hub if any model is missing.
    for env, folder in (("BUZZASR", "buzzasr-bulgarian"), ("CTC_BG", "wav2vec2-bg"), ("CTC_EN", "wav2vec2-en"), ("WHISPER", "faster-whisper-large-v3")):
        path = Path(os.getenv(f"SMART_VOICE_{env}_MODEL", str(ROOT / "models" / folder))).resolve()
        if not path.is_dir():
            raise FileNotFoundError(f"Local model required: {path}")
        os.environ[f"SMART_VOICE_{env}_MODEL"] = str(path)
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation and preflight happen BEFORE loading GPU models.
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        manager, handles, loads = ModelManager(), {}, []
        service, probes = None, None
        completed = failed = 0
        def emit(record):
            stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            stream.flush()
        emit({"event": "start", "gpu": get_gpu_status(), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(), "planned": len(cases), "thresholds": [LanguageResolver.CTC_BG_BOUNDARY, LanguageResolver.CTC_EN_BOUNDARY]})
        try:
            service, probes = build_service(manager, handles, loads)
            emit({"event": "loaded", "models": loads})
            for index, case in enumerate(cases, 1):
                print(f"[{index}/{len(cases)}] {case['prompt_id']}: {case['audio'].name}", flush=True)
                try:
                    record = run_case(case, service, probes)
                    completed += 1
                except Exception as exc:
                    failed += 1
                    record = {"prompt_id": case["prompt_id"], "status": "error", "error": repr(exc), "sha256": case["sha256"]}
                emit({"event": "case", "first_inference": index == 1, **record})
        finally:
            service = probes = None
            for handle in handles.values():
                handle.release()
            handles.clear()
            cleanup_errors = []
            for model_id in (ModelId.CTC_LANGUAGE, ModelId.BUZZ_BG, ModelId.WHISPER_LARGE_V3):
                try:
                    manager.unload(model_id)
                except Exception as exc:
                    cleanup_errors.append(repr(exc))
            gc.collect()
            torch.cuda.empty_cache()
            emit({"event": "end", "completed": completed, "failed": failed, "gpu": get_gpu_status(), "cleanup_errors": cleanup_errors})
            print(f"Completed {completed}; failed {failed}; planned {len(cases)}", flush=True)
    if failed or cleanup_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
