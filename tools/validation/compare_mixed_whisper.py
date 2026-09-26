"""Diagnostic paired comparison only; never executes assistant actions."""
import argparse
import gc
import hashlib
import importlib.metadata
import json
import os
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from tools.validation.run_stt_validation import ROOT, DEFAULT_DATA, accepted_cases, word_errors
from app.speech.stt.whisper_engine import WhisperSttEngine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, default=ROOT / 'docs/STT_VALIDATION_PILOT_01_DIAGNOSTICS.jsonl')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=['auto', 'bg', 'en', 'multilingual'], default='auto')
    args = parser.parse_args()
    cases = [c for c in accepted_cases(DEFAULT_DATA) if c['speech_label'] == 'MIXED']
    if {c['prompt_id'] for c in cases} != {f'MX{i:02}' for i in range(1, 9)}:
        raise ValueError('Expected exactly MX01–MX08')
    baseline = {}
    for line in args.baseline.read_text(encoding='utf-8').splitlines():
        record = json.loads(line)
        if record.get('event') == 'case':
            if record['prompt_id'] in baseline:
                raise ValueError('Duplicate baseline ID')
            baseline[record['prompt_id']] = record
    for case in cases:
        previous = baseline[case['prompt_id']]
        if previous['status'] != 'ok' or any(previous[k] != case[k] for k in ('sha256', 'attempt_id', 'reference_text')):
            raise ValueError('Baseline/input mismatch: ' + case['prompt_id'])
    model = Path(os.getenv('SMART_VOICE_WHISPER_MODEL', str(ROOT / 'models/faster-whisper-large-v3'))).resolve()
    if not (model / 'model.bin').is_file():
        raise FileNotFoundError(model)
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    engine = None
    completed = failed = 0
    with args.output.open('x', encoding='utf-8') as out:
        def emit(record):
            out.write(json.dumps(record, ensure_ascii=False) + '\n')
            out.flush()
        emit({'event': 'start', 'utc': datetime.now(timezone.utc).isoformat(),
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'diff': subprocess.check_output(['git', 'diff'], cwd=ROOT, encoding='utf-8'),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest(),
              'versions': {p: importlib.metadata.version(p) for p in ('faster-whisper', 'ctranslate2', 'torch', 'transformers')},
              'model': str(model), 'compute_type': 'int8_float16', 'beam_size': 5,
              'mode': args.mode, 'requested_language': args.mode if args.mode in ('bg', 'en') else None, 'offline': True,
              'limitation': 'Only Whisper resident; compare STT timing, not full service latency'})
        try:
            engine = WhisperSttEngine(model_name=str(model), compute_type='int8_float16', beam_size=5)
            emit({'event': 'loaded', 'seconds': engine.load_seconds})
            for index, case in enumerate(cases):
                old = baseline[case['prompt_id']]
                print(case['prompt_id'], flush=True)
                row = {k: case[k] for k in ('prompt_id', 'sha256', 'attempt_id', 'reference_text')}
                row.update(event='case', baseline_text=old['text'], baseline_route=old['route'],
                           baseline_wer=old['word_error'], baseline_stt_seconds=old['timings']['stt'], first_inference=index == 0)
                try:
                    # Diagnostic-only access: production engine behavior stays unchanged.
                    start = time.perf_counter()
                    segments, info = engine._model.transcribe(
                        str(case['audio']), language=args.mode if args.mode in ('bg', 'en') else None,
                        multilingual=args.mode == 'multilingual', task='transcribe', beam_size=5,
                        temperature=0.0, condition_on_previous_text=False, vad_filter=False,
                    )
                    segments = list(segments)
                    elapsed = time.perf_counter() - start
                    text = ' '.join(s.text.strip() for s in segments if s.text.strip()).strip()
                    row.update(status='ok', mode=args.mode, text=text, language=info.language,
                               language_confidence=info.language_probability, stt_seconds=elapsed,
                               segments=[{'start': s.start, 'end': s.end, 'text': s.text} for s in segments],
                               word_error=word_errors(case['reference_text'], text))
                    completed += 1
                except Exception as exc:
                    row.update(status='error', error=repr(exc))
                    failed += 1
                emit(row)
        finally:
            engine = None
            gc.collect()
            emit({'event': 'end', 'completed': completed, 'failed': failed})
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
