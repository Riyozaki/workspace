# Исследование: система работы с документами уровня Claude.ai и выше

**Дата:** 2026-08-20
**Статус:** исследование завершено; DOCX, XLSX, PPTX и PDF vertical slices реализованы после этого отчёта — см. [`docs/architecture/document-system.md`](../architecture/document-system.md)
**Объект:** создание, чтение, редактирование, конвертация и проверка DOCX/XLSX/PPTX/PDF и смежных форматов в среде выполнения Arena + Git-репозиторий

## 1. Краткий вывод

1. **Да, LibreOffice у Claude действительно используется**, но не как основной редактор и не как «Word в браузере». Это скрытый headless-движок для:
   - рендера DOCX/PPTX в PDF перед визуальной проверкой;
   - конвертации старых `.doc`/`.ppt`;
   - пересчёта формул XLSX;
   - некоторых операций с tracked changes.
2. Основная сила Claude.ai — не один LibreOffice, а связка:
   - изолированный компьютер с файловой системой и исполнением кода;
   - форматные Skills, загружаемые по необходимости;
   - специализированные библиотеки и прямое редактирование OOXML;
   - обязательные структурные, содержательные и визуальные проверки;
   - итерация «создать → отрендерить → посмотреть → исправить → проверить снова».
3. Официальные документные Skills Anthropic **source-available, но не open source**. Их можно изучать как референс, но нельзя просто скопировать в наш репозиторий и строить на них производную реализацию без подходящего лицензионного основания.
4. Загруженный `docx.zip` от Kimi полезен как источник архитектурных идей, но **его нельзя использовать как основу продукта**:
   - лицензия разрешает использование только внутри сервисов Moonshot AI и запрещает копирование, изменение и распространение;
   - WIR-движок закрыт в бинарных `.so`;
   - бинарники собраны для CPython 3.12, тогда как наша среда использует Python 3.11;
   - нет полноценной обязательной визуальной QA-петли;
   - bootstrap скачивает .NET через неприкреплённый сетевой install script.
5. Нужна **собственная clean-room система** на библиотеках с разрешительными лицензиями. Skills должны быть лишь управляющим слоем; реальная надёжность должна находиться в детерминированных инструментах, валидаторах, рендерерах и тестах.

## 2. Что официально известно об архитектуре Claude.ai

### 2.1 Исполнительная среда

Anthropic пишет, что создание файлов работает через «private computer environment», в котором Claude пишет код и запускает программы. Более позднее инженерное описание уточняет: code execution в Claude.ai выполняется серверно в изолированном **gVisor-контейнере**, файловая система эфемерна в рамках сессии, локальная машина пользователя недоступна.

Практическая модель:

```text
пользовательский запрос + вложения
              ↓
      модель выбирает Skill
              ↓
эфемерный Linux-контейнер с bash/FS/кодом
              ↓
 библиотеки + скрипты + LibreOffice/Poppler
              ↓
     созданный или изменённый файл
              ↓
      публикация файла пользователю
```

Это принципиально не «магия внутри модели». Качество создаёт агентная петля поверх полноценного компьютера.

### 2.2 Skills и progressive disclosure

Skill — каталог с `SKILL.md`, скриптами, шаблонами и справочными файлами. Anthropic описывает три уровня загрузки:

1. **Metadata:** имя и описание всегда доступны модели и помогают выбрать Skill.
2. **Instructions:** тело `SKILL.md` читается только после срабатывания Skill.
3. **Resources/code:** дополнительные справочники читаются, а скрипты запускаются только по необходимости.

Это важно для нашей системы: нельзя складывать огромную инструкцию по всем форматам в один системный промпт. Нужен компактный роутер и отдельные форматные/операционные руководства.

### 2.3 Входные файлы и визуальное понимание

Claude.ai официально принимает PDF, DOCX, CSV, TXT, HTML, ODT, RTF, EPUB, JSON и XLSX при включённом code execution. Для обычной загрузки:

