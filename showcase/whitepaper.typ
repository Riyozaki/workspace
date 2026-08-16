// Аналитический отчёт по ГОСТ Р 7.0.97-2016, набор Typst.
//
// Why Typst and not the HTML→PDF path: this is a real typesetting engine with
// Knuth-Plass line breaking and proper ru hyphenation patterns. The .docx build
// has to ask Word to hyphenate and hope; here the breaks are computed at
// compile time, so the justified Russian text has no whitespace rivers.
//
// Geometry is the standard, not a preference: 30/10/20/20 mm margins, A4,
// Times-compatible 14 pt, 1.5 leading, 1.25 cm red line.

#let INK = rgb("000000")
#let NAVY = rgb("1F3864")
#let MUTED = rgb("595959")
#let ZEBRA = rgb("F2F2F2")
#let RULE = rgb("BFBFBF")

#let SERIF = ("Tinos", "DejaVu Serif")
// Tinos has no U+2610/U+2612; DejaVu Sans carries both.
#let SYMBOL = ("DejaVu Sans",)

#let BODY = 14pt
#let SMALL = 12pt
#let NOTE = 10pt
#let INDENT = 1.25cm

// ---------------------------------------------------------------- страница
#set page(
  paper: "a4",
  margin: (left: 30mm, right: 10mm, top: 20mm, bottom: 20mm),
  // ГОСТ: номер страницы снизу по центру; титульный лист не нумеруется.
  footer: context {
    let n = counter(page).at(here()).first()
    if n > 1 {
      set align(center)
      set text(font: SERIF, size: SMALL, fill: INK)
      [#n]
    }
  },
)

#set text(font: SERIF, size: BODY, fill: INK, lang: "ru", hyphenate: true)
// ГОСТ «полуторный» = ~24.1 pt baseline-to-baseline for 14 pt Times. Typst's
// `leading` is the gap between line boxes, not the baseline pitch, so it is
// tuned to hit that pitch; verified by measuring the PDF, not by eyeballing.
#set par(justify: true, leading: 1.09em, first-line-indent: (amount: INDENT, all: true), spacing: 1.09em)

// ГОСТ: заголовки с абзацного отступа, полужирные, без точки в конце.
#show heading: it => {
  set text(font: SERIF, size: BODY, weight: "bold", fill: INK)
  set block(above: 1.2em, below: 0.8em)
  block(par(first-line-indent: (amount: INDENT, all: true), justify: false, it.body))
}

#set footnote.entry(separator: line(length: 40%, stroke: 0.5pt + RULE))
#show footnote.entry: set text(size: NOTE)
#set footnote(numbering: "1")

// Нумерация перечислений по ГОСТ: «1)» на красной строке.
#set enum(numbering: "1)", indent: INDENT, body-indent: 0.4cm, spacing: 1em)
#set list(marker: [—], indent: INDENT, body-indent: 0.4cm, spacing: 1em)

#let caption-table(n, title) = block(
  above: 1.2em, below: 0.5em, breakable: false,
  par(first-line-indent: (amount: INDENT, all: true), justify: false,
      text(size: BODY)[Таблица #n — #title]),
)

#let caption-figure(n, title) = block(
  above: 0.6em, below: 1.2em,
  align(center, par(first-line-indent: 0pt, justify: false,
      text(size: BODY)[Рисунок #n — #title])),
)

// Формула по центру, номер в круглых скобках у правого поля.
#let eq(body, n) = block(above: 1.2em, below: 1.2em, width: 100%, grid(
  columns: (1fr, auto, 1fr),
  align: (left + horizon, center + horizon, right + horizon),
  [], body, text(size: BODY)[(#n)],
))

#let where-block(lines) = {
  for (i, l) in lines.enumerate() {
    par(first-line-indent: (amount: INDENT, all: true),
        justify: true, text(size: BODY, (if i == 0 { "где " } else { "" }) + l))
  }
}

#let checkbox(checked) = text(font: SYMBOL, size: BODY, if checked { "☒" } else { "☐" })

#let cb-line(checked, body) = par(
  first-line-indent: (amount: INDENT, all: true), justify: false,
  checkbox(checked) + h(0.35em) + body,
)

// ------------------------------------------------------------ титульный лист
#[
  #set par(first-line-indent: 0pt, justify: false, leading: 1em)
  #set align(center)

  #text(weight: "bold")[АКЦИОНЕРНОЕ ОБЩЕСТВО «ЭНЕРГОСИСТЕМЫ СЕВЕРО-ЗАПАДА»]

  Департамент стратегического развития

  #v(38mm)

  #grid(
    columns: (1fr, 78mm),
    [], align(left)[
      #set text(hyphenate: false)
      УТВЕРЖДАЮ

      Заместитель генерального директора

      #v(3mm)
      \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ А. В. Соколов

      «\_\_\_\_» \_\_\_\_\_\_\_\_\_\_\_\_ 2026 г.
    ],
  )

  #v(30mm)

  #text(weight: "bold")[АНАЛИТИЧЕСКИЙ ОТЧЁТ]

  #text(weight: "bold")[О ЦЕЛЕСООБРАЗНОСТИ МОДЕРНИЗАЦИИ]

  #text(weight: "bold")[СЕТИ НАКОПИТЕЛЕЙ ЭНЕРГИИ]

  #v(4mm)

  на период 2026–2030 годов

  #v(1fr)

  #grid(
    columns: (1fr, 78mm),
    [], align(left)[
      #set text(hyphenate: false)
      Руководитель департамента

      #v(3mm)
      \_\_\_\_\_\_\_\_\_\_\_\_\_\_\_\_ М. И. Дорохов
    ],
  )

  #v(18mm)

  Псков

  2026
]

