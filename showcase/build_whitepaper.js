#!/usr/bin/env node
/**
 * Showcase 1 of 4 — a Word report formatted to ГОСТ Р 7.0.97-2016.
 *
 * The previous draft of this file was designed "freely" and it showed: wide
 * uneven margins, a cover that relied on a background image, and a table of
 * contents that opened empty. A serious Russian document is not a design
 * exercise — it has a standard, and the standard is the specification.
 *
 * Applied here:
 *   поля            левое 30 мм, правое 10 мм, верхнее и нижнее 20 мм
 *   шрифт           Tinos 14 пт (метрически совместим с Times New Roman)
 *   интервал        полуторный, абзацный отступ 1,25 см, выравнивание по ширине
 *   заголовки       с абзацного отступа, без точки в конце, не переносятся
 *   нумерация       сквозная, арабская, снизу по центру, на титуле не печатается
 *   таблицы         «Таблица N — Название» над таблицей, по левому краю
 *   рисунки         «Рисунок N — Название» под рисунком, по центру
 *   формулы         по центру, номер в круглых скобках у правого поля
 *   приложение      отдельный раздел, заголовок по центру
 *
 * Everything the toolchain can do is still exercised — footnotes, comments,
 * tracked changes, OMML, merged cells, landscape appendix — but inside the
 * standard rather than instead of it.
 *
 * Run from the repository root:
 *   node showcase/build_whitepaper.js
 */

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  Header, Footer, PageNumber, TableOfContents, PageBreak, LevelFormat,
  ImageRun, SectionType, PageOrientation, VerticalMergeType, VerticalAlign,
  FootnoteReferenceRun, CommentRangeStart, CommentRangeEnd, CommentReference,
  InsertedTextRun, DeletedTextRun, Bookmark, InternalHyperlink, ExternalHyperlink,
  Math: OMath, MathRun, MathFraction, MathSum, MathSuperScript, MathRadical,
  TabStopType, NumberFormat, HeightRule,
} = require('docx');
const { fixDocx } = require('../tools/js/docx_fix.js');
const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const ASSETS = path.join(HERE, 'assets');

// ------------------------------------------------------------ ГОСТ metrics
const MM = 1440 / 25.4;              // twips per millimetre
const PAGE = { width: Math.round(210 * MM), height: Math.round(297 * MM) };
const MARGIN = {
  top: Math.round(20 * MM),          // 1134
  right: Math.round(10 * MM),        // 567
  bottom: Math.round(20 * MM),       // 1134
  left: Math.round(30 * MM),         // 1701
};
const CONTENT_W = PAGE.width - MARGIN.left - MARGIN.right;   // 9638
const INDENT = Math.round(12.5 * MM);                        // 709 = 1,25 см
const LINE = 360;                                            // 1,5 интервала
const BODY_PT = 28;                                          // 14 пт (half-points)
const SMALL_PT = 24;                                         // 12 пт для таблиц
const NOTE_PT = 20;                                          // 10 пт для сносок

// Colour is used sparingly: ГОСТ expects black body text. Accents appear only
// in table headers and rules, where the standard is silent.
const INK = '000000';
const NAVY = '1F3864';
const MUTED = '595959';
const RULE = 'BFBFBF';
const ZEBRA = 'F2F2F2';

const SERIF = 'Tinos';

/** Body run: Times-compatible, 14 pt, black. */
const t = (text, o = {}) => new TextRun({ text, font: SERIF, size: BODY_PT, color: INK, ...o });

// docx CheckBox() renders an empty SDT in Word — use literal glyphs instead.
// Tinos lacks U+2610/U+2612, so these runs carry their own symbol font.
const checkbox = (checked) => new TextRun({
  text: checked ? '\u2612' : '\u2610',
  font: { ascii: 'Segoe UI Symbol', hAnsi: 'Segoe UI Symbol', cs: 'Segoe UI Symbol' },
  size: BODY_PT,
  color: INK,
});

/** Body paragraph: justified, first-line indent, 1.5 spacing, no extra gaps. */
const body = (text, o = {}) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  indent: { firstLine: INDENT },
  spacing: { line: LINE, before: 0, after: 0 },
  children: typeof text === 'string' ? [t(text)] : text,
  ...o,
});

