"""Offline test of wake-word detection by CTC keyword spotting (variant B).

Uses the already loaded BG CTC model (and, as a comparison, the EN CTC model)
to score whether a keyword such as "аурора" occurs in an audio window, instead
of transcribing the window with Whisper.

Score: best CTC alignment of the keyword anywhere in the window (free start
and end), measured as the log-probability deficit against the unconstrained
best path over the same frames, divided by the keyword length. 0 means the
greedy CTC output literally contains the keyword; larger means less likely.

Data (no microphone, no assistant actions):
  positives  data/language_dataset (42), pilot_01 first accepted per prompt
             (24), data/command_capture/wakeword (2), live_stt_diagnostic (1);
             searched only in the first 4.0 s, like the live wake prefix
  negatives  data/stt_benchmark/test_001..080 (commands without the wake word);
             searched over the whole file

Threshold is chosen on a calibration split (language_dataset + even-numbered
negatives) and reported on the held-out split (the rest).

Side effects: loads both CTC models (GPU float16 by default), writes one JSONL
report (exclusive create).

Run from the repository root:
    .\\.venv\\Scripts\\python.exe -B -m tools.diagnostics.diagnose_ctc_wake_kws
"""

import argparse
import json
import os
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")

import numpy as np
import torch
from transformers import AutoModelForCTC, Wav2Vec2FeatureExtractor, Wav2Vec2CTCTokenizer

from tools.diagnostics.diagnose_vram_residency import first_accepted_cases


ROOT = Path(__file__).resolve().parents[2]
BG_MODEL = ROOT / "models" / "wav2vec2-bg"
EN_MODEL = ROOT / "models" / "wav2vec2-en"
POSITIVE_PREFIX_SECONDS = 4.0

BG_KEYWORDS = ("аурора", "орора", "аврора")
EN_KEYWORDS = ("aurora",)


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as reader:
        if (reader.getnchannels(), reader.getsampwidth(), reader.getframerate()) != (1, 2, 16000):
            raise ValueError(f"{path}: expected 16 kHz mono PCM16")
        frames = reader.readframes(reader.getnframes())
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


class CtcScorer:
    def __init__(self, model_dir: Path, device: str, dtype: torch.dtype) -> None:
        self.device, self.dtype = device, dtype
        self.features = Wav2Vec2FeatureExtractor.from_pretrained(model_dir, local_files_only=True)
        self.tokenizer = Wav2Vec2CTCTokenizer.from_pretrained(model_dir, local_files_only=True)
        self.model = AutoModelForCTC.from_pretrained(model_dir, dtype=dtype, local_files_only=True)
        self.model.to(device).eval()
        self.blank = self.tokenizer.pad_token_id

    def log_probs(self, audio: np.ndarray) -> np.ndarray:
        inputs = self.features(audio, sampling_rate=16000, return_tensors="pt")
        values = inputs.input_values.to(device=self.device, dtype=self.dtype)
        with torch.inference_mode():
            logits = self.model(values).logits[0].float()
        return torch.log_softmax(logits, dim=-1).cpu().numpy()

    def token_ids(self, keyword: str) -> list[int]:
        vocab = self.tokenizer.get_vocab()
        return [vocab[char] for char in keyword]


def keyword_deficit(log_probs: np.ndarray, tokens: list[int], blank: int) -> float:
    """Minimum per-token deficit of a CTC keyword alignment with free start/end."""
    deficits = log_probs.max(axis=1, keepdims=True) - log_probs  # >= 0
    labels = [blank]
    for token in tokens:
        labels += [token, blank]
    states = len(labels)
    cost = deficits[:, labels]  # T x S

    best = np.inf
    previous = np.full(states, np.inf)
    for frame in range(cost.shape[0]):
        current = np.full(states, np.inf)
        for state in range(states):
            candidates = [previous[state]]
            if state >= 1:
                candidates.append(previous[state - 1])
            if state >= 2 and labels[state] != blank and labels[state] != labels[state - 2]:
                candidates.append(previous[state - 2])
            if state <= 1:
                candidates.append(0.0)  # free start
            current[state] = min(candidates) + cost[frame, state]
        best = min(best, current[-1], current[-2])  # free end
        previous = current
    return float(best) / len(tokens)


def collect_files() -> list[dict]:
    items: list[dict] = []

    manifest = ROOT / "data" / "language_dataset" / "manifest.csv"
    for wav in sorted((ROOT / "data" / "language_dataset").glob("*.wav")):
        items.append({"path": wav, "label": 1, "set": "language_dataset", "split": "calibration"})

    for case in first_accepted_cases(ROOT / "data" / "stt_validation" / "pilot_01").values():
        items.append({"path": case["audio"], "label": 1, "set": "pilot_01", "split": "test",
                      "reference": case["reference_text"]})

    for folder in ("wakeword", "live_stt_diagnostic"):
        for wav in sorted((ROOT / "data" / "command_capture" / folder).glob("*.wav")):
            items.append({"path": wav, "label": 1, "set": folder, "split": "test"})

    for number in range(1, 81):
        wav = ROOT / "data" / "stt_benchmark" / f"test_{number:03d}.wav"
        items.append({"path": wav, "label": 0, "set": "stt_benchmark",
                      "split": "calibration" if number % 2 == 0 else "test"})

    if not manifest.is_file():
        raise FileNotFoundError(manifest)
    return items


