# Fashion-MNIST: 45.79× полный инференс RBF-SVM

**ФИНАЛЬНО. ИЗМЕРЕНО на локальном holdout:** 20.273905 → 0.442803 с, пять полных пар; 95% timing CI [43.81; 47.79]. Accuracy 89.72% / 89.72%, agreement 100%. **Цель 50× не достигнута**, validation >50× не выдается за итог.

## Что именно ускорено

Полный **инференс предобученной модели**, включая свежий Python process, чтение модели, реальных IDX.gz, декодирование/предобработку, все 5000 предсказаний, голосование, метрики и output. Общий fit 60k и one-time model export/build не скрыты: они приведены отдельно, обучение не называется ускоренным. Все 18 802 SV сохранены. Нет Cartesian-grid/сепарабельной GP структуры.

Baseline — самый быстрый из **трёх действительно измеренных** готовых reference: native libsvm, threaded libsvm и ONNX Runtime CPU. Выбран до custom optimization. Метод: точные uint8 dot/distances через VNNI, приближённый float32 vector exp, float64 mixed sparse decisions, компактный checkpoint, ISA-L gzip. Математическое совпадение модели не подменяет frozen empirical quality gates.

## Одна команда

Из корня исходного repository:

```bash
bash competition50x/reproduce.sh
```

Свежая изолированная директория создаётся в `competition50x/artifacts/reproductions/`. Скачивание четырёх закреплённых blobs, новое обучение SVC, все три ready-reference ×3 runs, native build, тесты и пять holdout пар. Нет prediction cache, опубликованные результаты не перезаписываются. Скрипт не ждёт старого research deadline. Нужен интернет к GitHub API/PyPI для первого setup.

Требования: Python3.11 (проверен 3.11.2), Linux x86_64 **AVX512-VNNI**, C compiler/OpenMP/libmvec, два доступных CPU, ~4GB RAM. На другом hardware скорость не гарантирована; unsupported ISA честно отклоняется. Численные dependencies pinned в [requirements.txt](requirements.txt); полный реально наблюдённый environment в [results/environment.json](results/environment.json).

## Материалы

- [report.md](report.md) — один основной результат, вторичные ниже, обязательные ограничения/неудачи.
- [results.csv](results.csv) — **ровно 5** первичных полных пар, не смесь задач/лучших запусков.
- [protocol.md](protocol.md), [eval.py](eval.py), [sealed SHA-256](protocol_frozen.json), [заморозка метода до holdout](method_frozen.json).
- [work_log.md](work_log.md), [checkpoints.md](checkpoints.md), [математика/Amdahl/memory](math.md), [13 brainstorm идей](brainstorm.md).
- [Код](inference.py), [C backend](u8gemm.c), [baseline worker](reference_worker.py), [candidate worker](candidate_worker.py), [harness](harness.py), [тесты](tests).

## Границы

Это публичный dataset и собственный локально изолированный holdout, **не внешний hidden benchmark/рейтинг**. Одна модель/разбиение, batch5000, uint8-пиксели; float32 exp может менять ответы на других данных. Глобально лучший существующий SVM engine не установлен. Итог не ускоряет training+inference в 45.8 раза. Все остальные измерения помечены вторичными, и 50× на них не заменяет первичный результат.

**ИЗМЕРЕНО:** полная свежая команда реально завершилась с exit 0; внутренний study subprocess занял 600.939 с (без предшествующей pip-проверки и outer-wrapper startup). Новый corpus/model, все references/tests/pairs. [Индекс выполнения](results/fresh_reproduction_index.json).
