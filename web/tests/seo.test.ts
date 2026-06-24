import assert from 'node:assert/strict';
import test from 'node:test';

import {
  computeAgentUpdateRow,
  primaryTokenCount,
} from '../src/data/benchmark-core.js';
import worker from '../src/worker.js';
import {
  agentPageSeo,
  absoluteUrl,
  compareIndexPageSeo,
  comparePageSeo,
  compareSlug,
  generateComparePairs,
  homePageSeo,
  parseCompareSlug,
  primaryTokenMetric,
  rankingsItemListSchema,
  resolveSiteUrl,
  updatesPageSeo,
} from '../src/lib/seo.ts';

const site = 'https://hibench.dev';

test('worker redirects www host to apex while preserving path and query', async () => {
  const response = await worker.fetch(
    new Request('https://www.hibench.dev/agents/codex/?metric=anthropic'),
    {
      ASSETS: {
        fetch() {
          throw new Error('asset fetch should not be called for www redirects');
        },
      },
    },
  );

  assert.equal(response.status, 301);
  assert.equal(
    response.headers.get('location'),
    'https://hibench.dev/agents/codex/?metric=anthropic',
  );
});

test('worker serves static assets for apex host requests', async () => {
  let seenRequest: Request | null = null;
  const response = await worker.fetch(new Request('https://hibench.dev/rankings/'), {
    ASSETS: {
      fetch(request: Request) {
        seenRequest = request;
        return new Response('asset ok', { status: 200 });
      },
    },
  });

  assert.equal(response.status, 200);
  assert.equal(await response.text(), 'asset ok');
  assert.equal(seenRequest?.url, 'https://hibench.dev/rankings/');
});

test('resolveSiteUrl falls back to production origin', () => {
  assert.equal(resolveSiteUrl(), site);
  assert.equal(resolveSiteUrl(undefined), site);
});

test('absoluteUrl respects site base path', () => {
  assert.equal(absoluteUrl(site, '/agents/codex/'), 'https://hibench.dev/agents/codex/');
});

test('homePageSeo uses dynamic agent count', () => {
  const seo = homePageSeo(16);
  assert.match(seo.description, /16 coding agents/);
  const faq = seo.jsonLd.mainEntity as { acceptedAnswer: { text: string } }[];
  assert.match(faq[2].acceptedAnswer.text, /16 agents/);
});

test('primaryTokenMetric prefers anthropic totals when enabled', () => {
  const metric = primaryTokenMetric(
    {
      totalTokens: 1000,
      anthropicTotalTokens: 2000,
      toolCount: 1,
      skillCount: 0,
      subagentCount: 0,
      version: '1.0.0',
      startedAt: '2026-01-01T00:00:00Z',
    },
    true,
  );
  assert.equal(metric.tokens, 2000);
  assert.match(metric.label, /Anthropic/);
});

test('rankingsItemListSchema accepts agent summaries', () => {
  const schema = rankingsItemListSchema(
    site,
    [
      {
        agentId: 'pi',
        agentDisplayName: 'Pi',
        latest: {
          totalTokens: 100,
          anthropicTotalTokens: 150,
          toolCount: 1,
          skillCount: 0,
          subagentCount: 0,
          version: '1.0.0',
          startedAt: '2026-01-01T00:00:00Z',
        },
      },
      {
        agentId: 'codex',
        agentDisplayName: 'Codex CLI',
        latest: {
          totalTokens: 500,
          anthropicTotalTokens: 600,
          toolCount: 2,
          skillCount: 0,
          subagentCount: 0,
          version: '2.0.0',
          startedAt: '2026-01-02T00:00:00Z',
        },
      },
    ],
    true,
  );

  const items = schema.itemListElement as { position: number; name: string }[];
  assert.equal(items[0].name, 'Codex CLI');
  assert.equal(items[1].name, 'Pi');
});

const sampleRun = {
  totalTokens: 1000,
  anthropicTotalTokens: 2000,
  toolCount: 3,
  skillCount: 1,
  subagentCount: 0,
  version: '1.0.0',
  startedAt: '2026-01-01T00:00:00Z',
};

