# Точное ускорение структурной GP-регрессии

> **ФИНАЛЬНЫЙ ОТЧЁТ.** Опубликован после инструментальной проверки 90 реальных минут; границы утверждений и неудачи сохранены.


**Отклонение от строгого бюджета:** численная нагрузка остановлена на 5400.000090 с (90:00), но проверка/оформление финальных файлов выполнялись после окна. Инструмент финальной фиксации показал 5470.527269 с (91:10,527). Следовательно, если 90 минут включают оформление и выдачу отчёта, строгий общий лимит **не соблюдён**. Эти 70,527 с и последующая выдача не маскируются под ровно 90 минут.

## 1. Главный результат и границы утверждения

**ИЗМЕРЕНО, первичный зафиксированный эксперимент:** **11,5406×** на полном запуске процесса, 95%-й описательный seed-cluster bootstrap **[10,2796; 12,8830]**. Средние времена: **3,734245 с → 0,323574 с**. Все 15 пар прошли заранее заданные проверки качества.

Задача — точная Gaussian-process регрессия на полной декартовой обучающей сетке **128×64 = 8192 наблюдения**, с предсказанием **среднего И латентной дисперсии** на **512 независимых внесеточных тестовых точках**. Float64, два CPU-потока, один и тот же вероятностный GP. Это **не** метод ускорения произвольной нейросети или LLM.

Held-out RMSE: baseline **0,0566866543362479**, метод **0,0566866543362358**. Максимальная разница предсказанного среднего — **2,5465e−12**, дисперсии — **8,2157e−15**, NLL — **1,3092e−12**. Эти различия не являются содержательным улучшением качества: это roundoff разных линейно-алгебраических процедур.

**Техника известна:** используется точная кронекеровская спектральная факторизация. Новизна математического открытия **не заявляется**. Результат работы — реализация, полный измеренный CPU-пайплайн, проверки, дополнительные исследования и воспроизводимые артефакты. Существенное ограничение на структуру данных/ядра остаётся.

## 2. Что зафиксировано до результатов

Старт по инструменту: **2026-10-17 13:58:35.712731 UTC**. Метрика, допуск, baseline, размер, kernel, все seed и число повторов зафиксированы в **14:01:08.590169 UTC**, через **152,877 с**, то есть в первые 10 минут.

- Основная метрика: RMSE по независимым noisy test targets.
- Критерий: `RMSE_method <= RMSE_dense + 1e-7` absolute.
- Дополнительно, для **каждой** пары: `max_abs_mean_diff <= 1e-6`, `max_abs_latent_variance_diff <= 1e-6`, `abs_predictive_NLL_diff <= 1e-6`; все значения конечны. NLL здесь — средняя **поточечная marginal** Gaussian negative log likelihood с variance `latent_variance + noise_variance`, не joint log density всех test points. Именно эта неизменная формула находится в замороженном `metrics.py`.
- Данные: заранее объявленная гладкая **не обязательно сепарабельная** функция двух координат плюс Gaussian noise std=0,05. Train — полная сетка; test — отдельный RNG `10000+seed`, непрерывные uniform координаты, независимый шум. Обучающие точки как тестовые не используются.
- Kernel: signal variance=1, RBF lengthscales=(0,18; 0,23), observation noise variance=0,0025. Только вычитание среднего **обучающих** targets, одинаковое у обоих алгоритмов.
- Seed **0,1,2,3,4**, по **3** временных повтора. 5 различных задач качества, а не 15 независимых наборов качества.
- Первичный baseline: точный dense Cholesky через SciPy/LAPACK, без явного inverse; posterior variance — один batched `solve_triangular` для всех RHS. Никаких медленных Python-циклов факторизации.
- Оценка ускорения: **сумма всех dense cold times / сумма всех method cold times**, не лучшее наблюдение и не среднее выбранных отношений.
- Интервал: 10 000 bootstrap-перевыборок **пяти seed-кластеров**, с тремя повторами внутри каждого. Это описание разброса этой VM, а не универсальная гарантия.

[Полный протокол](research/preregister.json), [SHA-256](research/preregister.sha256), [хеши baseline до первого измерения](research/baseline_source_sha256.json).

