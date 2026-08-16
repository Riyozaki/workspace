#!/usr/bin/env node
/**
 * Showcase 1 of 4 — the hardest Word document this toolchain can produce.
 *
 * Everything here is a real OOXML feature, not a picture of one:
 *   - full-bleed cover image behind floating text (absolute positioning)
 *   - field-based TOC, page numbers, "Page X of Y", section restarts
 *   - portrait -> landscape -> portrait section flow
 *   - real footnotes, real threaded comments, real tracked changes
 *   - OMML equations (fraction, summation, radical, superscript)
 *   - vertically merged table cells, repeated header rows, zebra shading
 *   - internal bookmarks + cross-references, external hyperlinks
 *   - multilevel numbering, checkboxes, captioned figures
 *
 * Run from the repository root:
 *   node showcase/build_whitepaper.js
 */

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  Header, Footer, PageNumber, TableOfContents, PageBreak, LevelFormat,
  ImageRun, TextWrappingType, HorizontalPositionRelativeFrom,
  VerticalPositionRelativeFrom, HorizontalPositionAlign, VerticalPositionAlign,
  SectionType, PageOrientation, VerticalMergeType, VerticalAlign,
  FootnoteReferenceRun, CommentRangeStart, CommentRangeEnd, CommentReference,
  InsertedTextRun, DeletedTextRun, Bookmark, InternalHyperlink, ExternalHyperlink,
  Math: OMath, MathRun, MathFraction, MathSum, MathSuperScript, MathRadical,
  CheckBox, TabStopType, LeaderType, NumberFormat, HeightRule,
} = require('docx');
const { fixDocx } = require('../tools/js/docx_fix.js');
const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const ASSETS = path.join(HERE, 'assets');

// ---------------------------------------------------------------- palette
const INK = '1F2933';
const NAVY = '1E2761';
const ACCENT = '4A6FA5';
const CORAL = 'B85042';
const MUTED = '667085';
const RULE = 'D5D9E0';
const ZEBRA = 'F4F6FA';

// A4 portrait in DXA (1440 per inch).
const PAGE = { width: 11906, height: 16838 };
const MARGIN = 1134; // 20 mm
const CONTENT_W = PAGE.width - MARGIN * 2;
// Landscape section swaps the axes; margins stay the same.
const LAND_CONTENT_W = PAGE.height - MARGIN * 2;

const serif = (t, o = {}) => new TextRun({ text: t, font: 'PT Serif', size: 22, color: INK, ...o });
const sans = (t, o = {}) => new TextRun({ text: t, font: 'Inter', size: 20, color: INK, ...o });

const body = (t, o = {}) => new Paragraph({
  spacing: { after: 140, line: 300 },
  alignment: AlignmentType.JUSTIFIED,
  children: [serif(t)],
  ...o,
});

/** Table cell. Width must be set on the cell AND via columnWidths. */
const cell = (children, { w, fill, align = AlignmentType.LEFT, span, vMerge, valign } = {}) =>
  new TableCell({
    width: { size: w, type: WidthType.DXA },
    columnSpan: span,
    verticalMerge: vMerge,
    verticalAlign: valign,
    // CLEAR + fill, never SOLID — SOLID renders as a solid black block.
    shading: fill ? { type: ShadingType.CLEAR, color: 'auto', fill } : undefined,
    margins: { top: 90, bottom: 90, left: 130, right: 130 },
    children: Array.isArray(children) ? children : [
      new Paragraph({ alignment: align, children: [sans(String(children))] }),
    ],
  });

const txtCell = (t, o = {}) => cell([
  new Paragraph({
    alignment: o.align || AlignmentType.LEFT,
    children: [sans(String(t), { bold: o.bold, color: o.color, size: o.size })],
  }),
], o);

const caption = (t) => new Paragraph({
  style: 'Caption',
  spacing: { before: 80, after: 240 },
  children: [new TextRun({ text: t, font: 'Inter', size: 17, color: MUTED, italics: true })],
});

