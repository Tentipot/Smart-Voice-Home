# Smart voice home — PROJECT STATE
Updated: 2026-09-23

## Development status
Feature development is temporarily paused for architecture/history reconstruction after the long chat context became unreliable.

## Android lineage
Historical Android MVP evidence supports:
- local Whisper fallback;
- command parser/router;
- media-control path;
- Spotify Developer/App Remote/Web API integration work;
- Android as the predecessor/client of the larger platform.

Full current Android source still needs to be re-audited when available.

## Current Windows server/STT implementation
Known modules include:
- FastAPI skeleton (`/health`, `/status`);
- system/GPU monitoring;
- Whisper STT engine;
- BuzzASR Bulgarian engine;
- BG/EN CTC language-evidence provider;
- LanguageResolver;
- SttRouter;
- SttService;
- ModelHandle / ModelManager and lifecycle adapters;
- live microphone/VAD/wake capture;
- AuroraCapture.

## Current STT route
audio
→ BG/EN CTC evidence
→ LanguageResolver
→ BG / EN / MIXED
→ SttRouter
→ final STT.

BG → BuzzASR forced Bulgarian.
EN → Whisper forced English.
MIXED → Whisper auto-language.

## Resolver calibration
Current recovered production boundaries:
- BG: entropy_delta <= 0.003
- EN: entropy_delta >= 0.043
- otherwise MIXED.

Calibration dataset:
- 40 manually reviewed production-like WAVs;
- 20 BG / 20 EN;
- 32 direct classifications;
- 32/32 direct correct;
- 8 MIXED.

This is in-sample calibration, not independent validation.

## Resource configuration investigated
Later diagnostic composition:
- Whisper large-v3: GPU, CTranslate2, int8_float16;
- BuzzASR Bulgarian: GPU, PyTorch;
- BG+EN CTC pair: CPU/system RAM.

Do not extend this into a final local-LLM resource decision.

## ModelManager status
Implemented concepts:
- lazy loading;
- resident reuse;
- acquire/release leases;
- explicit unload;
- backend cleanup;
- concurrency/lifecycle tests.

Not yet proven as a complete global scheduler:
- automatic VRAM budgeting;
- LRU eviction;
- full gaming-aware policy;
- production inference scheduling/preloading.

## Server integration gap
`SttService` existing in source does not prove full production composition.
`app/main.py` does not yet prove a complete production `/stt` endpoint.


## AuroraCapture functional verification — 2026-09-23

Status: functionally verified for two live microphone test cases.

Confirmed:
- continuous utterance of wake word followed by a command, without
  requiring a deliberate pause between them;
- pre-roll buffering and capture of the complete phrase;
- WebRTC VAD phrase start and automatic ending;
- wake detection in Bulgarian and English test cases;
- delivery of `CapturedPhrase` containing the full audio blocks;
- pause before collector review, WAV playback, manual acceptance and
  subsequent capture resumption.

Accepted recordings:
- `data/language_dataset/bg_001_20260923_212640_017014.wav`
  — "Аурора, намали звука";
- `data/language_dataset/en_002_20260923_212654_840062.wav`
  — "Aurora, turn down the volume".

The isolated wake-word WAVs from 2026-09-20 were also successfully
recognized by Whisper large-v3 on CUDA during this verification.

Limitations:
- this is a functional test, not a measured wake-detection reliability
  benchmark across speakers, noise conditions or larger datasets;
- `wake_text` is preliminary wake-detection ASR output, not the final
  command transcript;
- command-only extraction and the connection from `AuroraCapture` to
  `SttService` have not been verified end-to-end;
- no real assistant actions were executed.

CUDA dependency finding:
- `cublas64_12.dll` exists and loads successfully by full path;
- CTranslate2 CUDA inference works when NVIDIA DLL directories are
  prepended to PATH before Python starts;
- a permanent project-level DLL discovery fix is still required.

See `docs/AUDIO_DATASETS.md` for the audio inventory and dataset
boundaries.

## Immediate technical continuation point
When development resumes:
1. validate end-to-end SttService WAV → evidence → resolver → router → transcript;
2. inspect transcription quality, especially MIXED;
3. monitor resource behavior;
4. avoid executing real assistant actions during diagnostics.

Architecture reconciliation should be completed before large cross-system changes.
