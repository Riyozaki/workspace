# Что лежит в `results/`

Все файлы — машинно-сгенерированные артефакты; ничего не редактировалось вручную.
Проверки: `python experiments/check_artifacts.py` и `python experiments/verify_claims.py`.

| Файл | Содержимое | Фаза |
|---|---|---|
| `phase1_grid.json`, `phase1_grid_partial.json`, `phase1.log` | сетка baseline (lr × dropout), **только validation** | 1 |
| `frozen_config.json` | замороженный конфиг baseline (lr=1e-3, dropout=0.2) | 1 → 2 |
| `runs.jsonl` | все прогоны обучения: `val_acc`, `val_curve`, FLOPs, параметры, время | 2 |
| `runs_backup_n3.jsonl` | снимок `runs.jsonl` после первых 3 сидов (для аудита) | 2 |
| `selection.json` | **замороженный до test** выбор ширины студента (160×96) и статистика по ширинам | 3 |
| `ablations.jsonl` | prune-only и random-prune + KD (validation) | 4 |
| `test_metrics.csv` | **единственный** проход по официальному test: 44 модели | 5 |
| `timings.csv` | сырые тайминги по batch 1/256/1024 (3 сида, все проходы усреднены медианой) | 6 |
| `timings_extra.csv` | тайминги batch 1024 для сидов 3–4 (тем же кодом) | 6 |
| `bench.log` | лог бенчмарка, включая проверку свёртки нормализации (`argmax agreement = 1.0`) | 6 |
| `summary.json` | агрегаты: средние, sd, 95% CI, разложение Амдала, ablation'ы | 7 |
| `results.csv` | итоговая таблица baseline vs метод (одна строка на конфигурацию) | 7 |
| `exploratory_60ep.jsonl`, `exploratory_60ep_summary.json` | **post-hoc** exploratory (60 эпох), не подтверждающий результат | 8 |
| `models/*.npz`, `models/*.json` | веса всех моделей (git-ignored, воспроизводятся обучением) | 2/4 |

## Важные оговорки

- `test_metrics.csv` — единственный проход по test. Он сделан **после** `selection.json`
  (выбор ширины по validation), поэтому выбора по test не было.
- Скорость (n=5) собрана из `timings.csv` (сиды 0–2) и `timings_extra.csv` (сиды 3–4, только batch 1024).
- `exploratory_60ep_*` — результат, полученный после просмотра primary-результатов; в выводах
  он помечен как exploratory и не заменяет primary.
- Перезапуск `run_all.sh` удаляет и заново создаёт эти файлы (кроме `models/`).
