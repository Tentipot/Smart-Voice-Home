# Smart voice home — PROJECT STATE
Updated: 2026-09-25

## Development status
След документалния етап потребителят разреши продължаване на разработката.
Добавен е отделен validation collector; проверен е с тестове без хардуер.
Първата жива collector проверка е приета: BG01, 5.50 s, Trust GXT 232,
с прослушване и повторно прослушване. Финален STT върху този WAV не е изпълнен.

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

Planned, not implemented in the current ModelManager:
- automatic VRAM budgeting;
- LRU eviction;
- full gaming-aware policy;
- production inference scheduling/preloading.

## Server integration gap
`SttService` existing in source does not prove full production composition.
`app/main.py` exposes `/health` and `/status` only. Production `/stt`,
`/tts`, `/command` and streaming integration remain planned.


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

## Обработка на AuroraCapture WAV през SttService — резултати от 2026-09-23

Диагностично проверено в отделен процес чрез `diagnose_captured_phrase_stt.py`:
- Приетият BG запис от 23 септември е класифициран като MIXED и получава
  грешна транскрипция: "Aurora normalis buka.".
- Приетият EN запис е класифициран като EN и връща
  "Aurora turn down the volume.".
- Новият 3.70 s запис
  `data/command_capture/live_stt_diagnostic/aurora_20260923_234840_331887.wav`
  преминава през цялата WAV → evidence → resolver → router → transcript
  верига за 3.211 s, но връща грешното "Аурора на малозвуке.".
- Последващата диагностика на същия WAV отчита entropy delta +0.040802,
  MIXED и Whisper AUTO език `ru`. Принудителният Whisper BG също греши;
  Buzz BG връща "А у Рора намали звука" и разпознава командните думи.
- Отчетената VRAM остава 6415 MB след cleanup; освобождаване на GPU паметта
  в същия процес не е доказано. Причината не е окончателно установена.

Това са вече документираните резултати в [PROJECT_HISTORY.md](PROJECT_HISTORY.md),
раздел 16, и [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md), точки 14 и 24;
не са нови измервания от настоящия документален етап.
Живата callback интеграция AuroraCapture → SttService в един процес,
общата надеждност и правилното BG/MIXED разпознаване остават непотвърдени.
Не са изпълнявани реални асистентски действия.

## Точка за продължаване

Предложената следваща техническа задача е независима оценка на BG/EN/MIXED
разпознаването с текущите компоненти, преди промяна на прагове или routing.
Подготвен е [STT_VALIDATION_PLAN.md](STT_VALIDATION_PLAN.md) с 24 предложени
фрази, правила за независимост, референции и оценяване. Нови записи и
измервания не са направени; production критерии за качество и време
още не са договорени. `collect_stt_validation.py` вече реализира отделен
collector с прослушване, приемане и manifest. Всички 24 фрази са приети;
един MX04 опит е отхвърлен и заменен с повторен запис. Този етап не променя
STT политиката. Финален STT анализ предстои.

Следваща интеграционна задача е живата AuroraCapture → SttService връзка
с проверка на ресурсите. CUDA DLL discovery и освобождаването на VRAM
остават отворени. Първоначалните диагностики не изпълняват реални действия.

Предоставените исторически материали и ограниченията на схемите са описани
в [EVIDENCE_MAP.md](EVIDENCE_MAP.md). Първоначалната съпоставка не е
изчерпателен одит на всички реплики и не затваря отворените архитектурни въпроси.

## Резултат от локален pilot_01 baseline — 2026-09-25

Изпълнени са 24/24 приети WAV записа без мрежови заявки, с локални модели и
CUDA DLL обход. Получени са 4/24 точни нормализирани транскрипции и среден
WER 0.325: BG 0.222, EN 0.292, MIXED 0.462. Това е baseline проверка;
CTC entropy, resolver route/reason, VRAM и автоматична проверка на смисъла
на командата още не се записват от runner-а. Вж. `STT_VALIDATION_PILOT_01_RESULTS.md`.

## Локален model set и offline подготовка — 2026-09-25

Изтеглени са локално всички модели за текущия STT validation маршрут:
BuzzASR Bulgarian, български и английски CTC модели и
`faster-whisper-large-v3`. Директориите са под `models/`, извън Git и backup.
STT компонентите приемат локални пътища чрез `SMART_VOICE_BUZZASR_MODEL`,
`SMART_VOICE_CTC_BG_MODEL`, `SMART_VOICE_CTC_EN_MODEL` и
`SMART_VOICE_WHISPER_MODEL`; при локална директория се използва
`local_files_only=True`. Пълният WER/latency отчет още не е наличен.
