# AIra Local Lab — работающий CPU веб-прототип

**Статус: инженерный прототип, не новая языковая архитектура и не готовый сильный агент.**

Реальная SmolLM2-135M-Instruct Q4_1, потоковая генерация, один nativeCPU thread,
безGPU/стороннего модельногоAPI. В измеренных API-пробах веб-процесс занимал
**207.7MiB RSS**. Preview работает в backend
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

Реально выполнено: **33 tests passed**, один dependency warning.
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