#pagebreak()

// ------------------------------------------------------------------ содержание
#[
  #set par(first-line-indent: 0pt, justify: false)
  #align(center, text(weight: "bold")[СОДЕРЖАНИЕ])
  #v(1em)
  #outline(title: none, depth: 2, indent: 1.25cm)
]

#pagebreak()

// ------------------------------------------------------------ 1 ОБЩИЕ ПОЛОЖЕНИЯ
= 1 Общие положения <sec1>

Настоящий отчёт подготовлен по поручению правления от 4 июня 2026 года и
содержит оценку целесообразности модернизации сети накопителей
энергии#footnote[Прогноз построен на консенсусе трёх независимых отраслевых
обзоров за II квартал 2026 года.]. Рынок промышленных накопителей вырос на
16,9 % за последние двенадцать месяцев. Инвестиционная программа предполагает
капитальные затраты в объёме 4,35 млрд рублей, распределённые на пять лет.

Совет директоров рассматривает программу на заседании 29 сентября 2026 года.
Решение принимается квалифицированным большинством голосов.

Финансирование предполагается за счёт комбинации собственных средств и целевого
кредита. Стоимость долга принята на уровне 11,5 % годовых, что соответствует
текущим условиям для заёмщиков сопоставимого кредитного качества.

== 1.1 Основные выводы

+ программа экономически обоснована: NPV базового сценария составляет 83 млн
  рублей при ставке дисконтирования 12,1 %;
+ внутренняя норма доходности равна 13,6 %, что превышает стоимость капитала на
  1,5 процентных пункта;
+ срок поставки контейнерных накопителей составляет 34 недели, что определяет
  критический путь программы;
+ запас прочности невелик: отклонение темпа роста выручки или валовой маржи на
  10 % уводит чистую приведённую стоимость в отрицательную область.

// ------------------------------------------------------- 2 СОСТОЯНИЕ РЫНКА
= 2 Состояние рынка и структура выручки

Отрасль проходит фазу консолидации. Три крупнейших участника контролируют 54 %
поставок промышленных систем, при этом сегмент сервисных контрактов остаётся
фрагментированным, что открывает возможность органического роста без
приобретений.

#block(above: 1.2em, below: 0pt, breakable: false, align(center,
  image("assets/facility.png", width: 118mm)))
#caption-figure(1)[Площадка контейнерных накопителей после модернизации первой очереди]

Наибольший вклад в прирост обеспечивает промышленный сегмент. Совокупный
среднегодовой темп роста по портфелю составляет 16,5 %#footnote[Среднегодовой
темп роста (CAGR) рассчитан по формуле сложного процента.]. Структура выручки
по направлениям приведена в таблице 1.

#caption-table(1)[Выручка по направлениям деятельности, млн рублей]

#show table: set par(justify: false, first-line-indent: 0pt, leading: 0.65em)
#show table: set text(hyphenate: false)

