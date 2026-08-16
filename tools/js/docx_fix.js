/**
 * docx_fix.js — post-process a .docx written by docx-js.
 *
 * WHY THIS EXISTS
 * docx-js (v9) emits a `word/styles.xml` that has no `Normal` style, while
 * every style it writes declares `w:basedOn="Normal"`. That is a dangling
 * reference: the base of the entire style hierarchy does not exist.
 *
 * Word papers over it — it has a built-in Normal to fall back on — so the file
 * looks fine when you open it. Everything else does not:
 *
 *   - pandoc cannot resolve the style chain, so it reports every heading as a
 *     plain paragraph. `convert_file(..., 'markdown')` returns no `#` at all.
 *   - Consequently the HTML->PDF preview renders headings as body text, and
 *     any tooling that reads structure (TOC extraction, accessibility checks,
 *     conversion to other formats) sees a flat document.
 *
 * The failure is invisible in Word and total everywhere else, which is the
 * worst combination: the document looks correct to the author and structureless
 * to every downstream consumer.
 *
 * This also sets `outlineLvl` on each heading style. Word uses it to build the
 * navigation pane and to decide what belongs in a TOC field; docx-js omits it,
 * so a generated TOC can come back empty.
 *
 * Usage:
 *   const { fixDocx } = require('./tools/js/docx_fix.js');
 *   await fixDocx('out.docx');            // rewrites in place
 *   await fixDocx('out.docx', 'fixed.docx');
 *
 * CLI:
 *   node tools/js/docx_fix.js out.docx
 */

const fs = require('fs');
const path = require('path');
const zlib = require('zlib');

const NORMAL_STYLE =
  '<w:style w:type="paragraph" w:default="1" w:styleId="Normal">' +
  '<w:name w:val="Normal"/><w:qFormat/></w:style>';

/** Minimal zip reader/writer so we do not add a dependency for this. */
function readZip(buffer) {
  const entries = [];
  // locate End Of Central Directory
  let eocd = -1;
  for (let i = buffer.length - 22; i >= 0; i--) {
    if (buffer.readUInt32LE(i) === 0x06054b50) { eocd = i; break; }
  }
  if (eocd < 0) throw new Error('not a zip file');
  const count = buffer.readUInt16LE(eocd + 10);
  let offset = buffer.readUInt32LE(eocd + 16);

  for (let i = 0; i < count; i++) {
    if (buffer.readUInt32LE(offset) !== 0x02014b50) break;
    const method = buffer.readUInt16LE(offset + 10);
    const compSize = buffer.readUInt32LE(offset + 20);
    const nameLen = buffer.readUInt16LE(offset + 28);
    const extraLen = buffer.readUInt16LE(offset + 30);
    const commentLen = buffer.readUInt16LE(offset + 32);
    const localOffset = buffer.readUInt32LE(offset + 42);
    const name = buffer.toString('utf8', offset + 46, offset + 46 + nameLen);

    const localNameLen = buffer.readUInt16LE(localOffset + 26);
    const localExtraLen = buffer.readUInt16LE(localOffset + 28);
    const dataStart = localOffset + 30 + localNameLen + localExtraLen;
    const raw = buffer.subarray(dataStart, dataStart + compSize);
    const content = method === 0 ? raw : zlib.inflateRawSync(raw);

    entries.push({ name, content });
    offset += 46 + nameLen + extraLen + commentLen;
  }
  return entries;
}

