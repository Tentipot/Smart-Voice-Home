# Smart voice home — PROJECT HISTORY
Updated: 2026-09-25

## 1. Origin — offline Bulgarian STT
The project begins on 2026-08-29 as a search for a free offline Bulgarian voice-recognition solution for a software project.

## 2. Android offline assistant
The work becomes an Android/Kotlin assistant with microphone capture, whisper.cpp/local Whisper, command parsing and Android media actions. Early manual Start/Stop listening is a development mechanism rather than the intended final interaction.

## 3. Media and Spotify
The assistant evolves from Spotify search/deep-link behavior into Spotify Developer setup, App Remote and Web API search so open-vocabulary artist/title queries can resolve to a real track URI and play.

## 4. Server-platform transition
The decisive architectural expansion occurs when the user requires:
- use outside the home over Internet;
- multiple users;
- future non-Android clients;
- server resource awareness while the PC is gaming/working.

The project becomes a client/server assistant platform rather than a phone app.

## 5. Smart-home expansion
Home Assistant is added as the smart-home authority. The design expands from one home to future multiple homes, with permission controls and voice-forbidden security-critical actions.

## 6. Identity and multi-device design
Personal user-selected wake words, general/shared wake context, authenticated accounts/devices, origin-vs-target separation and per-user services/preferences are developed. Wake word is explicitly not authentication.

## 7. Administration and personalization
The architecture gains a PC-oriented admin GUI, user/device/home/permission management, language profiles, response preferences, TTS planning, network management and audit.

## 8. Windows AssistantServer
The central server work starts on Windows 11 / Ryzen 5 3600 / 32 GB / RTX 3070 with FastAPI/system monitoring and extensive STT benchmarking.

## 9. STT model selection and routing
Multiple engines are compared. The implementation evolves toward:
- BuzzASR for Bulgarian;
- Whisper large-v3 for English/mixed;
- BG+EN CTC as language evidence;
- LanguageResolver + SttRouter + SttService.

## 10. Resource lifecycle
Model lifecycle abstractions, ModelHandle and ModelManager are developed and tested. GPU/RAM residency experiments lead to an investigated composition with Buzz+Whisper on GPU and CTC on CPU/RAM.

## 11. Natural capture / wake work
Live microphone capture, WebRTC VAD and wake-word experiments lead to AuroraCapture. "Аурора" is a wake word used in development, not the project name.

## 12. Language calibration
A dedicated 40-WAV BG/EN dataset is manually reviewed and used to calibrate the production LanguageResolver ambiguity zone.

## 13. Reconstruction checkpoint
On 2026-09-22 development pauses because the long chat no longer provides trustworthy complete historical context. A forensic source snapshot and then the full `VoiceAssistant_ChatLOG.txt` are used to reconstruct project history and architecture.

The official ChatGPT export remains useful as an independent completeness check when it arrives.

## 14. AuroraCapture functional verification — 2026-09-23

A live microphone test verifies the basic Aurora wake-word capture path
with one Bulgarian and one English utterance.

The user speaks the wake word and command continuously, without an
intentional pause. AuroraCapture retains pre-roll audio, uses WebRTC VAD
to detect the phrase boundaries, recognizes the wake word and delivers
the complete captured phrase.

Both recordings are played back and manually accepted:
- `data/language_dataset/bg_001_20260923_212640_017014.wav`
- `data/language_dataset/en_002_20260923_212654_840062.wav`

Two earlier isolated wake-word recordings are also successfully
recognized using Whisper large-v3 on CUDA.

This checkpoint establishes basic functional operation, not production
wake-detection reliability. Final command STT and real assistant actions
are outside the scope of this test.

A CUDA dependency issue is identified: CTranslate2 inference works
when the NVIDIA DLL directories are added to PATH before Python starts.
A permanent startup fix remains open.

The audio dataset inventory and its validation boundaries are recorded
in `docs/AUDIO_DATASETS.md`.

## 15. Retired STT diagnostic script — 2026-09-23

Removed `diagnose_full_stt_pipeline.py` to avoid confusion with the
current STT diagnostic path. The retired script had missing imports,
loaded CTC models on CUDA, and routed directly through SttRouter
instead of exercising SttService.

The verified offline diagnostic for accepted AuroraCapture recordings
is `diagnose_captured_phrase_stt.py`.

Live AuroraCapture callback-to-SttService integration remains untested.
The initial live diagnostic will capture one phrase and terminate its
process before STT models are loaded in a separate process, avoiding
simultaneous wake and STT model residency on the 8 GiB GPU.
No assistant actions will be executed.

## 16. Live AuroraCapture WAV through SttService — 2026-09-23

A separate-process diagnostic captures the spoken Bulgarian phrase
"Аурора, намали звука" using diagnose_live_aurora_capture.py.
AuroraCapture detects the wake word and saves a 3.70 s, 16 kHz PCM16
recording with RMS 0.0316:

`data/command_capture/live_stt_diagnostic/aurora_20260923_234840_331887.wav`

The preliminary wake ASR text is "Аурора на малюс". After the capture
process exits, diagnose_captured_phrase_stt.py is run with its new
optional --audio argument to process this WAV once through SttService.
The default four-case BG/EN diagnostic remains available.