- PDF до 100 страниц анализируется как текст + визуальные элементы;
- PDF 101–1000 страниц — только текст;
- для non-PDF документов базовый upload pipeline извлекает текст и не понимает вложенные изображения автоматически.

Документные Skills компенсируют последнее: Office-файл рендерится в PDF/изображения внутри контейнера, после чего модель визуально проверяет страницы или слайды.

## 3. Что именно делает LibreOffice

Проверен актуальный `anthropics/skills` на коммите `0a64e398ec6bb34a494f0c347e8ccae53a862f8e` от 2026-08-18.

### DOCX

Основной маршрут официального Skill:

- чтение: Pandoc;
- создание: npm-библиотека `docx` (`docx-js`);
- редактирование существующего файла: распаковка ZIP → точечное изменение OOXML → упаковка;
- проверка внешнего вида: LibreOffice headless → PDF → Poppler `pdftoppm` → просмотр изображений;
- legacy `.doc`: конвертация через LibreOffice;
- tracked changes/comments: прямой OOXML + специализированные скрипты; принятие изменений частично опирается на LibreOffice.

### XLSX

- создание/редактирование: `openpyxl`, `pandas`;
- чтение модели: отдельные проходы для формул и cached values;
- **пересчёт формул через LibreOffice обязателен**;
- после пересчёта проверяются `#REF!`, `#VALUE!`, `#DIV/0!` и другие ошибки.

### PPTX

- создание: `PptxGenJS`;
- редактирование шаблонов: точечный OOXML;
- структурная проверка отношений, content types, charts и слайдов;
- визуальная QA: LibreOffice → PDF → изображения слайдов;
- отдельные проверки на переполнение, перекрытия, остаточные placeholders и плохой контраст.

### PDF

LibreOffice здесь не является центральным инструментом. Используются библиотеки для PDF, Poppler, формы, извлечение таблиц, rasterization и OCR-маршрут.

### Вывод

**LibreOffice — compatibility/rendering worker, а не authoring core.** Делать всю систему через UNO или автоматизацию GUI LibreOffice было бы ошибкой: round-trip через LibreOffice способен менять OOXML, терять неподдерживаемые элементы и расходиться с Microsoft Office. Его следует использовать на копиях и для узких операций.

Для параллельного headless-запуска каждому процессу нужен отдельный `UserInstallation` profile, плюс timeout. Официальные Skills используют собственный wrapper `soffice.py` именно из-за особенностей sandbox и профилей.

## 4. Почему официальный подход работает

Сильные стороны не в конкретном prompt, а в инженерных правилах:

1. **Маршрут зависит от операции.** Создать с нуля, отредактировать существующее, прочитать и конвертировать — разные задачи с разными движками.
2. **Существующий Office-файл не пересоздаётся.** Для сохранения fidelity меняются минимально необходимые XML-части.
3. **Детерминированные операции вынесены в скрипты.** Модель не импровизирует упаковку, комментарии, relationship-файлы и валидацию каждый раз.
4. **Структурная валидность недостаточна.** Файл может быть валидным XML, но иметь съехавший макет; поэтому нужен render-and-look.
5. **Визуальная правка итеративна.** После каждого исправления PDF и изображения генерируются заново.
6. **Контент проверяется независимо от картинки.** Извлечённый текст, placeholders, формулы, notes/comments и количество изображений проверяются отдельно.
7. **Форматные ограничения явно перечислены.** Например, порядок OOXML-элементов, особенности таблиц, bullets, TOC и page breaks.

## 5. Аудит текущего репозитория и среды Arena

### 5.1 Репозиторий

Сейчас отслеживаются только:

- `README.md`;
- `docx.zip`.

`docx.zip`:

- SHA-256: `d5fd3331be306eabea02e2aa0fb1b1ef94aa79819a5e17eed49d00b83e731988`;
- размер ZIP: около 7 MiB;
- распакованный размер: 22,965,529 bytes;
- 38 файлов;
- 7 бинарных файлов занимают 22,700,872 bytes (сюда входят и стандартные DLL Open XML SDK).