Хеш preregistration: `4c9c3843843737bfd6c790f4e47226a7b81d6323464fc01454f24e397179eba5`.

## 3. Brainstorm и выбранные направления

До реализации рассмотрены **10** разных идей: точный Kronecker GP; masked Kronecker PCG; Nyström/inducing points; Toeplitz/FFT; mixed precision + refinement; batching/layout/thread control; low-rank neural weights; INT8 inference; exact memoization; speculative decoding. Для каждой записаны гипотеза, арифметическая оценка, влияние Амдала и риски: [полная таблица](research/brainstorm.md).

Выбраны:

1. Точный полный tensor eigensystem — основной алгоритм. Впоследствии та же алгебра расширена на точное обучение GP-гиперпараметров.
2. Matrix-free PCG при пропусках — отдельная проверка переносимости, **неудачная по полной скорости**.
3. Системный аудит: более сильный dense layout и отдельный NumPy-only cold-start путь. Они не подменяют зафиксированную исходную таблицу.

Остальные идеи не реализованы и не выдаются за проверенные.

## 4. Идея и архитектура

Пусть `K = Kx ⊗ Ky`, `A = K + noise I`, `Kx = Qx Λx Qxᵀ`, `Ky = Qy Λy Qyᵀ`. Тогда

\[
A=(Q_x\otimes Q_y)\operatorname{diag}(D)(Q_x\otimes Q_y)^T,\quad D_{ij}=\lambda_{xi}\lambda_{yj}+\sigma_n^2.
\]

Вместо N×N матрицы хранятся два маленьких полных собственных базиса и N шумных собственных значений. Для центрированных targets `Y`:

\[
H=Q_x^T Y Q_y,\qquad W=H/D.
\]

Для произвольного тестового положения `t`, `u=kx(t,Xx)Qx`, `v=ky(t,Xy)Qy`:

\[
\mu(t)=\sum_{ij}u_iW_{ij}v_j+\bar y_{train},\qquad
s^2(t)=\sigma_f^2-\sum_{ij}u_i^2D_{ij}^{-1}v_j^2.
\]

Никаких rank cutoff, inducing points, интерполяции kernel, подбора на test или приближённого logdet. В точной арифметике posterior совпадает. В float64 это **проверено**, а не объявлено без проверки. Минимум raw variance записывается до общего clipping отрицательных roundoff-значений.

Код: [dense baseline](tensor_gp/dense.py), [основной метод](tensor_gp/spectral.py), [NumPy-only вариант](tensor_gp/spectral_numpy.py), [измеритель](tensor_gp/experiments.py), [парный план/статистика](tensor_gp/benchmark.py).

Полная математика, условность и FLOPs: [research/math.md](research/math.md).

### Полный измеряемый endpoint

Первичный таймер в родительском процессе: **spawn → exit** дочернего процесса. Включены Python startup, импорты, NPZ load, centering, подготовка kernel, весь fit, все mean+variance predictions, test metrics, prediction NPZ и JSON metadata output. Проверка пар против reference и статистический анализ — внешняя работа оценщика, не часть ML-задачи.

Один раз исключены установка зависимостей и создание фиксированных benchmark fixtures. Обоим алгоритмам доступны одинаковые оси и kernel factors; dense не заставляют заново считать расстояния по N² парам. Отдельный внешний тест включает **PNG decode и саму подготовку данных внутри** полного таймера.

Fresh process означает новый интерпретатор, **не** принудительно очищенный файловый cache. Тайминги последовательные, перекрывающихся timed ML workers нет. VM/host не эксклюзивны. Другие действия агента — подготовка кода и документации, а не параллельное обучение другой модели.

## 5. Первичная таблица — все измерения, без замены baseline

| Система | Cold wall mean, с | Min–max, с | Test RMSE mean | Max process RSS | Запуски |
|---|---:|---:|---:|---:|---:|
| Frozen dense Cholesky | 3,734245 | 3,606782–3,974126 | 0,0566866543362479 | 1 134 878 720 bytes | 15 |
| Full-rank tensor spectral | 0,323574 | 0,239307–0,397826 | 0,0566866543362358 | 67 653 632 bytes | 15 |