const rule = () => new Paragraph({
  spacing: { before: 60, after: 200 },
  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE } },
  children: [],
});

// ------------------------------------------------------------------ cover
// The image is anchored to the page, behind the text, with no wrapping —
// that is what makes it full-bleed rather than an inline picture.
const coverImage = new Paragraph({
  frame: undefined,
  children: [
    new ImageRun({
      type: 'png',
      data: fs.readFileSync(path.join(ASSETS, 'cover-bg.png')),
      transformation: { width: 595, height: 842 }, // A4 in points
      floating: {
        horizontalPosition: {
          relative: HorizontalPositionRelativeFrom.PAGE,
          align: HorizontalPositionAlign.CENTER,
        },
        verticalPosition: {
          relative: VerticalPositionRelativeFrom.PAGE,
          align: VerticalPositionAlign.CENTER,
        },
        wrap: { type: TextWrappingType.NONE },
        behindDocument: true,
        zIndex: 0,
      },
    }),
  ],
});

const coverBlock = [
  coverImage,
  new Paragraph({ spacing: { before: 2600 }, children: [] }),
  new Paragraph({
    spacing: { after: 120 },
    children: [new TextRun({
      text: 'АНАЛИТИЧЕСКИЙ ОТЧЁТ',
      font: 'Inter', size: 20, bold: true, color: 'CADCFC',
      characterSpacing: 120,
    })],
  }),
  new Paragraph({
    heading: HeadingLevel.TITLE,
    spacing: { after: 160 },
    children: [new TextRun({
      text: 'Модернизация сети накопителей энергии',
      font: 'Inter', size: 52, bold: true, color: 'FFFFFF',
    })],
  }),
  new Paragraph({
    spacing: { after: 2400 },
    children: [new TextRun({
      text: 'Оценка инвестиционной программы на 2026–2030 годы',
      font: 'PT Serif', size: 26, color: 'CADCFC',
    })],
  }),
  new Paragraph({
    children: [new TextRun({ text: 'Департамент стратегического развития', font: 'Inter', size: 19, color: 'CADCFC' })],
  }),
  new Paragraph({
    children: [new TextRun({ text: '16 августа 2026 года · Конфиденциально', font: 'Inter', size: 19, color: 'CADCFC' })],
  }),
];

// --------------------------------------------------------------- big table
// Vertical merge: the "Сегмент" column spans several rows per group.
const COLS = [
  Math.round(CONTENT_W * 0.18), Math.round(CONTENT_W * 0.30),
  Math.round(CONTENT_W * 0.13), Math.round(CONTENT_W * 0.13),
  Math.round(CONTENT_W * 0.13), Math.round(CONTENT_W * 0.13),
];

const groups = [
  ['Промышленный', [
    ['Контейнерные накопители 2 МВт·ч', '1 240', '1 450', '+16,9', 'A'],
    ['Модули быстрой зарядки', '860', '1 017', '+18,3', 'A'],
    ['Сервисные контракты', '415', '458', '+10,4', 'B'],
  ]],
  ['Коммерческий', [
    ['Системы для торговых центров', '640', '695', '+8,6', 'B'],
    ['Резервное питание ЦОД', '1 105', '1 367', '+23,7', 'A'],
  ]],
  ['Розничный', [
    ['Домашние накопители 10 кВт·ч', '298', '323', '+8,4', 'C'],
  ]],
];

