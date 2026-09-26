# tools/

Помощни скриптове извън production кода (`app/`). Преместени от корена на
проекта на 2026-09-26 с `git mv`; историята им е запазена.

| Папка | Съдържание |
| --- | --- |
| `validation/` | Събиране на validation записи, runner, семантичен review, MIXED сравнения |
| `datasets/` | Запис и етикетиране на аудио набори |
| `analysis/` | Офлайн анализ на CTC резултати и проверка на праговете |
| `diagnostics/` | Диагностики на модели, VRAM, capture, wake и живия STT |
| `benchmarks/` | Исторически сравнения на модели (включително стари `test_*` скриптове, които зареждат модели) |

Unit тестовете без модели и хардуер са в `../tests/`.

## Стартиране

Винаги от корена на проекта, като модул:

```powershell
.\.venv\Scripts\python.exe -B -m tools.validation.collect_stt_validation --list
.\.venv\Scripts\python.exe -B -m tools.diagnostics.diagnose_live_production_stt
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -t .
```

Директно `python tools/.../script.py` няма да намери пакета `app`.
Преди стартиране провери дали скриптът зарежда модели, използва микрофон/GPU
или записва файлове (AGENTS.md).
