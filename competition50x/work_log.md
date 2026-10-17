# Журнал нового запроса: сквозное ускорение около 50×

## Предпусковая проверка — обязательные входные данные отсутствуют

- ИЗМЕРЕНО инструментом `functions.bash`: UTC `2026-10-17T15:53:08.552742+00:00`; Unix `1792252388.5527723`; monotonic `6469.019187991` s. Это время проверки окружения, не результат benchmark и не переиспользованный таймер этапа 1.
- Рабочий каталог: `/home/user/workspace`; ветка `arena/01a0f7e1-workspace`.
- ИЗМЕРЕНО проверкой файловой системы: `/eval/` и `/eval/run_eval.py` отсутствуют. Эталонный организаторский SHA-256 не предоставлен. Никаких попыток изменить, обойти или подменить eval не было.
- В новом запросе baseline указан как незаполненный шаблон `<репозиторий/команда запуска>`; метрика и допуск также не заданы конкретными значениями.
- Не предоставлены публичные входные данные и контракт подключения кандидата к официальной оценке. Скрытые данные не запрашивались и не разыскивались.
- При поиске файлов `run_eval.py`, `eval.py`, `*harness*`, `*competition*`, `AGENTS.md` в доступном рабочем пространстве вне окружения, Git и старых численных артефактов соответствующие инструкции не найдены.
- Начальное рабочее дерево было чистым. Код, baseline, отчёт и доказательства предыдущего исследования не изменены. Этот журнал изолирован в новом каталоге `competition50x/`.
- Измеренное ускорение нового запроса: **не определено**. Качество на скрытой выборке: **не проверено**. Итоговый балл: **не определён**. Числа предыдущего исследования в новый результат не переносятся.

### Блокировка и следующий шаг

Нужно получить конкретные baseline/команду/версию и публичные входы, фиксированные метрику/допуск, а также официальный eval или доступный интерфейс оценки с инструкцией подключения кандидата. Самостоятельно выбирать их вместо якобы фиксированных организаторских условий нельзя. Полноценное новое 90-минутное исследовательское окно и контрольные точки ещё не запущены; время ожидания недостающих условий не выдаётся за проведённый эксперимент.

Если пользователь уточнит, что запрос является шаблоном и разрешает самостоятельный выбор задачи, такой эксперимент нужно отдельно пре-регистрировать и прямо отличать его публичные измерения от отсутствующей независимой проверки на скрытых данных.

# Authorized autonomous study — new timer

## Stage 0: start and environment

- Tool clock UTC 2026-10-17T15:58:57.126796+00:00; Unix 1792252737.1267812; monotonic 6782.889747466. Research budget 5400 s; no final report before BOTH clocks reach 5400 s.
- User explicitly authorizes choosing task, strong baseline, data splits, metric/tolerance and evaluator; freeze in first 600 s. No external/hidden organizer infrastructure is claimed.

## Stage 1 — brainstorm, protocol and frozen evaluator

- Tool clock: `2026-10-17T16:05:39.647947+00:00`; wall `402.521161` s; monotonic `402.521151` s.
- 13 ideas recorded with conditional arithmetic/memory estimates and risks; no measured acceleration. Real Fashion-MNIST, unchanged full training split, local sequestered holdout. Native, threaded and ready ONNX references are selected before custom predictor implementation. Freezing scope/quality within first 600 seconds; installing ready reference now.

## Stage 2 — shared training and unmodified reference measurements

- Tool clock: `2026-10-17T16:09:40.279157+00:00`; wall `643.152373` s; monotonic `643.152363` s.
- Protocol/evaluator sealed before 600 s. Custom predictor not yet implemented. All 60k real training observations; reference-family calibration precedes any optimization.

## Stage 2A — independent source audit and arithmetic derivation while shared training runs

- Tool clock: `2026-10-17T16:11:39.243397+00:00`; wall `762.116610` s; monotonic `762.116600` s.
- No custom predictor has been implemented. Reading ready runtime/libsvm source to check voting, feature semantics and whether batch optimization already exists in the strong reference. Numerical benchmark workers remain sequential.

