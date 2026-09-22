# Smart voice home --- цялостна реконструкция от VoiceAssistant_ChatLOG.txt

**Източник:** `VoiceAssistant_ChatLOG.txt`\
**Обхват на източника:** 101 106 текстови реда, от 29 август 2026 г. до
текущата реконструкция на 22 септември 2026 г.\
**Метод:** целият файл е индексиран; решенията са проследени
хронологично и тематично. По-долу се разграничават: изрично
потребителско изискване, прието архитектурно решение, реално
имплементирано/тествано, историческо/заменено решение и отворен въпрос.

> Важно: този документ не приема автоматично всяко старо предложение на
> асистента за изискване. Където решението е само предложено, това е
> отбелязано. По-късните изрични решения на потребителя имат предимство
> пред по-ранните.

------------------------------------------------------------------------

## 1. Как е започнал проектът

Проектът започва като практически въпрос за **безплатно offline
speech-to-text на български**, след което бързо преминава към Android
приложение с Whisper. Първоначалната цел е локално гласово разпознаване,
без зависимост от облачен STT.

Ранната Android линия постепенно се превръща от тестово приложение в
реален гласов асистент: - Android/Kotlin клиент; - микрофон → PCM →
Whisper; - parser на гласови команди; - управление на Android media; -
Spotify; - по-късно wake word; - local fallback.

Историческият Android проект е `OfflineVoiceAssistant`, package
`com.example.offlinevoiceassistant`.

**Източникови области:** приблизително L1--L20500.

------------------------------------------------------------------------

## 2. Android MVP --- реалната изходна точка на по-голямата система

Android приложението не е страничен експеримент. То е прототипът, от
който се ражда по-голямата платформа.

### Потвърдени компоненти от лога

В различни етапи се разработват/обсъждат: - `MainActivity.kt`; -
`PcmRecorder`; - native `whisper.cpp`/JNI слой; - `CommandParser`; -
`VoiceCommand`; - `CommandRouter`; - `AndroidMediaController`; -
`SpotifyController`; - device registry/target логика; - Android
permissions и foreground microphone behavior.

Първоначално има ръчно `Start listening` → говор → `Stop and recognize`.
Това е било development механизъм, не крайният UX.

STT на Android е променян и тестван с различни Whisper
модели/квантизации. В даден етап `base.en-q5_1` е много добър за
ограничен английски команден речник, но се оказва недостатъчен за
свободни artist/title заявки. Това е един от основните фактори за
преместването на по-тежкия STT към централен PC server.

### Важен принцип, появил се още тук

Parser-ът не трябва да "измисля" имена на песни и изпълнители. Имената
са open vocabulary. Не се допуска hardcode на Metallica, Eminem, Dr. Dre
и т.н.

За противоположни действия като volume up/down е предпочетен безопасен
parser: по-добре "не разбрах", отколкото грешно противоположно действие.

**Източникови области:** L2400+, L7600+, L9000+, L11400+, L12100+,
L13900+, L20480--L20510.

------------------------------------------------------------------------

## 3. Spotify --- от deep link до реална интеграция

Spotify преминава през няколко ясно различими етапа.

### Етап 1 --- Android media/deep-link prototype

Първоначално `PlayMusic(query)` отваря Spotify search. Това доказва
веригата: **STT → parser → command router → Spotify action**, но не
гарантира автоматично пускане на точния track.

### Етап 2 --- Spotify Developer + App Remote

Потребителят регистрира приложението в Spotify Developer Dashboard. В
лога се работи с: - Client ID; - redirect URI; - Android package; -
fingerprint; - Spotify App Remote SDK; - `.aar` dependency; - Gson; -
authorization/connection flow.

### Етап 3 --- Spotify Web API Search + App Remote

Архитектурната цел става: 1. свободният artist/title query да се търси
през Spotify Web API; 2. да се получи точният `spotify:track:...` URI;
3. App Remote да подаде URI към Spotify клиента и да започне playback.

Това е важно за по-късната multi-user архитектура: Spotify връзката
трябва да бъде **per-user**, а не един глобален Spotify акаунт за
всички.

**Източникови области:** L650+, L7370+, L15360--L16860, L19400+,
L21620+.

------------------------------------------------------------------------

## 4. Преходът от Android app към истинска Assistant Platform

Критичният момент е около L20914.

