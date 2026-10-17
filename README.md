# AIra — текущий локальный прототип и архив исследований

## Новый компонент: AI Babysit Auto Runs

**Рабочий автономный data-worker и панель управления — не уже замкнутый цикл обучения.**

- **[Описание/команды](aira_babysit/README.md)**, **[фактический статус](aira_babysit/results/report.md)**.
- [Контракт автономной сессии](aira_babysit/AUTONOMOUS_SESSION.md), [протокол](aira_babysit/PROTOCOL.md).
- [Реальные browser/worker проверки](aira_babysit/results/browser_checks.json), [smoke](aira_babysit/results/live_smoke.json).

```bash
# Student server должен уже работать: bash aira_local/run.sh
bash aira_babysit/run.sh
# Либо один автономный запуск с верхним бюджетом час:
.venv/bin/python -m aira_babysit run --budget-seconds 3600 --max-examples 128
```

В Arena: **Live Preview → AI Babysit — Auto Runs**, порт8001. Чат остаётся на8000.
Бюджет, pause/stop/resume, SQLite checkpoints, frozen hashes и real student calls
проверены. Реальный12-example run был приостановлен после1 committed записи,
возобновлён без duplicate commits и завершил data-phase в **WAITING_TRAINING**.

Текущий учитель — узкая проверяемая синтетика, **не сильный API-учитель и не текущий чат**.
Пакет/точно-hashed Kaggle notebook создаются, но GPU-тренировка здесь не запускалась.
`training_executed=false`, `learning_cycle_complete=false`; candidate evaluation,
импорт/promotion и повторные учебные раунды ещё не реализованы. Worker прекращает
работу, если нет следующего backend, а не симулирует «работал час».

## Актуальная работа: AIra Local Lab v0.2

**Работающий веб-прототип с настоящей маленькой языковой моделью на CPU. Это ещё не новая языковая архитектура AIra и не агент уровня сильной облачной модели.**

- Предобученная **SmolLM2-135M-Instruct Q4_1** через llama.cpp: реальная потоковая генерация, один native inference thread, без GPU/стороннего модельного API.
- В выполненных HTTP-пробах RSS веб-процесса — около **208 MiB**. Это наблюдение в Arena backend, не гарантия для другого устройства, не вся память системы и не измерение энергии.
- Калькулятор и поиск по переданным заметкам подписаны отдельно: их результаты не приписываются языковой модели.
- Пилот **AI Babysit** действительно обучает маленький intent-router. При ухудшении development новые веса отклоняются. Веса языковой SmolLM2 пока не дообучались.
- **Отрицательные результаты сохранены:** слабый русский/факты/формат у 135M модели, плохое обобщение роутера, отсутствие преимущества recurrent-router над линейным контролем. Автоматическая маршрутизация экспериментальная и выключена по умолчанию.

### Исправление отправки сообщений (v0.2)

Отправка кнопкой и Enter больше не зависит от `allow-forms` внешнего iframe.
Добавлены явные ошибки связи, reconnect/retry, сохранение черновика и восстановление
после отмены/обрыва потока. Производитель ответа сам освобождает ресурсную блокировку.

Если открыта старая страница, обновите Live Preview один раз: в шапке `PROTOTYPE 0.2`.
**[Текущий review и доказательства](aira_local/results/review_001/report.md)**;
[реальная browser-регрессия во встроенном фрейме](aira_local/results/review_001/browser_checks.json).
Исторический [отчёт первого прототипа](aira_local/report.md) и отрицательные ML-результаты
не переписаны. Эта версия исправляет работоспособность, не качество языковой модели.

### Запуск и проверка

```bash
bash aira_local/setup.sh
bash aira_local/run.sh
```

В Arena откройте **Live Preview → AIra Local Lab**, порт8000. На своём компьютере после запуска откройте `http://localhost:8000`. Preview выполняет модель в CPU-песочнице Arena, **не в браузере пользователя**. Во время генерации внешний модельный API не используется; setup скачивает pinned GGUF из PyPI с проверкой SHA-256.

