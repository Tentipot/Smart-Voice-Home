# Smart voice home — AUDIO DATASETS

Updated: 2026-09-25

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

Prompt sources recovered 2026-09-26 (scripts, not re-listened audio):

| Files | Groups | Prompt list | Recording |
| --- | --- | --- | --- |
| `test_001`–`test_030` | 10 BG, 10 EN, 10 BG+EN | `TESTS` in `tools/benchmarks/benchmark_whisper_large_v3_accuracy.py` (same in `tools/datasets/rerecord_test_audio.py`) | fixed 8.00 s windows with ~4–5 s trailing silence (ChatLOG L29440–29715); may have been re-recorded |
| `test_031`–`test_060` | 10 BG, 10 EN, 10 MIXED = BG command + foreign entity | `TESTS` in `tools/benchmarks/benchmark_stt_validation_031_060.py`; 051–060 also in `benchmark_ctc_segment_validation_051_060.py` | manual start/stop, 2.1–6.0 s |
| `test_061`–`test_080` | 10 BG, 10 EN | `TESTS` in `tools/datasets/record_validation_audio.py` | manual start/stop, 2.0–3.8 s |
| `diagnostic_32s.wav` | — | synthetic: `test_001` repeated 4× (ChatLOG L68089) | VRAM test only; not for accuracy |

User listening check (ChatLOG L63115–63171): 021 and 051 are a BG command with
EN artist/song names; other files in the 021–030 group may mix more.
Known examples: 031 = „Намали звука на тридесет процента“, 041 = "Set the
volume to 40%".

## 4a. wakeword_gpu content (from filenames and ChatLOG, 2026-09-26)

`data/command_capture/wakeword_gpu/` (90 files, 12.7 MB, 2026-09-21..22):
44 `window_*` and 27 `wake_window_*` (wake-detection windows),
4 `_wake_*` temporary files, 2 `command_*`, 2 `command_vad_*`,
2 `wake_phrase_*`, 9 `command_full_*`. The user judged the 9 `command_full_*`
files unusable for calibration (noise, several commands, one 67 s artifact of a
block-size bug; ChatLOG L88111–88115). `command_full_20260922_124403_026821.wav`
is evidence for the finding CTC → EN (+0.009427) while Buzz returned
„Аурора намали звука“ (ChatLOG L80633–80961).

Total size of all project WAV files on 2026-09-26: ~39 MB (253 files).
Deleting diagnostic WAVs frees almost no disk space.

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

## 7. Първи validation запис — 2026-09-25 (Europe/Sofia)

Сесия: `data/stt_validation/pilot_01/20260924T225437Z_612fb22a31544d9b916cacd5267ef0df/`.
Името на сесията е в UTC; местната дата е 25 септември.
Файл: `BG01_7950771aedde4140805d0ae430913263.wav`.
SHA256: `04d515d14357be54142f5c218cc862714e1d0e4edeb946378fa2433a5f0a5689`.

Текст: „Аурора, намали силата на звука до двадесет процента.“
Език BG, говорител stan, микрофон Trust GXT 232, 16 kHz mono PCM16,
продължителност 5.50 s, RMS 0.03423636. Средата не е измерена за шум.
Приет от потребителя след две прослушвания; събитията са в `manifest.jsonl`.
Приблизителният енергийно активен интервал е 0.70–4.10 s (RMS праг 0.003,
20 ms блокове), не точна фонетична граница. Тихите части са запазени.
Wake текстът „أورورا“ е предварителен ASR резултат, не референтен текст.

Това е първият запис от планираните 24, не завършен набор или резултат
за STT качество. Финален SttService не е изпълняван върху този файл.

BG02 също е приет от потребителя: „Аурора, увеличи силата на звука до
шестдесет процента.“, 5.90 s, RMS 0.03199894, BG, същият говорител и микрофон.
Сесия: `data/stt_validation/pilot_01/20260924T230031Z_8247c244931a4567893c851e605cb657/`.
Файл: `BG02_44ba8b29e70240d681ee58fbba162427.wav`.
SHA256: `b7a2918dfc3562af939b30159e8fd6683b611f033b12a752d13741c8b9896ed0`.
Accepted review е записан в manifest; сесията приключи преди BG03.
Общо са приети 2 от 24 фрази към първия етап. Финален STT не е изпълняван.

## 8. Завършен pilot_01 capture — 2026-09-25

Събирането на пилота е завършено с 24 приети референции: 8 BG, 8 EN и
8 MIXED. Двата първи записа са в отделни по-ранни сесии; останалите са
в основната сесия от 24 септември UTC. Има две празни сесии след timeout.
За MX04 един първи опит е отхвърлен поради грешно произнасяне, а вторият
е приет. Manifest-ите са append-only и пазят двата опита. Пилотът е
фиксиран чрез playback review и потребителско приемане. Финален SttService
benchmark, WER и route резултати не са налични.