const headerRow = new TableRow({
  tableHeader: true, // repeats on every page — mandatory for tables that break
  height: { value: 560, rule: HeightRule.ATLEAST },
  children: [
    txtCell('Сегмент', { w: COLS[0], fill: NAVY, color: 'FFFFFF', bold: true, valign: VerticalAlign.CENTER }),
    txtCell('Направление', { w: COLS[1], fill: NAVY, color: 'FFFFFF', bold: true, valign: VerticalAlign.CENTER }),
    txtCell('2025', { w: COLS[2], fill: NAVY, color: 'FFFFFF', bold: true, align: AlignmentType.RIGHT, valign: VerticalAlign.CENTER }),
    txtCell('2026П', { w: COLS[3], fill: NAVY, color: 'FFFFFF', bold: true, align: AlignmentType.RIGHT, valign: VerticalAlign.CENTER }),
    txtCell('Δ, %', { w: COLS[4], fill: NAVY, color: 'FFFFFF', bold: true, align: AlignmentType.RIGHT, valign: VerticalAlign.CENTER }),
    txtCell('Класс', { w: COLS[5], fill: NAVY, color: 'FFFFFF', bold: true, align: AlignmentType.CENTER, valign: VerticalAlign.CENTER }),
  ],
});

const dataRows = [];
let flat = 0;
for (const [segment, items] of groups) {
  items.forEach((row, idx) => {
    const zebra = flat % 2 === 1 ? ZEBRA : undefined;
    const cells = [];
    // First row of the group owns the merged cell; the rest continue it.
    cells.push(cell(
      idx === 0
        ? [new Paragraph({ children: [sans(segment, { bold: true, color: NAVY })] })]
        : [new Paragraph({ children: [] })],
      {
        w: COLS[0],
        fill: zebra,
        vMerge: idx === 0 ? VerticalMergeType.RESTART : VerticalMergeType.CONTINUE,
        valign: VerticalAlign.CENTER,
      },
    ));
    cells.push(txtCell(row[0], { w: COLS[1], fill: zebra }));
    cells.push(txtCell(row[1], { w: COLS[2], fill: zebra, align: AlignmentType.RIGHT }));
    cells.push(txtCell(row[2], { w: COLS[3], fill: zebra, align: AlignmentType.RIGHT }));
    cells.push(txtCell(row[3], { w: COLS[4], fill: zebra, align: AlignmentType.RIGHT, color: ACCENT }));
    cells.push(txtCell(row[4], { w: COLS[5], fill: zebra, align: AlignmentType.CENTER }));
    dataRows.push(new TableRow({ children: cells }));
    flat += 1;
  });
}

const totalRow = new TableRow({
  children: [
    cell([new Paragraph({ children: [sans('Итого', { bold: true, color: 'FFFFFF' })] })],
      { w: COLS[0], fill: ACCENT, span: 2 }),
    txtCell('4 558', { w: COLS[2], fill: ACCENT, color: 'FFFFFF', bold: true, align: AlignmentType.RIGHT }),
    txtCell('5 310', { w: COLS[3], fill: ACCENT, color: 'FFFFFF', bold: true, align: AlignmentType.RIGHT }),
    txtCell('+16,5', { w: COLS[4], fill: ACCENT, color: 'FFFFFF', bold: true, align: AlignmentType.RIGHT }),
    txtCell('—', { w: COLS[5], fill: ACCENT, color: 'FFFFFF', bold: true, align: AlignmentType.CENTER }),
  ],
});

const revenueTable = new Table({
  columnWidths: COLS,
  width: { size: CONTENT_W, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 2, color: RULE },
    bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE },
    left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
    insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  },
  rows: [headerRow, ...dataRows, totalRow],
});

// ------------------------------------------------------------- landscape
const LCOLS = [
  Math.round(LAND_CONTENT_W * 0.22), Math.round(LAND_CONTENT_W * 0.13),
  Math.round(LAND_CONTENT_W * 0.13), Math.round(LAND_CONTENT_W * 0.13),
  Math.round(LAND_CONTENT_W * 0.13), Math.round(LAND_CONTENT_W * 0.13),
  Math.round(LAND_CONTENT_W * 0.13),
];
const scenarioRows = [
  ['Показатель', '2026', '2027', '2028', '2029', '2030', 'CAGR'],
  ['Выручка, млн ₽', '5 310', '6 186', '7 207', '8 396', '9 781', '16,5 %'],
  ['EBITDA, млн ₽', '1 168', '1 398', '1 672', '1 998', '2 387', '19,5 %'],
  ['Рентабельность EBITDA', '22,0 %', '22,6 %', '23,2 %', '23,8 %', '24,4 %', '—'],
  ['Капитальные затраты, млн ₽', '980', '1 020', '890', '760', '640', '−10,1 %'],
  ['Свободный денежный поток', '−104', '218', '641', '1 084', '1 542', '—'],
  ['Чистый долг / EBITDA', '2,4×', '2,0×', '1,5×', '1,0×', '0,6×', '—'],
];