Потребителят изрично казва, че: - асистентът трябва да работи и когато е
извън дома; - трябва да е достъпен през Internet; - трябва евентуално да
се използва от други хора; - не трябва да остане само Android; -
Apple/iOS може да е бъдещ етап; - gaming PC трябва да дава feedback за
натоварването, за да не бъде асистентът агресивен към ресурсите.

От този момент проектът вече е **client/server platform**, а не Android
app.

Приетата посока: - Android: Kotlin; - server backend: Python; - API:
FastAPI; - transport: HTTPS/WebSocket; - заменяем STT/TTS/AI backend; -
Android local fallback; - бъдещи Windows/Linux/Web/iOS/room endpoints; -
modular monolith, а не преждевременни microservices.

**Ключова източникова област:** L20914--L21300.

------------------------------------------------------------------------

## 5. Централен Assistant Server

Основната концепция е централен orchestration server, който да
предоставя общ API независимо от клиента.

Исторически предложени API категории: - `/health`; - `/status`; -
`/stt`; - по-късно command/TTS/auth/capabilities/streaming endpoints.

Основни server слоеве: - API/authentication; - session/user context; -
STT; - intent/assistant routing; - TTS; - users/devices; - media
integrations; - Home Assistant integration; - resource management; -
audit/logging.

Android не трябва да знае кой конкретен Whisper/TTS/LLM стои отзад.
Клиентът говори с наш protocol/API.

### Deployment

Разработката започва на: - Windows 11; - Ryzen 5 3600; - 32 GB RAM; -
RTX 3070 8 GB.

Дългосрочната посока е server-ът да може да се мигрира към Linux, без
Assistant Core да е пълен с Windows-specific команди и пътища.

**Източникови области:** L20914+, L24500--L24900.

------------------------------------------------------------------------

## 6. Resource-aware архитектура

Потребителят изрично иска асистентът да не пречи на gaming/workload.

Появява се концепция за Resource Manager/Scheduler, който следи: -
CPU; - RAM; - GPU; - VRAM; - температура; - активни задачи/процеси; -
текущи assistant requests.

Исторически режими: - IDLE; - NORMAL; - BUSY; - GAMING; - CRITICAL;
и/или manual policy режими AUTO/PERFORMANCE/GAMING/ECO.

Основният принцип е по-важен от имената на режимите: **асистентът трябва
да отстъпва ресурси, когато PC е натоварен.**

Android/local fallback трябва да може да поеме ограничена функционалност
при: - server offline; - server busy; - gaming; - липса на Internet.

**Източникова област:** L20914--L21300.

------------------------------------------------------------------------

## 7. Home Assistant и multi-home

Потребителят изрично добавя Home Assistant като част от проекта: -
първоначално един дом; - в бъдеще поне два дома.

Архитектурното разделение е: - нашият Assistant =
voice/AI/user/context/orchestration слой; - Home Assistant = authority
за smart-home devices/state/actions.

Това избягва повторното реализиране на лампи, контакти, термостати,
sensors и automation engine.

Предвидени са: - HA REST/WebSocket integration; - евентуално Wyoming
compatibility; - multi-home mapping; - per-user/per-device
permissions; - status queries; - smart-home actions.

### Security-critical устройства

Има твърдо изискване определени категории да бъдат **VOICE_FORBIDDEN**.
Примерът в разговорите е достъп/ключалки.

Това означава: дори admin + правилен акаунт + правилно устройство +
правилен wake word **не трябва** да може да изпълни voice action, ако
capability е забранена за voice.

**Източникови области:** L21302--L21618, L22100+, L22700+, L23100+.

------------------------------------------------------------------------

## 8. Multi-user е фундаментална характеристика, не бъдеща добавка

Потребителят иска отделни акаунти.

Всеки user може да има: - собствен профил; - няколко устройства; -
собствен Spotify/service connection; - preferences; - permissions; -
home/device access; - assistant context; - default language; - wake
word.

Permissions и preferences са различни системи.

### Permissions

Отговарят на: **Какво има право да направи authenticated
account/device?**

### Preferences

Отговарят на: **Как асистентът предпочита да взаимодейства с този
user?**

Например след: `Спри телевизора`

един user може да получи: `Да спра ли и лампата?`

друг: `Да спра ли климатика?`

а трети --- никакъв допълнителен въпрос.

Preferences не трябва автоматично да повишават permissions и не трябва
сами да се превръщат в скрити автоматизации.

