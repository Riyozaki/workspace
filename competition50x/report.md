# ФИНАЛЬНЫЙ ОТЧЁТ: полный RBF-SVM инференс Fashion-MNIST

## 1. Один главный результат

**ИЗМЕРЕНО: 45.7854×** на полном cold inference endpoint; описательный парный bootstrap 95% **[43.8068; 47.7887]**. **Цель ≥50× не достигнута.** Валидационное значение выше 50× не подменяет этот результат.

| ИЗМЕРЕНО на одном фиксированном holdout | Сильный baseline: sklearn/libsvm, 2 параллельных чанка | Замороженный compact-метод |
|---|---:|---:|
| Полное среднее время, с | 20.273905345 | 0.442802956 |
| SD между запусками, с | 0.975209718 | 0.007729214 |
| Min–max, с | 19.148718–21.437895 | 0.432659–0.454063 |
| Accuracy | 89.72% | 89.72% |
| Предсказанные метки | 5000 | 5000; совпадение **100.00%** |
| Полные парные повторения | 5 | 5; все 5 прошли оба gates |
| Max process RSS, bytes | 273022976 | 177315840 |

Это **инференс предобученной модели**, не ускорение обучения+инференса. Оба процесса читают реальные сжатые IDX-данные и checkpoint, выполняют всю предобработку, предсказания, голосование, метрики и вывод. Время родительского процесса от spawn до exit, плюс одинаково добавленная измеренная стоимость независимого gate/evaluator. Никакой component-only ratio в главном результате нет.

Это локальный, заранее изолированный split **публичного** dataset. Внешних организаторских hidden data/eval/рейтинга нет. Независимая внешняя верификация **не выполнена**. Иные агенты и прежнее GP-исследование не дают этому результату кредита.

[Все пять первичных пар](results.csv), [сводка/CI](results/primary_summary.json), [все 5000 labels/predictions](results/primary_predictions.csv), [заморозка метода](method_frozen.json).

## 2. Что зафиксировано до результатов

**ИЗМЕРЕНО:** protocol/evaluator/source sealed на **552.392813 с**, до 600 с. [Протокол](protocol.md), [SHA-256 seal](protocol_frozen.json), [eval.py](eval.py).

- Train: все 60 000 official Fashion-MNIST train examples. Validation и holdout: стратифицированные половины official 10 000 test, seed **20261017**, по 5000 observations. Разбиение по индексам не пересекается; content-duplicate аудит ниже, без изменения split после результата.
- Fixed SVC: C=10, RBF gamma=`scale`, tol=0.001, shrinking, probability=False, без max_iter cap, cache 1536 MB. Пиксели float64/255, без augmentation/подгонки гиперпараметров. Train только official train.
- Фиксированная accuracy non-inferiority: **не хуже baseline−0.001 absolute** (0.1 процентного пункта); дополнительный gate **agreement ≥0.999**. Не ослаблялись после результатов. ИЗМЕРЕНО на holdout: drop=0, disagreement=0.
- Обученная модель: ИЗМЕРЕНО **18802 SV**, gamma **0.010234694240516045**. Все SV, коэффициенты, intercept и 45 one-vs-one классификаторов сохранены. Предсказатель не принимает labels.
- Метод/модель/decoder/native binary заморожены до **первого** holdout score. После этого численный код не менялся.
- Пять пар, сбалансированный порядок, все попытки; seed bootstrap 20261017, 10 000 bootstrap draws. CI характеризует **изменчивость времени одного набора**, не пять независимых dataset/model seeds.

## 3. Сильный baseline — вторичные калибровочные результаты

До реализации custom predictor выполнены **все 3 fresh-process запроса каждого** готового референса на validation. По заранее заданному правилу выбран наименьший mean из всех трёх повторов среди вариантов, прошедших gates. Выбранный reference после оптимизации не менялся.