ZIP пока не является автоматически обнаруживаемым Skill: он просто лежит как архив.

### 5.2 Runtime

Текущая база:

- Debian 12;
- Python 3.11.2;
- Node 22.22.3 / npm 10.9.8;
- доступны `apt-get`, `sudo`, `gcc`, `zip`, `unzip`;
- около 20 GiB свободного диска и 3.8 GiB RAM;
- отсутствуют LibreOffice, Pandoc, Poppler, .NET и fontconfig/fonts;
- отсутствуют основные Python-библиотеки для документов;
- отсутствуют npm-пакеты для DOCX/PPTX.

Следствие: сейчас ни Claude-подобный, ни Kimi-подобный pipeline полноценно не заработает без воспроизводимого bootstrap.

## 6. Аудит Kimi `docx.zip`

### 6.1 Архитектура

В архиве три маршрута:

1. **Create:** C# + Microsoft Open XML SDK.
2. **WIR:** редактирование существующего DOCX через закрытый Python native engine.
3. **md2docx:** преобразование Markdown от subagents в DOCX.

Есть хорошие идеи:

- разделение creation/editing;
- C# Open XML SDK для пакетной структуры и native charts;
- business-rule validation поверх schema validation;
- отдельные справочники для charts, OMML, citations и оформления;
- принцип «шаблон дан → заполнять, а не передизайнивать»;
- обложки, колонтитулы, TOC и именование результата как часть стандарта качества.

### 6.2 Блокирующие проблемы

#### Лицензия

`LICENSE.txt` говорит, что материалы являются собственностью Moonshot AI, предоставлены для использования внутри сервисов Moonshot AI и не могут воспроизводиться, изменяться или распространяться. Поэтому:

- нельзя распаковать этот Skill в рабочую кодовую базу;
- нельзя модифицировать launcher или WIR;
- нельзя поставлять бинарники как часть нашей системы;
- нельзя строить производную реализацию из его кода.

Допустимо использовать только абстрактные инженерные наблюдения и независимо реализовать аналогичные возможности.

#### Совместимость

- `scripts/docx_lib/_core.cpython-312-...so` и `scripts/engine/_core.cpython-312-...so` рассчитаны на CPython 3.12.
- В Arena Python 3.11, поэтому оба импорта завершаются `ModuleNotFoundError`.
- .NET отсутствует.
- Launcher при `init` скачивает `https://dot.net/v1/dotnet-install.sh` и устанавливает текущий канал 8.0; это сетевой и неприкреплённый bootstrap.
- Рабочий каталог жёстко задан как `/tmp/docx-work`, что создаёт коллизии при нескольких заданиях.

#### Безопасность и аудитируемость

Главный WIR engine закрыт в 15 MB native `.so`. Полностью проверить его поведение без reverse engineering нельзя, а reverse engineering прямо запрещён лицензией. Запускать такой компонент над пользовательскими конфиденциальными документами в нашей системе не следует.

#### QA

Build pipeline выполняет OpenXML validation, business rules и текстовую статистику, но Skill не задаёт столь же строгую обязательную визуальную петлю, как Anthropic: render → изображения всех страниц → визуальный просмотр → исправление → повторный render. «Designer-quality» без такого gate остаётся декларацией.

### 6.3 Решение по архиву

- Сохранить как пользовательский исследовательский артефакт до отдельного решения владельца репозитория.
- Не распаковывать в продуктовые каталоги.
- Не исполнять закрытые `.so`/DLL в рабочем pipeline.
- Не коммитить производные файлы.
- Взять в собственный дизайн только идеи маршрутизации, native charts, OMML, content/business validation и template-preservation.

## 7. Лицензии официальных Skills Anthropic

README `anthropics/skills` прямо разделяет:

- многие example Skills — open source, обычно Apache-2.0;
- `docx`, `pdf`, `pptx`, `xlsx` — **source-available, not open source**.

