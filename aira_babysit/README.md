# AI Babysit Auto Runs v0.1

**Отдельный возобновляемый worker и панель управления. Это не «чат сам работает в фоне» и не уже завершённый цикл обучения новой LM.**

## Что работает сейчас

Реальная локальная LM → проверка ответов на TRAIN-задачах → проверенный offline
teacher target → SFT-пакет + Kaggle notebook → **WAITING_TRAINING** и выход процесса.

SQLite checkpoints, budget, pause/stop/resume, process leases и общий file lock,
проверка source/data/model hashes. Закрытие чата/вкладки не останавливает worker,
если его процесс и среда продолжают работать. Данные бесед пользователя не собираются.

**Текущий teacher — проверяемая синтетика арифметики/JSON, не сильный AI.**
Этот чат не является callable API. external_required без провайдера блокируется,
а не подменяется слабой LM. Платных внешних вызовов по умолчанию0.

## Быстрый запуск

Сначала должен работать обычный student server:

```bash
bash aira_local/setup.sh
bash aira_local/run.sh
```

В другом процессе:

```bash
.venv/bin/python -m aira_babysit run --budget-seconds 3600 --max-examples 128
```

Это **максимум час активного worker wall time**, не обязанность заполнять час
ожиданием. Если задачи закончились или нет следующего backend, worker прекращает
вычисления и сообщает точную стадию. Serving модель использует свой single-operation
gate; busy повторяется ограниченно, затем WAITING_RESOURCE, не бесконечный spin.

Более удобный вариант:

```bash
bash aira_babysit/run.sh
```

В Arena откройте **Live Preview → AI Babysit — Auto Runs**. UI работает и во
встроенном iframe, не использует native form submission. На своей машине
после запуска откройте localhost:8001. Браузер не обращается к чужому localhost:
student API8000 вызывается только серверным worker.

## Управление

Команда run печатает RUN_ID:

```bash
.venv/bin/python -m aira_babysit status RUN_ID
.venv/bin/python -m aira_babysit events RUN_ID
.venv/bin/python -m aira_babysit pause RUN_ID
.venv/bin/python -m aira_babysit resume RUN_ID
.venv/bin/python -m aira_babysit stop RUN_ID
```

Default registry/artifacts: `artifacts/aira_babysit/`. Другой каталог:
`python -m aira_babysit --runs-root /approved/path status`.
Сохраните этот каталог/экспорт перед уничтожением VM. SQLite переживает рестарт
worker, **не гарантирует сохранность после удаления самой песочницы**.

Нельзя менять spec, task pools, verifier/trainer/source в середине запуска.
При несовпадении SHA resume прекращается. Для новой версии — новый run или явная
отдельная миграция; старый run не «чинится» изменением результатов.

## Статусы — результат определяется ими

| Статус | Что означает |
|---|---|
| NEW / COLLECTING | задачи и реальные ответы ученика |
| PAUSED / STOPPED | явный control; завершённые записи сохранены |
| WAITING_RESOURCE | модель/другой worker заняты; вычисления прекращены |
| BLOCKED_TEACHER | нужного учителя нет, не делаем вид что он подключён |
| BUDGET_EXHAUSTED | суммарный активный бюджет исчерпан |
| FAILED | ошибка, детали в events/worker.log |
| WAITING_TRAINING | пакет готов, **обучение LM не выполнено**, процесс завершён |

`training_executed=false`, `learning_cycle_complete=false`, пока реального
обучающего backend здесь не было. Crash recovery может добавить **отдельно
помеченный консервативный budget charge**, не выдаваемый за измеренный CPU-time.

## Kaggle handoff

У WAITING_TRAINING доступны **bundle ZIP** и **per-run notebook** с exact bundle SHA.
В iframe браузер может запретить attachment download — откройте preview отдельно.
ZIP не содержит final holdout. Внутри:

- `babysit_train.jsonl` — ошибки TRAIN-ученика и детерминированный replay;
- `teacher_sft_control.jsonl` — plain teacher SFT control, не claim равных FLOPs;
- `development.jsonl` — только проверка, не обучение;
- run spec, file manifest и реальный LoRA job target.

Notebook: безопасное извлечение/checksum → pinned dependencies → фиксация actual
HF revision ДО обучения → отдельный ограниченный training subprocess → checkpoints
и candidate receipt. Выбранный public model —135M control; это не лучшая будущая
русская модель и не утверждение о frontier качестве.

**GPU-часть здесь НЕ запускалась.** Выполнены только bundle preflight, pure-Python
loss-mask tests, syntax/notebook checks. Kaggle trainer требует CUDA и не имитирует
обучение при отсутствии backend. На Kaggle интернет/веса/зависимости/GPU ещё нужно
проверить реальным небольшим прогоном перед полноценным часовым запуском.

Resume использует полный hashed checkpoint и собственное безопасно загружаемое
optimizer state. Сохраняйте Kaggle outputs/version отдельно: /kaggle/working не
является вечным хранилищем. Сначала требуется один ручной запуск notebook; API
автозапуск Kaggle из Arena в этой версии НЕ реализован.

## Не реализовано / не следует путать с результатом

- Нет callable сильного учителя/API из текущего чата; offline teacher узкий.
- Нет выполненного GPU SFT, полной повторной learning-loop и языкового улучшения.
- Нет импорта нового GGUF/независимого holdout+CPU-resource gate и автопубликации
  candidate в live chat. Candidate receipt не является таким разрешением.
- Нет автономного исследователя, который сам меняет архитектуру/код/eval.
  Worker исполняет утверждённый recipe; гипотезы и допуски задаются до него.
- Нет гарантии точного hard deadline внутри произвольного native/GPU вызова;
  controls кооперативны, notebook дополнительно ограничивает дочерний процесс.
- Это локальный общий demo control-plane без production-auth. Не вводите секреты.

## Что реально проверено

```bash
.venv/bin/python -m pytest aira_babysit/tests -q
node aira_babysit/browser_check.cjs
```

Unit fixtures явно используют fake student **только для тестов workflow**, не
для model-quality evidence. Отдельно реально выполнены CLI и browser runs на
настоящей SmolLM: сбор, pause/resume,12 уникальных committed task IDs, проверенные
teacher targets, отсутствие holdout в ZIP, WAITING_TRAINING без fake optimization.
[Фактический отчёт](results/report.md), [протокол](PROTOCOL.md), [журнал](work_log.md).

Для полного цикла следующие обязательные gates: реальный Kaggle smoke → внешний
teacher adapter/утверждённый teacher corpus → независимая candidate evaluation/
CPU resource checks → явная promotion policy. Только после этого допустимо
включать многораундовое автоматическое улучшение и называть цикл замкнутым.
