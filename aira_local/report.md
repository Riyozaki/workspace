# AIra Local Lab — первый работающий веб-прототип

## Краткий результат

**ИЗМЕРЕНО:** настоящая SmolLM2-135M-Instruct Q4_1 выполняет CPU-инференс в этой
песочнице через веб-интерфейс. При API-пробах RSS серверного процесса составил
**207.66 MiB** в наблюдённом idle-окне,
пиковый sampled RSS **207.66 MiB**.
Один native inference thread, контекст1024, без GPU и внешнего модельного API.

**Это не новая языковая архитектура и не уровень сильного облачного агента.**
Веса языковой модели предобучены HuggingFaceTB и здесь не дообучались. Собственная
маленькая модель — только intent-router. Его первая проверка обобщения **неудачна**.
Ни ускорение50×, ни перенос на реальный слабый компьютер, ни низкие ватты не заявляются.

Preview — backend на CPU Arena, **не inference в браузере пользователя**.
Процесс работает здесь; на другом устройстве измерения надо повторить.

## Что реально реализовано

- Локальная потоковая генерация настоящих token IDs, а не mock/заготовленные ответы.
- Явные режимы «модель», «калькулятор», «заметки», «автороутинг · опыт».
  Инструменты подписаны как инструменты, не приписаны способностям LM.
- Single-operation lock, cancel, output8..160tokens, bounded1024 context,
  ≤8 сообщений, один native thread, input-body cap128KiB, без shell/eval/network tools.
- Телеметрия процесса: sampled RSS/CPU, серверное и клиентское время,
  первый текст, действительное число сгенерированных token IDs. Ватты/джоули=null.
- Онлайн сильный ИИ-учитель не подключен: seed авторствован агентом офлайн,
  живые исправления вводит пользователь.
- Пилот AI Babysit: реальный NumPy backward, явные teacher-исправления,
  checkpoint-кандидат, dev non-regression guard, сохранение прежних весов при регрессии.
- Seed JSONL для будущего SFT:16 примеров,8 проверены арифметикой/JSON,
  остальные явно требуют review. Это не большой обучающий корпус.

## Происхождение модели и сборка

| Факт | Значение |
|---|---|
| Официальная основа | HuggingFaceTB/SmolLM2-135M-Instruct |
| Представление | Q4_1 |
| Файл, ИЗМЕРЕНО bytes | 98362432 |
| GGUF SHA-256 | `b179c9523d0e6a0f98a330c7562b682750a6f8c8c15e5bc70ea373728110db53` |
| Источник данных | `llm-smollm2==0.1.2`, PyPI, SHA distribution проверен |
| Лицензия модели/пакета | Apache-2.0 |
| Runtime | llama-cpp-python0.3.7, CPU AVX2 build, CUDA off/native off/AVX512 off |

Модель извлечена как данные из wheel; plugin не импортировался и не устанавливался.
Модель98MB и build/cache не входят в Git, setup скачивает проверяемый артефакт.
Первоначальная компиляция runtime и download реально выполнены. Затем полный
`bash aira_local/setup.sh` проверен на уже подготовленном окружении (cache verify),
а не повторно измерен как fresh installation. Это различие не скрывается.
Отдельно повторён fresh download/extraction в другую cache-папку: SHA совпал,
опубликованный manifest не переписан; новая длительность хранится отдельно.
[Проверка fresh model setup](results/setup_fresh_model_check.json).

## Реальные API-пробы — инженерная проверка, не benchmark качества

ИЗМЕРЕНО: HTTP client wall от запроса до полного ответа; модель уже resident.
Это не cold process time и не измерение чистого decode. Native generation time
в raw JSON включает prefill+decode, но не всё клиентское HTTP-время.

| Режим / запрос | Реальный ответ | HTTP wall, с | Native output tokens |
|---|---|---:|---:|
| model: Explain what a CPU does in one sentence. | A CPU (Central Processing Unit) is the brain of a computer, responsible for executing instructions and managing data. | 0.678559 | 22 |
| model: What is the capital of France? Answer briefly. | Le Grand Paris is the capital of France. | 0.550018 | 9 |
| model: Reply with exactly the word ready. | I'm ready to assist you. What's your request? | 0.585906 | 12 |
| model: Привет! Кто ты? | Привет! Кто ты? | 0.624952 | 13 |
| calculator: Посчитай (18+7)*4 | (18+7)*4 = 100 | 0.003277 | 0 |
| notes: Найди в заметках план обучения | [План обучения] Большое обучение позже на Kaggle. Сейчас проверяется локальный прототип. | 0.002827 | 0 |

Видны неудачи: «Le Grand Paris» — неточный фактический ответ; exact-one-word
инструкция не соблюдена; русское приветствие повторено. Мы не объявляем это
надежным русским чат-агентом. Цифры калькулятора получены ограниченным AST,
цитата заметки — lexical retrieval переданного текста. Они не доказывают умение LM.

Полные ответы/времена: [runtime_api_probes.json](results/runtime_api_probes.json),
первоначальный [model_smoke.json](results/model_smoke.json).

