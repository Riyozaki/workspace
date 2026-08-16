/**
 * chromium.js — one reliable way to get a headless browser in this sandbox.
 *
 * WHY THIS EXISTS
 * There is no apt here, so no system Chrome and no LibreOffice. We ship
 * Chromium as an npm payload (@sparticuz/chromium), but that build targets
 * Amazon Linux and needs libnspr4/libnss3, which this Debian image lacks. The
 * package carries those libraries inside `bin/al2023.tar.br` yet only inflates
 * them when it believes it is on Lambda — so a plain `puppeteer.launch()` dies
 * with `Code: 127 ... libnspr4.so: cannot open shared object file`.
 *
 * Fix: inflate the library and font payloads ourselves, then hand the browser
 * child process its own LD_LIBRARY_PATH via puppeteer's `env` option. The
 * dynamic linker reads that variable at exec time, and `env` applies to the
 * child we are about to spawn — so this works no matter how the parent node
 * process was started (`node file.js`, `node -e`, a REPL, a test runner).
 *
 * Usage:
 *   const { launch } = require('./chromium.js');
 *   const browser = await launch();
 */

const fs = require('fs');
const os = require('os');
const path = require('path');
const zlib = require('zlib');
const { execFileSync } = require('child_process');

const CACHE = path.join(os.tmpdir(), 'doc-agent-chromium');
const LIB_DIR = path.join(CACHE, 'lib');
const FONT_ROOT = path.join(CACHE, 'fontcfg');
const BUNDLED_FONTS = path.join(FONT_ROOT, 'fonts');
const REPO_FONTS = path.join(__dirname, '..', '..', 'assets', 'fonts');

function pkgBin(name) {
  // require.resolve on the package root is blocked by its "exports" map,
  // so resolve a known entrypoint and walk up to bin/.
  const entry = require.resolve('@sparticuz/chromium');
  return path.join(path.dirname(entry), '..', 'bin', name);
}

function inflateTarBr(brPath, destDir) {
  if (!fs.existsSync(brPath)) return false;
  fs.mkdirSync(destDir, { recursive: true });
  const tar = zlib.brotliDecompressSync(fs.readFileSync(brPath));
  const tmpTar = path.join(os.tmpdir(), `payload-${process.pid}-${Date.now()}.tar`);
  fs.writeFileSync(tmpTar, tar);
  try {
    execFileSync('tar', ['-xf', tmpTar, '-C', destDir], { stdio: 'ignore' });
  } finally {
    fs.rmSync(tmpTar, { force: true });
  }
  return true;
}

/** Inflate native deps + bundled fonts once. Idempotent. */
function ensureNativeDeps() {
  const marker = path.join(CACHE, '.ready');
  if (!fs.existsSync(marker)) {
    fs.mkdirSync(CACHE, { recursive: true });
    inflateTarBr(pkgBin('al2023.tar.br'), CACHE);      // -> CACHE/lib/*.so
    inflateTarBr(pkgBin('fonts.tar.br'), FONT_ROOT);   // -> FONT_ROOT/fonts/*
    fs.writeFileSync(marker, new Date().toISOString());
  }
  return LIB_DIR;
}

/**
 * Write a fontconfig file covering the system fonts, Chromium's bundled fonts,
 * and the repo's assets/fonts. Returns the dir to use as FONTCONFIG_PATH.
 */
function buildFontConfig(extraDirs = []) {
  const dirs = [
    '/usr/share/fonts',
    BUNDLED_FONTS,
    REPO_FONTS,
    ...extraDirs,
  ].filter((d) => fs.existsSync(d));

  fs.mkdirSync(FONT_ROOT, { recursive: true });
  fs.writeFileSync(
    path.join(FONT_ROOT, 'fonts.conf'),
    `<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
${dirs.map((d) => `  <dir>${d}</dir>`).join('\n')}
  <cachedir>${path.join(CACHE, 'fc-cache')}</cachedir>
  <match target="pattern">
    <test qual="any" name="family"><string>sans-serif</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>Inter</string></edit>
  </match>
  <match target="pattern">
    <test qual="any" name="family"><string>serif</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>PT Serif</string></edit>
  </match>
  <match target="pattern">
    <test qual="any" name="family"><string>monospace</string></test>
    <edit name="family" mode="prepend" binding="strong"><string>JetBrains Mono</string></edit>
  </match>
</fontconfig>
`
  );
  return FONT_ROOT;
}

/**
 * Launch headless Chromium. Use this instead of puppeteer.launch().
 * @param {{fontDirs?: string[], args?: string[], timeout?: number}} opts
 * @returns {Promise<import('puppeteer-core').Browser>}
 */
async function launch(opts = {}) {
  const libDir = ensureNativeDeps();
  const fontConfigDir = buildFontConfig(opts.fontDirs || []);

  const chromium = require('@sparticuz/chromium').default;
  const puppeteer = require('puppeteer-core');
  const executablePath = await chromium.executablePath();

  const existing = process.env.LD_LIBRARY_PATH;
  return puppeteer.launch({
    executablePath,
    headless: chromium.headless,
    timeout: opts.timeout ?? 60000,
    args: [
      ...chromium.args,
      '--no-sandbox',
      '--disable-dev-shm-usage',
      '--font-render-hinting=none', // stable metrics between PDF and PNG
      ...(opts.args || []),
    ],
    // The whole point: the browser child gets the linker path, whatever the
    // parent's environment looks like.
    env: {
      ...process.env,
      LD_LIBRARY_PATH: existing ? `${libDir}:${existing}` : libDir,
      FONTCONFIG_PATH: fontConfigDir,
    },
  });
}

/** Convenience: render an HTML file or string to PDF. */
async function renderPdf(html, outPath, pdfOptions = {}) {
  const browser = await launch();
  try {
    const page = await browser.newPage();
    if (html.startsWith('file://') || html.startsWith('http')) {
      await page.goto(html, { waitUntil: 'networkidle0' });
    } else if (fs.existsSync(html)) {
      await page.goto('file://' + path.resolve(html), { waitUntil: 'networkidle0' });
    } else {
      await page.setContent(html, { waitUntil: 'networkidle0' });
    }
    await page.evaluate(() => document.fonts.ready);
    await page.pdf({
      path: outPath,
      format: 'A4',
      printBackground: true,
      margin: { top: '20mm', bottom: '20mm', left: '18mm', right: '18mm' },
      ...pdfOptions,
    });
  } finally {
    await browser.close();
  }
  return outPath;
}

module.exports = {
  launch,
  renderPdf,
  ensureNativeDeps,
  buildFontConfig,
  CACHE,
  LIB_DIR,
  BUNDLED_FONTS,
};