**Източникови области:** L21620+, L22930+, L23143--L23437.

------------------------------------------------------------------------

## 9. Wake word архитектурата

Това е една от най-важните части, защото по-късната дума **„Аурора" не е
името на проекта**.

`Аурора` е конкретен wake word, използван по-късно в
development/testing.

### Персонални wake words

Потребителят предлага всеки user да има собствен wake word.

Приетата семантика е: - personal wake word избира персонален контекст; -
може да насочи към user-specific Spotify/preferences; - помага за
audit; - НЕ е authentication credential.

Причината е очевидна: друг човек може да произнесе чужд wake word.

### Authentication/authorization

Реалните права идват от authenticated account/device context.

Потребителят дава конкретен пример: ако той е admin и каже
`Спри бойлера` от свое устройство --- действието може да е разрешено;
ако произнесе същото през устройство/акаунт с по-малки права --- не
трябва да получи admin правата само защото гласът/думата е негов.

### User-selected wake word

Потребителят изрично иска wake word да се избира от самия user при
създаване/настройване на акаунта, а не да се генерира произволно.

Системата може да направи enrollment/test и да предупреди при технически
лош избор.

### General wake word

Потребителят приема и идеята за общ wake word.

General wake word е за shared/anonymous context и не трябва да се
преструва, че знае самоличността.

### Speaker recognition

Не е избран като основен identity механизъм. Може някога да бъде
optional confidence signal, но архитектурата не трябва да зависи от
voice biometrics.

**Ключова източникова област:** L22287--L23141.

------------------------------------------------------------------------

## 10. Origin device, user identity и playback target

Това е критичната multi-device логика.

Трябва да се разграничават: 1. кой user context е избран; 2. от кое
устройство идва заявката; 3. къде трябва да се изпълни действието; 4.
какви права има authenticated account/device; 5. коя service connection
се използва.

Основното правило, което се оформя: - **explicit target печели**; - ако
няма explicit target, може да се използва origin/default routing според
вида на действието; - provider и playback target са отделни понятия.

Пример: `<personal wake word>, play Eminem on Spotify on the bedroom TV`

тук: - personal wake → user context; - Spotify → media provider/service
account; - bedroom TV → explicit playback target; - origin device →
security/context/audit input; - permissions → отделна проверка.

Това е по-добро от идеята "песента винаги се пуска на телефона, който е
чул командата".

**Източникови области:** L22287+, L22614+, L22930+, L23060+.

------------------------------------------------------------------------

## 11. Media architecture

Потребителят иска не само Spotify, а и YouTube, плюс лесно добавяне на
други providers в бъдеще.

Оттук идва важна абстракция: - **MediaProvider**: Spotify, YouTube,
бъдещи; - **PlaybackTarget**: телефон, TV, PC, speaker, HA media player
и т.н.

Примерни команди: - `Пусни Eminem Real Slim Shady в Spotify`; -
`Пусни Eminem Real Slim Shady в YouTube на телевизора`; - video playback
към конкретен target.

Provider и target не трябва да са слети в един integration class.

**Източникови области:** L21620--L21621, L22100--L22400 и последващите
архитектурни уточнения.

------------------------------------------------------------------------

## 12. GUI / Web Admin

Потребителят изрично иска графична среда за управление на платформата.

Admin GUI не е просто Android settings screen.

Основни области: - Users; - Devices; - Wake Words; - Permissions; -
Homes; - Integrations; - Preferences; - Logs/Audit; - Server
resources; - speech/STT/TTS настройки; - Network settings.

Потребителят уточнява: - максимум приблизително 1--2 administrators; -
основният admin access ще е от PC; - admins трябва да могат да
управляват практически всички user настройки, с изключение на
паролите/тайните.

Добавено е изискване admin panel да има **network settings**: - server
access; - devices; - reserved addresses; - мрежови настройки/управление.

Windows-specific network operations не трябва да се разпръсват в
Assistant Core; необходим е platform adapter, за да има Linux
implementation по-късно.

**Източникови области:** L23143+, L23440+, L23676+, L24309+, L24590+.

------------------------------------------------------------------------

## 13. Language model / език на потребителя

Потребителят иска всеки account да има default language, който се
запазва в профила.

Но езикът трябва да може да се сменя и динамично с voice command.

Пример: `Please set language to Bulgarian`

след което новата стойност се записва към user profile.

