#!/usr/bin/env node
/**
 * Worked example: a multi-page Word report with cover, TOC, styled headings,
 * a real table, and page numbers.
 *
 *   cd tools && node ../examples/build_report.js
 *
 * Then verify it, which is the part that matters:
 *   .venv/bin/python tools/validate.py .workdir/Квартальный_отчёт.docx
 *   .venv/bin/python tools/render.py  .workdir/Квартальный_отчёт.docx -o .workdir/qa
 */

const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  Header, Footer, PageNumber, TableOfContents, PageBreak, LevelFormat,
} = require('docx');
const { fixDocx } = require('../tools/js/docx_fix.js');
const fs = require('fs');
const path = require('path');

const INK = '1F2933';
const ACCENT = '1E3A5F';
const MUTED = '667085';
const RULE = 'D5D9E0';

// A4 in DXA (1440 per inch). Content width = page - margins.
const PAGE = { width: 11906, height: 16838 };
const MARGIN = 1134; // 20mm
const CONTENT_W = PAGE.width - MARGIN * 2;

const text = (t, o = {}) => new TextRun({ text: t, font: 'PT Serif', ...o });

/** A table cell. Width is required on the cell AND via columnWidths. */
const cell = (content, { w, bold = false, fill, align = AlignmentType.LEFT } = {}) =>
  new TableCell({
    width: { size: w, type: WidthType.DXA },
    // CLEAR, never SOLID — SOLID renders as a black block.
    shading: fill ? { type: ShadingType.CLEAR, color: 'auto', fill } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({
      alignment: align,
      children: [text(content, { bold, size: 20, color: INK })],
    })],
  });

const COLS = [Math.round(CONTENT_W * 0.46), Math.round(CONTENT_W * 0.27), Math.round(CONTENT_W * 0.27)];

const rows = [
  ['Показатель', 'II квартал', 'III квартал'],
  ['Выручка, млн ₽', '1 250', '1 480'],
  ['Валовая прибыль, млн ₽', '412', '507'],
  ['Рентабельность, %', '33,0', '34,3'],
  ['Активные клиенты', '8 420', '9 106'],
];

const table = new Table({
  columnWidths: COLS,
  rows: rows.map((r, i) => new TableRow({
    tableHeader: i === 0,
    children: r.map((c, j) => cell(c, {
      w: COLS[j],
      bold: i === 0,
      fill: i === 0 ? 'EEF2F6' : undefined,
      align: j === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT,
    })),
  })),
});

const doc = new Document({
  creator: 'Document agent',
  title: 'Квартальный отчёт',
  styles: {
    // Heading styles must go under `default`. Declaring them in
    // `paragraphStyles` as { id: 'Heading1', ... } is silently ignored —
    // docx-js has already written its own built-in versions.
    default: {
      document: { run: { font: 'PT Serif', size: 22, color: INK }, paragraph: { spacing: { line: 320 } } },
      title: { run: { font: 'Inter', size: 56, bold: true, color: ACCENT } },
      heading1: { run: { font: 'Inter', size: 32, bold: true, color: ACCENT },
                  paragraph: { spacing: { before: 360, after: 160 }, keepNext: true } },
      heading2: { run: { font: 'Inter', size: 25, bold: true, color: ACCENT },
                  paragraph: { spacing: { before: 280, after: 120 }, keepNext: true } },
    },
    paragraphStyles: [
      { id: 'Caption', name: 'Caption', basedOn: 'Normal', quickFormat: true,
        run: { font: 'Inter', size: 17, color: MUTED, italics: true },
        paragraph: { spacing: { after: 240 } } },
    ],
  },
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 420, hanging: 240 } } } }],
    }],
  },
  sections: [
    // --- cover: no header/footer, vertically placed by spacing ---
    {
      properties: { page: { size: PAGE, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
      children: [
        new Paragraph({ spacing: { before: 3200 } }),
        // Title style, so the cover heading is real structure rather than a
        // large paragraph — it then appears in the navigation pane too.
        new Paragraph({
          heading: HeadingLevel.TITLE,
          children: [new TextRun({ text: 'Квартальный отчёт', font: 'Inter', size: 56, bold: true, color: ACCENT })],
        }),
        new Paragraph({ spacing: { before: 120 }, children: [new TextRun({ text: 'III квартал 2026 года', font: 'Inter', size: 28, color: MUTED })] }),
        new Paragraph({
          spacing: { before: 240 },
          border: { top: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 12 } },
        }),
        new Paragraph({ spacing: { before: 8000 }, children: [text('Подготовлено 16 августа 2026 г.', { size: 20, color: MUTED })] }),
        new Paragraph({ children: [new PageBreak()] }),
      ],
    },
    // --- body ---
    {
      properties: { page: { size: PAGE, margin: { top: MARGIN, bottom: MARGIN, left: MARGIN, right: MARGIN } } },
      headers: {
        default: new Header({ children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: RULE, space: 6 } },
          children: [new TextRun({ text: 'Квартальный отчёт · III кв. 2026', font: 'Inter', size: 16, color: MUTED })],
        })] }),
      },
      footers: {
        default: new Footer({ children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [new TextRun({ children: [PageNumber.CURRENT, ' / ', PageNumber.TOTAL_PAGES], font: 'Inter', size: 16, color: MUTED })],
        })] }),
      },
      children: [
        new Paragraph({ text: 'Содержание', heading: HeadingLevel.HEADING_1 }),
        // Renders as "update this field" until opened in Word — expected.
        new TableOfContents('Содержание', { hyperlink: true, headingStyleRange: '1-2' }),
        new Paragraph({ children: [new PageBreak()] }),

        new Paragraph({ text: 'Основные результаты', heading: HeadingLevel.HEADING_1 }),
        new Paragraph({ children: [text('Выручка за III квартал составила 1 480 млн ₽ — на 18,4% выше показателя предыдущего квартала. Рост обеспечен расширением клиентской базы и увеличением среднего чека.')] }),
        new Paragraph({ text: 'Выручка выросла на 18,4% квартал к кварталу', numbering: { reference: 'bullets', level: 0 } }),
        new Paragraph({ text: 'Рентабельность увеличилась с 33,0% до 34,3%', numbering: { reference: 'bullets', level: 0 } }),
        new Paragraph({ text: 'Клиентская база превысила 9 тысяч активных пользователей', numbering: { reference: 'bullets', level: 0 } }),

        new Paragraph({ text: 'Финансовые показатели', heading: HeadingLevel.HEADING_2 }),
        table,
        new Paragraph({ text: 'Таблица 1. Ключевые показатели за II–III кварталы 2026 года. Источник: управленческая отчётность.', style: 'Caption' }),

        new Paragraph({ text: 'Выводы', heading: HeadingLevel.HEADING_1 }),
        new Paragraph({ children: [text('Динамика подтверждает устойчивость выбранной стратегии. Рекомендуется сохранить текущий темп привлечения клиентов и пересмотреть план на IV квартал в сторону повышения.')] }),
      ],
    },
  ],
});

const outDir = path.join(__dirname, '..', '.workdir');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'Квартальный_отчёт.docx');
Packer.toBuffer(doc)
  .then((buf) => {
    fs.writeFileSync(out, buf);
    // Mandatory after every docx-js write: it omits the Normal style that all
    // its own styles are basedOn, which makes every heading read as body text
    // to pandoc and to the preview pipeline. See tools/js/docx_fix.js.
    return fixDocx(out);
  })
  .then(() => console.log('wrote ' + out));