#let hcell(b) = table.cell(fill: ZEBRA, align: center + horizon,
  text(size: SMALL, weight: "bold", b))
#let c(b, al: left) = table.cell(align: al + horizon, text(size: SMALL, b))

#table(
  columns: (34mm, 44mm, 17mm, 17mm, 18mm, 14mm),
  stroke: 0.5pt + INK,
  inset: (x: 5pt, y: 4pt),
  table.header(
    hcell[Сегмент], hcell[Направление], hcell[2025], hcell[2026],
    hcell[Прирост, %], hcell[Класс],
  ),

  table.cell(rowspan: 3, align: left + horizon, text(size: SMALL)[Промышленный]),
  c[Контейнерные накопители 2 МВт·ч], c(al: right)[1 240], c(al: right)[1 450], c(al: right)[+16,9], c(al: center)[A],
  c[Модули быстрой зарядки], c(al: right)[860], c(al: right)[1 017], c(al: right)[+18,3], c(al: center)[A],
  c[Сервисные контракты], c(al: right)[415], c(al: right)[458], c(al: right)[+10,4], c(al: center)[B],

  table.cell(rowspan: 2, align: left + horizon, text(size: SMALL)[Коммерческий]),
  c[Системы для торговых центров], c(al: right)[640], c(al: right)[695], c(al: right)[+8,6], c(al: center)[B],
  c[Резервное питание ЦОД], c(al: right)[1 105], c(al: right)[1 367], c(al: right)[+23,7], c(al: center)[A],

  c[Розничный], c[Домашние накопители 10 кВт·ч], c(al: right)[298], c(al: right)[323], c(al: right)[+8,4], c(al: center)[C],

  table.cell(colspan: 2, text(size: SMALL, weight: "bold")[Итого]),
  table.cell(align: right + horizon, text(size: SMALL, weight: "bold")[4 558]),
  table.cell(align: right + horizon, text(size: SMALL, weight: "bold")[5 310]),
  table.cell(align: right + horizon, text(size: SMALL, weight: "bold")[+16,5]),
  table.cell(align: center + horizon, text(size: SMALL, weight: "bold")[—]),
)

#par(first-line-indent: (amount: INDENT, all: true), justify: true,
  text(size: SMALL)[Примечание — Класс отражает приоритет инвестирования:
  A — высший, C — низший.])

== 2.1 Факторный анализ операционной прибыли

Эффект цены практически полностью компенсирует рост себестоимости, основной
вклад в прирост обеспечивает увеличение объёма. Разложение изменения показателя
EBITDA по факторам приведено на рисунке 2.

#block(above: 1.2em, below: 0pt, breakable: false, align(center,
  image("assets/waterfall.png", width: 135mm)))
#caption-figure(2)[Факторное разложение изменения показателя EBITDA, млн рублей]

// ----------------------------------------------------------- 3 МЕТОДИКА
= 3 Методика оценки

Оценка выполнена методом дисконтированных денежных потоков. Чистая приведённая
стоимость определяется как сумма дисконтированных потоков за вычетом
первоначальных вложений#footnote[Ставка дисконтирования принята равной
средневзвешенной стоимости капитала на дату оценки.] по формуле (1):

#eq($ "NPV" = sum_(t=1)^n (C F_t) / (1 + r)^t - "IC" $, 1)

#where-block((
  [$C F_t$ — денежный поток периода $t$, млн рублей;],
  [$r$ — ставка дисконтирования, доли единицы;],
  [$n$ — горизонт прогнозирования, лет;],
  [IC — первоначальные вложения, млн рублей.],
))

Ставка дисконтирования определяется как средневзвешенная стоимость капитала с
учётом налогового щита по заёмной части по формуле (2):

#eq($ "WACC" = E / V dot k_e + D / V dot k_d dot (1 - T) $, 2)

#where-block((
  [$E$, $D$ — рыночная стоимость собственного и заёмного капитала соответственно;],
  [$V$ — суммарная стоимость капитала, $V = E + D$;],
  [$k_e$, $k_d$ — стоимость собственного и заёмного капитала;],
  [$T$ — ставка налога на прибыль, доли единицы.],
))

Разброс результатов по методу Монте-Карло характеризуется выборочным
стандартным отклонением, вычисляемым по формуле (3):

#eq($ sigma = sqrt(1 / (n - 1) sum_(i=1)^n (x - mu)^2) $, 3)