/** Body paragraph built from runs (footnotes, tracked changes, comments). */
const bodyRuns = (children, o = {}) => body(children, o);

// ------------------------------------------------------------------ cover
// ГОСТ: титульный лист не нумеруется, реквизиты выравниваются по центру,
// наименование организации сверху, место и год — внизу. No background image:
// a state-standard cover is typographic, not decorative.
const centred = (text, o = {}) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { line: LINE, before: 0, after: 0 },
  children: [t(text, o)],
});

const blank = (count = 1) => Array.from({ length: count }, () => new Paragraph({
  spacing: { line: LINE }, children: [t('')],
}));

const coverBlock = [
  centred('АКЦИОНЕРНОЕ ОБЩЕСТВО «ЭНЕРГОСИСТЕМЫ СЕВЕРО-ЗАПАДА»', { bold: true }),
  centred('Департамент стратегического развития'),
  ...blank(6),
  centred('УТВЕРЖДАЮ'),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { line: LINE },
    children: [t('Заместитель генерального директора')],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { line: LINE },
    children: [t('________________ А. В. Соколов')],
  }),
  centred('«____» ____________ 2026 г.'),
  ...blank(5),
  centred('АНАЛИТИЧЕСКИЙ ОТЧЁТ', { bold: true }),
  ...blank(1),
  centred('О ЦЕЛЕСООБРАЗНОСТИ МОДЕРНИЗАЦИИ', { bold: true }),
  centred('СЕТИ НАКОПИТЕЛЕЙ ЭНЕРГИИ', { bold: true }),
  ...blank(1),
  centred('на период 2026–2030 годов'),
  ...blank(10),
  new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { line: LINE },
    children: [t('Руководитель департамента')],
  }),
  new Paragraph({
    alignment: AlignmentType.RIGHT,
    spacing: { line: LINE },
    children: [t('________________ М. И. Дорохов')],
  }),
  ...blank(6),
  centred('Псков'),
  centred('2026'),
];

// ------------------------------------------------------------------ tables
/**
 * ГОСТ table cell: 12 pt inside tables is permitted when 14 pt does not fit,
 * and it does not here. Header cells are bold on a light fill.
 */
const cell = (content, { w, bold = false, fill, align = AlignmentType.LEFT,
  span, vMerge, valign = VerticalAlign.CENTER } = {}) =>
  new TableCell({
    width: { size: w, type: WidthType.DXA },
    columnSpan: span,
    verticalMerge: vMerge,
    verticalAlign: valign,
    // CLEAR + fill, never SOLID — SOLID renders as a solid black block.
    shading: fill ? { type: ShadingType.CLEAR, color: 'auto', fill } : undefined,
    margins: { top: 60, bottom: 60, left: 108, right: 108 },
    children: [new Paragraph({
      alignment: align,
      spacing: { line: 240, before: 0, after: 0 },  // single spacing in tables
      children: [new TextRun({
        text: String(content), font: SERIF, size: SMALL_PT, bold, color: INK,
      })],
    })],
  });

const ALL_BORDERS = {
  top: { style: BorderStyle.SINGLE, size: 4, color: INK },
  bottom: { style: BorderStyle.SINGLE, size: 4, color: INK },
  left: { style: BorderStyle.SINGLE, size: 4, color: INK },
  right: { style: BorderStyle.SINGLE, size: 4, color: INK },
  insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: INK },
  insideVertical: { style: BorderStyle.SINGLE, size: 4, color: INK },
};

/** ГОСТ: «Таблица N — Название» над таблицей, с абзацного отступа, слева. */
const tableCaption = (n, title) => new Paragraph({
  alignment: AlignmentType.LEFT,
  indent: { firstLine: INDENT },
  spacing: { line: LINE, before: 240, after: 60 },
  keepNext: true,
  children: [t(`Таблица ${n} — ${title}`)],
});

/** ГОСТ: «Рисунок N — Название» под рисунком, по центру. */
const figureCaption = (n, title) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { line: LINE, before: 120, after: 240 },
  children: [t(`Рисунок ${n} — ${title}`)],
});

const figure = (file, widthPt, heightPt) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { line: LINE, before: 240, after: 0 },
  keepNext: true,
  children: [new ImageRun({
    type: 'png',
    data: fs.readFileSync(path.join(ASSETS, file)),
    transformation: { width: widthPt, height: heightPt },
  })],
});