Лицензия документных Skills запрещает сохранение копий вне Services, воспроизведение, создание производных работ и распространение. Поэтому в наш репозиторий нельзя просто скопировать их `SKILL.md` и scripts.

Правильная стратегия:

- публичные материалы использовать для исследования поведения и требований;
- написать собственные Skills с нуля;
- использовать открытые стандарты OOXML/OPC/PDF и библиотеки с совместимыми лицензиями;
- хранить provenance и список лицензий каждой зависимости.

## 8. Предлагаемая архитектура нашей системы

### 8.1 Принцип

Не «один большой Skill», а платформа из семи слоёв:

```text
1. Intake & safety
2. Router & task plan
3. Format adapters
4. Author/edit engines
5. Render/compatibility workers
6. QA gates
7. Delivery & provenance
```

### 8.2 Intake & safety

Для каждого входного файла:

- определить тип по сигнатуре/MIME, а не только расширению;
- вычислить SHA-256;
- для ZIP/OOXML проверить path traversal, symlinks, zip bombs, размеры и число entries;
- обнаружить macros, embedded OLE, внешние ссылки и remote templates;
- извлекать XML только безопасным parser без external entities;
- считать содержимое документа недоверенным: текст внутри файла может содержать prompt injection;
- никогда не менять исходник in-place.

### 8.3 Router

Классифицировать задачу минимум по двум измерениям:

**Операция:**

- inspect/read;
- create;
- edit-preserving-format;
- fill-template;
- redline/comment;
- convert;
- compare/diff;
- batch/cross-format.

**Требуемая fidelity:**

- content-only;
- structure-aware;
- layout-sensitive;
- exact-template-preservation.

От этих двух параметров выбирается движок. Нельзя превращать «есть DOCX» автоматически в «прочитать Pandoc» или «открыть python-docx».

### 8.4 Форматные adapters

#### DOCX

- Семантическое чтение: Pandoc + собственный OOXML extractor для headers, footnotes/endnotes, comments и revisions.
- Создание: сначала сравнить на evals C# Open XML SDK, `docx` npm и `python-docx`; выбрать основной маршрут по качеству, а не по чужому запрету.
- Сложное создание: Open XML SDK или собственный OOXML layer для charts, OMML, fields и comments.
- Редактирование: минимальные OOXML patches с сохранением неизвестных частей пакета.
- Визуальная проверка: LibreOffice → PDF → raster/contact sheet.

#### XLSX

- Данные: pandas.
- Структура/форматирование/edit: openpyxl.
- Богатое создание при необходимости: XlsxWriter.
- Формулы: LibreOffice recalc на контролируемой копии + повторное чтение cached values.
- Проверки: formula errors, broken refs, merged cells, hidden sheets, external links, macros, print areas и charts.

#### PPTX

- Создание: PptxGenJS как кандидат по умолчанию.
- Редактирование шаблона: точечный OOXML или python-pptx только там, где round-trip доказан тестами.
- Проверки: package relationships, missing media, content inventory, overflow/overlap heuristics.
- Визуальная проверка каждого слайда через PDF и contact sheet.

#### PDF

- Чтение текста/таблиц: pypdf + pdfplumber.
- Создание типографских документов: HTML/CSS + headless Chromium; ReportLab для координатных задач и forms; LaTeX/Tectonic как дополнительный academic route.
- Изображения: Poppler или PDFium.
- Scans: OCR route с явным языком и confidence.
- Forms: AcroForm сначала; overlay только для неинтерактивных форм.

#### Legacy/ODF

- `.doc`, `.xls`, `.ppt`, ODT/ODS/ODP/RTF: LibreOffice conversion worker.
- Исходник и результат сохранять раздельно; сообщать, что конвертация может быть lossy.

### 8.5 LibreOffice worker

Нужна собственная обёртка, которая:

- создаёт уникальный profile на каждый запуск;
- ставит `SAL_USE_VCLPLUGIN=svp`;
- использует `--headless --norestore --nodefault --nolockcheck` там, где применимо;
- задаёт timeout и завершает process group;
- работает в отдельном temporary directory;
- проверяет, что ожидаемый output действительно появился;
- логирует stdout/stderr и версию LibreOffice;
- не разрешает macros и сеть;
- не сохраняет сложный OOXML обратно без явной необходимости.

### 8.6 Единый CLI

Цель — детерминированный `documentctl`, например:

```bash
documentctl inspect input.docx --json
documentctl render input.docx --out work/render/
documentctl validate output.docx --original input.docx
documentctl diff input.docx output.docx --report work/qa/
documentctl recalc workbook.xlsx
documentctl contact-sheet work/render/*.png
```

Модель должна вызывать стабильный CLI, а не каждый раз писать новый ad-hoc script.

### 8.7 QA gates

Каждый deliverable проходит независимые gates:

1. **Package:** ZIP/OPC integrity, relationships, content types, missing media.
2. **Schema:** OOXML/Open XML SDK validation или форматный эквивалент.
3. **Semantic:** требуемый текст, таблицы, formulas, comments, notes, placeholders.
4. **Business rules:** язык, структура, обязательные sections, числа, названия, листы.
5. **Compatibility smoke test:** открытие/рендер в LibreOffice; при возможности отдельный Microsoft Office/Graph worker в будущем.
6. **Visual:** изображения всех страниц/слайдов/областей печати, overflow, overlap, clipping, contrast, пустые страницы.
7. **Round-trip fidelity:** для edits — сравнение исходного и результата, исключая разрешённые изменения.
8. **Safety:** macros/external links/embedded objects не появились неожиданно.

Итог — `qa-report.json` с версиями инструментов и статусом gates. Пользователю по умолчанию показывается основной файл, а отчёт остаётся для диагностики.

### 8.8 Fonts и локали

Для русского и международного контента bootstrap должен установить:

- Noto Sans/Serif;
- DejaVu;
- Liberation;
- Carlito/Caladea как метрически близкие замены Calibri/Cambria;
- Noto CJK и emoji при необходимости.

Рендер должен фиксировать font substitution warnings. Иначе визуальная проверка недостоверна.

## 9. Предлагаемая структура репозитория

```text
AGENTS.md                         # краткое обязательное правило для будущих агентов
skills/
  documents/SKILL.md             # router
  docx/SKILL.md
  xlsx/SKILL.md
  pptx/SKILL.md
  pdf/SKILL.md
  references/
src/document_system/
  cli.py
  intake/
  ooxml/
  render/
  qa/
  adapters/
scripts/
  bootstrap-documents.sh
  install-fonts.sh
tests/
  unit/
  integration/
  evals/
fixtures/
  source/                         # только малые, лицензионно чистые fixtures
docs/
  architecture/
  research/
```

`AGENTS.md` нужен потому, что Arena не обязана автоматически обнаруживать Claude-specific `.claude/skills`. Skills следует хранить vendor-neutral, а при необходимости генерировать адаптеры для Claude Code/API.

## 10. Evaluation-first план

До написания огромных Skills нужно определить измеримые кейсы.

### DOCX vertical slice

1. Создание русскоязычного 8–12-страничного отчёта: cover, TOC, headings, tables, chart, images, headers/footers, page numbers.
2. Заполнение корпоративного шаблона без изменения master formatting.
3. Точечное изменение договора с tracked changes и comments.
4. Замена изображения и текста в сложном DOCX с сохранением остального пакета.
5. Документ с footnotes, endnotes, equations, hyperlinks и section breaks.

### Общая матрица

Для каждого формата: read, create, edit, convert, compare, adversarial/large.

Оценки:

- structural validity;
- semantic correctness;
- visual defects;
- preservation fidelity;
- editability в целевом Office-приложении;
- runtime/memory;
- число итераций модели;
- человеческая blind review.

Цель «лучше Claude» должна означать не впечатление, а лучший суммарный score на нашей матрице, особенно на русских документах, шаблонах, tracked changes и повторяемости.