#where-block((
  [$x$ — значение показателя в отдельной итерации;],
  [$mu$ — среднее значение по выборке;],
  [$n$ — число итераций, принято равным 10 000.],
))

== 3.1 Анализ чувствительности

Результат наиболее чувствителен к темпу роста выручки и валовой марже. При
тонком базовом значении чистой приведённой стоимости отклонение любого из двух
ведущих факторов на 10 % переводит проект в отрицательную область, что требует
контроля именно этих параметров.

#block(above: 1.2em, below: 0pt, breakable: false, align(center,
  image("assets/tornado.png", width: 132mm)))
#caption-figure(3)[Чувствительность чистой приведённой стоимости к допущениям]

== 3.2 Контроль готовности

Состояние подготовительных мероприятий на дату составления отчёта:

#cb-line(true)[финансовая модель прошла независимую проверку;]
#cb-line(true)[технический аудит площадок завершён;]
#cb-line(false)[рамочный договор с поставщиком не подписан;]
#cb-line(false)[решение кредитного комитета банка не получено.]

// ---------------------------------------------------------- 4 ЗАКЛЮЧЕНИЕ
= 4 Заключение

Программа модернизации признаётся целесообразной при выполнении условий,
изложенных в разделе #link(<sec1>)[1 «Общие положения»]. Рекомендуется утвердить
программу в объёме 4,35 млрд рублей и делегировать правлению подписание
рамочного договора с поставщиком в срок до 31 октября 2026 года.

Нормативные требования к оформлению организационно-распорядительной документации
приведены на #link("https://www.consultant.ru/")[#text(fill: rgb("0563C1"))[портале правовой информации]].

Пятилетний прогноз основных показателей приведён в приложении А.

// --------------------------------------------------- ПРИЛОЖЕНИЕ А (альбомная)
#pagebreak()
#set page(flipped: true)

#[
  #show heading: it => align(center, text(weight: "bold", size: BODY, it.body))
  #set par(first-line-indent: 0pt, justify: false)
  = Приложение А
  #align(center, text(size: SMALL)[(справочное)])
  #v(0.6em)
  #align(center, text(weight: "bold")[Пятилетний прогноз основных показателей])
]

Прогноз построен на допущениях базового сценария. Таблица развёрнута на листе
альбомной ориентации, поскольку в книжной ориентации ширина граф не позволяет
сохранить читаемый кегль.

#caption-table[А.1][Консолидированный прогноз, базовый сценарий]

#table(
  columns: (68mm, 30mm, 30mm, 30mm, 30mm, 30mm, 29mm),
  stroke: 0.5pt + INK,
  inset: (x: 5pt, y: 5pt),
  table.header(
    hcell[Показатель], hcell[2026], hcell[2027], hcell[2028], hcell[2029],
    hcell[2030], hcell[CAGR],
  ),
  c[Выручка, млн руб.], c(al: right)[5 310], c(al: right)[6 186], c(al: right)[7 207], c(al: right)[8 396], c(al: right)[9 781], c(al: right)[16,5 %],
  c[EBITDA, млн руб.], c(al: right)[1 168], c(al: right)[1 398], c(al: right)[1 672], c(al: right)[1 998], c(al: right)[2 387], c(al: right)[19,5 %],
  c[Рентабельность EBITDA, %], c(al: right)[22,0], c(al: right)[22,6], c(al: right)[23,2], c(al: right)[23,8], c(al: right)[24,4], c(al: right)[—],
  c[Капитальные затраты, млн руб.], c(al: right)[980], c(al: right)[921], c(al: right)[866], c(al: right)[814], c(al: right)[765], c(al: right)[−6,0 %],
  c[Свободный денежный поток, млн руб.], c(al: right)[−84], c(al: right)[173], c(al: right)[459], c(al: right)[783], c(al: right)[1 150], c(al: right)[—],
  c[Дисконтированный поток, млн руб.], c(al: right)[−75], c(al: right)[137], c(al: right)[326], c(al: right)[495], c(al: right)[649], c(al: right)[—],
)

#par(first-line-indent: (amount: INDENT, all: true), justify: true,
  text(size: SMALL)[Примечание — Подготовлено на основе управленческой
  отчётности за период, закрытый 30 июня 2026 года. Прогнозные значения не
  являются публичной офертой.])