## Stage 2B — repair baseline-selection control-flow error, preserve all raw measurements

- Tool clock: `2026-10-17T16:19:41.989089+00:00`; wall `1244.862302` s; monotonic `1244.862292` s.
- All 9 reference workers succeeded at accuracy 0.9032. Selection crashed because comparison guard correctly refuses identical prediction paths when canonical native is compared with itself. This is a calibration self-comparison bug, NOT overwritten predictions or numerical invalidation. Recover using a distinct native replicate for that one self-comparison; use all 3 timings per engine, no rerunning/cherry-picking; reference worker/evaluator/protocol unchanged. No optimized predictor written yet.

## Stage 3 — implement and validate three inference systems

- Tool clock: `2026-10-17T16:23:00.172205+00:00`; wall `1443.045418` s; monotonic `1443.045408` s.
- Baseline threaded libsvm locked at mean 22.7585436 s before writing inference.py. Implemented float64 GEMM, float32 GEMM/float64 decisions, and compact NumPy+C integer GEMM. Exact uint8 arithmetic was brainstorm idea 12; it is the third compact system backend, not a new task/model/quality gate. AVX512-VNNI actually present. Build/export cost will be separately charged in non-amortized analysis. Tests use synthetic operator checks and validation only, never holdout.

## Stage 4 — full validation requests

- Tool clock: `2026-10-17T16:24:27.252994+00:00`; wall `1530.126208` s; monotonic `1530.126199` s.
- Round validation_r1; full 5000 validation examples, not holdout. Every declared block/repetition is retained. No primary result yet.

## Stage 4A — inspect all validation ablations, do not open holdout

- Tool clock: `2026-10-17T16:27:33.483793+00:00`; wall `1716.357006` s; monotonic `1716.356996` s.
- All 45 validation workers completed with all gates passed; no cherry-picked rows. Evaluate cold import/load/compute components before further compact implementation changes. Numerical work is sequential. Holdout remains unscored.

## Checkpoint 30 min

- Tool clock: `2026-10-17T16:28:57.127246+00:00`; wall `1800.000451` s; monotonic `1800.000441` s.
- Scheduled real-clock observation; numerical work continues in a separate controlled process, no fabricated timestamps.

## Stage 5 — compact fusion ablation and exact integer microtile upgrade

- Tool clock: `2026-10-17T16:34:48.057780+00:00`; wall `2150.930992` s; monotonic `2150.930983` s.
- Round 1 measured best validation 16.7518x, accuracy 0.9032, agreement 1.0; all 45 runs included. Diagnostic showed native dot 0.481s, float64 distance/exp 0.580s, decisions 0.154s, not headline speedups. Upgrade the compact system only: 16-query contiguous-address microtile and fused exact integer distance + float32 vector exp, with float64 decisions. Frozen eval/quality/model/reference unchanged. Float32 exp is explicitly approximate, unlike integer distances. Unit tests retain old float64 checks and add separate float32 checks.

## Stage 5A — fix native binding error; retain failed attempt

- Tool clock: `2026-10-17T16:35:13.421787+00:00`; wall `2176.295001` s; monotonic `2176.294991` s.
- V2 tests found missing ctypes u8_rbf signature: 21 pass/1 binding failure; the full diagnostic worker also failed and is preserved. Cause: concurrent edits to the same Python file lost the argtypes addition. No quality threshold changed; C integer/fused numerical tests already passed. Fix applied sequentially; all future same-file edits serialized. No failed timing will be called a speedup.

## Stage 5B — remove mixed-precision cast and structural-zero decision work

- Tool clock: `2026-10-17T16:38:46.724749+00:00`; wall `2389.597962` s; monotonic `2389.597952` s.
- Fused V2 full request measured 1.04146 s; exact/float32 kernel 0.459 s, cast 0.228 s, decisions 0.159 s. New V3 keeps float32 kernels and performs native float64 FMA reductions only for the nine logical coefficients per support vector, retaining every SV and every one-vs-one decision. This is the same compact system, not a changed model/metric. Old source/library/preparation records archived. Holdout still unscored.

