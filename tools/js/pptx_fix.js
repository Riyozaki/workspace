#!/usr/bin/env node
/**
 * Mandatory post-processing for pptxgenjs output.
 *
 * pptxgenjs emits three <c:axId> elements for every 2-D bar/line/area plot:
 *
 *     <c:axId val="cat"/><c:axId val="val"/><c:axId val="2094734556"/>
 *                                            ^ AXIS_ID_SERIES_PRIMARY
 *
 * but it only ever *defines* that series axis for BAR3D charts. For a plain
 * combo chart the third id therefore points at an axis that does not exist.
 * ECMA-376 requires a 2-D plot to carry exactly two axis references, and
 * PowerPoint enforces it: the slide opens blank or triggers the "repair"
 * prompt, while LibreOffice and the QA preview render it happily. That is the
 * worst kind of bug — invisible everywhere except the one program the client
 * actually uses.
 *
 * This strips the dangling reference from every 2-D plot, leaving 3-D charts
 * (which legitimately have a series axis) untouched.
 *
 *   const { fixPptx } = require('./tools/js/pptx_fix.js');
 *   await fixPptx('deck.pptx');
 *
 * CLI:  node tools/js/pptx_fix.js <in.pptx> [out.pptx]
 */

const fs = require('fs');
const path = require('path');
const { readZip, writeZip } = require('./docx_fix.js');

// Plot types that must reference exactly two axes.
const TWO_AXIS_PLOTS = [
  'barChart', 'lineChart', 'areaChart', 'scatterChart',
  'radarChart', 'bubbleChart',
];

/**
 * Remove axis references that no <c:catAx>/<c:valAx>/<c:serAx> defines.
 * Returns { xml, removed }.
 */
function patchChart(xml) {
  const defined = new Set();
  const axRe = /<c:(catAx|valAx|serAx)>([\s\S]*?)<\/c:\1>/g;
  let m;
  while ((m = axRe.exec(xml)) !== null) {
    const id = /<c:axId val="(\d+)"\/>/.exec(m[2]);
    if (id) defined.add(id[1]);
  }

  let removed = 0;
  for (const plot of TWO_AXIS_PLOTS) {
    const plotRe = new RegExp(`<c:${plot}>([\\s\\S]*?)</c:${plot}>`, 'g');
    xml = xml.replace(plotRe, (whole, inner) => {
      const patched = inner.replace(
        /<c:axId val="(\d+)"\/>/g,
        (tag, id) => {
          if (defined.has(id)) return tag;
          removed += 1;
          return '';
        },
      );
      return `<c:${plot}>${patched}</c:${plot}>`;
    });
  }
  return { xml, removed };
}

async function fixPptx(input, output) {
  const target = output || input;
  const entries = readZip(fs.readFileSync(input));

  let removed = 0;
  let charts = 0;
  for (const entry of entries) {
    if (!/^ppt\/charts\/chart\d+\.xml$/.test(entry.name)) continue;
    charts += 1;
    const result = patchChart(entry.content.toString('utf8'));
    if (result.removed) {
      entry.content = Buffer.from(result.xml, 'utf8');
      removed += result.removed;
    }
  }

  fs.writeFileSync(target, writeZip(entries));
  return { charts, removed, output: target };
}

module.exports = { fixPptx, patchChart };

if (require.main === module) {
  const args = process.argv.slice(2);
  if (!args.length) {
    console.error('usage: node tools/js/pptx_fix.js <in.pptx> [out.pptx]');
    process.exit(2);
  }
  fixPptx(args[0], args[1]).then((r) => {
    console.log(
      `${path.basename(r.output)}: ${r.charts} chart(s), ` +
      `${r.removed} dangling axis reference(s) removed`,
    );
  });
}
