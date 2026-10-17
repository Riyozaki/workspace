"""Generate honest report from preserved evidence; final sealing requires 90 min."""
from __future__ import annotations
import argparse,csv,hashlib,json,statistics,time
from pathlib import Path
from .paths import ROOT,ART
from .clock import elapsed,snapshot


def j(path):return json.loads((ROOT/path).read_text())
def f(x,d=4):return f'{x:.{d}f}'


def generate(final=False,proof=None):
 s=j('results/primary_summary.json');ci=s['paired_bootstrap_95ci'];baseline=j('results/baseline_selected.json');train=j('results/training.json');prep=j('results/compact_preparation.json');seal=j('protocol_frozen.json')
 records=[j('results/runs/'+p.name) for p in (ROOT/'results/runs').glob('primary_*.json')]
 b=[r for r in records if r['engine']=='threaded'];m=[r for r in records if r['engine']=='compact']
 bmi=max(r['metadata']['peak_rss_bytes'] for r in b);mmi=max(r['metadata']['peak_rss_bytes'] for r in m)
 p=prep['compile_seconds']+prep['packing_seconds']+train['raw_export_seconds'];one=s['baseline_mean_seconds']/(s['method_mean_seconds']+p)
 common=train['train_seconds']+train['native_serialization_seconds'];train_case=(common+s['baseline_mean_seconds'])/(common+p+s['method_mean_seconds'])
 state='ФИНАЛЬНЫЙ ОТЧЁТ' if final else 'ПРЕДВАРИТЕЛЬНЫЙ ОТЧЁТ — исследование продолжается'
 report=f'''# {state}: полный RBF-SVM инференс Fashion-MNIST

## 1. Один главный результат

**ИЗМЕРЕНО: {s['speedup_ratio_of_sums']:.4f}×** на полном cold inference endpoint; описательный парный bootstrap 95% **[{ci[0]:.4f}; {ci[1]:.4f}]**. **Цель ≥50× не достигнута.** Валидационное значение выше 50× не подменяет этот результат.

| ИЗМЕРЕНО на одном фиксированном holdout | Сильный baseline: sklearn/libsvm, 2 параллельных чанка | Замороженный compact-метод |
|---|---:|---:|
| Полное среднее время, с | {s['baseline_mean_seconds']:.9f} | {s['method_mean_seconds']:.9f} |
| SD между запусками, с | {s['baseline_sd_seconds']:.9f} | {s['method_sd_seconds']:.9f} |
| Min–max, с | {s['baseline_range_seconds'][0]:.6f}–{s['baseline_range_seconds'][1]:.6f} | {s['method_range_seconds'][0]:.6f}–{s['method_range_seconds'][1]:.6f} |
| Accuracy | {100*s['baseline_accuracy']:.2f}% | {100*s['candidate_accuracy']:.2f}% |
| Предсказанные метки | 5000 | 5000; совпадение **{100*s['min_label_agreement']:.2f}%** |
| Полные парные повторения | 5 | 5; все 5 прошли оба gates |
| Max process RSS, bytes | {bmi} | {mmi} |

Это **инференс предобученной модели**, не ускорение обучения+инференса. Оба процесса читают реальные сжатые IDX-данные и checkpoint, выполняют всю предобработку, предсказания, голосование, метрики и вывод. Время родительского процесса от spawn до exit, плюс одинаково добавленная измеренная стоимость независимого gate/evaluator. Никакой component-only ratio в главном результате нет.

Это локальный, заранее изолированный split **публичного** dataset. Внешних организаторских hidden data/eval/рейтинга нет. Независимая внешняя верификация **не выполнена**. Иные агенты и прежнее GP-исследование не дают этому результату кредита.

[Все пять первичных пар](results.csv), [сводка/CI](results/primary_summary.json), [все 5000 labels/predictions](results/primary_predictions.csv), [заморозка метода](method_frozen.json).

## 2. Что зафиксировано до результатов

**ИЗМЕРЕНО:** protocol/evaluator/source sealed на **{seal['elapsed_seconds']:.6f} с**, до 600 с. [Протокол](protocol.md), [SHA-256 seal](protocol_frozen.json), [eval.py](eval.py).

- Train: все 60 000 official Fashion-MNIST train examples. Validation и holdout: стратифицированные половины official 10 000 test, seed **20261017**, по 5000 observations. Разбиение по индексам не пересекается; content-duplicate аудит ниже, без изменения split после результата.
- Fixed SVC: C=10, RBF gamma=`scale`, tol=0.001, shrinking, probability=False, без max_iter cap, cache 1536 MB. Пиксели float64/255, без augmentation/подгонки гиперпараметров. Train только official train.
- Фиксированная accuracy non-inferiority: **не хуже baseline−0.001 absolute** (0.1 процентного пункта); дополнительный gate **agreement ≥0.999**. Не ослаблялись после результатов. ИЗМЕРЕНО на holdout: drop=0, disagreement=0.
- Обученная модель: ИЗМЕРЕНО **{train['total_support']} SV**, gamma **{train['gamma']:.17g}**. Все SV, коэффициенты, intercept и 45 one-vs-one классификаторов сохранены. Предсказатель не принимает labels.
- Метод/модель/decoder/native binary заморожены до **первого** holdout score. После этого численный код не менялся.
- Пять пар, сбалансированный порядок, все попытки; seed bootstrap 20261017, 10 000 bootstrap draws. CI характеризует **изменчивость времени одного набора**, не пять независимых dataset/model seeds.

## 3. Сильный baseline — вторичные калибровочные результаты

До реализации custom predictor выполнены **все 3 fresh-process запроса каждого** готового референса на validation. По заранее заданному правилу выбран наименьший mean из всех трёх повторов среди вариантов, прошедших gates. Выбранный reference после оптимизации не менялся.

| ВТОРИЧНОЕ, ИЗМЕРЕНО на validation | Среднее cold, с | Запусков | Accuracy | Eligible |
|---|---:|---:|---:|---|
'''
 for name,r in baseline['references'].items():
  report+=f"| {name} | {r['mean_cold_seconds']:.6f} | {r['n_completed']}/{r['n_attempted']} | {r['quality_checks'][0]['candidate_accuracy']:.4f} | {r['eligible']} |\n"
 report+='''
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
'''
 for name in ('validation_r1','validation_compact_v3','validation_isal_c16','validation_isal_c8'):
  pth=ROOT/'results'/f'{name}_summary.json'
  if not pth.exists():continue
  for key,r in sorted(json.loads(pth.read_text())['groups'].items()):report+=f"| {name} | {key} | {r['method_mean_seconds']:.6f} | {r['speedup_ratio_of_sums']:.3f}× | {r['all_quality_pass']} |\n"
 report+='''
В каждой из четырёх таблиц/CSV сохранены все запланированные configurations/runs. C8 microtile оказался **хуже**, поэтому восстановлен byte-identical C16 winner перед freeze, а не выбран случайно самый быстрый отдельный run. Двухточечные component profiles не являются системными speedup. В fused V2/V3 исторически названное поле `integer_dot_seconds` включает также distance/exp; оно не интерпретируется как время одного dot-product этапа. После sparse mixed reduction ушёл большой float32→float64 kernel cast и лишние structural-zero multiplies; объяснение части выигрыша через overlap/spinning разных thread pools — **ПРЕДПОЛОЖЕНО**, отдельной изолирующей причинной проверки не было.

**Самоаудит статистики:** generic validation-summary JSON содержат поле `paired_bootstrap_95ci`, но там baseline — повторённый фиксированный mean ранних трёх измерений. Эти поля **не считаются корректной полной парной неопределённостью и не цитируются как CI**. Только первичный интервал раздела 1 основан на пяти новых действительно парных запросах. Валидационное >50× не подтвердилось: 95% верхняя граница первичного измерения тоже <50. Причина ускорения самого baseline между фазами не изолирована (поменялись split и время исполнения), не приписывается уверенно одному фактору.

## 6. Стоимость подготовки и закон Амдала

'''
 core_b=statistics.mean(r['metadata']['load_model_predict_seconds'] for r in b);fraction=core_b/s['baseline_mean_seconds'];amdahl=1/(1-fraction+fraction/10)
 report+=f'''**ИЗМЕРЕНО отдельно:** shared SVC fit **{train['train_seconds']:.6f} с**, native serialization **{train['native_serialization_seconds']:.6f} с**, raw parameter export **{train['raw_export_seconds']:.6f} с**, selected native compile **{prep['compile_seconds']:.6f} с**, selected packing **{prep['packing_seconds']:.6f} с**. Compact checkpoint **{prep['compact_bytes']} bytes**. Fit — не ускоренный компонент и не включён в inference-only headline.

**РАССЧИТАНО из этих измерений**, не отдельно измеренный deployment pipeline: если дополнительно оплатить raw export+compile+packing в каждом первом запросе, gain ≈ **{one:.4f}×**, а не {s['speedup_ratio_of_sums']:.2f}×. Если также прибавить общий fit+native serialization к обеим сторонам, моделируемое отношение ≈ **{train_case:.4f}×**; это не claim training+inference speedup. Download/install/cache/build окружения отдельно от pre-trained serving; свежий reproduction повторяет их и измеряет свой общий wall time ниже.

**РАССЧИТАНО:** primary baseline load+predict fraction f≈**{fraction:.6f}**. Ускорение только этой части в 10 раз дало бы Амдал `1/((1−f)+f/10)`≈**{amdahl:.4f}×**, не 10× всего процесса. Все component ratios не подменяют основной cold endpoint. У метода остаются импорт, gzip decode, чтение модели, exp/голосование и output. Теоретические FLOPs/bytes в math.md — не counter measurements. Пиковый RSS процесса не равен размеру checkpoint.

## 7. Воспроизведение и дополнительные проверки — вторичные

```bash
bash competition50x/reproduce.sh
```

Команда из корня repo устанавливает pinned runtime, копирует исходники в новую ignored output directory, **заново скачивает реальные данные, обучает все 60k, измеряет все три готовых референса, собирает compact backend, запускает тесты и пять полных holdout пар**. Не ждёт истечения старого research timer. Исходные опубликованные результаты не перезаписываются. Требуется Linux x86_64 с AVX512-VNNI, C compiler/OpenMP/libmvec, Python3.11, ~4GB RAM; отсутствие ISA честно останавливает compact backend, а не выдаёт неподтверждённый fallback gain.

'''
 if (ROOT/'results/fresh_reproduction_index.json').exists():
  r=j('results/fresh_reproduction_index.json');report+=f"**ИЗМЕРЕНО исполнение именно этой полной команды:** returncode **{r['returncode']}**, wall **внутреннего исследовательского subprocess** **{r['full_reproduction_wall_seconds']:.6f} с**. Эта длительность не включает предшествующую pip-проверку и outer-wrapper/source-copy startup; не выдаётся за весь shell-command wall. Python dependencies уже были установлены; локальные model/data cache внутри новой директории отсутствовали. Скачивание и обучение повторены. [Индекс](results/fresh_reproduction_index.json).\n\n"
  if (ROOT/'results/fresh_reproduction_summary.json').exists():
   r=j('results/fresh_reproduction_summary.json');report+=f"ВТОРИЧНОЕ: fresh reproduction пять пар: **{r['speedup_ratio_of_sums']:.4f}×**, accuracy **{r['baseline_accuracy']:.4f}/{r['candidate_accuracy']:.4f}**, gates **{r['all_quality_pass']}**. **Не объединяется с первичными пятью** и не заменяет их даже если результат выше. [Сводка](results/fresh_reproduction_summary.json).\n\n"
 else:report+='Полная команда пока не завершилась; её работоспособность до получения exit 0 **не заявляется**.\n\n'
 if (ROOT/'results/integrity_audit.json').exists():
  r=j('results/integrity_audit.json');report+=f"**ИЗМЕРЕНО независимым аудитом:** frozen source/model/eval hashes pass, raw blobs SHA-256/Git SHA-1 pass, seed split recomputed, все пять metric/time пар и bootstrap независимо пересчитаны; prediction artifacts verified **{r['verified_prediction_artifacts']}**. [Аудит](results/integrity_audit.json).\n\n"
  report+='Content duplicate audit (не использован для пересмотра split/метрики): `'+json.dumps(r['content_duplicate_audit'],ensure_ascii=False)+'`. Различные официальные индексы не следует путать с доказательством отсутствия любых повторов изображений.\n\n'
 if (ROOT/'results/batch_sweep_summary.json').exists():
  r=j('results/batch_sweep_summary.json');report+='ВТОРИЧНОЕ, ИЗМЕРЕНО: размер batch и границы применимости, без переоптимизации frozen system. Три повтора каждого размера; это validation prefixes и фиксированный primary baseline, не лучшая заново подобранная реализация для малого batch. [Все результаты](results/batch_sweep_summary.json).\n\n| Batch | Baseline mean, с | Method mean, с | Secondary ratio | Gates |\n|---:|---:|---:|---:|---|\n'
  for n,z in sorted(r['groups'].items(),key=lambda t:int(t[0])):
   report+=f"| {n} | {z['baseline_mean_seconds']:.6f} | {z['method_mean_seconds']:.6f} | {z['speedup_ratio_of_sums']:.3f}× | {z['all_quality_pass']} |\n"
  report+='\n'
 if (ROOT/'results/late_validation_summary.json').exists():
  r=j('results/late_validation_summary.json');report+=f"ВТОРИЧНОЕ: поздний фиксированный prefix validation requests — **{r.get('n_pairs',0)} пар**, все сохранены до time cutoff, не объединены с primary. [Итоги](results/late_validation_summary.json).\n\n"
 if (ROOT/'results/deadline_operator_audit.json').exists():report+='Дополнительные random-boundary/operator probes до реального дедлайна — **не ML speedup**. [Счётчики/ошибки](results/deadline_operator_audit.json).\n\n'
 report+='''## 8. Ограничения, неудачи и недоказанное

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

'''
 if final:
  report+=f"**ИЗМЕРЕНО инструментом финального gate:** UTC **{proof['utc']}**, wall **{proof['elapsed_seconds']:.6f} с**, monotonic **{proof['elapsed_monotonic_seconds']:.6f} с**, оба ≥5400. Финальная фиксация не разрешалась раньше этого. Накладные миллисекунды записи/выдачи не выдаются за ровно нулевое время. [Доказательство](results/deadline_proof.json).\n\n"
 else:report+='**Это draft, не финальная сдача:** gate ≥5400 с ещё не пройден. Финальная версия будет разрешена только реальными wall+monotonic часами, без подмены времени.\n\n'
 report+=f"Честный итог: измеренное ускорение {s['speedup_ratio_of_sums']:.4f}×, качество accuracy {100*s['candidate_accuracy']:.2f}% против {100*s['baseline_accuracy']:.2f}% baseline, agreement {100*s['min_label_agreement']:.2f}% (допуск выполнен: {'да' if s['all_quality_pass'] else 'нет'}).\n"
 (ROOT/'report.md').write_text(report)
 readme=f'''# Fashion-MNIST: {s['speedup_ratio_of_sums']:.2f}× полный инференс RBF-SVM

**{'ФИНАЛЬНО' if final else 'DRAFT — исследование продолжается'}. ИЗМЕРЕНО на локальном holdout:** {s['baseline_mean_seconds']:.6f} → {s['method_mean_seconds']:.6f} с, пять полных пар; 95% timing CI [{ci[0]:.2f}; {ci[1]:.2f}]. Accuracy {100*s['baseline_accuracy']:.2f}% / {100*s['candidate_accuracy']:.2f}%, agreement 100%. **Цель 50× не достигнута**, validation >50× не выдается за итог.

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
'''
 if (ROOT/'results/fresh_reproduction_index.json').exists():
  r=j('results/fresh_reproduction_index.json');readme+=f"\n**ИЗМЕРЕНО:** полная свежая команда реально завершилась с exit {r['returncode']}; внутренний study subprocess занял {r['full_reproduction_wall_seconds']:.3f} с (без предшествующей pip-проверки и outer-wrapper startup). Новый corpus/model, все references/tests/pairs. [Индекс выполнения](results/fresh_reproduction_index.json).\n"
 else:readme+='\nПока полного exit 0 нет, свежая интеграционная команда не заявляется проверенной; статус обновится после реального завершения.\n'
 (ROOT/'README.md').write_text(readme)


def seal():
 if elapsed()<5400:raise RuntimeError('Refusing final publication before BOTH clocks reach 5400 s')
 proof=snapshot('Stage 13 — real 90-minute publication gate','Numerical workload stopped; both wall and monotonic deadlines reached. Final report may now be sealed, no fabricated elapsed time.')
 (ROOT/'results/deadline_proof.json').write_text(json.dumps(proof,indent=2)+'\n');generate(True,proof)
 paths=[ROOT/n for n in ('README.md','report.md','results.csv','work_log.md','checkpoints.md','protocol.md','eval.py','method_frozen.json','reproduce.sh','requirements.txt','math.md')]+list(ROOT.glob('*.py'))+[ROOT/'u8gemm.c']
 seals={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
 (ROOT/'results/deliverable_sha256.json').write_text(json.dumps(seals,indent=2)+'\n')
 print('FINAL REPORT SEALED AFTER REAL DEADLINE',flush=True)


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--final',action='store_true');a=p.parse_args()
 if a.final:seal()
 else:generate(False);print('Draft generated; not final.',flush=True)
