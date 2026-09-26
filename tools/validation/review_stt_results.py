"""Replay saved STT text through semantic review, without models or audio IO."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from app.commands.semantic_review import SemanticReviewer


def load_cases(path: Path):
    cases = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if row.get('event') != 'case':
            continue
        if row.get('status') != 'ok':
            raise ValueError(f'Failed input case in {path}')
        key = row['prompt_id']
        if key in cases or not row.get('sha256') or not isinstance(row.get('text'), str):
            raise ValueError(f'Invalid/duplicate case: {key}')
        cases[key] = row
    if not cases:
        raise ValueError(f'No cases in {path}')
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--alternatives', type=Path, nargs='*', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    paths = [args.input, *args.alternatives]
    baseline, *alternatives = [load_cases(p) for p in paths]
    for collection in alternatives:
        for key, row in collection.items():
            if key not in baseline or any(row.get(field) != baseline[key].get(field)
                                          for field in ('sha256', 'attempt_id', 'reference_text')):
                raise ValueError(f'Alternative audio/reference mismatch: {key}')
    reviewer = SemanticReviewer()
    # Exclusive output; original diagnostic artifacts remain untouched.
    with args.output.open('x', encoding='utf-8') as out:
        def emit(row):
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
        emit({'event': 'start', 'schema_version': 1,
              'reviewer_sha256': hashlib.sha256(Path('app/commands/semantic_review.py').read_bytes()).hexdigest(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'inputs': [{'path': str(p), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in paths],
              'limitation': 'Text grammar review, not acoustic accuracy or execution approval'})
        for key, row in baseline.items():
            source_paths = [str(p) for p, collection in zip(args.alternatives, alternatives)
                            if key in collection]
            texts = tuple(c[key]['text'] for c in alternatives if key in c)
            emit({'event': 'case', 'prompt_id': key, 'sha256': row['sha256'],
                  'alternative_sources': source_paths,
                  'review': asdict(reviewer.review(row['text'], alternatives=texts))})
        emit({'event': 'end', 'completed': len(baseline)})
    print(f'Reviewed {len(baseline)} saved transcripts')


if __name__ == '__main__':
    main()