/**
 * ГОСТ: формула по центру, её номер в круглых скобках у правого поля.
 * A right tab stop at the content edge is what puts the number there.
 */
const equation = (children, number) => new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { line: LINE, before: 240, after: 240 },
  tabStops: [
    { type: TabStopType.CENTER, position: Math.round(CONTENT_W / 2) },
    { type: TabStopType.RIGHT, position: CONTENT_W },
  ],
  children: [
    new TextRun({ text: '\t', font: SERIF, size: BODY_PT }),
    new OMath({ children }),
    new TextRun({ text: `\t(${number})`, font: SERIF, size: BODY_PT, color: INK }),
  ],
});

// ------------------------------------------------------- таблица 1: выручка
const COLS = [
  Math.round(CONTENT_W * 0.20), Math.round(CONTENT_W * 0.30),
  Math.round(CONTENT_W * 0.13), Math.round(CONTENT_W * 0.13),
  Math.round(CONTENT_W * 0.12), Math.round(CONTENT_W * 0.12),
];

const groups = [
  ['Промышленный', [
    ['Контейнерные накопители 2 МВт·ч', '1\u00a0240', '1\u00a0450', '+16,9', 'A'],
    ['Модули быстрой зарядки', '860', '1\u00a0017', '+18,3', 'A'],
    ['Сервисные контракты', '415', '458', '+10,4', 'B'],
  ]],
  ['Коммерческий', [
    ['Системы для торговых центров', '640', '695', '+8,6', 'B'],
    ['Резервное питание ЦОД', '1\u00a0105', '1\u00a0367', '+23,7', 'A'],
  ]],
  ['Розничный', [
    ['Домашние накопители 10 кВт·ч', '298', '323', '+8,4', 'C'],
  ]],
];

const headerRow = new TableRow({
  tableHeader: true,   // повторять на каждой странице
  height: { value: 400, rule: HeightRule.ATLEAST },
  children: [
    cell('Сегмент', { w: COLS[0], bold: true, fill: ZEBRA, align: AlignmentType.CENTER }),
    cell('Направление', { w: COLS[1], bold: true, fill: ZEBRA, align: AlignmentType.CENTER }),
    cell('2025', { w: COLS[2], bold: true, fill: ZEBRA, align: AlignmentType.CENTER }),
    cell('2026', { w: COLS[3], bold: true, fill: ZEBRA, align: AlignmentType.CENTER }),
    cell('Прирост, %', { w: COLS[4], bold: true, fill: ZEBRA, align: AlignmentType.CENTER }),
    cell('Класс', { w: COLS[5], bold: true, fill: ZEBRA, align: AlignmentType.CENTER }),
  ],
});

const dataRows = [];
for (const [segment, items] of groups) {
  items.forEach((row, idx) => {
    dataRows.push(new TableRow({
      children: [
        cell(idx === 0 ? segment : '', {
          w: COLS[0],
          vMerge: idx === 0 ? VerticalMergeType.RESTART : VerticalMergeType.CONTINUE,
        }),
        cell(row[0], { w: COLS[1] }),
        cell(row[1], { w: COLS[2], align: AlignmentType.RIGHT }),
        cell(row[2], { w: COLS[3], align: AlignmentType.RIGHT }),
        cell(row[3], { w: COLS[4], align: AlignmentType.RIGHT }),
        cell(row[4], { w: COLS[5], align: AlignmentType.CENTER }),
      ],
    }));
  });
}

const totalRow = new TableRow({
  children: [
    cell('Итого', { w: COLS[0] + COLS[1], span: 2, bold: true }),
    cell('4\u00a0558', { w: COLS[2], bold: true, align: AlignmentType.RIGHT }),
    cell('5\u00a0310', { w: COLS[3], bold: true, align: AlignmentType.RIGHT }),
    cell('+16,5', { w: COLS[4], bold: true, align: AlignmentType.RIGHT }),
    cell('—', { w: COLS[5], bold: true, align: AlignmentType.CENTER }),
  ],
});

const revenueTable = new Table({
  columnWidths: COLS,
  width: { size: CONTENT_W, type: WidthType.DXA },
  borders: ALL_BORDERS,
  rows: [headerRow, ...dataRows, totalRow],
});