function writeZip(entries) {
  const chunks = [];
  const central = [];
  let offset = 0;

  for (const { name, content } of entries) {
    const nameBuf = Buffer.from(name, 'utf8');
    const deflated = zlib.deflateRawSync(content, { level: 9 });
    const crc = crc32(content);

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);            // version needed
    local.writeUInt16LE(0, 6);             // flags
    local.writeUInt16LE(8, 8);             // deflate
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(deflated.length, 18);
    local.writeUInt32LE(content.length, 22);
    local.writeUInt16LE(nameBuf.length, 26);
    chunks.push(local, nameBuf, deflated);

    const dir = Buffer.alloc(46);
    dir.writeUInt32LE(0x02014b50, 0);
    dir.writeUInt16LE(20, 4);
    dir.writeUInt16LE(20, 6);
    dir.writeUInt16LE(8, 10);
    dir.writeUInt32LE(crc, 16);
    dir.writeUInt32LE(deflated.length, 20);
    dir.writeUInt32LE(content.length, 24);
    dir.writeUInt16LE(nameBuf.length, 28);
    dir.writeUInt32LE(offset, 42);
    central.push(dir, nameBuf);

    offset += local.length + nameBuf.length + deflated.length;
  }

  const centralBuf = Buffer.concat(central);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralBuf.length, 12);
  eocd.writeUInt32LE(offset, 16);

  return Buffer.concat([...chunks, centralBuf, eocd]);
}

let CRC_TABLE = null;
function crc32(buf) {
  if (!CRC_TABLE) {
    CRC_TABLE = new Int32Array(256);
    for (let i = 0; i < 256; i++) {
      let c = i;
      for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
      CRC_TABLE[i] = c;
    }
  }
  let crc = -1;
  for (let i = 0; i < buf.length; i++) {
    crc = (crc >>> 8) ^ CRC_TABLE[(crc ^ buf[i]) & 0xff];
  }
  return (crc ^ -1) >>> 0;
}

/** Apply the style fixes to a styles.xml string. */
function patchStyles(xml) {
  let changed = false;

  if (!/w:styleId="Normal"/.test(xml)) {
    const at = xml.indexOf('<w:style ');
    if (at !== -1) {
      xml = xml.slice(0, at) + NORMAL_STYLE + xml.slice(at);
      changed = true;
    }
  }

  // Give each heading style an outlineLvl so Word's TOC and navigation see it.
  for (let level = 1; level <= 6; level++) {
    const re = new RegExp(
      `(<w:style[^>]*w:styleId="Heading${level}"[^>]*>)([\\s\\S]*?)(</w:style>)`
    );
    xml = xml.replace(re, (all, open, body, close) => {
      if (/outlineLvl/.test(body)) return all;
      changed = true;
      if (/<w:pPr>/.test(body)) {
        return open + body.replace('<w:pPr>', `<w:pPr><w:outlineLvl w:val="${level - 1}"/>`) + close;
      }
      // pPr must precede rPr in the schema.
      const insertAt = body.indexOf('<w:rPr>');
      const pPr = `<w:pPr><w:outlineLvl w:val="${level - 1}"/></w:pPr>`;
      if (insertAt === -1) return open + body + pPr + close;
      return open + body.slice(0, insertAt) + pPr + body.slice(insertAt) + close;
    });
  }

  return { xml, changed };
}

/**
 * Repair a docx-js output file.
 * @returns {Promise<{changed: boolean, output: string}>}
 */
async function fixDocx(input, output = null) {
  const target = output || input;
  const entries = readZip(fs.readFileSync(input));

  let changed = false;
  for (const entry of entries) {
    if (entry.name !== 'word/styles.xml') continue;
    const result = patchStyles(entry.content.toString('utf8'));
    if (result.changed) {
      entry.content = Buffer.from(result.xml, 'utf8');
      changed = true;
    }
  }

  if (changed || target !== input) {
    fs.writeFileSync(target, writeZip(entries));
  }
  return { changed, output: target };
}

module.exports = { fixDocx, patchStyles };

if (require.main === module) {
  const [, , input, output] = process.argv;
  if (!input) {
    console.error('usage: node tools/js/docx_fix.js <in.docx> [out.docx]');
    process.exit(2);
  }
  fixDocx(path.resolve(input), output ? path.resolve(output) : null)
    .then(({ changed, output: out }) => {
      console.log(changed ? `fixed styles in ${out}` : `no changes needed (${out})`);
    })
    .catch((e) => { console.error(e.message); process.exit(1); });
}