const sampleAgents = [
  {
    agentId: 'pi',
    agentDisplayName: 'Pi',
    latest: { ...sampleRun, totalTokens: 100, anthropicTotalTokens: 150 },
  },
  {
    agentId: 'codex',
    agentDisplayName: 'Codex CLI',
    latest: sampleRun,
  },
  {
    agentId: 'cursor-cli',
    agentDisplayName: 'Cursor CLI',
    latest: { ...sampleRun, totalTokens: 500, anthropicTotalTokens: 600 },
  },
];

test('compareSlug canonicalizes agent order lexicographically', () => {
  assert.equal(compareSlug('cursor-cli', 'codex'), 'codex-vs-cursor-cli');
  assert.equal(compareSlug('codex', 'cursor-cli'), 'codex-vs-cursor-cli');
});

test('parseCompareSlug accepts canonical slugs and rejects reversed pairs', () => {
  assert.deepEqual(parseCompareSlug('codex-vs-cursor-cli'), {
    agentA: 'codex',
    agentB: 'cursor-cli',
  });
  assert.equal(parseCompareSlug('cursor-cli-vs-codex'), null);
  assert.equal(parseCompareSlug('not-a-compare-slug'), null);
});

test('generateComparePairs includes extremes and adjacent ranking pairs', () => {
  const pairs = generateComparePairs(sampleAgents, true);
  const slugs = pairs.map((pair) => pair.slug);

  assert.ok(slugs.includes('codex-vs-pi'));
  assert.ok(slugs.includes('codex-vs-cursor-cli'));
  assert.ok(slugs.includes('cursor-cli-vs-pi'));
  assert.equal(pairs.length, 3);
});

test('compareIndexPageSeo emits CollectionPage with comparison ItemList', () => {
  const seo = compareIndexPageSeo(
    site,
    [
      {
        slug: 'codex-vs-cursor-cli',
        agentADisplayName: 'Codex CLI',
        agentBDisplayName: 'Cursor CLI',
      },
      {
        slug: 'codex-vs-pi',
        agentADisplayName: 'Codex CLI',
        agentBDisplayName: 'Pi',
      },
    ],
    '2026-06-24T12:00:00Z',
  );

  assert.match(seo.description, /2 high-intent coding-agent pairs/);
  assert.equal(seo.jsonLd['@type'], 'CollectionPage');
  assert.equal(seo.jsonLd.url, 'https://hibench.dev/compare/');
  assert.equal(seo.jsonLd.dateModified, '2026-06-24T12:00:00Z');

  const list = seo.jsonLd.mainEntity as {
    numberOfItems: number;
    itemListElement: { name: string; url: string }[];
  };
  assert.equal(list.numberOfItems, 2);
  assert.equal(list.itemListElement[0].name, 'Codex CLI vs Cursor CLI');
  assert.equal(
    list.itemListElement[0].url,
    'https://hibench.dev/compare/codex-vs-cursor-cli/',
  );
});

test('comparePageSeo references both agents in title and datasets', () => {
  const seo = comparePageSeo(site, sampleAgents[1], sampleAgents[2], true);

  assert.match(seo.title, /Codex CLI vs Cursor CLI/);
  assert.match(seo.description, /2,000 default Anthropic request tokens/);
  assert.match(seo.description, /600 default Anthropic request tokens/);

  const webPage = seo.jsonLd[1] as {
    mainEntity: { itemListElement: { item: { name: string } }[] };
  };
  const names = webPage.mainEntity.itemListElement.map((entry) => entry.item.name);
  assert.deepEqual(names, [
    'Codex CLI default footprint benchmark',
    'Cursor CLI default footprint benchmark',
  ]);
});

test('primaryTokenCount prefers anthropic totals when enabled', () => {
  const run = {
    totalTokens: 1000,
    anthropicTotalTokens: 2000,
    toolCount: 1,
    skillCount: 0,
    subagentCount: 0,
    version: '1.0.0',
    startedAt: '2026-01-01T00:00:00Z',
  };

  assert.equal(primaryTokenCount(run, true), 2000);
  assert.equal(primaryTokenCount(run, false), 1000);
});

