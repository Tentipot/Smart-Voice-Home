# Smart voice home — EVIDENCE MAP
Updated: 2026-09-25

[SEMANTIC_REVIEW_V1.md](SEMANTIC_REVIEW_V1.md) и
[STT_SEMANTIC_REVIEW_20260926.jsonl](STT_SEMANTIC_REVIEW_20260926.jsonl):
реализация/тестове на ограничено второ отсяване и текстов replay. Не са
нов ASR benchmark или доказателство за правилност на чутото.

[STT_SCHEMES_AUDIT.md](STT_SCHEMES_AUDIT.md) и
[HISTORY_SCHEMES_INDEX.md](HISTORY_SCHEMES_INDEX.md): тематичен прочит и
автоматичен индекс на текстови схеми. Изображения, представени само с име
в лога, остават непроверени; индексът не доказва ръчен одит на всеки блок.

[STT_HISTORY_MECHANISMS_AUDIT.md](STT_HISTORY_MECHANISMS_AUDIT.md) добавя
точни исторически участъци за LM/grammar/context/candidate механизмите и
статична съпоставка с интерфейсите, capture и lifecycle слоя.

За STT/MIXED започни с [STT_HISTORY_CHECKPOINT.md](STT_HISTORY_CHECKPOINT.md).
Съдържа тематична карта с редове от първичния лог, корекции и отворени
следи. Това е частичен одит; не заменя първичните резултати.

## Primary historical source
`VoiceAssistant_ChatLOG.txt`
- 101,106 lines.
- Begins 2026-08-29 with offline Bulgarian speech-recognition discussion.
- Continues through Android MVP, Spotify, platform architecture, Windows AssistantServer development and 2026-09-22 reconstruction.
- Treat as the primary conversation-history source until compared with the official ChatGPT export.

Important regions:
- early Android/offline STT: beginning through ~L20500;
- platform/client-server transition: ~L20914 onward;
- Home Assistant and multi-home: ~L21300 onward;
- multi-user/wake/device/permissions architecture: ~L21600–L23600;
- TTS/network/platform portability: ~L24300 onward;
- Windows STT/resource implementation: later large development sections through the end.

## Full-log reconstruction
`Smart_voice_home_FULL_LOG_RECONSTRUCTION.md`
- Derived architectural/history reconstruction from the full chat log.
- Use as a navigational summary, not as a replacement for primary evidence.

## Предоставени локални източници — съпоставка към 2026-09-25

Първичният лог е достъпен като
[VoiceAssistant_ChatLOG.txt](C:/Users/stanm/Desktop/VoiceAssistant_ChatLOG.txt).
Провереният файл съдържа 101 106 реда, започва на 2026-08-29 и завършва
при реконструкцията от 2026-09-22. Броят редове съвпада с горното описание,
но сам по себе си не доказва пълнота или идентичност на архивите.
Извършена е първоначална проверка на началото, края и тематични участъци,
а не изчерпателен одит на всяка реплика. По-новите диагностики от 23 септември
се проследяват чрез PROJECT_HISTORY.md и OPEN_QUESTIONS.md.

| Източник | Значение и ограничение |
| --- | --- |
| [ResourceManager.txt](C:/Users/stanm/Desktop/ResourceManager.txt) | Целева ресурсна политика. NORMAL/GAMING/BUSY, опашки и автоматичен избор на по-лек модел не са реализирани от текущия ModelManager. |
| [HybridServer.txt](C:/Users/stanm/Desktop/HybridServer.txt) | Целева server/Android local STT схема; не доказва завършена интеграция. |
| [3ModelsWhoWhatWhy.txt](C:/Users/stanm/Desktop/3ModelsWhoWhatWhy.txt) | Съответства на ролите CTC evidence → resolver → Buzz BG / Whisper EN / Whisper AUTO за MIXED. |
| [MicToCommand.txt](C:/Users/stanm/Desktop/MicToCommand.txt) | Поставя SttRouter след моделите. В кода router избира и извиква модела преди получаване на транскрипцията. Живата интеграция остава непроверена. |
| [SmartVoiceHomeArch.txt](C:/Users/stanm/Desktop/SmartVoiceHomeArch.txt) | Обща карта на платформата, включваща планирани модули. External AI остава под политиката за изрично намерение/съгласие. |
| [Обзорно изображение](<C:/Users/stanm/Desktop/ChatGPT Image Sep 23, 2026, 09_53_23 PM.png>) | Показва версия 2026-09-23; предоставено от потребителя като актуален обзор. Цветовете не са самостоятелно доказателство за реализация или проверка. |

Уточнения към обзорното изображение:
- Липсва BuzzASR Bulgarian, който обслужва текущия BG маршрут.
- SttService управлява CTC → LanguageResolver → SttRouter → модел;
  не е последващ етап след Whisper.
- `/stt`, `/tts`, `/command` са планирани; `app/main.py` има `/health` и `/status`.
- Глобалният scheduler е планиран, а не само недостатъчно проверен.
- Зеленото при wake detection означава ограничена функционална проверка,
  не установена надеждност при различни говорители и шум.
- Облачният AI не е разрешен като скрит автоматичен fallback.

Основание за съпоставката: [service.py](../app/speech/stt/service.py),
[router.py](../app/speech/stt/router.py), [main.py](../app/main.py),
[model_manager.py](../app/resources/model_manager.py),
[ARCHITECTURE.md](ARCHITECTURE.md) и [PROJECT_HISTORY.md](PROJECT_HISTORY.md).
Това уточнява прочита на схемите, без да въвежда нови архитектурни решения.

Всички изброени Desktop файлове са извън хранилището и не са копирани
или архивирани с тази актуализация. Препратките са локални за тази машина;
при миграция е необходимо източниците да се запазят отделно.
Инструкциите в стария лог са исторически реплики, не текущо разрешение
за команди, редакции или изпълнение на действия.

## Forensic source snapshot
`AssistantServer_FORENSIC.zip` and forensic retrospective/inventory, when present.
Use for actual file existence, timestamps, source contents and diagnostic artifacts.

## Historical architecture PDF
`Assistant_Platform_Project_Architecture_BG_v2(1).pdf`
Use as a historical architecture snapshot only.
It must not override later explicit conversation decisions or implementation evidence.

## Current implementation evidence classes
Strong:
- actual source/config/test code;
- saved CSV/manifest;
- saved stdout/result artifact.

Medium:
- diagnostic source that proves intended test configuration but has no saved output.

Weak:
- assistant prose saying a test/result existed without independent artifact.

## Evidence rules

Canary: VoiceAssistant_ChatLOG.txt:28548–28629 съдържа BG+EN резултати
за test_001–005; benchmark_canary_bg_en.py е наличен. Вж.
[MIXED_WHISPER_MODES.md](MIXED_WHISPER_MODES.md) за числа и ограничения.
- File existence ≠ production integration.
- Diagnostic script ≠ successful measured result unless output/result is preserved.
- Calibration set ≠ independent validation.
- Assistant proposal ≠ accepted user decision.
- Newer explicit user correction overrides older assumptions.