// ------------------------------------------- таблица 2: прогноз (альбомная)
const LAND_CONTENT_W = PAGE.height - MARGIN.left - MARGIN.right;
const LCOLS = [
  Math.round(LAND_CONTENT_W * 0.26), Math.round(LAND_CONTENT_W * 0.123),
  Math.round(LAND_CONTENT_W * 0.123), Math.round(LAND_CONTENT_W * 0.123),
  Math.round(LAND_CONTENT_W * 0.123), Math.round(LAND_CONTENT_W * 0.123),
  Math.round(LAND_CONTENT_W * 0.125),
];
const scenarioRows = [
  ['Показатель', '2026', '2027', '2028', '2029', '2030', 'CAGR'],
  ['Выручка, млн руб.', '5\u00a0310', '6\u00a0186', '7\u00a0207', '8\u00a0396', '9\u00a0781', '16,5 %'],
  ['EBITDA, млн руб.', '1\u00a0168', '1\u00a0398', '1\u00a0672', '1\u00a0998', '2\u00a0387', '19,5 %'],
  ['Рентабельность EBITDA, %', '22,0', '22,6', '23,2', '23,8', '24,4', '—'],
  ['Капитальные затраты, млн руб.', '980', '921', '866', '814', '765', '−6,0 %'],
  ['Свободный денежный поток, млн руб.', '−84', '173', '459', '783', '1\u00a0150', '—'],
  ['Дисконтированный поток, млн руб.', '−75', '137', '326', '495', '649', '—'],
];

const scenarioTable = new Table({
  columnWidths: LCOLS,
  width: { size: LAND_CONTENT_W, type: WidthType.DXA },
  borders: ALL_BORDERS,
  rows: scenarioRows.map((r, i) => new TableRow({
    tableHeader: i === 0,
    children: r.map((v, j) => cell(v, {
      w: LCOLS[j],
      bold: i === 0,
      fill: i === 0 ? ZEBRA : undefined,
      align: i === 0 ? AlignmentType.CENTER
        : (j === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT),
    })),
  })),
});

// ------------------------------------------------------------------- OMML
const eqNPV = equation([
  new MathRun('NPV = '),
  new MathSum({
    children: [new MathFraction({
      numerator: [new MathRun('CF'), new MathRun('t')],
      denominator: [new MathSuperScript({
        children: [new MathRun('(1 + r)')],
        superScript: [new MathRun('t')],
      })],
    })],
    subScript: [new MathRun('t = 1')],
    superScript: [new MathRun('n')],
  }),
  new MathRun(' − IC'),
], 1);

const eqWACC = equation([
  new MathRun('WACC = '),
  new MathFraction({ numerator: [new MathRun('E')], denominator: [new MathRun('V')] }),
  new MathRun(' · k'),
  new MathRun('e'),
  new MathRun(' + '),
  new MathFraction({ numerator: [new MathRun('D')], denominator: [new MathRun('V')] }),
  new MathRun(' · k'),
  new MathRun('d'),
  new MathRun(' · (1 − T)'),
], 2);

const eqSigma = equation([
  new MathRun('σ = '),
  new MathRadical({
    children: [
      new MathFraction({
        numerator: [new MathRun('1')],
        denominator: [new MathRun('n − 1')],
      }),
      new MathSum({
        children: [new MathSuperScript({
          children: [new MathRun('(x − μ)')],
          superScript: [new MathRun('2')],
        })],
        subScript: [new MathRun('i = 1')],
        superScript: [new MathRun('n')],
      }),
    ],
  }),
], 3);

/** Экспликация к формуле: «где X — расшифровка». */
const where = (lines) => lines.map((line, i) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  indent: { firstLine: INDENT },
  spacing: { line: LINE, before: 0, after: 0 },
  children: [t((i === 0 ? 'где ' : '') + line)],
}));