## Stage 4 — full validation requests

- Tool clock: `2026-10-17T16:40:10.686402+00:00`; wall `2473.559617` s; monotonic `2473.559607` s.
- Round validation_compact_v3; full 5000 validation examples, not holdout. Every declared block/repetition is retained. No primary result yet.

## Stage 6 — optimize real input decoding, preserving identical bytes

- Tool clock: `2026-10-17T16:43:35.658749+00:00`; wall `2678.531963` s; monotonic `2678.531953` s.
- Compact V3 validation: all 15 requests/gates passed, best predeclared block 256 gave 51.1899x versus all-3-run strong baseline mean (SECONDARY validation only). Holdout unscored. Investigating SIMD gzip because decoder is a measured part of the complete request, not trying to omit loading. Same compressed files, same split/labels; byte equality will be tested. Baseline/evaluator remain unchanged.

## Stage 4 — full validation requests

- Tool clock: `2026-10-17T16:45:56.177899+00:00`; wall `2819.051113` s; monotonic `2819.051103` s.
- Round validation_isal_c16; full 5000 validation examples, not holdout. Every declared block/repetition is retained. No primary result yet.

## Stage 6B — validation-only eight-query microtile ablation

- Tool clock: `2026-10-17T16:47:15.020621+00:00`; wall `2897.893834` s; monotonic `2897.893824` s.
- ISA-L decoder byte identity passed; all 15 C16 SIMD-decoder validation requests passed, best 3-run mean 51.874x at block128. Timing noise is visible and 50x on holdout is NOT yet established. Compare query microtile8 against archived C16 using all 5 blocks x3 runs, no data/quality/model changes. Choose by the preregistered validation rule, never by holdout.

## Stage 4 — full validation requests

- Tool clock: `2026-10-17T16:48:19.189649+00:00`; wall `2962.062863` s; monotonic `2962.062853` s.
- Round validation_isal_c8; full 5000 validation examples, not holdout. Every declared block/repetition is retained. No primary result yet.

## Stage 7A — restore validation winner and freeze before first holdout score

- Tool clock: `2026-10-17T16:54:15.103746+00:00`; wall `3317.976960` s; monotonic `3317.976950` s.
- All C8 validation runs passed but were slower (best 46.10x) than C16+ISA-L block128 (51.874x). Retain negative ablation. Select the smallest mean of all three runs, not the fastest individual run. Restore archived C16 source/library; verify byte identity against winning raw worker provenance. No holdout labels/quality have been inspected; no numerical changes permitted after this freeze.

## Stage 7B — complete freeze with the correct interpreter

- Tool clock: `2026-10-17T16:54:52.578074+00:00`; wall `3355.451287` s; monotonic `3355.451277` s.
- Previous restoration checks and 28 tests passed, but the final freeze import used system python without NumPy and failed before writing method_frozen.json. Holdout has NOT run. Record this orchestration failure; retry only the freeze using .venv/bin/python. No numerical code, baseline, quality gate or selection changed. Future multi-command stages use set -euo pipefail.

## Stage 7 — frozen-candidate full holdout inference

- Tool clock: `2026-10-17T16:54:58.512063+00:00`; wall `3361.385276` s; monotonic `3361.385267` s.
- primary: fixed engine=compact, block=128, baseline=threaded; 5 paired fresh processes; no optimization after seeing holdout.

## Checkpoint 60 min

- Tool clock: `2026-10-17T16:58:57.127179+00:00`; wall `3600.000393` s; monotonic `3600.000384` s.
- Scheduled real-clock observation; numerical work continues in a separate controlled process, no fabricated timestamps.

## Stage 8 — independent fresh one-command reproduction

- Tool clock: `2026-10-17T16:59:09.335011+00:00`; wall `3612.208222` s; monotonic `3612.208213` s.
- PRIMARY complete: 5/5 pairs, 45.7853884x [43.8068355,47.7886500], accuracy 0.8972 vs 0.8972, label agreement1.0. 50x NOT achieved. No numerical/model changes after holdout. Now execute documented shell entrypoint from scratch in isolated copied source/data/model directories; all three ready references and all five final pairs repeated, not pooled into primary.

