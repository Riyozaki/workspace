# Как задавать автономную сессию

## Две разные роли

- **Агент-исследователь в Arena:** формулирует/реализует утверждённые изменения,
  готовит teacher-материал, анализирует результаты и публикует воспроизводимый код.
  Текущий чат не превращается в постоянно доступный API после завершения ответа.
- **Worker:** исполняет зафиксированный recipe без открытого чата. Не меняет сам
  код/eval/критерии, не покупает ресурсы и не объявляет обучение выполненным по таймеру.

## Контракт до запуска

1. Цель/проверяемая гипотеза и ожидаемый артефакт.
2. Утверждённые model/dataset/evaluator hashes и семейства train/development/holdout.
3. Верхние бюджеты wall time, student/teacher calls, tokens, optimizer steps и RAM.
4. Разрешённые изменения; запрет менять frozen eval и смотреть final holdout для tuning.
5. Teacher/trainer/evaluator adapters, реальные требования к ресурсам и цена.
6. Stop/rollback conditions и кому можно разрешить promotion.

Пример локального запуска текущей стадии:

```bash
.venv/bin/python -m aira_babysit run --budget-seconds 3600 --max-examples 128
```

128 — лимит учебных попыток, не128 независимых quality tests. Verified teacher
узкий. После data package worker прекращает вычисления WAITING_TRAINING.
Если исчерпаны ресурсы/нет учителя/ошибка — статус соответственно WAITING_RESOURCE,
BLOCKED_TEACHER или FAILED, а не фальшивый DONE.

## Сохраняемый результат

- immutable spec + SHA и data pools;
- raw student attempts, проверка и teacher target с источником;
- append-only SQLite events (UI/CLI показывают последние100, DB хранит все);
- checkpoints, active-wall budget и отдельно консервативные recovery charges;
- package manifest, точный ZIP SHA и notebook без executed-output фикции;
- явные training_executed / learning_cycle_complete / promotion flags.

Worker может остановиться раньше верхнего бюджета: нет смысла вырабатывать час,
если следующая операция невозможна. Backoff/foreground yield видимы и входят в
WALL budget, но не называются вычислительным ускорением.

## Как замыкается полная учебная петля (следующие gates)

`train tasks → реальные student replies → сильный/верифицированный teacher → SFT
→ independent candidate eval + CPU resource gate → registry acceptance/rollback
→ новый on-policy curriculum`.

В v0.1 исполняется первая часть до SFT-handoff. Kaggle job target подготовлен,
но GPU integration не проверена. Его receipt — только кандидат, не разрешение
на deployment. API submission Kaggle, импорт/конверсия checkpoint, независимая
candidate evaluation и автоматическое многораундовое возвращение пока не реализованы.
Они должны быть испытаны до утверждения «полный цикл работает сам».

После подготовки инфраструктуры один ручной запуск Kaggle notebook должен
передавать управление обычному training worker: он сохраняет checkpoints и
завершает работу по бюджету/ошибке. Потеря несохранённой VM/session не является
обычным restart процесса: внешнее сохранение outputs необходимо отдельно.