**Сквозное ускорение: 11,5406× [10,2796; 12,8830].** Отдельные пары: **9,1487–15,6884×**, поэтому формулировка «каждый запуск ≥10×» неверна.

Внутрипроцессный load-to-output pipeline ускорился в **63,3431×**, но это **вторичная** величина без startup/import и не выдается за основной результат.

[Все 15 строк](results.csv), [сырые JSON](results/runs/preregistered_primary), [сводка](results/preregistered_primary_summary.json). Начальный baseline измерен на всех пяти seed **до появления оптимизированного solver**: [сохранённые результаты](research/baseline_initial_summary.json).

## 6. Проверка против более сильного baseline и startup

После первичного результата, в отдельном плане: 15 групп, в каждой четыре настоящих запуска: frozen dense, dense с однопроходным Fortran-layout kernel, первоначальный spectral, NumPy-only spectral. Все пары используют те же данные и допуски; из четырёх вариантов не выбирается благоприятный seed.

| Отдельное сравнение | Полное ускорение | 95% seed-cluster bootstrap | Пар |
|---|---:|---:|---:|
| Frozen dense → original spectral | 11,7999× | 10,9771–12,6755 | 15 |
| Better-layout dense → original spectral | 11,0941× | 10,4051–11,8746 | 15 |
| Frozen dense → NumPy-only spectral | 32,2604× | 31,5529–33,0135 | 15 |
| Better-layout dense → NumPy-only spectral | 30,3306× | 29,6112–31,0918 | 15 |

Для последней строки: **3,509283 с → 0,115701 с**, все guards пройдены; max mean difference **2,30e−12**. У NumPy-only worker действительно отсутствует импорт SciPy — это проверено отдельным флагом и CLI-тестом. Численная схема при этом полная и проверена против обоих dense вариантов.

Однопроходный dense layout сократил kernel stage примерно с **1,408 до 1,206 с**, а не на порядок. Cholesky stages почти одинаковы: **1,571 и 1,554 с**. Для маленьких тестовых матриц факторы совпали побитово. Основной вывод не держится только на искусственно медленной факторизации.

[CSV](results/audit_four_way.csv), [сводка](results/audit_four_way_summary.json), [реализация stronger baseline](tensor_gp/dense_fortran.py).

## 7. Обучение гиперпараметров — отдельный полный эксперимент

Первичный benchmark фиксировал GP-гиперпараметры. В последующем **отдельно**, до просмотра его результатов, зафиксирован план полного обучения signal variance, двух lengthscales и noise variance по **точной log marginal likelihood**.

Baseline — настоящий **scikit-learn GaussianProcessRegressor**, `ConstantKernel * RBF + WhiteKernel`, `alpha=0`, без restarts. У обоих тот же SciPy L-BFGS-B, bounds, initialization, tolerances, maxiter/maxfun/maxls. Включены все line-search evaluations, финальный refit и все mean+variance predictions.

| Система, train=4096, test=512 | Cold mean, с | RMSE mean | Max RSS | Полных запусков |
|---|---:|---:|---:|---:|
| sklearn dense GPR, гиперпараметры обучаются | 110,093074 | 0,0495943258774210 | 1 741 225 984 bytes | 10 |
| Точный tensor objective + gradients + posterior | 0,397765 | 0,0495943258774204 | 82 513 920 bytes | 10 |

**ИЗМЕРЕНО: 276,7793×**, 95% seed-cluster CI **[258,0355; 302,3639]**. Это 5 seed × 2 повтора и **не замена первичного 11,54×**.

Успешная сходимость у обоих во всех полных парах. Числа итераций и objective evaluations **совпали в каждой паре**, то есть выигрыш не получен меньшим числом шагов. Различия предсказаний ≤1,264e−12; параметров — порядка 1e−11. Pilot train=256 дал лишь **3,1458×**, также сохранён.

Объектив:
\[
J=\tfrac12\sum H_{ij}^2/D_{ij}+\tfrac12\sum\log D_{ij}+\tfrac N2\log(2\pi),\quad
\partial J/\partial\theta=\tfrac12\operatorname{tr}[(A^{-1}-\alpha\alpha^T)\partial A/\partial\theta].
\]
Trace и quadratic terms вычисляются в полном tensor basis без N×N precision matrix. Gradients независимо сопоставлены с sklearn и finite differences. Подробный вывод: [hyperparameter_math.md](research/hyperparameter_math.md).

