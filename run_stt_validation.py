"""Run the fixed STT diagnostic route over accepted pilot_01 recordings.

This runner reports measurements only. It does not parse or execute commands.
"""

import argparse
import json
import os
import time
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


ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "data" / "stt_validation" / "pilot_01"
DEFAULT_OUTPUT = ROOT / "reports" / "stt_validation" / "pilot_01_results.jsonl"


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
                captured[attempt_id] = (manifest.parent / event["filename"]).resolve()
            elif event.get("event") == "review" and event.get("status") == "accepted":
                accepted[attempt_id] = event

    cases = []
    for attempt_id, review in accepted.items():
        audio = captured.get(attempt_id)
        if audio is None or not audio.is_file():
            raise FileNotFoundError(f"accepted attempt has no WAV: {attempt_id}")
        attempt = attempts.get(attempt_id, {})
        cases.append({"attempt_id": attempt_id, "audio": audio, **attempt, **review})
    return sorted(cases, key=lambda item: item["prompt_id"])


def build_service(manager):
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
    handles = {model_id: manager.acquire(model_id) for model_id in (
        ModelId.WHISPER_LARGE_V3, ModelId.BUZZ_BG, ModelId.CTC_LANGUAGE
    )}
    evidence = handles[ModelId.CTC_LANGUAGE].resource
    resolver = LanguageResolver()
    router = SttRouter(
        bulgarian_engine=handles[ModelId.BUZZ_BG].resource,
        english_engine=handles[ModelId.WHISPER_LARGE_V3].resource,
        mixed_engine=handles[ModelId.WHISPER_LARGE_V3].resource,
    )
    return SttService(evidence_provider=evidence, language_resolver=resolver, router=router), handles


def run_case(case, service):
    started = time.perf_counter()
    result = service.transcribe_file(case["audio"])
    elapsed = time.perf_counter() - started
    return {
        "attempt_id": case["attempt_id"],
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
    cases = accepted_cases(args.data_root)
    if args.limit:
        cases = cases[:args.limit]
    if not cases:
        raise RuntimeError("No accepted validation cases found.")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; fixed pilot configuration requires GPU STT.")

    manager = ModelManager()
    service, handles = build_service(manager)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("w", encoding="utf-8", newline="\n") as stream:
            for index, case in enumerate(cases, 1):
                print(f"[{index}/{len(cases)}] {case['prompt_id']}: {case['audio'].name}", flush=True)
                record = run_case(case, service)
                stream.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                stream.flush()
    finally:
        for handle in handles.values():
            handle.release()
        for model_id in (ModelId.CTC_LANGUAGE, ModelId.BUZZ_BG, ModelId.WHISPER_LARGE_V3):
            manager.unload(model_id)
        print(f"Wrote {len(cases)} records to {args.output}", flush=True)


if __name__ == "__main__":
    main()