## Собственная маленькая модель: контрольный отрицательный результат

144 authored synthetic train,36 development,36 holdout; раздельные template families.
Этого недостаточно для оценки реального пользовательского распределения. Три seed
каждого семейства, одинаковые450 optimizer steps, **не одинаковые FLOPs**.
Порог эмпирической fast-path precision≥98% выбран только на development;
это не статистическая гарантия98% на новых данных.

| Модель | Seed | Параметры | Dev accuracy | Holdout accuracy | Ошибки fast path на holdout |
|---|---:|---:|---:|---:|---:|
| linear | 0 | 1539 | 83.33% | 52.78% | 0 |
| linear | 1 | 1539 | 83.33% | 61.11% | 0 |
| linear | 2 | 1539 | 83.33% | 55.56% | 0 |
| loop | 0 | 12987 | 80.56% | 44.44% | 1 |
| loop | 1 | 12987 | 77.78% | 41.67% | 0 |
| loop | 2 | 12987 | 72.22% | 55.56% | 1 |

ИЗМЕРЕНО: средняя holdout accuracy linear **56.48%**, loop
**47.22%**. До открытия holdout критерий mean-dev coverage выбрал
loop seed0: его holdout accuracy **44.44%**, принят6/36 быстрых
путей, из них1 ошибочный (precision83.33%). Простая рекуррентность не дала выигрыша.
Сам критерий выбора по coverage оказался недостаточным для цели качества.

Результаты **не перетюнивались после holdout**. Исходный checkpoint сохранён,
автороутинг отмечен экспериментальным и **выключен по умолчанию**. Default —
настоящая LM; инструменты можно выбрать явно. [Все6 запусков](results/router_ablation.json).

## AI Babysit: исправленный образец не равен улучшенной модели

ИЗМЕРЕНО в настоящем browser/API запуске:180 дополнительных шагов NumPy из текущих
weights, 0.057059 с. Кандидат выучил новый **учебный**
пример chat→notes. Но development accuracy:
**80.56% → 72.22%**.
Кандидат **не принят**: `development regression: previous router retained`. Предыдущие weights сохранены.
SmolLM2 не изменена; новый независимый holdout не запускался.

Guard добавлен после первой наблюдавшейся регрессии как инженерная защита,
не выдается за исходно пререгистрированное подтверждение. Development при многократной
работе является рабочим диагностическим набором, не слепой внешней оценкой.

[Первая регрессия до guard](results/babysit_regression_observed.json),
[реальное browser выполнение после guard](results/browser_checks.json).

## Проверки и ограничения безопасности

**ИЗМЕРЕНО:** 33 tests passed; одна сохранённая dependency DeprecationWarning.
Конечные разности проверяют handwritten backward, включая shared matrix;
проверены реальное изменение весов, checkpoint roundtrip, пределы арифметики,
неисполнение кода, body/token caps, busy lock, реальные streamed LM tokens,
отсутствие текста ответа в telemetry и сброс logical context.

HeadlessChrome133: desktop и mobile, реальные calculator/model requests,
teacher correction/train с новым job ID, видимый rollback, cancel,
отсутствие JS errors и горизонтального overflow. Все required checks прошли.
Изначальный headless запуск не работал безlibnss3 — dependency исправлена; исходная
ошибка сохранена. Исправлена и гонка теста: старый completed-job DOM больше не
считается подтверждением нового обучения.

Чаты не пишутся на диск и не превращаются автоматически в training data. Явные
teacher-исправления — часть общей demo-сессии; кандидатные веса сохраняются в ignored
artifacts. Контекст LM логически сбрасывается после каждого запроса. Это не обещание
криптографического стирания/production multi-user security. Нет авторизации;
чувствительные данные в общую preview сессию вводить не следует.

## Что ещё не установлено

- Нет нового обученного языкового ядра AIra, полноценного SFT на LM или Kaggle-тренировки.
- Нет качества Haiku/DeepSeek, общего владения русским и надежного многошагового агента.
- Нет доказательства, что такой pilot масштабируется в нужные способности.
- Нет измеренной энергии, температуры, battery life, влияния на foreground-приложения.
- RSS процесса не равен всей памяти системы: OS page cache, браузер и setup не учтены.
- Один native thread — не жесткий предел полногоCPU% процесса; web/telemetry потоки тоже есть.
- Нет целевого-device испытания: работали только на CPU текущей Arena-песочницы.
- Текущий135M выбран из-за проверяемой доступности артефакта, не как лучший SLM.

## Следующий полезный этап

Сначала реальные сценарии и бюджет минимального устройства; затем сильный малый
pretrained donor и независимый eval, после этого teacher-SFT control против Babysit.
Архитектурное изменение — отдельно, с проверками gradient path/causality/реального
CPU runtime. Не следует переносить Kaggle ресурсы в ещё одну комбинацию механизмов
до появления качественного контрольного checkpoint.

[Математика/гипотезы](research.md), [scope до эксперимента](PLAN.md),
[журнал с неудачами](work_log.md), [software/hardware](results/environment.json).