| ВТОРИЧНОЕ, ИЗМЕРЕНО на validation | Среднее cold, с | Запусков | Accuracy | Eligible |
|---|---:|---:|---:|---|
| onnx | 52.910425 | 3/3 | 0.9032 | True |
| threaded | 22.758544 | 3/3 | 0.9032 | True |
| native | 59.658364 | 3/3 | 0.9032 | True |

`native` — настоящий sklearn/libsvm C predictor; `threaded` — два вызова того же public API в ThreadPoolExecutor; `onnx` — установленный ONNX Runtime CPU SVMClassifier, 2 intra-op / 1 inter-op thread. Все 3 референса дали одинаковые метки. Это не Python-петля вместо промышленного baseline. Но это **быстрейший из трёх измеренных**, не доказательство глобальной оптимальности среди всех когда-либо существовавших SVM систем.

Исходники готовых реализаций независимо проверены: у ORT v1.23.2 RBF branch в `batched_kernel_dot` использует вложенные loops по query/SV/feature, а не GEMM; настройка CPU pool не превращает эту ветку автоматически в batch GEMM. Сохранены исходники и Git blob/SHA в [references](references/manifest.json). Никакой собственной подмены ORT на слабый код не делалось.

## 4. Архитектура и математическое отличие

1. **Float64 GEMM:** norm identity вместо многих отдельных dot/distance loops, точная семантика SVM с float64 rounding differences.
2. **Float32 dot + float64 решения:** больше SIMD throughput, но дополнительные преобразования и библиотечный startup ограничивают полный выигрыш.
3. **Compact serving:** все исходные SV pixels без потерь восстановлены в uint8; packed AVX512-VNNI exact integer dot / squared distances; float32 vector exp из glibc libmvec; native float64 FMA accumulation девяти логических coefficients per SV; то же majority voting/tie rule. Python+NumPy+ISA-L+small C runtime, **не** SciPy/sklearn/ONNX в serving-процессе.

Сеть/скачиватель не импортируются в serving. ISA-L декодирует **тот же gzip**; byte identity с frozen decoder проверена. Это оптимизация ввода, а не исключение загрузки из таймера. Модельный формат — параметры/коэффициенты, не сохранённые ответы. Никакой train/test answer cache, отказа от сложных примеров, pruning SV или меньшего числа требуемых outputs нет.

ИЗМЕРЕНО сохранение uint8 roundtrip **для всех SV**; целочисленный этап точен. **Полный метод смешанной точности, не bit-exact IEEE SVM:** float32 exp может менять near-boundary решения на других данных. Frozen quality gates проверены именно для serving path, не для более точной диагностической версии.

[Полный вывод и FLOPs/memory/Amdahl](math.md), [C source](u8gemm.c), [численный код](inference.py), [worker](candidate_worker.py).

## 5. Все ablation — вторичные, не замена первичного результата

Каждая строка — **mean всех трёх** полных validation requests для конфигурации, не лучший отдельный run. Все времена/отношения здесь **ИЗМЕРЕНО**, но используют общий mean baseline из ранней validation-калибровки. Они не были свежими парными holdout-запусками. Полные CSV содержат каждый повтор.