def choose_threshold(scores: list[tuple[float, int]]) -> float:
    """Largest threshold with zero false accepts on the calibration split."""
    negatives = sorted(score for score, label in scores if label == 0)
    positives = sorted(score for score, label in scores if label == 1)
    lowest_negative = negatives[0]
    below = [score for score in positives if score < lowest_negative]
    return (max(below) + lowest_negative) / 2 if below else lowest_negative / 2


def evaluate(rows: list[dict], key: str, threshold: float, split: str) -> dict:
    subset = [row for row in rows if row["split"] == split]
    positives = [row for row in subset if row["label"] == 1]
    negatives = [row for row in subset if row["label"] == 0]
    return {
        "split": split,
        "detected": sum(row[key] < threshold for row in positives),
        "positives": len(positives),
        "false_accepts": sum(row[key] < threshold for row in negatives),
        "negatives": len(negatives),
        "missed": [row["file"] for row in positives if row[key] >= threshold],
        "false_accept_files": [row["file"] for row in negatives if row[key] < threshold],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / (
            "CTC_WAKE_KWS_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".jsonl"
        ),
    )
    args = parser.parse_args()
    dtype = torch.float16 if args.device == "cuda" else torch.float32

    bg = CtcScorer(BG_MODEL, args.device, dtype)
    en = CtcScorer(EN_MODEL, args.device, dtype)
    bg_tokens = {keyword: bg.token_ids(keyword) for keyword in BG_KEYWORDS}
    en_tokens = {keyword: en.token_ids(keyword) for keyword in EN_KEYWORDS}

    rows: list[dict] = []
    forward_seconds: list[float] = []

    for item in collect_files():
        audio = load_wav(item["path"])
        if item["label"] == 1:
            audio = audio[: int(POSITIVE_PREFIX_SECONDS * 16000)]

        started = time.perf_counter()
        bg_log_probs = bg.log_probs(audio)
        if args.device == "cuda":
            torch.cuda.synchronize()
        forward_seconds.append(time.perf_counter() - started)
        en_log_probs = en.log_probs(audio)

        row = {
            "file": str(item["path"].relative_to(ROOT)),
            "set": item["set"],
            "split": item["split"],
            "label": item["label"],
            "seconds": round(len(audio) / 16000, 2),
        }
        for keyword, tokens in bg_tokens.items():
            row[f"bg_{keyword}"] = round(keyword_deficit(bg_log_probs, tokens, bg.blank), 4)
        for keyword, tokens in en_tokens.items():
            row[f"en_{keyword}"] = round(keyword_deficit(en_log_probs, tokens, en.blank), 4)
        row["bg_best"] = min(row[f"bg_{keyword}"] for keyword in BG_KEYWORDS)
        row["bg_main"] = row["bg_аурора"]
        row["bg_or_en"] = min(row["bg_best"], row["en_aurora"])
        rows.append(row)

    results = []
    for key in ("bg_main", "bg_best", "bg_or_en", "en_aurora"):
        calibration = [(row[key], row["label"]) for row in rows if row["split"] == "calibration"]
        threshold = choose_threshold(calibration)
        result = {
            "event": "result",
            "score": key,
            "threshold": round(threshold, 4),
            "calibration": evaluate(rows, key, threshold, "calibration"),
            "test": evaluate(rows, key, threshold, "test"),
        }
        results.append(result)

    timing = {
        "event": "timing",
        "device": args.device,
        "dtype": str(dtype),
        "bg_forward_median_seconds": round(sorted(forward_seconds)[len(forward_seconds) // 2], 4),
        "bg_forward_max_seconds": round(max(forward_seconds), 4),
    }

    with args.output.open("x", encoding="utf-8") as report:
        for row in [{"event": "start", "utc": datetime.now(timezone.utc).isoformat()}, *rows, *results, timing]:
            report.write(json.dumps({"event": "file", **row} if "event" not in row else row,
                                    ensure_ascii=False) + "\n")

    for result in results:
        cal, test = result["calibration"], result["test"]
        print(
            f"{result['score']:<10} thr={result['threshold']:<7} "
            f"calib {cal['detected']}/{cal['positives']} FA {cal['false_accepts']}/{cal['negatives']} | "
            f"test {test['detected']}/{test['positives']} FA {test['false_accepts']}/{test['negatives']}"
        )
        if test["missed"]:
            print("   missed:", ", ".join(Path(name).name for name in test["missed"]))
        if test["false_accept_files"]:
            print("   false accepts:", ", ".join(Path(name).name for name in test["false_accept_files"]))
    print(json.dumps(timing))
    print(f"Report: {args.output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