Причината не е само UI: - различни users предпочитат различни езици; -
search за песен/филм може да е по-точен на оригиналния език; - STT
routing може да зависи от езика; - response/TTS language също може да е
различен аспект.

Архитектурно трябва да се различават поне: - STT/input language; -
response language; - search/query language; - per-request override.

Потребителят коригира идеята admins да нямат контрол върху user
language: admins трябва да могат да управляват тези настройки при нужда,
защото някои users може да не са технически грамотни.

**Ключова източникова област:** L23440--L23676.

------------------------------------------------------------------------

## 14. TTS и гласът на асистента

Потребителят изрично напомня, че трябва да бъде решено: - как текстът ще
се превръща в глас; - какви TTS модели; - какви езици; - как ще звучи
самият voice persona.

Изискване: - български; - английски; - добро звучене; - по възможност
multilingual/mixed-language поведение.

Конкретен TTS модел/глас не е окончателно фиксиран. Планът е да се
benchmark-нат реални модели и да се направи слухов тест.

TTS трябва да бъде abstraction/engine, а не hardcoded dependency.

**Източникова област:** L24309--L24519.

------------------------------------------------------------------------

## 15. Online/offline политика

Основната идентичност на проекта е local/offline-first.

В по-късните разговори се оформя важно правило: - Internet/cloud
search/API не трябва да е скрит автоматичен fallback; - online действие
се използва при изрично разрешение/намерение според политиката.

Отдалеченият достъп до **нашия собствен server** е различен въпрос от
изпращане на съдържание към външен AI/cloud provider.

Тоест: - remote access до собствен Assistant Server може да бъде
нормална функция; - външен AI/search/cloud STT трябва да има отделна
consent/policy логика.

------------------------------------------------------------------------

## 16. Local conversational AI

Обсъждан е бъдещ local AI/LLM.

В определен момент се разглеждат: - CPU + RAM; - hybrid CPU/GPU
offload; - GPU mode; - Ollama/LM Studio/llama.cpp тип integration; -
streaming response към TTS.

Исторически е предложено local AI да работи основно CPU/RAM, за да
остави RTX 3070 за STT/TTS/gaming.

**Текущ статус след последното потребителско уточнение:** това НЕ трябва
да се счита за окончателно фиксирана архитектура. Реалното placement на
local AI трябва да се реши след измерване на ресурсите на работещия
асистент. CPU също е споделен ресурс.

Следователно: **Local AI resource strategy = OPEN / benchmark-driven.**

ChatGPT/друг платен AI API е отложен по финансови причини в този етап,
но provider abstraction остава разумна архитектурна възможност.

------------------------------------------------------------------------

## 17. Реалната Windows STT еволюция

След архитектурната фаза започва реалната `D:\AssistantServer`
разработка.

Хронологията от лога и съпоставените diagnostic етапи е:

1.  FastAPI/server skeleton.
2.  System/GPU monitoring.
3.  STT model comparison:
    -   Parakeet;
    -   Whisper large-v3;
    -   Whisper large-v3-turbo;
    -   Canary;
    -   BuzzASR;
    -   Distil-Whisper;
    -   forced BG/EN;
    -   mixed-language tests.
4.  Общ STT interface/result.
5.  Whisper/Buzz engines.
6.  Language policy/router.
7.  Language-ID experiments.
8.  CTC BG/EN evidence approach.
9.  LanguageResolver/LanguageEvidence.
10. `SttService`.
11. Model lifecycle infrastructure.
12. `ModelHandle`/`ModelManager`.
13. concurrency/lifecycle diagnostics.
14. VRAM/RAM experiments.
15. live microphone capture.
16. WebRTC VAD.
17. wake-word experiments.
18. `AuroraCapture`.
19. production-like 40-WAV BG/EN dataset.
20. CTC calibration.
21. production resolver boundaries.

Това е последователна инженерна еволюция, не произволна колекция от
файлове.

------------------------------------------------------------------------

## 18. Текуща STT архитектура към 22 септември

### Модели

**Bulgarian final STT** - BuzzASR Bulgarian; - GPU/PyTorch.

**English final STT** - Whisper large-v3; - GPU/CTranslate2; - в
по-късните resource tests `int8_float16`.

**Mixed/auto** - Whisper large-v3 auto language.

**Language evidence** - BG + EN CTC models; - не са final transcript
engine; - дават acoustic/language evidence.

### Routing