const scenarioTable = new Table({
  columnWidths: LCOLS,
  width: { size: LAND_CONTENT_W, type: WidthType.DXA },
  borders: {
    top: { style: BorderStyle.SINGLE, size: 2, color: RULE },
    bottom: { style: BorderStyle.SINGLE, size: 2, color: RULE },
    left: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    right: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
    insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: RULE },
    insideVertical: { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' },
  },
  rows: scenarioRows.map((r, i) => new TableRow({
    tableHeader: i === 0,
    children: r.map((v, j) => txtCell(v, {
      w: LCOLS[j],
      fill: i === 0 ? NAVY : (i % 2 === 0 ? ZEBRA : undefined),
      color: i === 0 ? 'FFFFFF' : (j === 6 && i > 0 ? ACCENT : INK),
      bold: i === 0 || j === 0,
      align: j === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT,
    })),
  })),
});

// ------------------------------------------------------------------ math
const equationNPV = new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 200, after: 120 },
  children: [
    new OMath({
      children: [
        new MathRun('NPV = '),
        new MathSum({
          children: [new MathFraction({
            numerator: [new MathRun('CF'), new MathRun('t')],
            denominator: [
              new MathSuperScript({
                children: [new MathRun('(1 + r)')],
                superScript: [new MathRun('t')],
              }),
            ],
          })],
          subScript: [new MathRun('t = 1')],
          superScript: [new MathRun('n')],
        }),
        new MathRun(' − '),
        new MathRun('C'),
        new MathRun('0'),
      ],
    }),
  ],
});

const equationWACC = new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 120, after: 120 },
  children: [
    new OMath({
      children: [
        new MathRun('WACC = '),
        new MathFraction({ numerator: [new MathRun('E')], denominator: [new MathRun('V')] }),
        new MathRun(' · k'),
        new MathRun('e'),
        new MathRun(' + '),
        new MathFraction({ numerator: [new MathRun('D')], denominator: [new MathRun('V')] }),
        new MathRun(' · k'),
        new MathRun('d'),
        new MathRun(' · (1 − T)'),
      ],
    }),
  ],
});

const equationSigma = new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 120, after: 200 },
  children: [
    new OMath({
      children: [
        new MathRun('σ = '),
        new MathRadical({
          children: [
            new MathFraction({
              numerator: [new MathRun('1')],
              denominator: [new MathRun('n − 1')],
            }),
            new MathSum({
              children: [
                new MathSuperScript({
                  children: [new MathRun('(x − μ)')],
                  superScript: [new MathRun('2')],
                }),
              ],
              subScript: [new MathRun('i = 1')],
              superScript: [new MathRun('n')],
            }),
          ],
        }),
      ],
    }),
  ],
});

// ----------------------------------------------------------------- images
const figure = (file, widthPt, heightPt) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 160, after: 40 },
  children: [new ImageRun({
    type: 'png',
    data: fs.readFileSync(path.join(ASSETS, file)),
    transformation: { width: widthPt, height: heightPt },
  })],
});

