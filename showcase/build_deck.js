#!/usr/bin/env node
/**
 * Showcase 3 of 4 — a board-ready deck in 16:9.
 *
 * Demonstrated:
 *   - a reusable master slide (background, rule, footer, slide number)
 *   - full-bleed image title slide with a scrim for legible text
 *   - native, editable PowerPoint charts (combo, bar, doughnut) — not pictures
 *   - a KPI strip, a 2x2 matrix, a timeline built from real autoshapes
 *   - a table with a banded header, and speaker notes on every slide
 *
 * Run from the repository root:
 *   node showcase/build_deck.js
 */

const PptxGenJS = require('pptxgenjs');
const fs = require('fs');
const path = require('path');

const HERE = __dirname;
const ASSETS = path.join(HERE, 'assets');
const OUT = path.join(HERE, 'out', 'Совет_директоров_накопители.pptx');

// pptxgenjs colours are hex WITHOUT '#'. With '#' they silently go black.
const NAVY = '1E2761';
const ACCENT = '4A6FA5';
const CORAL = 'B85042';
const GREEN = '2E7D5B';
const INK = '1F2933';
const MUTED = '667085';
const LIGHT = 'F4F6FA';
const WHITE = 'FFFFFF';

const pptx = new PptxGenJS();
pptx.layout = 'LAYOUT_WIDE'; // 13.333 x 7.5 in
const W = 13.333;
const H = 7.5;

pptx.author = 'Департамент стратегического развития';
pptx.company = 'Совет директоров';
pptx.title = 'Модернизация сети накопителей энергии';

// A master keeps every content slide identical without repeating the code.
pptx.defineSlideMaster({
  title: 'CONTENT',
  background: { color: WHITE },
  objects: [
    { rect: { x: 0, y: 0, w: W, h: 0.06, fill: { color: NAVY } } },
    { line: { x: 0.6, y: 6.85, w: W - 1.2, h: 0, line: { color: 'D5D9E0', width: 0.75 } } },
    {
      text: {
        text: 'Модернизация сети накопителей · Конфиденциально',
        options: { x: 0.6, y: 6.95, w: 8, h: 0.3, fontSize: 10, color: MUTED, fontFace: 'Inter' },
      },
    },
  ],
  slideNumber: { x: W - 1.0, y: 6.95, w: 0.5, h: 0.3, fontSize: 10, color: MUTED, fontFace: 'Inter', align: 'right' },
});

/** Standard slide heading + optional kicker. */
function heading(slide, title, kicker) {
  if (kicker) {
    slide.addText(kicker.toUpperCase(), {
      x: 0.6, y: 0.42, w: 11, h: 0.28,
      fontSize: 11, bold: true, color: ACCENT, fontFace: 'Inter', charSpacing: 1.4,
    });
  }
  slide.addText(title, {
    x: 0.6, y: kicker ? 0.72 : 0.55, w: 12.1, h: 0.7,
    fontSize: 28, bold: true, color: NAVY, fontFace: 'Inter',
  });
}

// ============================================================ 1. Title
{
  const s = pptx.addSlide();
  s.addImage({ path: path.join(ASSETS, 'facility.png'), x: 0, y: 0, w: W, h: H, sizing: { type: 'cover', w: W, h: H } });
  // Scrim: without it, white text on a photograph is unreadable.
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: W, h: H, fill: { color: '0B1230', transparency: 28 } });
  s.addShape(pptx.ShapeType.rect, { x: 0, y: 0, w: 6.6, h: H, fill: { color: NAVY, transparency: 18 } });

  s.addText('ЗАСЕДАНИЕ СОВЕТА ДИРЕКТОРОВ · 29 СЕНТЯБРЯ 2026', {
    x: 0.8, y: 2.15, w: 8, h: 0.3, fontSize: 12, bold: true, color: 'CADCFC', fontFace: 'Inter', charSpacing: 1.6,
  });
  s.addText('Модернизация сети\nнакопителей энергии', {
    x: 0.8, y: 2.6, w: 8.2, h: 1.9, fontSize: 42, bold: true, color: WHITE, fontFace: 'Inter', lineSpacing: 46,
  });
  s.addShape(pptx.ShapeType.rect, { x: 0.82, y: 4.62, w: 1.3, h: 0.05, fill: { color: 'CADCFC' } });
  s.addText('Инвестиционная программа 2026–2030\nЗапрос на утверждение 4,35 млрд ₽', {
    x: 0.8, y: 4.85, w: 8, h: 0.9, fontSize: 16, color: 'CADCFC', fontFace: 'Inter', lineSpacing: 24,
  });
  s.addNotes('Открытие. Цель заседания — получить решение по программе. Ключевая мысль: проект создаёт стоимость, но запас прочности узкий, поэтому нужен контроль двух драйверов.');
}