| ВТОРИЧНОЕ, раунд | Семейство:block | Mean method, с | Validation ratio | Все gates |
|---|---|---:|---:|---|
| validation_r1 | compact:1024 | 1.383813 | 16.447× | True |
| validation_r1 | compact:128 | 1.358634 | 16.752× | True |
| validation_r1 | compact:2048 | 1.391060 | 16.362× | True |
| validation_r1 | compact:256 | 1.370341 | 16.609× | True |
| validation_r1 | compact:512 | 1.401788 | 16.236× | True |
| validation_r1 | gemm32:1024 | 2.338045 | 9.734× | True |
| validation_r1 | gemm32:128 | 2.023706 | 11.247× | True |
| validation_r1 | gemm32:2048 | 2.306087 | 9.869× | True |
| validation_r1 | gemm32:256 | 2.125691 | 10.707× | True |
| validation_r1 | gemm32:512 | 2.136556 | 10.652× | True |
| validation_r1 | gemm64:1024 | 2.555127 | 8.907× | True |
| validation_r1 | gemm64:128 | 2.465431 | 9.232× | True |
| validation_r1 | gemm64:2048 | 2.592546 | 8.779× | True |
| validation_r1 | gemm64:256 | 2.462784 | 9.241× | True |
| validation_r1 | gemm64:512 | 2.473527 | 9.201× | True |
| validation_compact_v3 | compact:1024 | 0.472688 | 48.149× | True |
| validation_compact_v3 | compact:128 | 0.456027 | 49.909× | True |
| validation_compact_v3 | compact:2048 | 0.469752 | 48.450× | True |
| validation_compact_v3 | compact:256 | 0.444610 | 51.190× | True |
| validation_compact_v3 | compact:512 | 0.474304 | 47.987× | True |
| validation_isal_c16 | compact:1024 | 0.453341 | 50.204× | True |
| validation_isal_c16 | compact:128 | 0.438744 | 51.874× | True |
| validation_isal_c16 | compact:2048 | 0.460723 | 49.400× | True |
| validation_isal_c16 | compact:256 | 0.473160 | 48.101× | True |
| validation_isal_c16 | compact:512 | 0.485517 | 46.879× | True |
| validation_isal_c8 | compact:1024 | 0.514112 | 44.270× | True |
| validation_isal_c8 | compact:128 | 0.501495 | 45.384× | True |
| validation_isal_c8 | compact:2048 | 0.590102 | 38.569× | True |
| validation_isal_c8 | compact:256 | 0.493685 | 46.102× | True |
| validation_isal_c8 | compact:512 | 0.507619 | 44.837× | True |

В каждой из четырёх таблиц/CSV сохранены все запланированные configurations/runs. C8 microtile оказался **хуже**, поэтому восстановлен byte-identical C16 winner перед freeze, а не выбран случайно самый быстрый отдельный run. Двухточечные component profiles не являются системными speedup. В fused V2/V3 исторически названное поле `integer_dot_seconds` включает также distance/exp; оно не интерпретируется как время одного dot-product этапа. После sparse mixed reduction ушёл большой float32→float64 kernel cast и лишние structural-zero multiplies; объяснение части выигрыша через overlap/spinning разных thread pools — **ПРЕДПОЛОЖЕНО**, отдельной изолирующей причинной проверки не было.

**Самоаудит статистики:** generic validation-summary JSON содержат поле `paired_bootstrap_95ci`, но там baseline — повторённый фиксированный mean ранних трёх измерений. Эти поля **не считаются корректной полной парной неопределённостью и не цитируются как CI**. Только первичный интервал раздела 1 основан на пяти новых действительно парных запросах. Валидационное >50× не подтвердилось: 95% верхняя граница первичного измерения тоже <50. Причина ускорения самого baseline между фазами не изолирована (поменялись split и время исполнения), не приписывается уверенно одному фактору.

## 6. Стоимость подготовки и закон Амдала

**ИЗМЕРЕНО отдельно:** shared SVC fit **133.717830 с**, native serialization **0.101200 с**, raw parameter export **0.136481 с**, selected native compile **0.499989 с**, selected packing **0.416826 с**. Compact checkpoint **17236388 bytes**. Fit — не ускоренный компонент и не включён в inference-only headline.

**РАССЧИТАНО из этих измерений**, не отдельно измеренный deployment pipeline: если дополнительно оплатить raw export+compile+packing в каждом первом запросе, gain ≈ **13.5512×**, а не 45.79×. Если также прибавить общий fit+native serialization к обеим сторонам, моделируемое отношение ≈ **1.1388×**; это не claim training+inference speedup. Download/install/cache/build окружения отдельно от pre-trained serving; свежий reproduction повторяет их и измеряет свой общий wall time ниже.