## 11. Поэтапная реализация

### Phase 1 — фундамент и DOCX vertical slice

- воспроизводимый bootstrap LibreOffice/Pandoc/Poppler/fonts/Python/Node;
- безопасный intake;
- `documentctl inspect/render/validate/contact-sheet`;
- независимый DOCX Skill;
- 5 DOCX evals;
- создание и template-preserving edit с полной QA-петлёй.

### Phase 2 — XLSX

- read/edit/create;
- recalc worker;
- formula error gate;
- charts/print areas/hidden sheets/macros/external links;
- финансовые и обычные spreadsheet evals.

### Phase 3 — PPTX и PDF

- PptxGenJS + template editing + slide QA;
- HTML/CSS PDF creation, PDF forms и OCR;
- cross-format workflows.

### Phase 4 — hardening

- zip bombs, malformed OOXML/PDF, timeouts, resource limits;
- deterministic manifests и provenance;
- batch/concurrency;
- regression corpus;
- optional Microsoft Office compatibility worker.

## 12. Решения, которые не стоит принимать преждевременно

- Не объявлять один authoring library «единственно правильным» без evals.
- Не использовать LibreOffice как основной редактор существующего OOXML.
- Не считать schema validation доказательством визуального качества.
- Не считать PDF-render через LibreOffice доказательством 100% совместимости с Word/Excel/PowerPoint.
- Не загружать модель всеми справочниками сразу.
- Не исполнять proprietary/opaque Skills на пользовательских данных.
- Не ставить зависимости неприкреплёнными командами в каждом задании.

## 13. Рекомендованный следующий шаг

Начать с **Phase 1 / DOCX vertical slice**:

1. создать bootstrap среды;
2. реализовать безопасный LibreOffice wrapper;
3. реализовать inspect/render/validate/contact-sheet;
4. создать первый собственный DOCX Skill;
5. добавить 2 простых и 3 сложных eval-case;
6. только после baseline выбрать основной creation engine между Open XML SDK, docx-js и python-docx/direct OOXML.

Это быстрее приведёт к работающей системе, чем немедленное копирование чужих Skills, и даст фундамент, который затем переиспользуется для XLSX/PPTX/PDF.

## 14. Основные источники

### Anthropic — первичные

1. [Claude can now create and edit files](https://claude.com/blog/create-files) — private computer environment и file creation.
2. [How we contain Claude across products](https://www.anthropic.com/engineering/how-we-contain-claude) — gVisor, server-side ephemeral container Claude.ai.
3. [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview) — progressive disclosure, scripts/resources, security.
4. [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — eval-first, concise Skills, deterministic scripts, visual analysis.
5. [Upload files to Claude](https://support.claude.com/en/articles/8241126-upload-files-to-claude) — supported formats и text/vision limits.
6. [Create and edit files with Claude](https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude) — code execution, package/network behavior.
7. [anthropics/skills](https://github.com/anthropics/skills) — production-reference document Skills and licensing status.
8. [Anthropic DOCX Skill](https://github.com/anthropics/skills/blob/main/skills/docx/SKILL.md) — author/edit/read routes и visual QA.
9. [Anthropic XLSX Skill](https://github.com/anthropics/skills/blob/main/skills/xlsx/SKILL.md) — mandatory LibreOffice recalculation.
10. [Anthropic PPTX Skill](https://github.com/anthropics/skills/blob/main/skills/pptx/SKILL.md) — content/file/visual QA.

### Локальные материалы

11. `docx.zip` и его `LICENSE.txt`, `SKILL.md`, launcher, references и binary metadata — исследованы только во временном каталоге; в репозиторий не распаковывались.

### Дополнительные технические

12. [Microsoft Open XML SDK](https://github.com/dotnet/Open-XML-SDK) — низкоуровневая работа с OPC/OOXML и validator.
13. [Agent Skills standard](https://agentskills.io/) — vendor-neutral структура Skills.