Логиката е концептуално:
`audio → CTC evidence → LanguageResolver → BG / EN / MIXED → SttRouter → final STT engine`

BG → Buzz\
EN → Whisper forced EN\
MIXED → Whisper auto

### Production boundaries

Към последната calibration: - BG direct: `entropy_delta <= 0.003`; - EN
direct: `entropy_delta >= 0.043`; - между тях: MIXED.

40 manually reviewed production-like WAV: - 20 BG; - 20 EN; - 32
direct; - 32/32 direct correct; - 8 MIXED.

Важно: това е calibration върху същия dataset, не независима validation
set. Следователно не трябва да се представя като доказана general
accuracy.

------------------------------------------------------------------------

## 19. GPU/RAM стратегията, която реално е тествана

Тук логът съдържа важна еволюция.

Първо са тествани: - Buzz самостоятелно; - Whisper `int8_float16`; -
CTC; - двойки; - дълъг audio diagnostic; - тройна residency идея.

Важният извод е, че inference-ите не е необходимо да вървят
едновременно. Моделите могат да бъдат resident, а CTC → Buzz/Whisper да
се изпълняват последователно.

След тестовете се стига до практичната конфигурация:

-   Whisper large-v3 --- GPU;
-   BuzzASR --- GPU;
-   CTC BG+EN --- CPU/RAM.

Това освобождава GPU budget за двата final STT engine-а и избягва
ненужно притискане на 8 GB VRAM.

Това е **реално изследвана STT resource configuration**, но не трябва да
се смесва с бъдещото решение къде ще работи local conversational AI.

------------------------------------------------------------------------

## 20. ModelManager

Разработен е отделен resource/model lifecycle слой.

Цели: - lazy load; - resident model reuse; - acquire/release leases; -
explicit unload; - backend-specific cleanup; - thread/concurrency
safety.

Важно ограничение: текущият ModelManager не трябва да се представя като
завършен global scheduler.

По наличната история той все още няма доказано: - автоматичен VRAM
budget; - LRU eviction; - автоматично gaming-aware unload policy; -
цялостно inference scheduling; - production preloading policy.

Това са бъдещи Resource Manager функции.

------------------------------------------------------------------------

## 21. Wake word / „Аурора" --- реалният development контекст

`Аурора` се появява много късно спрямо началото на проекта.

Следователно: **Аурора ≠ име на проекта.**

Тя е wake word, използвана за разработката на natural voice capture.

Практическата причина е да не се натиска постоянно Enter/бутон по време
на микрофонните тестове и едновременно да започне разработката на
реалния wake flow.

Целевият UX е: `Аурора, намали звука`

без изкуствена пауза между wake word и command.

`AuroraCapture` използва: - continuous microphone stream; - WebRTC
VAD; - pre-roll; - growing-prefix wake checking; - pause/resume на
callback/recording logic; - запазване на цялата phrase.

Wake transcription не трябва да се използва като ground-truth language
detection. В тестовете Whisper понякога интерпретира „Аурора" като други
езици/текстове. За wake layer ни интересува trigger/no-trigger, не
красив transcript.

------------------------------------------------------------------------

## 22. Security модел

Сигурността се появява като системно изискване, не само като login
screen.

Основни правила:

1.  Wake word не е authentication.
2.  Authenticated account/device определя permissions.
3.  Един user може да има няколко устройства.
4.  При нужда може да има device-level restrictions.
5.  Explicit target не заобикаля permissions.
6.  Admin status не заобикаля `VOICE_FORBIDDEN`.
7.  Audit трябва да записва реалния контекст:
    -   account/device;
    -   wake context;
    -   origin;
    -   target;
    -   action;
    -   allow/deny.
8.  Passwords/secrets не трябва да са видими на admins като plaintext.
9.  Remote server не трябва просто да се expose-не като необезопасен
    Python port.
10. Външни cloud/AI providers са отделен trust boundary.

------------------------------------------------------------------------

## 23. Audit/logging

Потребителят свързва personal wake words и акаунтите с възможност да се
следи кой какво е направил.

Архитектурната корекция е важна: логът не трябва да твърди, че voice
identity е доказана само от wake word.

Audit трябва да записва доказуемото: - authenticated device/account; -
използван wake context; - action; - target; - result; - timestamp; -
permission decision.

Това е особено важно за smart-home actions.

------------------------------------------------------------------------

## 24. ON/OFF и privacy на клиента

