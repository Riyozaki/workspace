#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { createWorker, OEM } from 'tesseract.js';
import eng from '@tesseract.js-data/eng';
import rus from '@tesseract.js-data/rus';

const [, , languages = 'eng', ...images] = process.argv;
if (!images.length) {
  console.error('Usage: wasm-ocr.mjs LANGUAGE IMAGE...');
  process.exit(64);
}
const requested = languages.split('+');
const supported = { eng, rus };
for (const language of requested) {
  if (!supported[language]) {
    console.error(`Unsupported bundled OCR language: ${language}; bundled: eng, rus`);
    process.exit(65);
  }
}
const tessdata = path.resolve('.cache/tesseract-js-data');
fs.mkdirSync(tessdata, { recursive: true });
for (const language of requested) {
  const source = path.join(supported[language].langPath, `${language}.traineddata.gz`);
  const destination = path.join(tessdata, `${language}.traineddata.gz`);
  if (!fs.existsSync(destination)) fs.copyFileSync(source, destination);
}

const worker = await createWorker(requested, OEM.LSTM_ONLY, {
  langPath: tessdata,
  cachePath: path.resolve('.cache/tesseract-js-cache'),
  gzip: true,
  logger: () => {},
});
const results = [];
for (const image of images) {
  const started = Date.now();
  const { data } = await worker.recognize(image, {}, { text: true, tsv: true });
  results.push({
    image: path.resolve(image),
    text: data.text || '',
    tsv: data.tsv || '',
    durationMs: Date.now() - started,
  });
}
await worker.terminate();
process.stdout.write(`${JSON.stringify({
  engine: 'tesseract.js@7.0.0',
  languages: requested,
  results,
})}\n`);
process.exit(0);
