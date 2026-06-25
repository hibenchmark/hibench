import assert from 'node:assert/strict';
import test from 'node:test';

import {
  canonicalTokenCount,
  computeAgentUpdateRow,
  primaryTokenCount,
  PRIMARY_METRIC,
  SECONDARY_METRICS,
} from '../src/data/benchmark-core.js';
import worker from '../src/worker.js';
import {
  agentPageSeo,
  absoluteUrl,
  compareIndexPageSeo,
  comparePageSeo,
  compareSlug,
  dataPageSeo,
  generateComparePairs,
  getPageLastModified,
  homePageSeo,
  INDEXED_COMPARISON_PAIRS,
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

test('homePageSeo uses dynamic agent count and omits FAQ structured data', () => {
  const seo = homePageSeo(16);
  assert.match(seo.description, /16 coding agents/);
  assert.deepEqual(seo.jsonLd, []);
});

test('canonicalTokenCount and metric exports use o200k totals', () => {
  const run = {
    totalTokens: 1000,
    anthropicTotalTokens: 2000,
    toolCount: 1,
    skillCount: 0,
    subagentCount: 0,
    version: '1.0.0',
    startedAt: '2026-01-01T00:00:00Z',
  };
  assert.equal(PRIMARY_METRIC, 'o200k');
  assert.deepEqual(SECONDARY_METRICS, ['anthropic']);
  assert.equal(canonicalTokenCount(run), 1000);

  const metric = primaryTokenMetric(run);
  assert.equal(metric.tokens, 1000);
  assert.match(metric.label, /o200k_base/);
});

test('primaryTokenMetric prefers anthropic totals when explicitly enabled', () => {
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

test('rankingsItemListSchema ranks by o200k totals by default', () => {
  const agents = [
    {
      agentId: 'pi',
      agentDisplayName: 'Pi',
      latest: {
        totalTokens: 100,
        anthropicTotalTokens: 900,
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
        anthropicTotalTokens: 150,
        toolCount: 2,
        skillCount: 0,
        subagentCount: 0,
        version: '2.0.0',
        startedAt: '2026-01-02T00:00:00Z',
      },
    },
  ];

  const schema = rankingsItemListSchema(site, agents, false);
  const items = schema.itemListElement as { position: number; name: string; description: string }[];
  assert.equal(items[0].name, 'Codex CLI');
  assert.equal(items[1].name, 'Pi');
  assert.match(items[0].description, /500 default tokens/);

  const anthropicSchema = rankingsItemListSchema(site, agents, true);
  const anthropicItems = anthropicSchema.itemListElement as { name: string }[];
  assert.equal(anthropicItems[0].name, 'Pi');
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
  const pairs = generateComparePairs(sampleAgents, false);
  const slugs = pairs.map((pair) => pair.slug);

  assert.ok(slugs.includes('codex-vs-pi'));
  assert.ok(slugs.includes('codex-vs-cursor-cli'));
  assert.ok(slugs.includes('cursor-cli-vs-pi'));
  assert.equal(pairs.length, 3);
});

test('generateComparePairs always includes indexed comparison pairs when agents exist', () => {
  const indexedAgents = INDEXED_COMPARISON_PAIRS.flatMap(([a, b]) => [a, b]);
  const uniqueIds = [...new Set(indexedAgents)];
  const agents = uniqueIds.map((agentId, index) => ({
    agentId,
    agentDisplayName: agentId,
    latest: { ...sampleRun, totalTokens: 1000 - index * 10 },
  }));

  const pairs = generateComparePairs(agents, false);
  const slugs = new Set(pairs.map((pair) => pair.slug));

  for (const [idA, idB] of INDEXED_COMPARISON_PAIRS) {
    const slug =
      idA < idB ? `${idA}-vs-${idB}` : `${idB}-vs-${idA}`;
    assert.ok(slugs.has(slug), `missing indexed pair ${slug}`);
  }
});

test('getPageLastModified uses agent and compare capture dates', () => {
  const globalLatest = getPageLastModified('https://hibench.dev/rankings/');
  const methodology = getPageLastModified('https://hibench.dev/methodology/');
  const compare = getPageLastModified('https://hibench.dev/compare/claude-code-vs-codex/');
  const agent = getPageLastModified('https://hibench.dev/agents/codex/');

  assert.ok(globalLatest);
  assert.equal(methodology, '2026-06-24T00:00:00.000Z');
  assert.ok(compare);
  assert.ok(agent);
  assert.ok(compare >= agent || compare <= agent);
});

test('dataPageSeo emits Dataset JSON-LD with downloadable distributions', () => {
  const seo = dataPageSeo(site, '2026-06-24T12:00:00Z', [
    'runs.csv',
    'export.json',
  ]);

  assert.match(seo.title, /Dataset Downloads/);
  const dataset = seo.jsonLd as {
    '@type': string;
    distribution: { contentUrl: string; encodingFormat: string }[];
    version: string;
  };
  assert.equal(dataset['@type'], 'Dataset');
  assert.equal(dataset.version, 'hibench.benchmark.v1');
  assert.equal(dataset.distribution.length, 2);
  assert.equal(dataset.distribution[0].contentUrl, 'https://hibench.dev/data/runs.csv');
  assert.equal(dataset.distribution[0].encodingFormat, 'text/csv');
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
  const seo = comparePageSeo(site, sampleAgents[1], sampleAgents[2]);

  assert.match(seo.title, /Codex CLI vs Cursor CLI/);
  assert.match(seo.description, /1,000 default tokens \(o200k_base\)/);
  assert.match(seo.description, /500 default tokens \(o200k_base\)/);

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
  const seo = agentPageSeo(site, {
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
  });

  assert.match(seo.description, /1,000 default tokens \(o200k_base\)/);

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

  const primaryDisplay = dataset.variableMeasured.find(
    (entry) => entry.name === 'primary_display_tokens',
  );
  assert.equal(primaryDisplay?.value, 1000);
});