test('computeAgentUpdateRow calculates token and count deltas vs previous version', () => {
  const latest = {
    runId: 'run-2',
    agentId: 'codex',
    agentName: 'Codex',
    version: '2.0.0',
    model: 'gpt-5',
    hasPrimary: true,
    startedAt: '2026-02-01T00:00:00Z',
    bodyBytes: 0,
    totalTokens: 1200,
    anthropicTotalTokens: 1500,
    anthropicTokenizerModel: '',
    systemPromptTokens: 0,
    toolTokens: 0,
    skillTokens: 0,
    mcpTokens: 0,
    subagentTokens: 0,
    userPromptTokens: 0,
    envContextTokens: 0,
    defaultContextTokens: 0,
    toolCount: 5,
    skillCount: 2,
    mcpCount: 0,
    subagentCount: 1,
  };
  const previous = {
    ...latest,
    runId: 'run-1',
    version: '1.0.0',
    startedAt: '2026-01-01T00:00:00Z',
    totalTokens: 1000,
    anthropicTotalTokens: 1200,
    toolCount: 4,
    skillCount: 1,
    subagentCount: 0,
  };

  const row = computeAgentUpdateRow(latest, previous, true);

  assert.equal(row.primaryTokens, 1500);
  assert.equal(row.tokenDelta, 300);
  assert.equal(row.tokenDeltaPct, 25);
  assert.equal(row.toolDelta, 1);
  assert.equal(row.skillDelta, 1);
  assert.equal(row.subagentDelta, 1);
});

test('computeAgentUpdateRow leaves deltas null for first captured version', () => {
  const latest = {
    runId: 'run-1',
    agentId: 'pi',
    agentName: 'Pi',
    version: '1.0.0',
    model: 'gpt-5',
    hasPrimary: true,
    startedAt: '2026-01-01T00:00:00Z',
    bodyBytes: 0,
    totalTokens: 500,
    anthropicTotalTokens: 0,
    anthropicTokenizerModel: '',
    systemPromptTokens: 0,
    toolTokens: 0,
    skillTokens: 0,
    mcpTokens: 0,
    subagentTokens: 0,
    userPromptTokens: 0,
    envContextTokens: 0,
    defaultContextTokens: 0,
    toolCount: 2,
    skillCount: 0,
    mcpCount: 0,
    subagentCount: 0,
  };

  const row = computeAgentUpdateRow(latest, null, false);

  assert.equal(row.primaryTokens, 500);
  assert.equal(row.tokenDelta, null);
  assert.equal(row.tokenDeltaPct, null);
  assert.equal(row.previousVersion, null);
});

test('updatesPageSeo emits CollectionPage with recent capture ItemList', () => {
  const seo = updatesPageSeo(
    site,
    [
      {
        agentId: 'codex',
        agentDisplayName: 'Codex CLI',
        version: '2.0.0',
        startedAt: '2026-02-01T00:00:00Z',
        primaryTokens: 1500,
        tokenDelta: 300,
      },
      {
        agentId: 'pi',
        agentDisplayName: 'Pi',
        version: '1.0.0',
        startedAt: '2026-01-01T00:00:00Z',
        primaryTokens: 500,
        tokenDelta: null,
      },
    ],
    16,
    '2026-02-01T00:00:00Z',
    true,
  );

  assert.match(seo.title, /Benchmark Updates/);
  assert.match(seo.description, /16 coding agents/);
  assert.match(seo.description, /February 1, 2026/);

  const collection = seo.jsonLd as {
    '@type': string;
    dateModified: string;
    mainEntity: { itemListElement: { position: number; name: string }[] };
  };
  assert.equal(collection['@type'], 'CollectionPage');
  assert.equal(collection.dateModified, '2026-02-01T00:00:00Z');
  assert.equal(collection.mainEntity.itemListElement[0].name, 'Codex CLI v2.0.0');
  assert.equal(collection.mainEntity.itemListElement[1].name, 'Pi v1.0.0');
});

test('agentPageSeo emits distinct token fields in dataset schema', () => {
  const seo = agentPageSeo(
    site,
    {
      agentId: 'codex',
      agentDisplayName: 'Codex CLI',
      latest: {
        totalTokens: 1000,
        anthropicTotalTokens: 2000,
        toolCount: 3,
        skillCount: 1,
        subagentCount: 0,
        version: '1.0.0',
        startedAt: '2026-01-01T00:00:00Z',
      },
    },
    true,
  );

  const dataset = seo.jsonLd[1] as { variableMeasured: { name: string; value: number }[] };
  const names = dataset.variableMeasured.map((entry) => entry.name);
  assert.deepEqual(names, [
    'o200k_total_tokens',
    'anthropic_total_tokens',
    'primary_display_tokens',
    'tool_count',
    'skill_count',
    'subagent_count',
    'agent_version',
  ]);
});