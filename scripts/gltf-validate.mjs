#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import validator from 'gltf-validator';

const [, , input] = process.argv;
if (!input) {
  console.error('Usage: gltf-validate.mjs MODEL.glb');
  process.exit(64);
}

try {
  const source = path.resolve(input);
  const data = fs.readFileSync(source);
  const report = await validator.validateBytes(new Uint8Array(data), {
    uri: path.basename(source),
    maxIssues: 10000,
    externalResourceFunction: async (uri) => {
      throw new Error(`External glTF resource is forbidden: ${uri}`);
    },
  });
  process.stdout.write(`${JSON.stringify(report)}\n`);
  process.exit(report.issues?.numErrors ? 2 : 0);
} catch (error) {
  console.error(error?.stack || String(error));
  process.exit(3);
}