// ------------------------------------------------------------------- doc
const doc = new Document({
  creator: 'АО «Энергосистемы Северо-Запада», Департамент стратегического развития',
  title: 'Аналитический отчёт о целесообразности модернизации сети накопителей энергии',
  description: 'Оценка инвестиционной программы на 2026–2030 годы',
  // Word only refreshes field results (TOC, PAGE) when told to. Without this
  // the contents page opens blank.
  features: { updateFields: true },
  // Justified Russian text without hyphenation tears holes between words:
  // «Совет   директоров   рассматривает». ГОСТ requires выравнивание по
  // ширине, so hyphenation is not optional, it is the other half of it.
  hyphenation: { autoHyphenation: true, hyphenationZone: 357 },
  footnotes: {
    1: { children: [new Paragraph({ children: [new TextRun({ text: 'Прогноз построен на консенсусе трёх независимых отраслевых обзоров за II квартал 2026 года.', font: SERIF, size: NOTE_PT })] })] },
    2: { children: [new Paragraph({ children: [new TextRun({ text: 'Среднегодовой темп роста (CAGR) рассчитан по формуле сложного процента.', font: SERIF, size: NOTE_PT })] })] },
    3: { children: [new Paragraph({ children: [new TextRun({ text: 'Ставка дисконтирования принята равной средневзвешенной стоимости капитала на дату оценки.', font: SERIF, size: NOTE_PT })] })] },
  },
  comments: {
    children: [
      {
        id: 1, author: 'Финансовый контроль', initials: 'ФК',
        date: new Date('2026-08-12T10:15:00Z'),
        children: [new Paragraph({ children: [new TextRun({ text: 'Проверить с казначейством: ставка привлечения могла измениться после июльского пересмотра.', font: SERIF, size: NOTE_PT })] })],
      },
      {
        id: 2, author: 'Технический директор', initials: 'ТД',
        date: new Date('2026-08-13T08:40:00Z'),
        children: [new Paragraph({ children: [new TextRun({ text: 'Сроки поставки реалистичны только при заключении рамочного договора до конца октября.', font: SERIF, size: NOTE_PT })] })],
      },
    ],
  },
  numbering: {
    config: [
      // ГОСТ: перечисление начинается с абзацного отступа 1,25 см, текст
      // выравнивается по ширине как и основной. hanging = INDENT ставит номер
      // ровно на красную строку, а текст — на левое поле, без второй ступени.
      {
        reference: 'gost-list',
        levels: [
          {
            level: 0, format: LevelFormat.DECIMAL, text: '%1)',
            alignment: AlignmentType.LEFT,
            style: {
              paragraph: {
                indent: { left: INDENT + 360, hanging: 360 },
                alignment: AlignmentType.JUSTIFIED,
                spacing: { line: LINE, before: 0, after: 0 },
              },
            },
          },
          {
            level: 1, format: LevelFormat.LOWER_LETTER, text: '%2)',
            alignment: AlignmentType.LEFT,
            style: {
              paragraph: {
                indent: { left: INDENT + 720, hanging: 360 },
                alignment: AlignmentType.JUSTIFIED,
                spacing: { line: LINE, before: 0, after: 0 },
              },
            },
          },
        ],
      },
      {
        reference: 'dash-list',
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: '—',
          alignment: AlignmentType.LEFT,
          style: {
            paragraph: {
              indent: { left: INDENT + 360, hanging: 360 },
              alignment: AlignmentType.JUSTIFIED,
              spacing: { line: LINE, before: 0, after: 0 },
            },
          },
        }],
      },
    ],
  },
  styles: {
    // Heading styles MUST be set through styles.default.* — entries in
    // styles.paragraphStyles with id 'Heading1' are silently ignored by docx-js.
    default: {
      document: {
        run: { font: SERIF, size: BODY_PT, color: INK },
        paragraph: { spacing: { line: LINE, before: 0, after: 0 } },
      },
      // ГОСТ: заголовки с абзацного отступа, полужирные, без точки в конце,
      // не отрываются от последующего текста.
      heading1: {
        run: { font: SERIF, size: BODY_PT, bold: true, color: INK },
        paragraph: {
          spacing: { line: LINE, before: 360, after: 240 },
          indent: { firstLine: INDENT },
          outlineLevel: 0, keepNext: true, keepLines: true,
        },
      },
      heading2: {
        run: { font: SERIF, size: BODY_PT, bold: true, color: INK },
        paragraph: {
          spacing: { line: LINE, before: 240, after: 180 },
          indent: { firstLine: INDENT },
          outlineLevel: 1, keepNext: true, keepLines: true,
        },
      },
      heading3: {
        run: { font: SERIF, size: BODY_PT, bold: true, color: INK },
        paragraph: {
          spacing: { line: LINE, before: 240, after: 180 },
          indent: { firstLine: INDENT },
          outlineLevel: 2, keepNext: true, keepLines: true,
        },
      },
    },
  },
  sections: [
    // ---- 1. Титульный лист: без колонтитулов и без номера ----
    {
      properties: {
        page: { size: { width: PAGE.width, height: PAGE.height }, margin: MARGIN },
        titlePage: true,
      },
      children: coverBlock,
    },

    // ---- 2. Содержание + основной текст, сквозная нумерация со 2-й стр. ----
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: {
          size: { width: PAGE.width, height: PAGE.height },
          margin: MARGIN,
          // Сквозная нумерация: титул — страница 1, но номер на нём не печатается.
          pageNumbers: { start: 2, formatType: NumberFormat.DECIMAL },
        },
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { line: 240 },
            children: [new TextRun({
              children: [PageNumber.CURRENT], font: SERIF, size: SMALL_PT, color: INK,
            })],
          })],
        }),
      },
      children: [
        // ------------------------------------------------ СОДЕРЖАНИЕ
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { line: LINE, before: 0, after: 240 },
          children: [t('СОДЕРЖАНИЕ', { bold: true })],
        }),
        // Поле TOC. Заполняется Word при открытии благодаря updateFields.
        new TableOfContents('Содержание', {
          hyperlink: true,
          headingStyleRange: '1-3',
        }),

        new Paragraph({ children: [new PageBreak()] }),

        // ------------------------------------------------ 1 ОБЩИЕ ПОЛОЖЕНИЯ
        new Paragraph({
          heading: HeadingLevel.HEADING_1,
          children: [
            new Bookmark({
              id: 'sec1',
              children: [t('1 Общие положения', { bold: true })],
            }),
          ],
        }),
        bodyRuns([
          t('Настоящий отчёт подготовлен по поручению правления от 4 июня 2026 года и содержит оценку целесообразности модернизации сети накопителей энергии. Рынок промышленных накопителей вырос на 16,9 % за последние двенадцать месяцев'),
          new FootnoteReferenceRun(1),
          t('. Инвестиционная программа предполагает капитальные затраты в объёме 4,35 млрд рублей, распределённые на пять лет.'),
        ]),
        bodyRuns([
          t('Совет директоров рассматривает программу на заседании '),
          new DeletedTextRun({
            text: '15 сентября', font: SERIF, size: BODY_PT,
            id: 101, author: 'Секретариат', date: '2026-08-14T09:00:00Z',
          }),
          new InsertedTextRun({
            text: '29 сентября', font: SERIF, size: BODY_PT,
            id: 102, author: 'Секретариат', date: '2026-08-14T09:00:00Z',
          }),
          t(' 2026 года. Решение принимается квалифицированным большинством голосов.'),
        ]),
        bodyRuns([
          t('Финансирование предполагается за счёт комбинации собственных средств и целевого кредита. '),
          new CommentRangeStart(1),
          t('Стоимость долга принята на уровне 11,5 % годовых'),
          new CommentRangeEnd(1),
          new TextRun({ children: [new CommentReference(1)] }),
          t(', что соответствует текущим условиям для заёмщиков сопоставимого кредитного качества.'),
        ]),

        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          children: [t('1.1 Основные выводы', { bold: true })],
        }),
        new Paragraph({
          numbering: { reference: 'gost-list', level: 0 },
          alignment: AlignmentType.JUSTIFIED,
          spacing: { line: LINE },
          children: [t('программа экономически обоснована: NPV базового сценария составляет 83 млн рублей при ставке дисконтирования 12,1 %;')],
        }),
        new Paragraph({
          numbering: { reference: 'gost-list', level: 0 },
          alignment: AlignmentType.JUSTIFIED,
          spacing: { line: LINE },
          children: [t('внутренняя норма доходности равна 13,6 %, что превышает стоимость капитала на 1,5 процентных пункта;')],
        }),
        new Paragraph({
          numbering: { reference: 'gost-list', level: 0 },
          alignment: AlignmentType.JUSTIFIED,
          spacing: { line: LINE },
          children: [
            new CommentRangeStart(2),
            t('срок поставки контейнерных накопителей составляет 34 недели, что определяет критический путь программы;'),
            new CommentRangeEnd(2),
            new TextRun({ children: [new CommentReference(2)] }),
          ],
        }),
        new Paragraph({
          numbering: { reference: 'gost-list', level: 0 },
          alignment: AlignmentType.JUSTIFIED,
          spacing: { line: LINE },
          children: [t('запас прочности невелик: отклонение темпа роста выручки или валовой маржи на 10 % уводит чистую приведённую стоимость в отрицательную область.')],
        }),

        // ------------------------------------------------ 2 СОСТОЯНИЕ РЫНКА
        new Paragraph({
          heading: HeadingLevel.HEADING_1,
          children: [t('2 Состояние рынка и структура выручки', { bold: true })],
        }),
        body('Отрасль проходит фазу консолидации. Три крупнейших участника контролируют 54 % поставок промышленных систем, при этом сегмент сервисных контрактов остаётся фрагментированным, что открывает возможность органического роста без приобретений.'),
        figure('facility.png', 400, 223),
        figureCaption(1, 'Площадка контейнерных накопителей после модернизации первой очереди'),

        bodyRuns([
          t('Наибольший вклад в прирост обеспечивает промышленный сегмент. Совокупный среднегодовой темп роста по портфелю составляет 16,5 %'),
          new FootnoteReferenceRun(2),
          t('. Структура выручки по направлениям приведена в таблице 1.'),
        ]),
        tableCaption(1, 'Выручка по направлениям деятельности, млн рублей'),
        revenueTable,
        new Paragraph({
          spacing: { line: LINE, before: 120, after: 0 },
          indent: { firstLine: INDENT },
          children: [t('Примечание — Класс отражает приоритет инвестирования: A — высший, C — низший.', { size: SMALL_PT })],
        }),

        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          children: [t('2.1 Факторный анализ операционной прибыли', { bold: true })],
        }),
        body('Эффект цены практически полностью компенсирует рост себестоимости, основной вклад в прирост обеспечивает увеличение объёма. Разложение изменения показателя EBITDA по факторам приведено на рисунке 2.'),
        figure('waterfall.png', 420, 205),
        figureCaption(2, 'Факторное разложение изменения показателя EBITDA, млн рублей'),

        // ------------------------------------------------ 3 МЕТОДИКА
        new Paragraph({
          heading: HeadingLevel.HEADING_1,
          children: [t('3 Методика оценки', { bold: true })],
        }),
        bodyRuns([
          t('Оценка выполнена методом дисконтированных денежных потоков. Чистая приведённая стоимость определяется как сумма дисконтированных потоков за вычетом первоначальных вложений'),
          new FootnoteReferenceRun(3),
          t(' по формуле (1):'),
        ]),
        eqNPV,
        ...where([
          'CF\u209C — денежный поток периода t, млн рублей;',
          'r — ставка дисконтирования, доли единицы;',
          'n — горизонт прогнозирования, лет;',
          'IC — первоначальные вложения, млн рублей.',
        ]),
        body('Ставка дисконтирования определяется как средневзвешенная стоимость капитала с учётом налогового щита по заёмной части по формуле (2):'),
        eqWACC,
        ...where([
          'E, D — рыночная стоимость собственного и заёмного капитала соответственно;',
          'V — суммарная стоимость капитала, V = E + D;',
          'k\u2091, k_d — стоимость собственного и заёмного капитала;',
          'T — ставка налога на прибыль, доли единицы.',
        ]),
        body('Разброс результатов по методу Монте-Карло характеризуется выборочным стандартным отклонением, вычисляемым по формуле (3):'),
        eqSigma,
        ...where([
          'x — значение показателя в отдельной итерации;',
          'μ — среднее значение по выборке;',
          'n — число итераций, принято равным 10 000.',
        ]),

        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          children: [t('3.1 Анализ чувствительности', { bold: true })],
        }),
        body('Результат наиболее чувствителен к темпу роста выручки и валовой марже. При тонком базовом значении чистой приведённой стоимости отклонение любого из двух ведущих факторов на 10 % переводит проект в отрицательную область, что требует контроля именно этих параметров.'),
        figure('tornado.png', 410, 215),
        figureCaption(3, 'Чувствительность чистой приведённой стоимости к допущениям'),

        new Paragraph({
          heading: HeadingLevel.HEADING_2,
          children: [t('3.2 Контроль готовности', { bold: true })],
        }),
        body('Состояние подготовительных мероприятий на дату составления отчёта:'),
        new Paragraph({
          spacing: { line: LINE }, indent: { firstLine: INDENT },
          children: [checkbox(true), t('  финансовая модель прошла независимую проверку;')],
        }),
        new Paragraph({
          spacing: { line: LINE }, indent: { firstLine: INDENT },
          children: [checkbox(true), t('  технический аудит площадок завершён;')],
        }),
        new Paragraph({
          spacing: { line: LINE }, indent: { firstLine: INDENT },
          children: [checkbox(false), t('  рамочный договор с поставщиком не подписан;')],
        }),
        new Paragraph({
          spacing: { line: LINE }, indent: { firstLine: INDENT },
          children: [checkbox(false), t('  решение кредитного комитета банка не получено.')],
        }),

        // ------------------------------------------------ 4 ЗАКЛЮЧЕНИЕ
        new Paragraph({
          heading: HeadingLevel.HEADING_1,
          children: [t('4 Заключение', { bold: true })],
        }),
        bodyRuns([
          t('Программа модернизации признаётся целесообразной при выполнении условий, изложенных в разделе '),
          new InternalHyperlink({
            anchor: 'sec1',
            children: [t('1 «Общие положения»')],
          }),
          t('. Рекомендуется утвердить программу в объёме 4,35 млрд рублей и делегировать правлению подписание рамочного договора с поставщиком в срок до 31 октября 2026 года.'),
        ]),
        bodyRuns([
          t('Нормативные требования к оформлению организационно-распорядительной документации приведены на '),
          new ExternalHyperlink({
            link: 'https://www.consultant.ru/',
            children: [new TextRun({
              text: 'портале правовой информации',
              font: SERIF, size: BODY_PT, color: '0563C1',
              underline: { type: 'single' },
            })],
          }),
          t('.'),
        ]),
        body('Пятилетний прогноз основных показателей приведён в приложении А.'),
      ],
    },

    // ---- 3. Приложение А, альбомная ориентация ----
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: {
          size: {
            width: PAGE.width, height: PAGE.height,
            orientation: PageOrientation.LANDSCAPE,
          },
          margin: MARGIN,
        },
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { line: 240 },
            children: [new TextRun({
              children: [PageNumber.CURRENT], font: SERIF, size: SMALL_PT, color: INK,
            })],
          })],
        }),
      },
      children: [
        // ГОСТ: заголовок приложения по центру, слово «Приложение» и его буква.
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { line: LINE, before: 0, after: 0 },
          children: [t('Приложение А', { bold: true })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { line: LINE, before: 0, after: 240 },
          children: [t('(справочное)', { size: SMALL_PT })],
        }),
        new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { line: LINE, before: 0, after: 240 },
          children: [t('Пятилетний прогноз основных показателей', { bold: true })],
        }),
        body('Прогноз построен на допущениях базового сценария. Таблица развёрнута на листе альбомной ориентации, поскольку в книжной ориентации ширина граф не позволяет сохранить читаемый кегль.'),
        tableCaption('А.1', 'Консолидированный прогноз, базовый сценарий'),
        scenarioTable,
        new Paragraph({
          spacing: { line: LINE, before: 240, after: 0 },
          indent: { firstLine: INDENT },
          children: [t('Примечание — Подготовлено на основе управленческой отчётности за период, закрытый 30 июня 2026 года. Прогнозные значения не являются публичной офертой.', { size: SMALL_PT })],
        }),
      ],
    },
  ],
});

const out = path.join(HERE, 'out', 'Модернизация_сети_накопителей.docx');
fs.mkdirSync(path.dirname(out), { recursive: true });
Packer.toBuffer(doc)
  .then((buf) => {
    fs.writeFileSync(out, buf);
    // Mandatory after every docx-js write — see tools/js/docx_fix.js.
    return fixDocx(out);
  })
  .then(() => console.log('wrote ' + path.relative(process.cwd(), out)));