// ------------------------------------------------------------------- doc
const doc = new Document({
  creator: 'Департамент стратегического развития',
  title: 'Модернизация сети накопителей энергии',
  description: 'Оценка инвестиционной программы на 2026–2030 годы',
  // Footnotes are document-level, keyed by id; FootnoteReferenceRun(id) cites them.
  footnotes: {
    1: { children: [new Paragraph({ children: [serif('Прогноз построен на консенсусе трёх независимых отраслевых обзоров за II квартал 2026 года.', { size: 18 })] })] },
    2: { children: [new Paragraph({ children: [serif('Здесь и далее — среднегодовой темп роста (CAGR) рассчитан по формуле сложного процента.', { size: 18 })] })] },
    3: { children: [new Paragraph({ children: [serif('Ставка дисконтирования принята равной средневзвешенной стоимости капитала на дату оценки.', { size: 18 })] })] },
  },
  comments: {
    children: [
      {
        id: 1,
        author: 'Финансовый контроль',
        initials: 'ФК',
        date: new Date('2026-08-12T10:15:00Z'),
        children: [new Paragraph({ children: [sans('Проверить с казначейством: ставка привлечения могла измениться после июльского пересмотра.', { size: 18 })] })],
      },
      {
        id: 2,
        author: 'Технический директор',
        initials: 'ТД',
        date: new Date('2026-08-13T08:40:00Z'),
        children: [new Paragraph({ children: [sans('Сроки поставки контейнеров реалистичны только при заключении рамочного договора до конца октября.', { size: 18 })] })],
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [
          { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 420, hanging: 240 } } } },
          { level: 1, format: LevelFormat.BULLET, text: '–', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 840, hanging: 240 } } } },
        ],
      },
      {
        reference: 'legal',
        levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 420, hanging: 420 } }, run: { bold: true, color: NAVY } } },
          { level: 1, format: LevelFormat.DECIMAL, text: '%1.%2.', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 900, hanging: 540 } } } },
          { level: 2, format: LevelFormat.LOWER_LETTER, text: '%3)', alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1360, hanging: 400 } } } },
        ],
      },
    ],
  },
  styles: {
    // Heading styles MUST go through styles.default.* — declarations in
    // styles.paragraphStyles with id 'Heading1' are silently ignored.
    default: {
      title: { run: { font: 'Inter', size: 52, bold: true, color: 'FFFFFF' },
        paragraph: { spacing: { after: 160 } } },
      heading1: { run: { font: 'Inter', size: 30, bold: true, color: NAVY },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      heading2: { run: { font: 'Inter', size: 24, bold: true, color: ACCENT },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      heading3: { run: { font: 'Inter', size: 21, bold: true, color: INK },
        paragraph: { spacing: { before: 220, after: 100 }, outlineLevel: 2 } },
      document: { run: { font: 'PT Serif', size: 22, color: INK } },
    },
    // Custom (non-heading) styles DO work here.
    paragraphStyles: [
      { id: 'Caption', name: 'Caption', basedOn: 'Normal', next: 'Normal',
        run: { font: 'Inter', size: 17, italics: true, color: MUTED },
        paragraph: { alignment: AlignmentType.CENTER, spacing: { after: 240 } } },
      { id: 'Callout', name: 'Callout', basedOn: 'Normal', next: 'Normal',
        run: { font: 'Inter', size: 21, color: NAVY },
        paragraph: {
          spacing: { before: 200, after: 200, line: 300 },
          indent: { left: 340, right: 340 },
          border: { left: { style: BorderStyle.SINGLE, size: 18, color: ACCENT, space: 18 } },
        } },
    ],
  },
  sections: [
    // ---- Section 1: cover, no header/footer, no page number ----
    {
      properties: {
        page: {
          size: { width: PAGE.width, height: PAGE.height },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
        titlePage: true,
      },
      children: coverBlock,
    },

    // ---- Section 2: front matter, roman numerals ----
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: {
          size: { width: PAGE.width, height: PAGE.height },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
          pageNumbers: { start: 1, formatType: NumberFormat.LOWER_ROMAN },
        },
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [new TextRun({ children: [PageNumber.CURRENT], font: 'Inter', size: 17, color: MUTED })],
          })],
        }),
      },
      children: [
        new Paragraph({ text: 'Содержание', heading: HeadingLevel.HEADING_1 }),
        new TableOfContents('Содержание', {
          hyperlink: true,
          headingStyleRange: '1-3',
          // Dotted leader to a right tab — what makes a TOC look typeset.
          stylesWithLevels: undefined,
        }),
      ],
    },

    // ---- Section 3: main body, arabic restart, running header/footer ----
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: {
          size: { width: PAGE.width, height: PAGE.height },
          margin: { top: 1400, right: MARGIN, bottom: 1300, left: MARGIN },
          pageNumbers: { start: 1, formatType: NumberFormat.DECIMAL },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
              border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 6 } },
              children: [
                new TextRun({ text: 'Модернизация сети накопителей энергии', font: 'Inter', size: 17, color: MUTED }),
                new TextRun({ text: '\tКонфиденциально', font: 'Inter', size: 17, color: MUTED }),
              ],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              tabStops: [{ type: TabStopType.RIGHT, position: CONTENT_W }],
              children: [
                new TextRun({ text: 'Департамент стратегического развития', font: 'Inter', size: 17, color: MUTED }),
                new TextRun({ text: '\tс. ', font: 'Inter', size: 17, color: MUTED }),
                new TextRun({ children: [PageNumber.CURRENT], font: 'Inter', size: 17, color: MUTED, bold: true }),
                new TextRun({ text: ' из ', font: 'Inter', size: 17, color: MUTED }),
                new TextRun({ children: [PageNumber.TOTAL_PAGES], font: 'Inter', size: 17, color: MUTED }),
              ],
            }),
          ],
        }),
      },
      children: [
        // ---------------------------------------------------- 1 Резюме
        new Paragraph({
          heading: HeadingLevel.HEADING_1,
          children: [
            new Bookmark({ id: 'summary', children: [new TextRun({ text: 'Резюме для руководства', font: 'Inter', size: 30, bold: true, color: NAVY })] }),
          ],
        }),
        new Paragraph({
          style: 'Callout',
          children: [sans('Программа окупается за 4,1 года и создаёт стоимость при базовом сценарии, однако запас прочности невелик: NPV без учёта терминальной стоимости составляет 83 млн ₽, а спред IRR к стоимости капитала — всего 1,5 п.п.', { size: 21, color: NAVY }),
          ],
        }),
        // Footnote reference: superscript number + entry at the foot of the page.
        new Paragraph({
          spacing: { after: 140, line: 300 },
          alignment: AlignmentType.JUSTIFIED,
          children: [
            serif('Рынок промышленных накопителей энергии вырос на 16,9 % за последние двенадцать месяцев, и мы ожидаем сохранения двузначных темпов до конца десятилетия'),
            new FootnoteReferenceRun(1),
            serif('. Инвестиционная программа предполагает капитальные затраты в объёме 4,35 млрд ₽, распределённые на пять лет, с максимумом в первый год.'),
          ],
        }),
        // Tracked changes: an insertion and a deletion by named authors.
        new Paragraph({
          spacing: { after: 140, line: 300 },
          alignment: AlignmentType.JUSTIFIED,
          children: [
            serif('Совет директоров рассматривает программу на заседании '),
            new DeletedTextRun({
              text: '15 сентября',
              font: 'PT Serif', size: 22,
              id: 101, author: 'Секретариат', date: '2026-08-14T09:00:00Z',
            }),
            new InsertedTextRun({
              text: '29 сентября',
              font: 'PT Serif', size: 22,
              id: 102, author: 'Секретариат', date: '2026-08-14T09:00:00Z',
            }),
            serif(' 2026 года. Решение требует квалифицированного большинства.'),
          ],
        }),
        // Comment anchored to a range of text.
        new Paragraph({
          spacing: { after: 140, line: 300 },
          alignment: AlignmentType.JUSTIFIED,
          children: [
            serif('Финансирование предполагается за счёт комбинации собственных средств и целевого кредита. '),
            new CommentRangeStart(1),
            serif('Стоимость долга принята на уровне 11,5 % годовых'),
            new CommentRangeEnd(1),
            new TextRun({ children: [new CommentReference(1)] }),
            serif(', что соответствует текущим условиям для заёмщиков нашего кредитного качества.'),
          ],
        }),

        new Paragraph({ text: 'Ключевые выводы', heading: HeadingLevel.HEADING_2 }),
        new Paragraph({ numbering: { reference: 'legal', level: 0 }, children: [serif('Программа экономически обоснована.')] }),
        new Paragraph({ numbering: { reference: 'legal', level: 1 }, children: [serif('NPV базового сценария составляет 83 млн ₽ при ставке дисконтирования 12,1 %.')] }),
        new Paragraph({ numbering: { reference: 'legal', level: 1 }, children: [serif('IRR равна 13,6 %, что превышает стоимость капитала на 1,5 п.п.')] }),
        new Paragraph({ numbering: { reference: 'legal', level: 2 }, children: [serif('Порог равен WACC и пересматривается ежеквартально инвестиционным комитетом.')] }),
        new Paragraph({ numbering: { reference: 'legal', level: 0 }, children: [serif('Основные риски — сроки поставки и узкий запас по доходности.')] }),
        new Paragraph({
          numbering: { reference: 'legal', level: 1 },
          children: [
            new CommentRangeStart(2),
            serif('Контейнерные накопители имеют цикл поставки 34 недели.'),
            new CommentRangeEnd(2),
            new TextRun({ children: [new CommentReference(2)] }),
          ],
        }),

        // ---------------------------------------------------- 2 Рынок
        new Paragraph({ text: 'Состояние рынка', heading: HeadingLevel.HEADING_1, pageBreakBefore: true }),
        body('Отрасль проходит фазу ускоренной консолидации. Три крупнейших игрока контролируют 54 % поставок промышленных систем, однако сегмент сервисных контрактов остаётся фрагментированным, что открывает возможность для органического роста без крупных приобретений.'),
        figure('facility.png', 440, 246),
        caption('Рисунок 1. Площадка контейнерных накопителей после модернизации первой очереди.'),

        new Paragraph({ text: 'Структура выручки по сегментам', heading: HeadingLevel.HEADING_2 }),
        new Paragraph({
          spacing: { after: 140, line: 300 },
          alignment: AlignmentType.JUSTIFIED,
          children: [
            serif('Наибольший вклад в прирост даёт промышленный сегмент. Совокупный среднегодовой темп роста по портфелю составляет 16,5 %'),
            new FootnoteReferenceRun(2),
            serif('.'),
          ],
        }),
        revenueTable,
        caption('Таблица 1. Выручка по направлениям, млн ₽. Класс отражает приоритет инвестирования (A — высший).'),

        new Paragraph({ text: 'Динамика EBITDA', heading: HeadingLevel.HEADING_2 }),
        body('Мостик показывает, за счёт каких факторов формируется прирост операционной прибыли. Эффект цены почти полностью компенсирует рост себестоимости, а основной вклад даёт объём.'),
        figure('waterfall.png', 460, 225),
        caption('Рисунок 2. Мостик EBITDA: факторный разбор изменения за год, млн ₽.'),

        // ---------------------------------------------------- 3 Методика
        new Paragraph({ text: 'Методика оценки', heading: HeadingLevel.HEADING_1, pageBreakBefore: true }),
        new Paragraph({
          spacing: { after: 140, line: 300 },
          alignment: AlignmentType.JUSTIFIED,
          children: [
            serif('Оценка выполнена методом дисконтированных денежных потоков. Чистая приведённая стоимость рассчитывается как сумма дисконтированных потоков за вычетом первоначальных вложений'),
            new FootnoteReferenceRun(3),
            serif(':'),
          ],
        }),
        equationNPV,
        caption('Формула 1. Чистая приведённая стоимость проекта.'),
        body('Ставка дисконтирования определена как средневзвешенная стоимость капитала с учётом налогового щита по заёмной части:'),
        equationWACC,
        caption('Формула 2. Средневзвешенная стоимость капитала.'),
        body('Разброс результатов по методу Монте-Карло характеризуется выборочным стандартным отклонением:'),
        equationSigma,
        caption('Формула 3. Выборочное стандартное отклонение по 10 000 итераций.'),

        new Paragraph({ text: 'Чувствительность', heading: HeadingLevel.HEADING_2 }),
        body('Результат наиболее чувствителен к темпу роста выручки и валовой марже. При тонком базовом NPV отклонение любого из двух первых драйверов на 10 % уводит проект в отрицательную зону, поэтому решение требует контроля именно этих параметров.'),
        figure('tornado.png', 450, 236),
        caption('Рисунок 3. Торнадо-диаграмма чувствительности NPV.'),

        new Paragraph({ text: 'Контрольный список готовности', heading: HeadingLevel.HEADING_2 }),
        new Paragraph({ spacing: { after: 90 }, children: [new CheckBox({ checked: true }), sans('  Финансовая модель прошла независимую проверку')] }),
        new Paragraph({ spacing: { after: 90 }, children: [new CheckBox({ checked: true }), sans('  Технический аудит площадок завершён')] }),
        new Paragraph({ spacing: { after: 90 }, children: [new CheckBox({ checked: false }), sans('  Рамочный договор с поставщиком подписан')] }),
        new Paragraph({ spacing: { after: 90 }, children: [new CheckBox({ checked: false }), sans('  Кредитный комитет банка вынес решение')] }),

        // Cross-reference back to the bookmark + an external link.
        new Paragraph({
          spacing: { before: 240, after: 140, line: 300 },
          children: [
            serif('Итоговые рекомендации приведены в разделе '),
            new InternalHyperlink({
              anchor: 'summary',
              children: [new TextRun({ text: '«Резюме для руководства»', font: 'PT Serif', size: 22, color: ACCENT, underline: { type: 'single' } })],
            }),
            serif('. Методические требования опубликованы на '),
            new ExternalHyperlink({
              link: 'https://www.consultant.ru/',
              children: [new TextRun({ text: 'портале правовой информации', font: 'PT Serif', size: 22, color: ACCENT, underline: { type: 'single' } })],
            }),
            serif('.'),
          ],
        }),
      ],
    },

    // ---- Section 4: landscape appendix ----
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: {
          size: { width: PAGE.width, height: PAGE.height, orientation: PageOrientation.LANDSCAPE },
          margin: { top: MARGIN, right: MARGIN, bottom: MARGIN, left: MARGIN },
        },
      },
      headers: {
        default: new Header({
          children: [new Paragraph({
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 6 } },
            children: [new TextRun({ text: 'Приложение А · Пятилетний прогноз', font: 'Inter', size: 17, color: MUTED })],
          })],
        }),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [
              new TextRun({ text: 'с. ', font: 'Inter', size: 17, color: MUTED }),
              new TextRun({ children: [PageNumber.CURRENT], font: 'Inter', size: 17, color: MUTED, bold: true }),
            ],
          })],
        }),
      },
      children: [
        new Paragraph({ text: 'Приложение А. Пятилетний прогноз', heading: HeadingLevel.HEADING_1 }),
        body('Таблица развёрнута на альбомной странице — единственный корректный способ разместить широкий финансовый прогноз без уменьшения кегля до нечитаемого размера.'),
        scenarioTable,
        caption('Таблица 2. Консолидированный прогноз, базовый сценарий.'),
        rule(),
        new Paragraph({
          children: [sans('Подготовлено на основе управленческой отчётности за период, закрытый 30 июня 2026 года. Прогнозные значения не являются публичной офертой.', { size: 17, color: MUTED, italics: true })],
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