[Протокол](research/hyperparameter_protocol.json), [полный CSV с nfev/nit](results/hyperparameter_training.csv), [сводка](results/hyperparameter_training_summary.json), [код](tensor_gp/hyperparameters.py).

## 8. Внешняя проверка, масштабирование и неудачи

### 8.1 Все 12 естественных изображений Set12

**ИЗМЕРЕНО: 22.5114×**, 95% bootstrap по **12 изображениям**, не по повторным замерам: **[22.1564; 22.9141]**.
Полный PNG-to-output endpoint: **3.792760 с → 0.168482 с**.
Завершены **180/180 пар**, 12 изображений × 5 seed × 3 повтора; неудачных/пропущенных пар: **0**.
RMSE **0.14715508575001 → 0.14715508575008**; все исходные guards пройдены.
Максимальное расхождение mean **3.683e-11**, variance **9.548e-15**.

Использованы **все** PNG Set12, без выбора по качеству. Corpus закреплён до декодирования по commit/blob/SHA-256. Для каждой картинки отдельная пространственная GP: train — 8192 пикселя на coarse Cartesian grid, test — 512 **других** пикселей. Время включает PNG decode, выбор train/test, шум, centering, fit, все mean+variance и запись. Оси после округления индексов могут быть неравномерными; алгоритму нужна Cartesian-структура, не равномерный шаг.

Это **не** стандартный SOTA super-resolution benchmark: абсолютный RMSE показывает, что фиксированный гладкий GP для фотографий далёк от лучшего image-реконструктора. Проверяется сохранение **этой** модели на естественных targets, а не превосходство качества над современными image-моделями. Структурное ограничение не исчезает.

| Изображение | Пар | Cold ускорение | Baseline RMSE | Method RMSE | Guards |
|---|---:|---:|---:|---:|---|
| 01.png | 15 | 22.802× | 0.14144970 | 0.14144970 | pass |
| 02.png | 15 | 24.143× | 0.11512261 | 0.11512261 | pass |
| 03.png | 15 | 22.767× | 0.16178196 | 0.16178196 | pass |
| 04.png | 15 | 22.747× | 0.14733440 | 0.14733440 | pass |
| 05.png | 15 | 22.195× | 0.19008235 | 0.19008235 | pass |
| 06.png | 15 | 23.212× | 0.14610953 | 0.14610953 | pass |
| 07.png | 15 | 22.141× | 0.17751408 | 0.17751408 | pass |
| 08.png | 15 | 21.975× | 0.13836442 | 0.13836442 | pass |
| 09.png | 15 | 21.630× | 0.15605633 | 0.15605633 | pass |
| 10.png | 15 | 22.080× | 0.12892509 | 0.12892509 | pass |
| 11.png | 15 | 21.818× | 0.13622765 | 0.13622765 | pass |
| 12.png | 15 | 22.774× | 0.12689291 | 0.12689291 | pass |

[Протокол](research/external_protocol.json), [все 180 пар](results/external_set12.csv), [сводка](results/external_set12_summary.json), [provenance](research/external_corpus_manifest.json).

### 8.2 Scaling — где 10× не получается

На каждом размере: **3 seed × 2 повтора = 6 пар**, test=512. Это отдельные запуски и отдельные временные условия, не замена первичной строки 8192. Все исходные quality guards пройдены.

| Train N | Размер | Dense → original spectral, cold | Better-layout dense → NumPy spectral, cold |
|---|---|---:|---:|
| 256 | 16×16 | 1.032× | 2.417× |
| 1024 | 32×32 | 1.223× | 2.977× |
| 4096 | 64×64 | 3.473× | 7.679× |
| 8192 | 128×64 | 14.007× | 29.713× |
| 12288 | 128×96 | 28.218× | 72.930× |

[Исходный scaling CSV](results/scaling.csv), [NumPy/stronger-baseline CSV](results/scaling_tuned.csv). Для малых матриц выигрыш съедают startup/import/I/O; утверждать 10× на каждом размере неверно.

