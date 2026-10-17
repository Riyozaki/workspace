# AIra Local Lab v0.2 — исправленное интерактивное CPU-демо

**Реальная маленькая языковая модель + явно отделённые инструменты и pilot AI Babysit.**
Это инженерный прототип, не новая качественная языковая архитектура и не сильный
облачный агент. Preview исполняется в backend Arena, не в браузере пользователя.

## Исправление отправки сообщений

Встроенный iframe без `allow-forms` блокировал старую отправку через HTML form.
Теперь click/Enter вызывают fetch напрямую; флаг allow-forms не нужен. Проверены
реальные модельные ответы **внутри такого iframe**, не только в отдельной вкладке.

Если у вас уже была открыта старая страница, **обновите Live Preview один раз**:
в шапке должна быть `PROTOTYPE 0.2`. При отсутствии связи виден баннер с причиной
и кнопкой повторения, а не бесконечная «загрузка». Ошибки и обрыв потока сохраняют
черновик; отмена/закрытие клиента не оставляют ресурсный gate навсегда занятым.

**[Ревью, исправления и доказательства](results/review_001/report.md)**.
Исторический [отчёт v0.1](report.md) и его отрицательные результаты не переписаны.

## Запуск

```bash
bash aira_local/setup.sh
bash aira_local/run.sh
```

Linux x86_64/AVX2, Python3.11, C/C++ compiler; проверено на двух логических CPU,
около4GB RAM, без GPU. Во время inference нет внешнего модельного API.
Setup требует PyPI; веса скачиваются с pinned SHA, не входят в Git.
Другие платформы/ARM не проверены. На своей машине после запуска откройте
`http://localhost:8000`; в Arena — **Live Preview → AIra Local Lab**, порт8000.
Другой порт: `PORT=8001 bash aira_local/run.sh`.

Preview не является постоянным хостингом: если среда полностью сброшена,
необходимо повторить setup/run. Это не повод показывать в UI ложный статус ready.

## Режимы

- **Модель:** настоящая SmolLM2-135M-Instruct Q4_1,98,362,432bytes GGUF, один native
  inference thread, context1024 и output≤160. Это предобученный контроль, не наши LM weights.
- **Калькулятор:** ограниченный AST без eval/shell. `Посчитай -3+5` даёт2; знак
  сохраняется. Несколько выражений/дополнительный текст/неоднозначные запятые
  отвергаются, не выбирается молча «самая длинная» числовая подстрока.
- **Заметки:** lexical lookup только в переданных текстах. Они отправляются из
  браузера только в режимах «Заметки»/«Авто»; не читается пользовательский диск.
- **Авто · опыт:** экспериментальный intent-router с известной плохой generalization,
  выключен по умолчанию. Нет утверждения, что он надёжный агент.
- **AI Babysit:** явное teacher correction → реальный NumPy backward маленького
  router → dev non-regression guard. Языковая SmolLM2 НЕ дообучается. Сильный
  автоматический teacher API не подключён; seed подготовлен агентом офлайн.

Одна активная операция. При busy/error запрос не теряется: есть объяснение и retry.
История не дополняется недоставленными запросами. Softmax score роутера не считается
калиброванной вероятностью. Необходимое сокращение истории помечается в ответе.

## Проверки v0.2

После setup:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 .venv/bin/python -m pytest aira_local/tests -q
node --test aira_local/tests/test_transport.cjs
```

Реально выполнено: **65 Python tests**, один dependency warning; **10 Node tests**.
Тестируются actual model tokens, ручной backward, ограничения/ошибки, lifecycle,
потеря потребителя, cancellation, checkpoint integrity/atomicity и total body timeout.

Optional real browser smoke (сервер уже работает):

```bash
npm install --prefix artifacts/aira_browser --no-audit --no-fund puppeteer-core@24.4.0 @sparticuz/chromium@133.0.0
node aira_local/browser_review.cjs
```

По умолчанию новый replay пишет результат в ignored `artifacts/aira_browser/review_runs/`,
не переписывая опубликованный отчёт. `--record` — явная запись нового release evidence
в `results/review_001/`; это используется при подготовке текущей публикации.

[Зафиксированная browser-проверка](results/review_001/browser_checks.json) включает
sandbox iframe, настоящие click/Enter/model/tool requests и отдельно обозначенные
simulated transport faults. Старый `browser_check.cjs` — standalone smoke v0.1,
он не является достаточной регрессией для embedded-preview.

## Что осталось ограниченным

Исходный LM ошибается в фактах, нарушает exact-format запрос и повторял русское
приветствие. Router holdout44.44% у выбранного checkpoint; средний loop хуже linear.
Teacher correction исправила учебный пример, но ухудшила development — guard
отклонил кандидата. Эти исходные результаты [сохранены](report.md).

Никаких новых50×, гарантированной энергии/батареи, универсальной bit-exactness,
Haiku-класса и автоматического масштабирования не заявляется. Inference работает
в серверной CPU-песочнице; RSS не включает весь browser/OS page cache. Отмена
кооперативна, не является принудительным прерыванием произвольного native C-вызова.
Нет production-авторизации; используйте только несекретные demo-данные.

## Материалы

- [review_001/report.md](results/review_001/report.md) — текущий bug review.
- [research.md](research.md), [PLAN.md](PLAN.md), [work_log.md](work_log.md).
- [engine.py](engine.py), [jobs.py](jobs.py), [app.py](app.py), [static/transport.js](static/transport.js).
- [Источники/лицензии](THIRD_PARTY.md), [model hashes](model_manifest.json).
- [Router ablation v0.1](results/router_ablation.json), [teacher seed](data/babysit_seed.jsonl).

Kaggle language-model trainer пока не реализован и не запускался. Исторические
GP/SVM ускорения не относятся ни к этому приложению, ни к исправлению его UI.
