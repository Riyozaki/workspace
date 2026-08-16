#!/usr/bin/env node
/**
 * Worked example: a short deck with a dark cover, a native chart, stat
 * callouts, and speaker notes.
 *
 *   node examples/build_deck.js
 *   .venv/bin/python tools/validate.py .workdir/Итоги_квартала.pptx
 *   .venv/bin/python tools/render.py  .workdir/Итоги_квартала.pptx -o .workdir/qa
 *
 * The chart is native (addChart), not an image: it stays editable, scales
 * without blurring, and picks up PowerPoint's own rendering.
 */

const pptxgen = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

// Midnight Executive, from skills/pptx/SKILL.md. One dominant colour, one
// support, one accent — never four colours of equal weight.
const NAVY = '1E2761';
const ICE = 'CADCFC';
const WHITE = 'FFFFFF';
const INK = '1F2933';
const MUTED = '667085';
const RULE = 'E4E9F0';

const pres = new pptxgen();
pres.layout = 'LAYOUT_16x9';            // 10 x 5.625in — NOT 13.3 wide
pres.author = 'Document agent';
pres.title = 'Итоги квартала';

// ---------------------------------------------------------------- 1. cover
const cover = pres.addSlide();
cover.background = { color: NAVY };
cover.addText('Итоги III квартала', {
  x: 0.6, y: 1.9, w: 8.8, h: 0.9,
  fontSize: 40, bold: true, color: WHITE, fontFace: 'Inter',
});
cover.addText('Финансовые результаты и планы на IV квартал', {
  x: 0.6, y: 2.85, w: 8.8, h: 0.5,
  fontSize: 16, color: ICE, fontFace: 'Inter',
});
// Motif: a short accent rule under the title, repeated on every section slide.
cover.addShape(pres.ShapeType.rect, { x: 0.62, y: 2.72, w: 1.2, h: 0.04, fill: { color: ICE } });
cover.addText('16 августа 2026 г.', {
  x: 0.6, y: 4.6, w: 4, h: 0.3, fontSize: 11, color: ICE, fontFace: 'Inter',
});
cover.addNotes('Задать тон: квартал закрыт лучше плана, дальше — детали.');

// ------------------------------------------------------- 2. stat callouts
const stats = pres.addSlide();
stats.addText('Ключевые показатели', {
  x: 0.5, y: 0.35, w: 9, h: 0.5, fontSize: 26, bold: true, color: NAVY, fontFace: 'Inter',
});
stats.addShape(pres.ShapeType.rect, { x: 0.52, y: 0.92, w: 1.2, h: 0.035, fill: { color: NAVY } });

const figures = [
  ['1 480', 'млн ₽ выручки', '+18,4% к II кв.'],
  ['34,3', '% рентабельности', '+1,3 п.п.'],
  ['9 106', 'активных клиентов', '+8,1%'],
];
figures.forEach(([value, caption, delta], i) => {
  const x = 0.5 + i * 3.07;
  stats.addShape(pres.ShapeType.roundRect, {
    x, y: 1.35, w: 2.85, h: 2.2,
    fill: { color: 'F7F9FB' }, line: { color: RULE, width: 1 }, rectRadius: 0.08,
  });
  // Big number, small label — the callout pattern.
  stats.addText(value, {
    x, y: 1.6, w: 2.85, h: 0.85,
    fontSize: 40, bold: true, color: NAVY, align: 'center', fontFace: 'Inter', margin: 0,
  });
  stats.addText(caption, {
    x, y: 2.45, w: 2.85, h: 0.3,
    fontSize: 12, color: INK, align: 'center', fontFace: 'Inter', margin: 0,
  });
  stats.addText(delta, {
    x, y: 2.8, w: 2.85, h: 0.3,
    fontSize: 11, color: MUTED, align: 'center', fontFace: 'Inter', margin: 0,
  });
});
stats.addText('Источник: управленческая отчётность за III квартал 2026 года.', {
  x: 0.5, y: 4.9, w: 9, h: 0.25, fontSize: 9, color: MUTED, fontFace: 'Inter',
});
stats.addNotes('Три цифры, которые нужно запомнить. Подробности — на следующем слайде.');

// ------------------------------------------------------------- 3. chart
const chart = pres.addSlide();
chart.addText('Динамика выручки по кварталам', {
  x: 0.5, y: 0.35, w: 9, h: 0.5, fontSize: 26, bold: true, color: NAVY, fontFace: 'Inter',
});
chart.addShape(pres.ShapeType.rect, { x: 0.52, y: 0.92, w: 1.2, h: 0.035, fill: { color: NAVY } });

// Defaults render bare and dated: always set colours, labels, and gridlines.
chart.addChart(
  pres.ChartType.bar,
  [{ name: 'Выручка, млн ₽', labels: ['I кв.', 'II кв.', 'III кв.'], values: [1080, 1250, 1480] }],
  {
    x: 0.5, y: 1.2, w: 9, h: 3.5,
    barDir: 'col',
    chartColors: [NAVY, '4A6FA5', '8FB0D9'],
    varyColors: true,
    showValue: true,
    dataLabelPosition: 'outEnd',     // never 'outEnd' on a *stacked* chart
    dataLabelColor: INK,
    dataLabelFontSize: 11,
    showLegend: false,
    catAxisLabelColor: MUTED,
    valAxisLabelColor: MUTED,
    catAxisLabelFontSize: 11,
    valAxisLabelFontSize: 10,
    valGridLine: { color: RULE, size: 1 },
    catGridLine: { style: 'none' },
    valAxisMaxVal: 1600,
  }
);
chart.addText('Рост третий квартал подряд; темп ускорился с 15,7% до 18,4%.', {
  x: 0.5, y: 4.8, w: 9, h: 0.3, fontSize: 11, color: MUTED, fontFace: 'Inter',
});
chart.addNotes('Отметить ускорение темпа, а не только абсолютный рост.');

// ------------------------------------------------------------ 4. closing
const close = pres.addSlide();
close.background = { color: NAVY };
close.addText('Планы на IV квартал', {
  x: 0.6, y: 0.9, w: 8.8, h: 0.6, fontSize: 28, bold: true, color: WHITE, fontFace: 'Inter',
});
close.addShape(pres.ShapeType.rect, { x: 0.62, y: 1.6, w: 1.2, h: 0.035, fill: { color: ICE } });
close.addText(
  [
    { text: 'Пересмотреть план выручки в сторону повышения', options: { bullet: true, breakLine: true } },
    { text: 'Сохранить темп привлечения клиентов', options: { bullet: true, breakLine: true } },
    { text: 'Запустить программу удержания в ноябре', options: { bullet: true } },
  ],
  { x: 0.9, y: 2.0, w: 8.2, h: 2.2, fontSize: 16, color: ICE, fontFace: 'Inter', paraSpaceAfter: 12 }
);
close.addNotes('Закончить конкретным решением, которое нужно от аудитории.');

const outDir = path.join(__dirname, '..', '.workdir');
fs.mkdirSync(outDir, { recursive: true });
const out = path.join(outDir, 'Итоги_квартала.pptx');
pres.writeFile({ fileName: out }).then(() => console.log('wrote ' + out));