### 8.3 Пропуски в сетке — честный отрицательный результат

Matrix-free PCG использует точный full-grid inverse как ограниченный preconditioner. Но после удаления точек это **не** точный inverse observed covariance. Для каждого из 512 posterior variances потребовались дополнительные CG solves. Все они включены в полное время.

| Пропущено | Baseline mean, с | PCG mean, с | Полный speedup | То есть медленнее | Guards / пар |
|---|---:|---:|---:|---:|---|
| 1% | 3.401581 | 21.366319 | 0.15920× | 6.28× | 5/5 |
| 10% | 2.778364 | 46.812289 | 0.05935× | 16.85× | 5/5 |
| 30% | 1.845721 | 57.324656 | 0.03220× | 31.06× | 5/5 |
| 50% | 0.996926 | 54.726033 | 0.01822× | 54.89× | 5/5 |

Завершены все 3 pilot + 20 full пары, без timeout/выборочного исключения. Факт прохождения качества **не** превращает замедление в ускорение. Быстрый training/mean-only компонент здесь не доказывал бы ускорения full mean+variance системы. Нельзя переносить неудачу именно этого preconditioner/скалярных solves на все возможные structured missing-data методы.

[Все исправленные результаты](results/masked_extension_fixed.csv), [план](research/extension_protocol.json), [код](tensor_gp/masked.py).

### 8.4 Плохая обусловленность — 10× без потерь не универсально

Фиксированный заранее sweep: 6 noise variances × 3 lengthscale pairs × 3 seed = **54 пары**. Генеративный шум данных остаётся std=0,05, меняется model regularization; это stress test, не поиск нового основного benchmark. Допуски не ослаблены, jitter не добавлен, спектр не обрезан.

| Model noise variance | Все guards pass | Завершились, но guards FAIL | Solver failure |
|---|---:|---:|---:|
| 0.1 | 9 | 0 | 0 |
| 0.0025 | 9 | 0 | 0 |
| 1e-06 | 2 | 7 | 0 |
| 1e-10 | 0 | 9 | 0 |
| 1e-14 | 0 | 3 | 6 |
| 1e-16 | 0 | 0 | 9 |

Итого **20 pass, 19 quality/guard failures, 15 solver-failure пар**. Иногда RMSE ещё укладывается в допуск, но не проходит более строгий NLL guard при огромном NLL маленькой noise variance — такая строка всё равно **не** считается lossless. При почти нулевом noise обе реализации могут численно потерять SPD. Без high-precision reference нельзя объявить одну из них абсолютной истиной. Эти строки не входят в положительную оценку ускорения.

[CSV всех 54 случаев](results/numerical_robustness.csv), [сырые ошибки](results/runs/numerical_robustness), [протокол](research/robustness_protocol.json).

### 8.5 Найденная ошибка измерителя — аннулирование, не сокрытие

В первом вспомогательном missing-grid запуске decimal run ID вроде `missing0.01_...` передавался в `Path.with_suffix`. Метод отбрасывал часть имени после точки, и два prediction-файла могли совпадать. **Три старые pilot-пары имеют недействительные pointwise guard-сравнения**; шесть завершённых попыток и одна прерванная full попытка сохранены и помечены invalid. Их числа не используются для выводов. Процесс остановлен сразу после обнаружения, новый полный план заново запущен под `masked_extension_fixed`.

Исправление: расширение добавляется, не заменяется; evaluator запрещает общий путь, записывает SHA-256 и отвергает перезаписанный artifact. Есть реальные CLI regression tests с точками в именах. Все 30 первичных файлов имели разные имена без точек в stem; они независимо перепроверены, их сохранённые SHA-256 совпали, RMSE и все 15 guard-сравнений пересчитаны. Первичный результат не затронут.

[Явное аннулирование](results/masked_extension_INVALIDATED.json), [исторические попытки](results/runs/masked_extension), [регрессионные тесты](tests/test_measurement_integrity.py), [проверка целостности](results/integrity_audit.json), [полные held-out predictions первичных seed](results/primary_predictions.csv).