// ======================================================== 2. KPI strip
{
  const s = pptx.addSlide({ masterName: 'CONTENT' });
  heading(s, 'Ключевые параметры программы', 'резюме');

  const kpis = [
    { v: '4,35', u: 'млрд ₽', l: 'Капитальные затраты', c: NAVY },
    { v: '13,6', u: '%', l: 'IRR проекта', c: GREEN },
    { v: '12,1', u: '%', l: 'Стоимость капитала', c: ACCENT },
    { v: '4,1', u: 'года', l: 'Срок окупаемости', c: NAVY },
  ];
  kpis.forEach((k, i) => {
    const x = 0.6 + i * 3.05;
    s.addShape(pptx.ShapeType.roundRect, {
      x, y: 1.75, w: 2.8, h: 1.75, fill: { color: LIGHT }, rectRadius: 0.06,
      line: { color: 'E1E7F0', width: 1 },
    });
    s.addText([
      { text: k.v, options: { fontSize: 34, bold: true, color: k.c, fontFace: 'Inter' } },
      { text: ' ' + k.u, options: { fontSize: 14, color: MUTED, fontFace: 'Inter' } },
    ], { x: x + 0.18, y: 1.98, w: 2.5, h: 0.7 });
    s.addText(k.l, { x: x + 0.18, y: 2.68, w: 2.5, h: 0.5, fontSize: 12, color: INK, fontFace: 'Inter' });
  });

  s.addShape(pptx.ShapeType.roundRect, {
    x: 0.6, y: 3.85, w: 12.1, h: 0.95, fill: { color: 'FDF4E7' }, rectRadius: 0.05,
    line: { color: 'F0D9B5', width: 1 },
  });
  s.addShape(pptx.ShapeType.rect, { x: 0.6, y: 3.85, w: 0.06, h: 0.95, fill: { color: 'C98A2B' } });
  s.addText('Спред IRR к стоимости капитала — 1,5 п.п. Решение чувствительно к темпу роста выручки и валовой марже: отклонение любого из них на 10 % уводит NPV в отрицательную зону.', {
    x: 0.95, y: 3.98, w: 11.5, h: 0.7, fontSize: 13, color: '6B4E16', fontFace: 'Inter', lineSpacing: 19,
  });

  // The lower third would otherwise be dead space: state the conditions the
  // base case depends on, which is the question the board will ask anyway.
  s.addText('Базовый сценарий выполним при трёх условиях', {
    x: 0.6, y: 5.05, w: 11, h: 0.3, fontSize: 13, bold: true, color: NAVY, fontFace: 'Inter',
  });
  const conds = [
    { n: '01', t: 'Рамочный договор подписан до 31 октября 2026 года' },
    { n: '02', t: 'Валовая маржа удерживается не ниже 41,2 % в 2026 году' },
    { n: '03', t: 'Стоимость долга не превышает 11,5 % на горизонте программы' },
  ];
  conds.forEach((c, i) => {
    const x = 0.6 + i * 4.07;
    s.addShape(pptx.ShapeType.rect, { x, y: 5.45, w: 3.82, h: 0.04, fill: { color: ACCENT } });
    s.addText(c.n, { x, y: 5.58, w: 0.6, h: 0.3, fontSize: 15, bold: true, color: ACCENT, fontFace: 'Inter' });
    s.addText(c.t, { x: x + 0.6, y: 5.58, w: 3.2, h: 0.75, fontSize: 11.5, color: INK, fontFace: 'Inter', lineSpacing: 15 });
  });

  s.addText('Источник: финансовая модель, лист DCF. Расчёт без учёта терминальной стоимости.', {
    x: 0.6, y: 6.45, w: 11, h: 0.3, fontSize: 10, italic: true, color: MUTED, fontFace: 'Inter',
  });
  s.addNotes('Четыре числа, которые нужно запомнить, и три условия, при которых они верны. Если спросят про запас прочности — это следующий слайд.');
}