Потребителят иска в Android app бутон за включване/изключване на
assistant listening, когато човек не желае: - да се хаби battery; - да
се хаби Internet; - да се използват ресурси; - устройството да "слухти".

Това е user-facing privacy/resource control.

Local wake-word detection трябва по принцип да не изисква постоянен
audio stream към server.

------------------------------------------------------------------------

## 25. Network management

По-късно към Admin GUI е добавено управление на network/server access: -
devices; - server connectivity; - reserved addresses; - бъдещи network
settings.

Това трябва да се реализира чрез platform-specific adapters, защото
текущият Windows host е development environment, а бъдещият production
host е Linux.

------------------------------------------------------------------------

## 26. Какво е имплементирано и какво е само концепция

### Реално имплементирано/тествано в Android историята

-   Android microphone recording;
-   local Whisper pipeline;
-   parser;
-   media command routing;
-   Spotify prototype;
-   Spotify App Remote/Web API integration work;
-   Android local fallback concept с реална основа.

### Реално имплементирано/тествано в Windows server/STT историята

-   FastAPI skeleton;
-   system monitoring;
-   multiple STT engines/benchmarks;
-   Buzz/Whisper engines;
-   CTC evidence;
-   resolver;
-   router;
-   `SttService`;
-   model lifecycle/manager;
-   GPU/RAM diagnostics;
-   live capture;
-   VAD;
-   wake-word development;
-   40-file language dataset/calibration.

### Архитектурно договорено, но не доказано като production implementation

-   пълна authentication/account система;
-   multi-user database;
-   Web Admin;
-   Home Assistant integration;
-   multi-home production routing;
-   YouTube provider;
-   generic MediaProvider/PlaybackTarget framework;
-   remote Internet production gateway;
-   TTS engine/model;
-   local conversational AI;
-   full Resource Manager/Gaming policy;
-   final network admin;
-   final audit database;
-   full production `/stt` composition endpoint.

------------------------------------------------------------------------

## 27. Исторически решения, които НЕ трябва да се приемат автоматично за текущи

1.  Конкретен Android Whisper модел --- променян е многократно.
2.  `base.en-q5_1` като общ STT --- достатъчен за ограничени команди, не
    за open-vocabulary media.
3.  Един Spotify account --- валиден само за прототип.
4.  Wake word като identity --- изрично отхвърлено.
5.  Speaker recognition като основен identity layer --- не е избрано.
6.  CTC на GPU --- по-късната изследвана композиция го мести на CPU/RAM.
7.  Local AI задължително CPU-only --- вече не е окончателно решение.
8.  „Аурора" като име на проекта --- неправилно; това е wake word.
9.  Всеки assistant suggestion от стария разговор --- не е user
    requirement, ако няма приемане/потвърждение.

------------------------------------------------------------------------

## 28. Текущо най-точно описание на Smart voice home

**Smart voice home** е local/offline-first, multi-user, multi-device,
multi-home-ready voice assistant platform с централен Assistant Server и
леки клиенти.

Системата трябва да може да: - слуша локален wake word; - приема
свободна реч; - определя езиковия маршрут; - транскрибира
локално/server-side; - разбира и изпълнява команди; - управлява media
providers и playback targets; - управлява позволени Home Assistant
действия; - работи с различни users/accounts/devices; - прилага
permissions независимо от wake word; - използва per-user preferences; -
говори поне български и английски; - работи локално и през Internet; -
запазва offline/local fallback; - отстъпва ресурси при
gaming/натоварване; - поддържа audit; - позволява централизирано admin
управление; - в бъдеще използва local conversational AI и по желание
външни AI providers при подходяща consent policy.

------------------------------------------------------------------------

## 29. Отворени въпроси, които логът не затваря окончателно

1.  Финалният database/schema за users/devices/homes/permissions.
2.  Точният authentication/token protocol.
3.  Финалната remote-access технология.
4.  Точният arbitration protocol, когато няколко устройства чуят една и
    съща wake phrase.
5.  Финалният general wake-word policy.
6.  Финалният TTS модел и voice.
7.  Финалната local-AI model/resource стратегия.
8.  Финалният Web Admin stack.
9.  Точната Home Assistant permission mapping.
10. Финалният MediaProvider/PlaybackTarget API.
11. Production composition root на server-а.
12. Production `/stt` endpoint.
13. Независима validation на CTC thresholds.
14. Качеството на MIXED fallback за български.
15. Production Resource Manager policy.
16. Какви части от Android клиента ще останат локални след server
    integration.
