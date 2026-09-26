# Smart voice home — OPEN QUESTIONS
Updated: 2026-09-26

These are intentionally unresolved. Do not silently invent answers.

2026-09-26: [Semantic Review v1](SEMANTIC_REVIEW_V1.md) вече проверява
ограничени единични команди и противоречиви кандидати. Остават широк езиков
обхват, entity resolution, акустична проверка и контекст. parsed не е
изпълнима/разрешена команда; всички can_execute стойности са false.

2026-09-26: aggregate evidence и resolution вече се предават с STT резултата
чрез `transcribe_with_evidence()`. Остават semantic review, CTC текстови и
времеви evidence, candidate selection и независима валидация. Новото API
не доказва подобрена точност на разпознаването.

Допълнително възстановени механизми и оставащи неизвестни:
[STT_HISTORY_MECHANISMS_AUDIT.md](STT_HISTORY_MECHANISMS_AUDIT.md).
CTC+LM, grammar/context и каскадните предложения не са потвърдени като
един общ приет дизайн. Старо предложение за MIXED отказ се различава от
последващия/текущ код; не въвеждай отказ само въз основа на старата реплика.

Приоритет за продължаване: [историческият STT checkpoint](STT_HISTORY_CHECKPOINT.md).
Кои допълнителни механизми към speech masking / temporal evidence /
smoothing / STT candidates са обсъждани, проверени, одобрени или заменени?
Потребителят изрично помни още механизми; съдържанието им предстои да се
възстанови. Не приемай наличната схема за пълна и не започвай автоматично
поредния моделeн тест по старите предложения по-долу.

1. Exact arbitration when multiple devices hear the same wake phrase/command.
2. Final authentication/token/device-registration protocol.
3. Final user/device/home/permission database schema.
4. Final production remote-access/gateway technology.
5. Final general/shared wake-word policy.
6. Final TTS model(s), voice(s), streaming strategy and resource placement.
7. Final local conversational-AI model and CPU/RAM/GPU placement.
8. Final Web Admin technology stack and deployment.
9. Exact Home Assistant permission/capability mapping.
10. Final MediaProvider / PlaybackTarget API and default-routing rules for every action type.
11. Production server composition root.
12. Production `/stt` endpoint and streaming protocol.
13. Independent validation dataset for CTC resolver thresholds.
14. MIXED fallback quality, especially Bulgarian/mixed speech.
    Real AuroraCapture BG sample bg_001_20260923_212640_017014.wav:
    CTC resolved MIXED (CTC_AMBIGUOUS_EVIDENCE); Whisper returned
    "Aurora normalis buka." Earlier isolated BuzzASR testing of the
    same WAV returned "Аурора намали звука". Validate with more
    independent recordings before changing resolver thresholds or routing.
    On the separate 3.70 s live capture
    aurora_20260923_234840_331887.wav, CTC again resolved MIXED
    (entropy delta +0.040802). Whisper AUTO detected `ru` with
    probability 0.323974609375 and transcribed
    "Аурора на малозвуке."; forced Whisper BG returned
    "Аурора на малезвука."; forced Buzz BG returned
    "А у Рора намали звука". This isolates a failure of the current
    MIXED/Whisper path for this recording, but does not validate a
    replacement routing rule or new CTC thresholds.
15. Production Resource Manager policy, budgets and gaming behavior.
16. Exact split of Android-local vs server-side functionality after integration.
17. Profile/preferences synchronization across multiple devices.
18. Ownership/trust model for shared room endpoints.
19. Detailed explicit-consent UX/policy for each type of external online provider.
20. Backup/restore/versioning strategy for server configuration, users and integrations.
21. Full re-audit of Android source and Spotify implementation against current platform design.
22. Reconciliation of this reconstruction with the official ChatGPT export when received.

23. Permanent CUDA DLL discovery for CTranslate2/Whisper on Windows.
    Current verified workaround: prepend the installed NVIDIA DLL
    directories to PATH before starting Python.

24. End-to-end integration of AuroraCapture with SttService:
    full captured phrase → language evidence → resolver → STT router
    → final command transcript. No real assistant actions during
    initial integration diagnostics.
    Offline replay through SttService verified for two accepted
    AuroraCapture WAVs using diagnose_captured_phrase_stt.py:
    BG resolved MIXED with incorrect transcript; EN resolved EN
    with transcript "Aurora turn down the volume."
    A new live AuroraCapture WAV was replayed through SttService in
    a separate process: BG resolved MIXED with incorrect transcript
    "Аурора на малозвуке." (3.211 s total SttService time).
    Live AuroraCapture callback → SttService integration in one
    process remains untested.

25. Command-only audio extraction and precise wake-word boundary,
    if required by the final command-processing design.

26. Wake-detection reliability validation across speakers, noise
    conditions and a larger BG/EN command dataset. The two accepted
    live recordings establish functional operation only.

27. Separation of preliminary wake-detection ASR text/language labels
    from final command transcription and language routing.

28. Preservation and backup of local audio datasets under data/,
    which is excluded from Git. See docs/AUDIO_DATASETS.md.

29. Разширеният pilot_01 показва BG маршрут за 5/8 MIXED фрази.
    Директен Whisper AUTO върху 8/8 MIXED записа подобрява три случая,
    влошава два (MX04 критично) и оставя три непроменени. Вж.
    MIXED_WHISPER_AUTO_COMPARISON.md; предложено е forced BG/EN сравнение.
    Следва анализ без автоматична промяна на праговете. Необходими са
    пълен ръчен semantic checklist, model revisions/dependency snapshot
    и проверка на offline режима извън batch runner-а.

30. Живата латентност 9–13 s: дали причината е препълнена VRAM, защото
    AuroraCapture зарежда собствен Whisper large-v3 fp16 (~3.8 GB) до
    production Whisper int8 (~2 GB) и Buzz (~3.2 GB). Нужно е NVML замерване
    по време на живия тест. Вж. CHATLOG_FULL_READ_2026-09-26.md §1 и D034.

31. MIXED маршрут: сегашното MIXED → Whisper AUTO е предложение на
    асистента (ChatLOG L97416). Потребителското правило L47599 е „не е
    английски → български“. Кое важи — решава потребителят.

32. Трите STT модела на GPU не са опитвани реално (тестът спира от
    собствения си праг, ChatLOG L69997). Възможно освобождаване на VRAM чрез
    CTranslate2 int8 версия на BuzzASR (архитектура Whisper large-v3) не е
    тествано.
