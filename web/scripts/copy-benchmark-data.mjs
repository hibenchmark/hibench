#!/usr/bin/env node

import { copyFile, mkdir, stat } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '../..');
const resultsDir = process.env.RESULTS_DIR
  ? resolve(process.env.RESULTS_DIR)
  : join(repoRoot, 'results');
const outDir = resolve(__dirname, '../public/data');

const FILES = [
  'runs.csv',
  'tools.csv',
  'skills.csv',
  'subagents.csv',
  'mcp.csv',
  'text_fields.csv',
  'export.json',
  'github_stars.json',
];

await mkdir(outDir, { recursive: true });

let copied = 0;
for (const file of FILES) {
  const source = join(resultsDir, file);
  try {
    await stat(source);
  } catch {
    continue;
  }
  await copyFile(source, join(outDir, file));
  copied += 1;
}

console.log(`Copied ${copied} benchmark export file(s) to ${outDir}`);