17. Как точно се синхронизират profile/preferences между устройства.
18. Как се решава ownership на shared room endpoints.
19. Как се обработва explicit online consent по видове external
    providers.
20. Backup/restore/versioning на server configuration и user data.

------------------------------------------------------------------------

## 30. Най-важната възстановена архитектурна верига

Цялата платформа може да се мисли като:

**Wake / Push-to-talk**\
→ **Origin device context**\
→ **Authenticated account/device**\
→ **Personal/General wake context**\
→ **Audio capture**\
→ **STT language evidence**\
→ **STT routing**\
→ **Transcript**\
→ **Intent / conversational routing**\
→ **Permission policy**\
→ **Preference/context layer**\
→ **Provider/integration**\
→ **Explicit/default target resolution**\
→ **Action**\
→ **Response/TTS**\
→ **Audit**

Resource Manager стои напречно на тежките server компоненти и решава
какво може да бъде заредено/изпълнено спрямо CPU/RAM/GPU/VRAM и текущото
натоварване.

------------------------------------------------------------------------

## 31. Хронологичен master outline

### 29 август --- начална Android/offline STT линия

Whisper за Bulgarian → Android feasibility → resources → първи MVP →
mic/Whisper/parser/media.

### Следващите Android итерации

Build/debug → command parser → media control → Spotify search → Spotify
Developer → App Remote/Web API → по-добро media execution.

### 14 септември --- възобновяване на Android проекта

Blackview Tab 16 Pro → стабилизиране на build/Whisper → parser/STT/media
тестове.

### След това --- архитектурният прелом

Open-vocabulary media показва лимита на mobile STT → идея за RTX server
→ потребителят добавя remote Internet, multi-user, future clients,
resource-awareness.

### Platform design

Home Assistant → multi-home → security → per-user Spotify → YouTube →
ON/OFF → multi-device routing → personal wake words → general wake word
→ permissions/device identity → GUI/preferences → multilingual profile →
admin control → TTS → network management → Windows→Linux portability.

### Windows AssistantServer

Server skeleton → STT benchmark → BG/EN model selection → language
routing → CTC → `SttService` → lifecycle/ModelManager → resource
diagnostics → live capture → wake word → `AuroraCapture` →
production-like dataset → resolver calibration.

### 22 септември

Реконструкция на проекта от forensic archive/PDF/memory → открит пълен
`VoiceAssistant_ChatLOG.txt` → настоящата master reconstruction.

------------------------------------------------------------------------

## 32. Правила за бъдеща работа по проекта

За да не се повтори загубата на контекст:

-   този документ трябва да служи като **историческа/концептуална
    основа**;
-   отделен `PROJECT_STATE.md` трябва да съдържа само реалното текущо
    състояние;
-   отделен `DECISION_REGISTER.md` трябва да пази решенията и superseded
    решенията;
-   отделен `EVIDENCE_MAP.md` трябва да сочи към log/code/test evidence;
-   `OPEN_QUESTIONS.md` трябва да съдържа само нерешените точки;
-   ново решение не трябва да се счита за окончателно, докато не бъде
    записано;
-   assistant proposal ≠ user requirement;
-   code existence ≠ production integration;
-   diagnostic script ≠ measured result, ако stdout/result не е запазен;
-   calibration set ≠ independent validation set.

------------------------------------------------------------------------

## 33. Статус на тази реконструкция

Този документ е **пълна концептуална реконструкция на основните проектни
решения и развитието им от целия наличен VoiceAssistant_ChatLOG.txt**.

Той умишлено не копира дословно десетките хиляди редове build output,
replacement source code и повтарящи се диагностични инструкции. Те
остават в оригиналния лог като forensic evidence. Нито една такава
нискониво итерация не трябва да бъде загубена при бъдещ audit, но
повтарянето ѝ дословно тук би скрило архитектурните решения.

Следващата документална стъпка е тази реконструкция да бъде разделена
на: 1. `PROJECT_MASTER.md` 2. `PROJECT_STATE.md` 3. `PROJECT_HISTORY.md`
4. `DECISION_REGISTER.md` 5. `EVIDENCE_MAP.md` 6. `OPEN_QUESTIONS.md`

След получаването на официалния ChatGPT export той трябва да бъде
сравнен срещу този лог, а не да замести автоматично тази реконструкция.
