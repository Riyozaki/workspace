#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { createSubprocessConverter } from '@matbee/libreoffice-converter';

const [, , input, output, outputFormat] = process.argv;
if (!input || !output || !outputFormat) {
  console.error('Usage: wasm-office.mjs INPUT OUTPUT FORMAT');
  process.exit(64);
}

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const wasmPath = path.join(
  root,
  'node_modules',
  '@matbee',
  'libreoffice-converter',
  'wasm',
);

let converter;
try {
  const started = Date.now();
  converter = await createSubprocessConverter({ wasmPath, verbose: false });
  const inputData = fs.readFileSync(input);
  const inputFormat = path.extname(input).slice(1).toLowerCase();
  let data;
  let mimeType;
  if (inputFormat === outputFormat) {
    const session = await converter.openDocument(inputData, { inputFormat });
    // Reading Calc structure forces formula evaluation before the document is saved.
    if (inputFormat === 'xlsx' || inputFormat === 'xls' || inputFormat === 'ods') {
      await converter.editorOperation(session.sessionId, 'getStructure', []);
    }
    data = await converter.closeDocument(session.sessionId);
    if (!data) throw new Error('LibreOffice editor session returned no saved document');
    mimeType = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
  } else {
    const result = await converter.convert(
      inputData,
      { outputFormat },
      path.basename(input),
    );
    data = result.data;
    mimeType = result.mimeType;
  }
  fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true });
  fs.writeFileSync(output, data);
  process.stdout.write(`${JSON.stringify({
    output: path.resolve(output),
    format: outputFormat,
    mimeType,
    bytes: data.length,
    durationMs: Date.now() - started,
    engine: '@matbee/libreoffice-converter@2.7.2',
  })}\n`);
  // Output is fully materialized. Exit immediately; the Python supervisor
  // terminates this process group, including the subprocess and WASM pthreads.
  // Awaiting converter.destroy() can itself block indefinitely in this runtime.
  process.exit(0);
} catch (error) {
  console.error(error?.stack || String(error));
  process.exit(2);
}
