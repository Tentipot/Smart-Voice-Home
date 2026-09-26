# Smart voice home — Project memory package

Checkpoint: 2026-09-22

Най-нов етап: [SEMANTIC_REVIEW_V1.md](SEMANTIC_REVIEW_V1.md) — реализирано
ограничено второ отсяване след STT, тестове и replay върху запазените текстове.
Пълният resolver още липсва; по-долните бележки описват предходните етапи.

Текущо продължение — 2026-09-26: SttService има `transcribe_with_evidence()`;
предаването на aggregate evidence след STT е реализирано. Семантичният
филтър още липсва. Вж. PROJECT_STATE.md. По-долната задача за исторически
одит е предходният checkpoint.

Последна документална актуализация: 2026-09-25.
Историческият checkpoint по-горе е запазен; текущата точка за продължаване
е в [PROJECT_STATE.md](PROJECT_STATE.md). Предоставените лог и схеми,
локалните им пътища и установените ограничения са в
[EVIDENCE_MAP.md](EVIDENCE_MAP.md). Това е първоначална съпоставка,
а не завършен изчерпателен одит на историята.

Recommended reading order:
1. PROJECT_MASTER.md
2. ARCHITECTURE.md
3. PROJECT_STATE.md
4. DECISION_REGISTER.md
5. OPEN_QUESTIONS.md
6. PROJECT_HISTORY.md
7. AUDIO_DATASETS.md
8. EVIDENCE_MAP.md
9. Smart_voice_home_FULL_LOG_RECONSTRUCTION.md

[Одит на схемите](STT_SCHEMES_AUDIT.md) проследява отсяването преди/след
STT и разликите с capture, ресурси, media и permissions.
[Индексът](HISTORY_SCHEMES_INDEX.md) дава директни места в целия текстов лог.

Текуща точка за продължаване: **по-дълбок исторически одит преди нови STT
експерименти**. За всяка STT/MIXED задача първо прочети
[STT_HISTORY_CHECKPOINT.md](STT_HISTORY_CHECKPOINT.md): проверени находки,
корекции, конкретни редове в лога и оставащи исторически следи.
Схемата за времеви езиков анализ още не е възстановена изчерпателно.
Продължение: [одит на STT механизмите](STT_HISTORY_MECHANISMS_AUDIT.md) —
CTC+LM, grammar/context, каскади и разлики между предложенията и текущия код.

Налични диагностични материали (не автоматичен план за следваща задача):
[STT_VALIDATION_PLAN.md](STT_VALIDATION_PLAN.md) — предложен пилот с нови
BG/EN/MIXED записи, референции и показатели. Първият baseline е в
[STT_VALIDATION_PILOT_01_RESULTS.md](STT_VALIDATION_PILOT_01_RESULTS.md).
Разширеният runner записва отделно CTC, route/reason, времена и VRAM;
смисловата оценка на командите остава ръчна.

[MIXED_WHISPER_MODES.md](MIXED_WHISPER_MODES.md) — BG/EN/multilingual
резултати, исторически Canary тест и резервното продуктово предложение.

[MIXED_WHISPER_AUTO_COMPARISON.md](MIXED_WHISPER_AUTO_COMPARISON.md) —
директно Whisper AUTO сравнение, включително критичното обръщане при MX04.

This package preserves the previous HISTORY archive contents and adds the structured project-memory documents above.
