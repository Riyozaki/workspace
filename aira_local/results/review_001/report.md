# AIra Local Lab v0.2 — ревью отправки сообщений и потока ответа

## Воспроизведённая причина

В исходном commit `0cc469fb4b1bbc426e56e9539959352ecf7e01b2` отправка зависела от
нативного HTML form submit / `requestSubmit()`. В `iframe` с
`sandbox="allow-scripts allow-same-origin"` **без allow-forms** Chromium блокировал
и кнопку, и Enter **до обработчика submit**:

- кнопка не была disabled, но сообщений в UI оставалось0;
- текст оставался в поле;
- ни одного POST `/api/chat` не происходило;
- console: `Blocked form submission ... 'allow-forms' permission is not set`.

[Сохранённое воспроизведение до исправления](before_embedded_reproduction.json).
Флаги конкретного браузера пользователя не инспектировались: это воспроизведение
совпадающего симптома в стандартном sandboxed embedding, а не утверждение о
доступе к его клиенту. Предыдущий standalone-browser smoke не покрывал этот режим.

## Исправления интерфейса

1. Кнопка стала `type=button`, click и Enter вызывают JavaScript fetch напрямую.
   Разрешения внешнего iframe не ослаблялись; native form submit больше не нужен.
2. Добавлены постоянный индикатор связи, понятные ошибки API/HTML вместо JSON,
   reconnect и повтор загрузки модели. Убрано пустое `catch {}` у status polling.
3. Таймауты JSON/status/chat, отмена HTTP при повреждённом потоке, восстановление
   черновика, retry, разблокировка input после ошибок/отмены.
4. История обновляется только после завершённого ответа; HTTP/protocol failures
   не добавляют недоставленные сообщения в будущий контекст. Режим/заметки фиксируются
   на момент отправки, контролы не меняют текущий запрос задним числом.
5. Отдельный SSE parser: LF/CRLF, split delimiters, UTF-8 decoder flush,
   final event без пустой строки, heartbeat, явная ошибка при обрыве без done,
   malformed JSON и ограничения размера события.
6. Enter во время IME composition не отправляет сообщение. Версионированы assets,
   HTML/API/static получают `Cache-Control: no-store`; UI показывает v0.2.
7. Уточнены context history/pair trimming и видимое сокращение старого контекста.
   Поле токенов теперь отличает пустой LM output от отсутствия генерации инструмента.

## Исправления сервера

1. Ресурсную блокировку больше не держит читатель StreamingResponse. Производитель
   запускается до возврата HTTP response и сам освобождает gate в finally, даже если
   браузер не начал читать/закрыл вкладку. Async consumer не выполняет native inference.
2. Per-request cancellation Event, ограниченная очередь, backpressure cancellation,
   heartbeat и кооперативный deadline. Старый запрос не сбрасывает состояние нового.
3. Отмена уже законченного недавнего запроса идемпотентна. Active cancellation ID
   больше не публикуется всем через `/api/status`.
4. Ошибки cleanup/thread-start также освобождают gate. Shared gate остаётся общим
   для генерации/обучения/повтора загрузки: native model не вызывается параллельно.
5. Health/status не зависят от необязательного файла результата пилота. При отсутствии
   router/архива работают явный чат и инструменты; auto корректно отступает к LM.
6. Загрузка модели сериализована; GGUF SHA проверяется до native parsing; partial/error
   model не считается ready. В UI можно повторить загрузку существующих весов.
7. Request-body timeout теперь общий, а не обнуляемый каждым chunk. Сохранён128KiB cap.
8. Checkpoint save атомарен; live-модель заменяется только после успешной записи.
   Проверки лимитов feedback/training защищены; lifecycle telemetry корректно повторяется.

## Другой подтверждённый дефект

Старый extractor выбирал числовую подстроку и терял ведущий минус:
`Посчитай -3+5` мог превратиться в `3+5`. Теперь разбирается **одно полное**
выражение после явной команды, с сохранением знака. Поддержаны Unicode `− × ÷`;
дополнительный текст, несколько выражений и неоднозначные запятые отвергаются,
а не молча интерпретируются как другой пример. Исполнение произвольного кода
по-прежнему запрещено ограниченным AST-интерпретатором.

## Реально выполненные проверки

- Python:65passed,1 сохранённый dependency DeprecationWarning.
  [Лог](tests_backend.txt). Во время фикса был пойман отдельный comma-prefix regression;
  первоначальный failed лог сохранён: [tests_initial.txt](tests_initial.txt).
- Node transport tests:10passed. [Лог](transport_tests.txt).
- Реальный HeadlessChrome133 **внутри iframe без allow-forms**: click, Enter,
  настоящий17-token LM output, калькулятор, заметки, повтор после отмены/обрыва,
  освобождение gate после настоящего HTTP abort, IME, desktop/mobile,
  настоящий teacher feedback job, сохранение LM weights, отсутствие JS/form errors.
- Сетевые отказы, HTML proxy errors и truncated SSE тестировались **явной fault injection**.
  Эти синтетические transport responses не выдаются за работу модели или её качество.
- [Browser checks](browser_checks.json) отдельно разделяют реальные model/backend
  вызовы и injected transport negatives. После исправления blocked form errors=0.

## Сохранение истории и границы

Веса SmolLM2, исходный router checkpoint, данные и все результаты v0.1 не
перетюнивались. Старые33tests/browser/model/holdout результаты сохранены как
исторические, не заменены новыми обещаниями. Полный исходный payload и его seal
относятся к commit0cc469f. Новая версия имеет отдельный delivery seal.

Это ревью **работоспособности**, не улучшение качества языковой модели:
ошибки русского/фактов и плохое обобщение pilot-router остаются. Независимого
подтверждения новой архитектуры/энергии/целевого устройства не появилось.

Отмена native inference кооперативна между шагами: неисправимый зависший native
C-вызов/segfault требует перезапуска процесса, жёсткая subprocess isolation здесь
не заявляется. Preview — не постоянный хостинг и не production multi-user сервис;
после сброса среды нужны setup/run. Приватные данные в общий demo вводить не следует.