// ================================================ 3. Native combo chart
{
  const s = pptx.addSlide({ masterName: 'CONTENT' });
  heading(s, 'Выручка и рентабельность EBITDA', 'прогноз');

  const years = ['2026', '2027', '2028', '2029', '2030'];
  s.addChart(
    [
      {
        type: pptx.ChartType.bar,
        data: [{ name: 'Выручка, млн ₽', labels: years, values: [5310, 6186, 7207, 8396, 9781] }],
        options: { chartColors: [ACCENT], barGapWidthPct: 60 },
      },
      {
        type: pptx.ChartType.line,
        data: [{ name: 'Рентабельность EBITDA', labels: years, values: [0.220, 0.226, 0.232, 0.238, 0.244] }],
        options: {
          chartColors: [CORAL], secondaryValAxis: true, secondaryCatAxis: true,
          lineSize: 3, lineSmooth: false,
        },
      },
    ],
    {
      x: 0.6, y: 1.6, w: 12.1, h: 4.9,
      showLegend: true, legendPos: 'b', legendFontFace: 'Inter', legendFontSize: 11,
      catAxisLabelFontFace: 'Inter', catAxisLabelFontSize: 11, catAxisLabelColor: MUTED,
      valAxisLabelFontFace: 'Inter', valAxisLabelFontSize: 11, valAxisLabelColor: MUTED,
      valAxisTitle: 'млн ₽', showValAxisTitle: true, valAxisTitleFontSize: 11,
      valGridLine: { color: 'E8EDF5', size: 1 },
      catGridLine: { style: 'none' },
      secondaryValAxis: true,
      catAxes: [{ catAxisHidden: false }, { catAxisHidden: true }],
      valAxes: [
        { showValAxisTitle: true, valAxisTitle: 'млн ₽', valAxisLabelFormatCode: '#,##0',
          valAxisLabelFontFace: 'Inter', valAxisLabelFontSize: 11, valAxisLabelColor: MUTED,
          valGridLine: { color: 'E8EDF5', size: 1 } },
        { showValAxisTitle: true, valAxisTitle: 'маржа', valAxisLabelFormatCode: '0.0%',
          valAxisLabelFontFace: 'Inter', valAxisLabelFontSize: 11, valAxisLabelColor: MUTED,
          valGridLine: { style: 'none' }, valAxisMinVal: 0.18, valAxisMaxVal: 0.28 },
      ],
    },
  );
  s.addNotes('График — настоящий объект PowerPoint: ряды можно править прямо в файле. Маржа растёт медленно и линейно, это заложенное допущение, а не результат.');
}

// ========================================== 4. Waterfall + doughnut split
{
  const s = pptx.addSlide({ masterName: 'CONTENT' });
  heading(s, 'Откуда берётся прирост EBITDA', 'факторный анализ');

  s.addImage({ path: path.join(ASSETS, 'waterfall.png'), x: 0.6, y: 1.6, w: 7.6, h: 3.72 });
  s.addText('Мостик построен вне PowerPoint: waterfall не входит в набор нативных типов диаграмм OOXML.', {
    x: 0.6, y: 5.4, w: 7.6, h: 0.4, fontSize: 10, italic: true, color: MUTED, fontFace: 'Inter',
  });

  s.addChart(
    pptx.ChartType.doughnut,
    [{
      name: 'Структура выручки',
      labels: ['Промышленный', 'Коммерческий', 'Розничный'],
      values: [2925, 2062, 323],
    }],
    {
      x: 8.5, y: 1.7, w: 4.2, h: 3.5,
      chartColors: [NAVY, ACCENT, 'A9BDDB'],
      holeSize: 58,
      showLegend: true, legendPos: 'b', legendFontFace: 'Inter', legendFontSize: 10,
      showValue: false, showPercent: true,
      dataLabelFontFace: 'Inter', dataLabelFontSize: 10, dataLabelColor: WHITE,
      title: 'Выручка 2026 по сегментам', showTitle: true,
      titleFontFace: 'Inter', titleFontSize: 12, titleColor: INK,
    },
  );
  s.addNotes('Слева — почему прибыль выросла. Справа — на каком сегменте держится выручка. Промышленный даёт больше половины.');
}

