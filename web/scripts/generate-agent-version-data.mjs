#!/usr/bin/env node

import { mkdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import {
  buildVersionDatum,
  getAgentIds,
  getAgentVersions,
  safeVersionFilename,
} from '../src/data/benchmark-core.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const outRoot = resolve(__dirname, '../public/data/agents');

await rm(outRoot, { recursive: true, force: true });

for (const agentId of getAgentIds()) {
  const agentDir = join(outRoot, agentId);
  await mkdir(agentDir, { recursive: true });
  for (const run of getAgentVersions(agentId)) {
    const datum = buildVersionDatum(run);
    const file = join(agentDir, `${safeVersionFilename(run.version)}.json`);
    await writeFile(file, `${JSON.stringify(datum)}\n`, 'utf8');
  }
}

console.log(`Wrote per-version agent data under ${outRoot}`);