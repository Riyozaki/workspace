# Autonomous Babysit v0.1 — фактический статус

## Один честный итог

**Реально работает автономная data/handoff стадия. Полный учебный цикл пока НЕ замкнут.**
Реальная языковая SmolLM2 отвечает через действующий student API; worker проверяет
TRAIN-примеры, формирует verified teacher targets и экспортирует Kaggle package.
По завершении **WAITING_TRAINING**, `training_executed=false`,
`learning_cycle_complete=false`, `production_promoted=false`.

## Выполненный интеграционный запуск

- Run ID `f270246ca9e74222`, бюджет3600 активных wall seconds,12 TRAIN попыток.
- Реальный CLI/process, не unit fixture. В browser приостановлен после
  **1** committed примера, затем возобновлён.
- Итог **12** уникальных committed task IDs,
  duplicate commits=0, **12** verified teacher targets.
- Active worker wall: **15.143745 с**, не «час работы».
  Задачи закончились — worker не тратил остаток на искусственное ожидание.
- Ученик прошёл **0/12** строгих проверок
  этого синтетического УЧЕБНОГО пула. Это не independent benchmark, не dataset
  для всех навыков и не утверждение о качестве будущей обученной модели.
- ZIP SHA `495698e56425408ae6f6555ff0b79200dd354639a3bc945e7bdcd5824f984bda`;12,218bytes в этом наблюдённом пакете.
  Holdout не вошёл в ZIP. Per-run notebook содержит этот точный SHA.
- Native LM weights не менялись; teacher не является сильным LLM/API.

[Actual smoke](live_smoke.json), [browser checks](browser_checks.json),
[raw TRAIN episodes](live_run/episodes.jsonl), [events](live_run/events.jsonl),
[frozen run spec](live_run/spec.json), [bundle manifest](live_run/bundle_manifest.json).

Дополнительно настоящий HTTP поток был приостановлен тестовой инструментализацией
на первом checkpoint:0 committed до паузы,2 после resume, дубликатов0.
Native student/API не mocked. [Проверка](real_stream_pause.json).

## Проверки кода

- Общий suite существующего приложения + нового worker: **88passed**, один
  сохранённый dependency DeprecationWarning. [Лог](combined_tests.txt).
- Из них новый pipeline имеет23 теста; workflow unit fixtures с fake student
  явно отделены от real-model integration. Они не доказывают качество LM.
- Старые10 transport tests также выполнены: [лог](transport_tests.txt).
- Проверены cumulative budget, pause/resume, stop, lock/lease/recovery,
  immutable spec/data/source, missing-teacher block, no-training success without
  backend, target-only loss mask, pad mask, bundle integrity/holdout exclusion,
  notebook syntax/empty outputs, URL guards и controls.
- Пакетный `kaggle_train.py --check-bundle` действительно выполнен **без Torch**:
  [результат](bundle_preflight.json). Это проверка пакета, не optimizer step.

## Что не выдаётся за выполненную работу

| Компонент | Статус |
|---|---|
| Бюджет/SQLite/real student/corrections/export | выполнено и проверено |
| Проверяемый offline teacher арифметики/JSON | выполнено, узкий synthetic curriculum |
| Сильный AI teacher, callable текущий чат | не подключён/такого API у чата нет |
| GPU LoRA SFT | code/notebook target, **не выполнен/не интеграционно проверен** |
| Фактический gradient test на GPU/backbone | требует первого реального Kaggle smoke |
| API-запуск Kaggle из Arena | не реализован; первый notebook launch ручной |
| Candidate import/independent holdout+CPU gate | не реализовано |
| Auto-promotion/следующий on-policy round | не включено, learning_cycle_complete=false |

Код GPU target содержит checkpoint/resume, assistant-target loss masking,
nonzero-gradient assertions, frozen revision, baseline/candidate dev проверки,
cooperative budget и candidate-only receipt. Присутствие кода не заменяет его
проверки на реальном GPU. После learning надо отдельно проверить вернувшийся
checkpoint; собственные отчёты trainer нельзя считать независимой оценкой.

## Границы автономности и безопасности

Процесс worker не зависит от открытой вкладки/текущего ответа чата, но зависит от
живой среды и доступного student API. SQLite под ignored artifacts переживает
restart worker в том же сохранённом каталоге, не уничтожение самой песочницы.
Kaggle outputs нужно сохранить отдельно. No credentials/logged tokens; default
paid/remote teacher calls=0. Нет model-generated shell/code execution.

Это общий локальный demo control-plane без production-auth. Native/GPU операции
отменяются кооперативно; notebook дополнительно ограничивает subprocess. Нет
идеального жёсткого time/power isolation и гарантий чужого target-device.

[Протокол](../PROTOCOL.md), [команды](../README.md),
[контракт автономной сессии](../AUTONOMOUS_SESSION.md).
