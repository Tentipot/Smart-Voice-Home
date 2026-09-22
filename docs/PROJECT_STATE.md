# Smart voice home — PROJECT STATE
Updated: 2026-09-22

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

## Immediate technical continuation point
When development resumes:
1. validate end-to-end SttService WAV → evidence → resolver → router → transcript;
2. inspect transcription quality, especially MIXED;
3. monitor resource behavior;
4. avoid executing real assistant actions during diagnostics.

Architecture reconciliation should be completed before large cross-system changes.