## Stage 8A — documentation and provenance audit during isolated reproduction

- Tool clock: `2026-10-17T17:03:13.513475+00:00`; wall `3856.386688` s; monotonic `3856.386678` s.
- Primary result remains fixed at 45.7854x; no numerical edits after holdout. Restore selected C16 preparation metadata alias (C8 metadata preserved separately) to match the already-restored source/library, not alter measurements. Document validation-CI limitation: generic summaries used a fixed pre-optimization baseline mean, so their bootstrap fields are NOT valid full paired uncertainty; only primary five freshly paired requests provide reported CI. Reproduction currently runs alone as the only numerical workload.

## Stage 8B — assemble provisional report and actual environment record

- Tool clock: `2026-10-17T17:10:10.563126+00:00`; wall `4273.436339` s; monotonic `4273.436329` s.
- No new numerical benchmark overlaps the running reproduction. Report keeps one primary number 45.7854x; all ablations/reproduction are secondary. Correct mathematics to describe float32 exp and float64 sparse native reductions, not pretend bit-exact full inference. Report remains explicitly DRAFT until actual 5400-second gate.

## Stage 9 — completed fresh reproduction and independent integrity audit

- Tool clock: `2026-10-17T17:13:03.664652+00:00`; wall `4446.537865` s; monotonic `4446.537856` s.
- The FULL documented shell command really exited0: new download, new 60k SVC training, all9 ready reference runs, native build, all28 tests, five new holdout pairs. Secondary reproduction44.8160x, same accuracy/agreement; primary45.7854x unchanged. The 600.939s index clock covers the inner study subprocess, not preceding pip/wrapper startup; document that scope explicitly. Now no numerical benchmark is running; independent raw-data/split/source/prediction/CI audit.

## Stage 10 — frozen-system batch-size counterexamples

- Tool clock: `2026-10-17T17:14:07.446223+00:00`; wall `4510.319438` s; monotonic `4510.319428` s.
- SECONDARY only; no retuning. N=2/8/32/128/512/5000, validation prefixes, 3 repeats each, balanced order. Same frozen source/model; actual complete requests, no duplicated data to inflate primary.

## Stage 11 preparation — complete pre-deadline audit and documentation

- Tool clock: `2026-10-17T17:19:30.693000+00:00`; wall `4833.566213` s; monotonic `4833.566204` s.
- Fresh full one-command reproduction passed (all4 stages exit0), all primary metrics/CI/raw inputs/frozen hashes independently audited. Batch-size sweep18/18 pairs complete, all quality gates passed. No numerical source/model changes after holdout. Prepare final documents now; remaining time is reserved for additional real paired requests and random operator boundary probes, followed by automated >=5400s sealing.

## Stage 11 — late stability and deadline operator audit

- Tool clock: `2026-10-17T17:20:12.189703+00:00`; wall `4875.062918` s; monotonic `4875.062908` s.
- Numerical model/code frozen. Predeclare up to 100 complete validation pairs in order, start pairs only before elapsed5280s, baseline timeout45s, method20s. Every attempt kept; no quality/speed selection. Remaining time is random integer/fused-exp/mixed-score boundary tests, NOT a new ML speedup. Final sealing automated after BOTH real clocks reach5400s.

## Checkpoint 85 min

- Tool clock: `2026-10-17T17:23:57.127331+00:00`; wall `5100.000546` s; monotonic `5100.000537` s.
- Scheduled real-clock observation; numerical work continues in a separate controlled process, no fabricated timestamps.

## Stage 13 — real 90-minute publication gate

- Tool clock: `2026-10-17T17:28:57.133668+00:00`; wall `5400.006885` s; monotonic `5400.006874` s.
- Numerical workload stopped; both wall and monotonic deadlines reached. Final report may now be sealed, no fabricated elapsed time.
