import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AGENT_PAGE_MAX_BYTES,
  findOversizedAgentPages,
} from '../scripts/check-agent-page-size.mjs';

test('built agent detail pages stay under HTML payload budget', () => {
  const { distMissing, oversize } = findOversizedAgentPages();
  if (distMissing) {
    console.log('skip: dist/agents missing; run `npm run build` to enforce agent page size budget');
    return;
  }

  assert.equal(
    oversize.length,
    0,
    oversize
      .map((row) => `${row.agentId}: ${row.bytes} bytes (max ${AGENT_PAGE_MAX_BYTES})`)
      .join('\n'),
  );
});