// ================================================== 5. Risk 2x2 matrix
{
  const s = pptx.addSlide({ masterName: 'CONTENT' });
  heading(s, 'Карта рисков', 'управление');

  const X0 = 2.2, Y0 = 1.75, MW = 8.4, MH = 4.4;
  s.addShape(pptx.ShapeType.rect, { x: X0, y: Y0, w: MW, h: MH, fill: { color: LIGHT }, line: { color: 'D5D9E0', width: 1 } });
  s.addShape(pptx.ShapeType.line, { x: X0 + MW / 2, y: Y0, w: 0, h: MH, line: { color: 'D5D9E0', width: 1, dashType: 'dash' } });
  s.addShape(pptx.ShapeType.line, { x: X0, y: Y0 + MH / 2, w: MW, h: 0, line: { color: 'D5D9E0', width: 1, dashType: 'dash' } });

  s.addText('Вероятность →', { x: X0, y: Y0 + MH + 0.12, w: MW, h: 0.3, fontSize: 11, color: MUTED, fontFace: 'Inter', align: 'center' });
  s.addText('Влияние →', { x: X0 - 2.05, y: Y0 + MH / 2 - 0.15, w: 1.9, h: 0.3, fontSize: 11, color: MUTED, fontFace: 'Inter', align: 'right' });

  const risks = [
    { t: 'Срыв сроков\nпоставки', x: 0.60, y: 0.20, c: CORAL },
    { t: 'Рост ставки\nфинансирования', x: 0.83, y: 0.47, c: CORAL },
    { t: 'Падение спроса\nв рознице', x: 0.28, y: 0.34, c: 'C98A2B' },
    { t: 'Курсовые\nразницы', x: 0.44, y: 0.68, c: 'C98A2B' },
    { t: 'Изменение\nтарифов', x: 0.20, y: 0.78, c: GREEN },
  ];
  risks.forEach((r) => {
    const cx = X0 + r.x * MW, cy = Y0 + r.y * MH;
    // Bubble sized to the label, not the other way round: 2.0in wide keeps
    // two-line Russian captions inside the ellipse at 9.5pt.
    s.addShape(pptx.ShapeType.ellipse, { x: cx - 1.0, y: cy - 0.5, w: 2.0, h: 1.0, fill: { color: r.c, transparency: 12 }, line: { color: WHITE, width: 2 } });
    s.addText(r.t, { x: cx - 0.95, y: cy - 0.5, w: 1.9, h: 1.0, fontSize: 9.5, color: WHITE, bold: true, fontFace: 'Inter', align: 'center', valign: 'middle', lineSpacing: 12 });
  });

  s.addText('Красные риски требуют решения до подписания рамочного договора.', {
    x: X0, y: Y0 + MH + 0.5, w: MW, h: 0.3, fontSize: 11, color: INK, fontFace: 'Inter', align: 'center',
  });
  s.addNotes('Два красных риска: сроки поставки и ставка. Оба контролируемы договором. Остальные — мониторинг.');
}