**РАССЧИТАНО:** primary baseline load+predict fraction f≈**0.986710**. Ускорение только этой части в 10 раз дало бы Амдал `1/((1−f)+f/10)`≈**8.9317×**, не 10× всего процесса. Все component ratios не подменяют основной cold endpoint. У метода остаются импорт, gzip decode, чтение модели, exp/голосование и output. Теоретические FLOPs/bytes в math.md — не counter measurements. Пиковый RSS процесса не равен размеру checkpoint.

## 7. Воспроизведение и дополнительные проверки — вторичные

```bash
bash competition50x/reproduce.sh
```

Команда из корня repo устанавливает pinned runtime, копирует исходники в новую ignored output directory, **заново скачивает реальные данные, обучает все 60k, измеряет все три готовых референса, собирает compact backend, запускает тесты и пять полных holdout пар**. Не ждёт истечения старого research timer. Исходные опубликованные результаты не перезаписываются. Требуется Linux x86_64 с AVX512-VNNI, C compiler/OpenMP/libmvec, Python3.11, ~4GB RAM; отсутствие ISA честно останавливает compact backend, а не выдаёт неподтверждённый fallback gain.

**ИЗМЕРЕНО исполнение именно этой полной команды:** returncode **0**, wall **внутреннего исследовательского subprocess** **600.939144 с**. Эта длительность не включает предшествующую pip-проверку и outer-wrapper/source-copy startup; не выдаётся за весь shell-command wall. Python dependencies уже были установлены; локальные model/data cache внутри новой директории отсутствовали. Скачивание и обучение повторены. [Индекс](results/fresh_reproduction_index.json).

ВТОРИЧНОЕ: fresh reproduction пять пар: **44.8160×**, accuracy **0.8972/0.8972**, gates **True**. **Не объединяется с первичными пятью** и не заменяет их даже если результат выше. [Сводка](results/fresh_reproduction_summary.json).

**ИЗМЕРЕНО независимым аудитом:** frozen source/model/eval hashes pass, raw blobs SHA-256/Git SHA-1 pass, seed split recomputed, все пять metric/time пар и bootstrap независимо пересчитаны; prediction artifacts verified **113**. [Аудит](results/integrity_audit.json).

Content duplicate audit (не использован для пересмотра split/метрики): `{"official_train_unique_images": 60000, "official_test_exact_matches_train": 0, "validation_exact_matches_train": 0, "holdout_exact_matches_train": 0, "validation_holdout_content_overlap_unique": 0}`. Различные официальные индексы не следует путать с доказательством отсутствия любых повторов изображений.

ВТОРИЧНОЕ, ИЗМЕРЕНО: размер batch и границы применимости, без переоптимизации frozen system. Три повтора каждого размера; это validation prefixes и фиксированный primary baseline, не лучшая заново подобранная реализация для малого batch. [Все результаты](results/batch_sweep_summary.json).

| Batch | Baseline mean, с | Method mean, с | Secondary ratio | Gates |
|---:|---:|---:|---:|---|
| 2 | 0.789032 | 0.168741 | 4.676× | True |
| 8 | 0.836578 | 0.170461 | 4.908× | True |
| 32 | 0.987952 | 0.179077 | 5.517× | True |
| 128 | 1.345850 | 0.183413 | 7.338× | True |
| 512 | 2.773870 | 0.200703 | 13.821× | True |
| 5000 | 18.225452 | 0.452373 | 40.289× | True |

ВТОРИЧНОЕ: поздний фиксированный prefix validation requests — **22 пар**, все сохранены до time cutoff, не объединены с primary. [Итоги](results/late_validation_summary.json).

Дополнительные random-boundary/operator probes до реального дедлайна — **не ML speedup**. [Счётчики/ошибки](results/deadline_operator_audit.json).

## 8. Ограничения, неудачи и недоказанное