Measured STT results:
- CTC CPU: 1.578 s.
- LanguageResolver: 0.000028 s.
- STT via router: 1.632 s.
- Total SttService: 3.211 s.
- Resolved mode: MIXED; reason: CTC_AMBIGUOUS_EVIDENCE.
- Final transcript: "Аурора на малозвуке." (incorrect).
- VRAM: 1085 MB baseline, 6333 MB after model loading,
  6415 MB after the case and after cleanup.

The diagnostic reports unloading all three model resources, but VRAM
does not decrease before process exit. In-process GPU memory
reclamation is not established by this test.

This verifies offline SttService processing of a newly captured live
AuroraCapture WAV. It does not verify callback-to-SttService
integration in one process, reliable wake detection, correct Bulgarian
command recognition, command-only extraction, or assistant actions.
The language thresholds are not changed based on this single sample.

Follow-up diagnostics on the same live WAV:
- Repeated SttService run: CTC BG entropy 0.079617, EN entropy
  0.038815, delta +0.040802. Resolver boundaries: BG <= 0.003,
  EN >= 0.043; the result remains MIXED.
- Whisper large-v3 in MIXED mode (`language=None`) detected Russian
  (`ru`) with language probability 0.323974609375 and returned
  "Аурора на малозвуке." The measured SttService time was 2.873 s
  (CTC 1.596 s; router 1.277 s).
- Isolated Whisper large-v3 with forced `language="bg"` returned
  "Аурора на малезвука." (0.962 s inference).
- Isolated BuzzASR/bulgarian with forced `language="bg"` returned
  "А у Рора намали звука" (0.55 s inference). The command words
  were recognized, although the wake name was split.

For this WAV, forcing Bulgarian in Whisper does not recover the
command, whereas Buzz BG recognizes the command words. These
diagnostics do not establish a general MIXED routing policy. No
production resolver thresholds, routing, or assistant actions changed.

## 17. Актуализация на проектната памет — 2026-09-25

След разрешение от потребителя е актуализирана само документацията.
EVIDENCE_MAP.md вече посочва предоставения исторически лог, пет текстови
схеми и обзорното изображение с версия 2026-09-23, включително ограниченията
на съпоставката и разминаванията с кода. Източниците остават извън Git.

PROJECT_STATE.md отразява вече описаните резултати от 23 септември:
WAV обработката през SttService в отделен процес е проверена, но BG/MIXED
качеството и живата интеграция не са потвърдени. Индексът сочи към
актуалната точка за продължаване.

Не са изпълнявани нови STT тестове и не са променяни код, прагове,
модели или аудиоданни. Независима BG/EN/MIXED оценка остава предложената
следваща техническа задача; протоколът и изпълнението ѝ предстоят.

## 18. Отделен validation collector — 2026-09-25

Добавени са `collect_stt_validation.py` и шест теста без хардуер в
`test_stt_validation_collector.py`. Collector-ът използва съществуващия
AuroraCapture, нови уникални сесии, прослушване и append-only manifest.
Приети, отхвърлени и прекъснати опити се разграничават; WAV не се презаписват.
Тестовете са успешни. Проверена е и CLI селекция на MIXED фрази без модели.
При първия тестов опит sandbox блокира временните файлове; повторното
разрешено изпълнение премина успешно. Коригиран е UTF-8 изходът на новия CLI
за Windows пренасочен stdout.

Това не е жива capture проверка. Не са записвани нови реални фрази, не са
стартирани модели и не са променяни съществуващите STT/capture компоненти.

## 19. Първа жива collector проверка — 2026-09-25

BG01 е записан с Trust GXT 232 и съществуващия CUDA PATH обход.
Получени са 5.50 s аудио; потребителят потвърди ясна фраза и прие записа
след две прослушвания. Collector-ът записа accepted review с BG референция
и приключи. Данните са описани в AUDIO_DATASETS.md. Финален STT не е стартиран.

По желание на потребителя са добавени видими начало/край и продължителност
при първо и повторно прослушване. Маркерите обозначават целия WAV,
не границите на речта. Оригиналният запис не е изрязван или променян.

Последващо продължение: BG02 (5.90 s) е приет от потребителя. Текстовите
маркери в чата са оценени като недостатъчни заради закъснението им.
Добавени са висок начален и нисък краен тон само при playback, в един
аудиопоток с WAV. Проверка с mock output потвърди запазване на оригиналните
аудиосемпли. Събирането продължи до завършен pilot_01: приети са BG01–BG08,
EN01–EN08 и MX01–MX08, общо 24/24. Един MX04 опит е отхвърлен и повторен.
Има две празни timeout сесии без WAV. Финалният STT анализ не е изпълнен.

## 20. Подготовка за изцяло локален STT — 2026-09-25

По решение на потребителя са изтеглени локално BuzzASR Bulgarian,
българският и английският CTC модел и `faster-whisper-large-v3`.
Моделите са големи runtime assets и не се включват в Git или backup.
Добавена е конфигурация за локални model paths чрез environment variables,
с `local_files_only=True` при локални Transformers директории. Batch runner-ът
използва тези директории по подразбиране. Синтаксисът и manifest селекцията
на 24 приети записа са проверени; пълният benchmark остава непроверен.
