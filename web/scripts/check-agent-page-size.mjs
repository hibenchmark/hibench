#!/usr/bin/env node

import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const AGENT_PAGE_MAX_BYTES = 250 * 1024;

const distAgentsDir = resolve(dirname(fileURLToPath(import.meta.url)), '../dist/agents');

export function findOversizedAgentPages(distDir = distAgentsDir, maxBytes = AGENT_PAGE_MAX_BYTES) {
  if (!existsSync(distDir)) {
    return { distMissing: true, oversize: [] };
  }

  const oversize = [];
  for (const entry of readdirSync(distDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const pagePath = join(distDir, entry.name, 'index.html');
    if (!existsSync(pagePath)) continue;
    const bytes = statSync(pagePath).size;
    if (bytes > maxBytes) {
      oversize.push({ agentId: entry.name, bytes, pagePath });
    }
  }

  oversize.sort((a, b) => b.bytes - a.bytes);
  return { distMissing: false, oversize };
}

function main() {
  const { distMissing, oversize } = findOversizedAgentPages();
  if (distMissing) {
    console.error('Agent page size check skipped: dist/agents is missing. Run astro build first.');
    process.exit(1);
  }
  if (oversize.length > 0) {
    console.error(`Agent detail HTML exceeds ${AGENT_PAGE_MAX_BYTES} bytes:`);
    for (const row of oversize) {
      console.error(`  ${row.agentId}: ${row.bytes} bytes (${row.pagePath})`);
    }
    process.exit(1);
  }
  console.log(`Agent detail HTML within ${AGENT_PAGE_MAX_BYTES}-byte budget (${distAgentsDir})`);
}

const invokedPath = process.argv[1] ? resolve(process.argv[1]) : '';
if (invokedPath && import.meta.url === pathToFileURL(invokedPath).href) {
  main();
}