Дополнительная неподтверждённая гипотеза: подозревалось, что diagonal update через `.flat` объясняет секундный kernel stage. Проверка 27 component trials этого **не подтвердила**: при N=8192 сами diagonal updates занимали доли миллисекунды. [Отрицательный диагностический результат](results/diagonal_component_diagnostic.json). Его не выдают за системное ускорение.

## 9. Воспроизведение

```bash
bash reproduce.sh        # tests + все primary pairs + four-way audit
bash reproduce.sh --all  # все дополнительные положительные и отрицательные исследования
```

Тестирован Linux/CPython 3.11, NumPy 2.2.6, SciPy 1.15.3, sklearn 1.7.2, OpenBLAS; два потока BLAS одинаковы у обоих методов. GPU не используется. [Полный фактический environment](results/environment.json).

**Проверен целиком именно краткий entrypoint** (tests + primary + four-way). Все дополнительные исследования реально выполнены отдельными CLI-запусками, однако единая длинная команда `--all` целиком повторно не прогонялась; её интеграционный результат отдельно не заявляется. Запуски создают новую `artifacts/reproductions/<UTC>/`, не затирают опубликованные результаты и не ждут старого research-deadline. Внешние изображения скачиваются через GitHub API с проверкой закреплённых хешей. Большие массивы и окружение не добавлены в Git. [README](README.md), [код runner](tensor_gp/reproduce.py), [requirements](requirements.txt).

## 10. Источники и трактовка результата