| Материал актуального прототипа | Путь |
|---|---|
| Описание и команды | **[aira_local/README.md](aira_local/README.md)** |
| Что реально получилось и что не получилось | **[текущий review](aira_local/results/review_001/report.md)**; [исходный отчёт v0.1](aira_local/report.md) |
| Расчёты и границы вывода | [research.md](aira_local/research.md), [PLAN.md](aira_local/PLAN.md) |
| Реальные LM/API-пробы | [runtime_api_probes.json](aira_local/results/runtime_api_probes.json), [model_smoke.json](aira_local/results/model_smoke.json) |
| Все шесть запусков своей маленькой модели | [router_ablation.json](aira_local/results/router_ablation.json) |
| Browser-проверка реального обучения/rollback/cancel | [browser_checks.json](aira_local/results/browser_checks.json) |
| Исходники | [app.py](aira_local/app.py), [engine.py](aira_local/engine.py), [router.py](aira_local/router.py), [guard.py](aira_local/guard.py) |
| Данные учителя | [router_pilot.jsonl](aira_local/data/router_pilot.jsonl), [SFT seed JSONL](aira_local/data/babysit_seed.jsonl) |
| Происхождение весов / лицензии | [model_manifest.json](aira_local/model_manifest.json), [THIRD_PARTY.md](aira_local/THIRD_PARTY.md) |
| Журнал | [aira_local/work_log.md](aira_local/work_log.md) |

Реально выполнены Python tests и desktop/mobile browser checks. Подробности/ограничения в README прототипа. Большой Kaggle language-model trainer пока не реализован и не запускался. Запуск маленькой модели не доказывает, что при масштабировании будет достигнуто желаемое качество.

## Историческое исследование: Fashion-MNIST / RBF-SVM

Это **отдельный завершённый эксперимент**, не результат текущего языкового прототипа и не его ускорение.

- [Описание](competition50x/README.md), [отчёт](competition50x/report.md).
- [Пять первичных пар](competition50x/results.csv), [журнал](competition50x/work_log.md), [checkpoints](competition50x/checkpoints.md).
- [Протокол](competition50x/protocol.md), [eval.py](competition50x/eval.py), [исходная фиксация](competition50x/protocol_frozen.json).
- [Полное свежee воспроизведение](competition50x/results/fresh_reproduction_index.json).

Его единственный первичный результат —45,7854× на полном инференсе конкретной предобученной SVM, качество сохранено на локальном holdout. Порог50× не достигнут. Он не доказывает ускорения LLM/обучения и не даёт кредита текущему AIra Local Lab.

## Первый цикл: Kronecker-GP — архив

Корневые [report.md](report.md), [results.csv](results.csv), [work_log.md](work_log.md), код [tensor_gp/](tensor_gp/) и команда `bash reproduce.sh` относятся **к первому GP-исследованию**, а не к текущему приложению.

Нужны полная обучающая декартова сетка, подходящее ядро и скалярный шум. Преимущество перед специализированными linear_operator/GPyTorch не измерено. Более поздние эксперименты не устраняют эти ограничения и не пересчитывают старые результаты.

Численные исходники, отчёт, первичные измерения и ожидаемые SHA обоих исторических исследований **не переписаны**. Изначальный корневой README сохранён побайтно в [архивной копии](research/archive/README.stage1.original.txt); исторический снимок — [c526490](https://github.com/Riyozaki/workspace/tree/c526490855c6fd6ac45d35cec49e65cf7472cf37).

## Комплектность и публикация

[publication.json](publication.json) разделяет **latest_delivery** (прототип) и **latest_research_study** (последнее отдельное исследование). Там же описан архивный путь исходного README для проверки его исторического SHA.

```bash
python3 scripts/verify_publication.py
bash scripts/publish.sh "Publish verified AIra updates"
```

Проверка использует стандартную библиотеку: проверяет запечатанные файлы исторических исследований, payload актуального приложения, frozen evaluator/source и первичные CSV. Она не превращает отрицательные результаты прототипа в положительные и не является внешней научной сертификацией.

Скрипт публикации добавляет все неигнорируемые изменения, проверяет staged bytes, коммитит, пушит только рабочую ветку и подтверждает совпадение remote/local SHA и чистоту дерева. Правило доставки — [AGENTS.md](AGENTS.md). Крупные веса/corpora/runtime/cache остаются вне Git и создаются setup-командой.