- **50× не достигнуто на первичном holdout**. Нельзя цитировать validation winner, старые GP числа или удачную reproduction вместо него. Качество сохранено, но inference-система специально для одного заранее выбранного реального SVM workload, не универсальный AI accelerator.
- Готовые reference сравнения ограничены тремя реально измеренными реализациями. Существование ещё более быстрого специализированного SVM engine не исключено; глобальное лидерство/SOTA и скорректированный рейтинг не доказаны.
- Large-batch serving: Q=5000. 50× на одиночном online request не обещается; latency/throughput и другие batch sizes — разные нагрузки. Самый малый измеренный batch — 2; для N=1 эта фиксированная двухчанковая baseline-обёртка не рассчитана на пустой второй chunk и отдельно не тестировалась. Сетка/сепарабельное ядро не нужны, но исходные uint8 features, 784 dimensions, 10 classes, RBF и AVX512-VNNI — реальные ограничения этой реализации.
- Pixel encoding exact, **float32 exp approximate**. На near-boundary/других gamma/C/models возможны label flips; формального no-loss для любых будущих данных нет. Здесь оба фиксированных gates пройдены на конкретном holdout.
- Public self-sequestered holdout не равен независимому organizer hidden set. Agent мог знать dataset по обучению; защиты слепой внешней оценки нет. Код не содержит ответы, но это ограничивает силу вывода о переносимости.
- Одна модель/один split; bootstrap из пяти временных повторов не измеряет dataset/model uncertainty. VM не эксклюзивна; fresh interpreter **не** очищает OS page cache. Порядок сбалансирован, все повторы сохранены, но hardware/frequency isolation отсутствует.
- **Calibration orchestration failure:** исходный выбор baseline упал на self-comparison guard общего output path. Все 9 numerical requests были исправны. Выбор восстановлен с другим native replicate, без удаления timings/изменения reference worker/evaluator.
- **Native binding failure:** параллельные edits одного Python файла потеряли `ctypes.argtypes`; тест 21pass/1fail и один failed worker сохранены. Исправлено до финальной валидации/freeze, без ослабления quality tolerance. Все последующие same-file edits сериализованы.
- **Wrong interpreter freeze failure:** system python без NumPy не смог записать freeze; никаких holdout запусков до исправления не было. Затем использован venv и source/model sealed; multi-command этапы переведены на strict shell mode. Это не скрывается как успешный первый запуск.
- C8 microtile проиграл; float64-only и float32 GEMM без compact startup/fused mixed reduction не дали целевого результата. Никакие отрицательные/failed попытки не превращены в gain.
- Повторяемая подготовка модели/компиляция и обучение радикально уменьшают amortized gain. Выбирать inference task и затем заявлять 45.8× для полного обучения было бы подменой — здесь такого утверждения нет.

## 9. Время, контрольные точки и воспроизводимость доказательств

Начало — первый tool action нового разрешённого окна, `2026-10-17T15:58:57.126796+00:00`. Контрольные точки 30/60/85 минут записываются реальным монитором: [checkpoints.md](checkpoints.md); субъективные вероятности явно помечены **ПРЕДПОЛОЖЕНО**, не статистическая гарантия. Полный журнал [work_log.md](work_log.md), предрегистрация [protocol.md](protocol.md), идеи [brainstorm.md](brainstorm.md), точные software/hardware данные [environment](results/environment.json).

**ИЗМЕРЕНО инструментом финального gate:** UTC **2026-10-17T17:28:57.133668+00:00**, wall **5400.006885 с**, monotonic **5400.006874 с**, оба ≥5400. Финальная фиксация не разрешалась раньше этого. Накладные миллисекунды записи/выдачи не выдаются за ровно нулевое время. [Доказательство](results/deadline_proof.json).

Честный итог: измеренное ускорение 45.7854×, качество accuracy 89.72% против 89.72% baseline, agreement 100.00% (допуск выполнен: да).