// ==================================================== 6. Timeline
{
  const s = pptx.addSlide({ masterName: 'CONTENT' });
  heading(s, 'Дорожная карта', 'этапы');

  const y = 3.4;
  s.addShape(pptx.ShapeType.line, { x: 0.9, y, w: 11.6, h: 0, line: { color: 'D5D9E0', width: 2 } });

  const stages = [
    { q: 'IV кв. 2026', t: 'Рамочный договор,\nпервые 3 площадки', done: true },
    { q: 'II кв. 2027', t: 'Ввод Псков-1,\nТула-Восток', done: true },
    { q: 'IV кв. 2027', t: 'Урал: 2 объекта,\n76 МВт·ч', done: false },
    { q: 'II кв. 2028', t: 'Сибирь,\nзавершение', done: false },
    { q: '2029–2030', t: 'Выход на\nполную мощность', done: false },
  ];
  stages.forEach((st, i) => {
    const x = 1.15 + i * 2.42;
    const col = st.done ? NAVY : ACCENT;
    s.addShape(pptx.ShapeType.ellipse, { x: x - 0.13, y: y - 0.13, w: 0.26, h: 0.26, fill: { color: col }, line: { color: WHITE, width: 2 } });
    const above = i % 2 === 0;
    s.addShape(pptx.ShapeType.line, { x, y: above ? y - 0.55 : y + 0.13, w: 0, h: 0.42, line: { color: 'D5D9E0', width: 1 } });
    s.addText(st.q, {
      x: x - 1.05, y: above ? y - 1.5 : y + 0.6, w: 2.1, h: 0.28,
      fontSize: 12, bold: true, color: col, fontFace: 'Inter', align: 'center',
    });
    s.addText(st.t, {
      x: x - 1.05, y: above ? y - 1.2 : y + 0.9, w: 2.1, h: 0.62,
      fontSize: 10.5, color: INK, fontFace: 'Inter', align: 'center', lineSpacing: 13,
    });
  });

  s.addText('Тёмные точки — этапы с подтверждённым финансированием.', {
    x: 0.9, y: 5.6, w: 11.6, h: 0.3, fontSize: 10, italic: true, color: MUTED, fontFace: 'Inter', align: 'center',
  });
  s.addNotes('Пять этапов. Критический путь проходит через рамочный договор в IV квартале — без него сдвигается всё остальное.');
}

// ==================================================== 7. Table + ask
{
  const s = pptx.addSlide({ masterName: 'CONTENT' });
  heading(s, 'Сценарии и запрос решения', 'к утверждению');

  const head = ['Сценарий', 'Рост выручки', 'NPV, млн ₽', 'IRR', 'Решение'];
  const rows = [
    ['Пессимистичный', '8,0 %', '−412', '9,1 %', 'Не проходит порог'],
    ['Базовый', '16,5 %', '83', '13,6 %', 'Проходит'],
    ['Оптимистичный', '24,0 %', '612', '18,4 %', 'Проходит с запасом'],
  ];

  const table = [
    head.map((h) => ({
      text: h,
      options: { bold: true, color: WHITE, fill: { color: NAVY }, fontSize: 12, fontFace: 'Inter', align: 'center', valign: 'middle' },
    })),
    ...rows.map((r, i) => r.map((v, j) => ({
      text: v,
      options: {
        fontSize: 12, fontFace: 'Inter',
        color: j === 4 && i === 0 ? CORAL : (j === 4 ? GREEN : INK),
        bold: i === 1,
        fill: { color: i === 1 ? 'EAF1E9' : (i % 2 === 0 ? WHITE : LIGHT) },
        align: j === 0 ? 'left' : 'center', valign: 'middle',
      },
    }))),
  ];

  s.addTable(table, {
    x: 0.6, y: 1.65, w: 12.1, colW: [3.0, 2.2, 2.3, 1.9, 2.7],
    rowH: [0.5, 0.52, 0.52, 0.52],
    border: { type: 'solid', color: 'D5D9E0', pt: 1 },
    fontFace: 'Inter',
  });

  s.addShape(pptx.ShapeType.roundRect, { x: 0.6, y: 4.15, w: 12.1, h: 1.5, fill: { color: NAVY }, rectRadius: 0.06 });
  s.addText('Запрос к совету директоров', {
    x: 1.0, y: 4.35, w: 11.3, h: 0.35, fontSize: 13, bold: true, color: 'CADCFC', fontFace: 'Inter',
  });
  s.addText('Утвердить программу в объёме 4,35 млрд ₽ и делегировать правлению подписание рамочного договора с поставщиком до 31 октября 2026 года.', {
    x: 1.0, y: 4.7, w: 11.3, h: 0.8, fontSize: 15, color: WHITE, fontFace: 'Inter', lineSpacing: 21,
  });
  s.addNotes('Финальный слайд. Нужны два решения: сумма и делегирование подписания. Дата 31 октября — не формальность, это критический путь.');
}

fs.mkdirSync(path.dirname(OUT), { recursive: true });
pptx.writeFile({ fileName: OUT }).then(() => {
  console.log('wrote ' + path.relative(process.cwd(), OUT));
});