- [scikit-learn 1.7.2 GP source](https://github.com/scikit-learn/scikit-learn/blob/1.7.2/sklearn/gaussian_process/_gpr.py): использует dense Cholesky и batched triangular posterior-variance solve, как первичный baseline.
- [linear_operator Kronecker + diagonal source](https://github.com/cornellius-gp/linear_operator/blob/main/linear_operator/operators/kronecker_product_added_diag_linear_operator.py): существующая реализация аналогичной известной спектральной идеи. [Зафиксированные source blob IDs](research/references.json).
- [Все исходные гипотезы](research/brainstorm.md), [математика](research/math.md), [журнал всех попыток](results/experiments.jsonl), [tool-clock журнал](work_log.md).

Цифры относятся к названным моделям, endpoint и hardware. Они **не** означают, что получен новый data-agnostic метод «ускорять любой ИИ без потерь». Структурно подходящая задача объявлена заранее, все seed/варианты публикуются; тем не менее выбор такой области — существенное ограничение независимости benchmark. Требование общего ускорения вне этой области остаётся недоказанным.

<!-- publication-audit -->
## 11. Математика сложности, память и закон Амдала

**РАССЧИТАНО, не hardware-counter measurement:** dense Cholesky требует около `N³/3` leading FLOPs, batched predictive variance — `M N²`; tensor fit — `O(nx³+ny³+N(nx+ny))`, off-grid mean+variance — `O(M(nx²+ny²)+MN)`.
Для N=8192, M=512: Cholesky **183,25 млрд** leading FLOPs, variance solve **34,36 млрд**. Tensor forward training transform — около **3,15 млн**, cross-basis transforms — **20,97 млн**, каждый mean/variance contraction — около **8,39 млн**, плюс полные маленькие eigensystems. Константа eigensolver не приравнивается к одному FLOP на куб; теоретические тысячи раз сокращения arithmetic **не** выдаются за измеренные wall-clock тысячи раз.

**РАССЧИТАНО:** principal model arrays dense — **536 936 448 bytes**, tensor — **294 912 bytes**. Это не RSS: оси, Python, inputs, temporaries, BLAS и runtime не входят. **ИЗМЕРЕНО:** peak RSS в первичном опыте **1 134 878 720 → 67 653 632 bytes**. Полное обучение sklearn GPR достигает **1 741 225 984 bytes**, tensor — **82 513 920 bytes**. Пропускная способность памяти не подменяется теоретическим vendor peak: dense должен хранить/переносить N² doubles, tensor этого вообще не материализует.

Для исходного baseline доля Cholesky во всём cold endpoint — примерно **41.78%**. Если ускорить **только её** в 10 раз, Амдал даёт

`S = 1 / ((1 − f) + f/10) = 1.6026×`, **не 10×**.

В нашей системе устранены и dense kernel materialization, и cubic fitting, и dense posterior-variance solve. Средний остаток `cold − internal pipeline` около **0.2642 с**. Если условно считать эту startup/output-часть неизменной, её Амдал-cap около **14.14×**; отсюда арифметическое сокращение на порядки не даёт такого же cold-speedup. NumPy-only путь отдельно уменьшает сам import/runtime overhead. Главные **измеренные** числа остаются 11,54× / 30,33× / 276,78× в своих разных, явно названных экспериментах.

[Полный вывод, bandwidth/conditioning](research/math.md), [точные objective/gradient формулы](research/hyperparameter_math.md).

## 12. Ограничения и недоказанные переносы

- Реализация двумерная. Нужны **полная обучающая Cartesian grid**, separable kernel и scalar noise. Off-grid test inputs допустимы; arbitrary off-grid training inputs — нет. При одной длинной оси и другой размера 1 eigensystem сам остаётся кубическим: заявленного выигрыша для общего 1D GP нет.
- Это не новая Kronecker-теория и не превосходство над существующими специализированными Kronecker GP библиотеками. Generic dense LAPACK/sklearn — реальные широко используемые baseline, но не best-in-class structured solvers.
- Первичный benchmark специально структурный и синтетический. Все seed и естественные Set12 targets убирают выбор только удачных outputs, **но не устраняют выбор выгодной области задач**. Ускорение на независимо заданной неструктурированной AI-задаче не установлено. Если запрет «подбирать данные под метод» трактовать как запрет любой такой структурной специализации, общий успех по этому более строгому требованию **не подтверждён**; результат остаётся ограниченным специальным случаем.
- Качество image-GP не SOTA. Сохранение слабого абсолютного image-score не делает его полезной заменой современным vision-моделям; ценно здесь тождество вероятностной модели и полная проверка скорости в этой задаче.
- Near-singular float64 settings действительно не проходят guards. Никакого обещания «без потери на всех данных/числах» нет.
- Выигрыш зависит от N, количества запросов, mean-only против mean+variance, startup и библиотеки. Нет 10× на маленьких задачах; нельзя выдавать 63× internal или 1697× training-internal за полный cold-speedup.
- CPU VM не эксклюзивная. Bootstrap содержит 5 primary seed-кластеров / 12 image-кластеров; это ограниченная описательная статистика, не гарантия переноса на другое железо, GPU или Transformer/LLM.

## 13. Воспроизводимость и последний контроль времени

Документированная команда `bash reproduce.sh --output artifacts/reproduction_check` реально выполнена: все 4 этапа завершились с exit 0. Длительности runner stages: environment=0.124 с, tests=3.218 с, primary=60.386 с, four_way=120.459 с. Зависимости на этом повторе уже были установлены; это не заявление о времени fresh network install. Оригинальные данные/CSV не перезаписаны. [Индекс реального повтора](results/reproduction_check.json).

Оставшееся окно использовано на заранее объявленные **новые seed 100..399**, по порядку, без фильтра по score. Завершено 111 сравнений, failed pairs: 0; не начатые из-за времени seed сохранены. Отдельный late-time strong-dense → NumPy результат: **31.8693× [31.4514; 32.2663]**, all quality guards=True. Он **не объединён** с первичными 15 парами. [План/правило остановки](research/late_audit_protocol.json), [CSV](results/late_stability.csv), [сводка](results/late_stability_summary.json).

До истечения бюджета выполнено ещё **119914** независимо seeded random-RHS residual probes полного tensor solve: max relative residual **6.421e-11**, предел **1e−8**, failed probes **0**. Это дополнительная algebraic correctness check, **не новое измерение системного ускорения**. [Все итоги](results/deadline_residual_audit.json).

**Финальная проверка инструмента:** UTC **2026-10-17T15:29:46.240301+00:00**, wall elapsed **5470.527269 с**, monotonic elapsed **5470.527267 с**, оба ≥5400. До этого файл был явно помечен предварительным и не сдавался как финальный. [Машиночитаемое доказательство времени](results/deadline_proof.json), [полный рабочий журнал](work_log.md).
