# Smart voice home — AUDIO DATASETS

Updated: 2026-09-23

## Purpose

This document records the purpose, provenance and validation status of
local audio datasets. File existence alone does not establish that a
recording is correct, accepted or suitable for model evaluation.

All paths below are relative to the repository root.

The entire `data/` directory is excluded from Git. This document is
version-controlled, but the recordings and their manifests are not.
Preserve the original data separately when backing up or migrating
the project.

## 1. Language calibration dataset

Location: `data/language_dataset/`

Original calibration recordings:
- `bg_001_20260922_*.wav` through `bg_020_20260922_*.wav`
- `en_021_20260922_*.wav` through `en_040_20260922_*.wav`

Purpose:
- 40 manually reviewed, production-like BG/EN recordings;
- calibration of the CTC-based LanguageResolver ambiguity zone.

Associated files:
- `manifest.csv`: recording metadata and prompted text;
- `ctc_analysis.csv`: analysis results;
- `data/stt_ctc_pure_40.csv`: additional CTC analysis data.

Recorded calibration result:
- 20 BG and 20 EN recordings;
- 32 direct classifications, all 32 correct in-sample;
- 8 MIXED classifications.

These figures describe the original 40 recordings only.
They are not independent validation results.

## 2. AuroraCapture functional verification — 2026-09-23

Two additional recordings were accepted after live microphone capture,
wake detection, automatic VAD ending, playback and manual review.

| File | Prompted text | Duration | Wake ASR |
| --- | --- | ---: | --- |
| `data/language_dataset/bg_001_20260923_212640_017014.wav` | Аурора, намали звука | 4.000 s | Аурора на мой |
| `data/language_dataset/en_002_20260923_212654_840062.wav` | Aurora, turn down the volume | 4.400 s | Aurora |

Both passed the collector's automatic quality checks and were manually
accepted. AuroraCapture paused before review and resumed between samples.

These two files are NOT part of the original 40-file resolver
calibration. The directory currently contains 42 WAV files:
21 BG and 21 EN.

Wake detection is functionally verified for these two cases.
Reliability across speakers, noise conditions and a larger command set
has not been established.

## 3. Isolated wake-word recordings — 2026-09-20

Location: `data/command_capture/wakeword/`

| File | Purpose | Verified result |
| --- | --- | --- |
| `english_20260920_192224.wav` | Isolated English wake-word diagnostic | Whisper large-v3: `Aurora`; wake=True |
| `bulgarian_20260920_192248.wav` | Isolated Bulgarian wake-word diagnostic | Whisper large-v3: `Aurora`; wake=True |

Both were tested on 2026-09-23 using CUDA, float16 and beam_size=1.
Whisper's automatic language labels were `es` and `ru`, respectively.
Those labels must not be treated as reliable command-language evidence.

## 4. Other command-capture diagnostics

Locations:
- `data/command_capture/command_*.wav`
- `data/command_capture/webrtc/`
- `data/command_capture/wakeword_gpu/`

These contain earlier command-capture, WebRTC VAD and GPU wake-word
experiments. The `wakeword_gpu` directory includes files named
`window_*`, `wake_window_*`, `wake_phrase_*`, `command_*`,
`command_full_*`, `command_vad_*` and `_wake_*`.

Their individual prompts, acceptance status and suitability for
regression testing have NOT been independently verified in this
documentation. Do not infer those properties from filenames.

`data/command_capture/ctc_language_labels.csv` contains related
language-label data; its exact relationship to individual recordings
should be checked before reuse.

## 5. STT benchmark recordings

Location: `data/stt_benchmark/`

Inventory:
- `test_001.wav` through `test_080.wav`;
- `diagnostic_32s.wav`.

These belong to earlier STT benchmarking and diagnostics.
The precise prompt and validated expected transcript of each recording
must be recovered from the relevant benchmark scripts or historical
results before it is used for a new quality comparison.

## 6. Preservation and future recording policy

For every new test dataset, record:
- exact relative filename and creation date;
- recording script and purpose;
- prompted or expected text and language, when known;
- model/settings and test result;
- whether a person reviewed and accepted the recording;
- whether it belongs to calibration, independent validation or
  diagnostic experiments.

Do not silently merge datasets with different purposes.
Do not delete or rename existing audio files solely because their
purpose is not yet documented.
