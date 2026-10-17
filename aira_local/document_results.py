"""Document only executed observations; no claims of a new frontier model."""
from pathlib import Path
import json,statistics,re
ROOT=Path(__file__).resolve().parent


def j(p):return json.loads((ROOT/p).read_text())


def main():
 model=j('model_manifest.json');r=j('results/router_ablation.json');runtime=j('results/runtime_api_probes.json');browser=j('results/browser_checks.json');s=r['deployed_holdout'];train=browser['full_training_result'];testtext=(ROOT/'results/tests.txt').read_text();n=re.search(r'(\d+) passed',testtext).group(1)
 report=f'''# AIra Local Lab — первый работающий веб-прототип

## Краткий результат

**ИЗМЕРЕНО:** настоящая SmolLM2-135M-Instruct Q4_1 выполняет CPU-инференс в этой
песочнице через веб-интерфейс. При API-пробах RSS серверного процесса составил
**{runtime['idle_process_rss_bytes']/1048576:.2f} MiB** в наблюдённом idle-окне,
пиковый sampled RSS **{runtime['peak_sampled_process_rss_bytes']/1048576:.2f} MiB**.
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
| Официальная основа | {model['model_id']} |
| Представление | {model['quantization']} |
| Файл, ИЗМЕРЕНО bytes | {model['gguf_bytes']} |
| GGUF SHA-256 | `{model['gguf_sha256']}` |
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
'''
 for row in runtime['raw_cases']:
  answer=row['answer'].replace('|','/').replace('\n',' ')
  report+=f"| {row['mode']}: {row['prompt']} | {answer} | {row['client_http_wall_seconds']:.6f} | {row['metrics']['generated_tokens']} |\n"
 report+='''
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
'''
 for row in r['all_runs']:report+=f"| {row['kind']} | {row['seed']} | {row['fit']['parameters']} | {100*row['development']['accuracy']:.2f}% | {100*row['holdout']['accuracy']:.2f}% | {row['holdout']['wrong_fast_paths']} |\n"
 means={k:statistics.mean(x['holdout']['accuracy'] for x in r['all_runs'] if x['kind']==k) for k in ('linear','loop')}
 report+=f'''
ИЗМЕРЕНО: средняя holdout accuracy linear **{100*means['linear']:.2f}%**, loop
**{100*means['loop']:.2f}%**. До открытия holdout критерий mean-dev coverage выбрал
loop seed0: его holdout accuracy **{100*s['accuracy']:.2f}%**, принят6/36 быстрых
путей, из них1 ошибочный (precision83.33%). Простая рекуррентность не дала выигрыша.
Сам критерий выбора по coverage оказался недостаточным для цели качества.

Результаты **не перетюнивались после holdout**. Исходный checkpoint сохранён,
автороутинг отмечен экспериментальным и **выключен по умолчанию**. Default —
настоящая LM; инструменты можно выбрать явно. [Все6 запусков](results/router_ablation.json).

## AI Babysit: исправленный образец не равен улучшенной модели

ИЗМЕРЕНО в настоящем browser/API запуске:180 дополнительных шагов NumPy из текущих
weights, {train['fit']['train_seconds']:.6f} с. Кандидат выучил новый **учебный**
пример chat→notes. Но development accuracy:
**{100*train['before_development']['accuracy']:.2f}% → {100*train['development']['accuracy']:.2f}%**.
Кандидат **не принят**: `{train['promotion_reason']}`. Предыдущие weights сохранены.
SmolLM2 не изменена; новый независимый holdout не запускался.

Guard добавлен после первой наблюдавшейся регрессии как инженерная защита,
не выдается за исходно пререгистрированное подтверждение. Development при многократной
работе является рабочим диагностическим набором, не слепой внешней оценкой.

[Первая регрессия до guard](results/babysit_regression_observed.json),
[реальное browser выполнение после guard](results/browser_checks.json).

## Проверки и ограничения безопасности

'''
 report+=f'''**ИЗМЕРЕНО:** {n} tests passed; одна сохранённая dependency DeprecationWarning.
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
'''
 (ROOT/'report.md').write_text(report)
 readme=f'''# AIra Local Lab — работающий CPU веб-прототип

**Статус: инженерный прототип, не новая языковая архитектура и не готовый сильный агент.**

Реальная SmolLM2-135M-Instruct Q4_1, потоковая генерация, один nativeCPU thread,
безGPU/стороннего модельногоAPI. В измеренных API-пробах веб-процесс занимал
**{runtime['idle_process_rss_bytes']/1048576:.1f}MiB RSS**. Preview работает в backend
Arena, **не в вашем браузере и не на вашем компьютере**. Ниже — локальный запуск.

## Запуск

Linux x86_64 с AVX2, Python3.11, C/C++ compiler; около4GB RAM хватает в проверенной
среде. Setup требует PyPI; во время inference внешний модельныйAPI не нужен.
Другие платформы/ARM не проверены. Runtime/build и большой GGUF исключены изGit.

```bash
bash aira_local/setup.sh
bash aira_local/run.sh
```

На своей машине откройте `http://localhost:8000`. В Arena откройте live preview
**AIra Local Lab**. Порт можно поменять: `PORT=8001 bash aira_local/run.sh`.
Модель скачивается из pinned PyPI wheel с проверкой SHA-256. Полные источник,
лицензия и hashes: [model_manifest.json](model_manifest.json), [THIRD_PARTY.md](THIRD_PARTY.md).

## Что попробовать

- **Модель:** `Explain what a CPU does in one sentence.` Ответ действительно генерирует LM.
- **Калькулятор:** `Посчитай (18+7)*4` — явный проверяемый инструмент, не способность LM.
- **Заметки:** поиск только в текстах, явно переданных из вкладки «Границы прототипа».
- **AI Babysit:** прогноз маленького router → teacher label/пояснение → реальные180
  шагов дообучения → проверка development → принятие либо отказ от новых weights.
  При регрессии старые weights сохраняются. Языковая SmolLM2 при этом НЕ обучается.
  Автоматического сильного teacher API здесь нет: seed подготовлен агентом офлайн,
  а живое исправление задаёт пользователь.
- Остановка генерации, live RSS/CPU и фактические output-token счётчики.

## Отрицательные результаты — прочитайте до оценки

1. SmolLM2 ошибается в фактах, нарушает простую format-инструкцию и повторяет
   русское приветствие. Это пока не надежный русский чат-агент.
2. Собственный экспериментальный router12987params — **не LM**. На36 отложенных
   формулировках accuracy44.44%; mean трёхseed хуже линейного контроля. Поэтому
   автороутинг экспериментальный и **не включён по умолчанию**.
3. Реальное исправление учителя выучено на учебном примере, но dev accuracy упала
   80.56→72.22%. Проверенный guard отклонил кандидата. Улучшение generalization не заявлено.
4. Нет измеренных ватт/джоулей, целевого-device результатов и доказанного масштабирования.

## Проверки

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest aira_local/tests -q
```

Реально выполнено: **{n} tests passed**, один dependency warning.
Реально проверен desktop/mobile Chromium: streaming, tools, teacher training,
rollback, cancel, no JS errors/overflow. Для повторения optional browser smoke:

```bash
npm install --prefix artifacts/aira_browser --no-audit --no-fund puppeteer-core@24.4.0 @sparticuz/chromium@133.0.0
node aira_local/browser_check.cjs  # сервер уже запущен; добавляет явный demo-feedback
```

Этот smoke извлекает bundled native NSS libraries Chromium, а не требует внешнего
browser service. Нативные зависимости сохраняются только в ignored artifacts/tmp.

## Материалы

- [report.md](report.md) — наблюдения, неудачи, raw replies и границы.
- [research.md](research.md) — расчёты памяти/петель, что нужно доKaggle.
- [PLAN.md](PLAN.md), [work_log.md](work_log.md).
- [router.py](router.py), [app.py](app.py), [engine.py](engine.py), [tools.py](tools.py).
- [Все6 router-прогонов](results/router_ablation.json), [browser checks](results/browser_checks.json), [API probes](results/runtime_api_probes.json).
- [Teacher seed JSONL](data/babysit_seed.jsonl):16 примеров формата, не готовый корпус.

Исторические GP/SVM ускорения не засчитываются в этот прототип. БольшойKaggle trainer
для языковой модели ещё не реализован/не запускался. Нельзя выдавать эту систему
за Haiku-класс, zero-load устройство или подтверждённую новую архитектуру.
'''
 (ROOT/'README.md').write_text(readme)
 print('Documented executed prototype observations; no capability inflation.')
if __name__=='__main__':main()
