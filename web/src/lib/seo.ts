/** JSON-LD builders and page SEO helpers for static pages. */

import { canonicalTokenCount, primaryTokenCount } from '../data/benchmark-core.js';
import { formatBenchmarkDate, formatNumber, withBase } from './format';
import { METHODOLOGY_REVISION_DATE } from './methodology-date.mjs';

export { METHODOLOGY_REVISION_DATE };
export { getPageLastModified } from './page-lastmod.js';

export type JsonLd = Record<string, unknown>;

export const DEFAULT_SITE_URL = 'https://hibench.dev';

const SITE_DESCRIPTION =
  'Open-source benchmark comparing default token footprint, tools, skills, MCP, and sub-agents across coding agents.';

type TokenRun = {
  totalTokens: number;
  anthropicTotalTokens: number;
  toolCount: number;
  skillCount: number;
  subagentCount: number;
  version: string;
  startedAt: string;
};

type SeoAgentSummary = {
  agentId: string;
  agentDisplayName: string;
  latest: TokenRun;
};

export function resolveSiteUrl(site?: string | URL): string {
  if (site) return site.toString();
  return DEFAULT_SITE_URL;
}

export function absoluteUrl(site: string, path: string): string {
  return new URL(withBase(path), site).toString();
}

/** Canonical SEO/SSR metric uses o200k (`useAnthropic: false`). */
export function primaryTokenMetric(run: TokenRun, useAnthropic = false) {
  const tokens = primaryTokenCount(run, useAnthropic);
  const label = useAnthropic
    ? 'default Anthropic request tokens'
    : 'default tokens (o200k_base)';
  return { tokens, label };
}

export function organizationSchema(site: string): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    name: 'hibench',
    url: site,
    logo: absoluteUrl(site, '/favicon.svg'),
    sameAs: [
      'https://github.com/hibenchmark/hibench',
      'https://x.com/hibenchmark',
    ],
  };
}

export function webSiteSchema(site: string): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    name: 'hibench',
    url: site,
    description: SITE_DESCRIPTION,
    publisher: {
      '@type': 'Organization',
      name: 'hibench',
      url: site,
    },
  };
}

export function faqSchema(
  items: { question: string; answer: string }[],
): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((item) => ({
      '@type': 'Question',
      name: item.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: item.answer,
      },
    })),
  };
}

export function homePageSeo(agentCount: number) {
  return {
    description: `Compare how many tokens, tools, skills, and MCP servers ${agentCount} coding agents load on the first request. Open-source benchmark with reproducible captures.`,
    jsonLd: [],
  };
}

export function agentsIndexPageSeo(agentCount: number) {
  return {
    title: 'Benchmarked Coding Agents | hibench',
    description: `Explore default token footprint, tool counts, skill bundles, and version history for ${agentCount} coding agents measured by the open-source hibench benchmark.`,
  };
}

export function rankingsPageSeo(site: string, agents: SeoAgentSummary[]) {
  const agentCount = agents.length;
  return {
    title: 'Coding Agent Token Rankings | hibench',
    description: `Ranking of ${agentCount} coding agents by default request token footprint (o200k_base), tool count, skill surface, and sub-agent declarations in their latest hibench capture.`,
    jsonLd: rankingsItemListSchema(site, agents, false),
  };
}

export function rankingsItemListSchema(
  site: string,
  agents: SeoAgentSummary[],
  useAnthropic: boolean,
): JsonLd {
  const sorted = [...agents].sort((a, b) => {
    const av = useAnthropic
      ? a.latest.anthropicTotalTokens || a.latest.totalTokens
      : a.latest.totalTokens;
    const bv = useAnthropic
      ? b.latest.anthropicTotalTokens || b.latest.totalTokens
      : b.latest.totalTokens;
    return bv - av;
  });

  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: 'Coding agent default token footprint ranking',
    description:
      'Coding agents ranked by total default request tokens in their latest captured hibench run.',
    numberOfItems: sorted.length,
    itemListElement: sorted.map((agent, index) => {
      const tokens = useAnthropic
        ? primaryTokenCount(agent.latest, true)
        : canonicalTokenCount(agent.latest);
      return {
        '@type': 'ListItem',
        position: index + 1,
        name: agent.agentDisplayName,
        url: absoluteUrl(site, `/agents/${agent.agentId}/`),
        description: `${agent.agentDisplayName} loads ${tokens.toLocaleString('en-US')} default tokens.`,
      };
    }),
  };
}

export function breadcrumbSchema(
  site: string,
  items: { name: string; path?: string }[],
): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((item, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: item.name,
      ...(item.path ? { item: absoluteUrl(site, item.path) } : {}),
    })),
  };
}

export function agentDatasetSchema(
  site: string,
  agent: {
    agentId: string;
    agentDisplayName: string;
    version: string;
    o200kTotalTokens: number;
    anthropicTotalTokens: number;
    primaryDisplayTokens: number;
    toolCount: number;
    skillCount: number;
    subagentCount: number;
    startedAt: string;
  },
): JsonLd {
  const variableMeasured = [
    {
      '@type': 'PropertyValue',
      name: 'o200k_total_tokens',
      value: agent.o200kTotalTokens,
    },
    {
      '@type': 'PropertyValue',
      name: 'primary_display_tokens',
      value: agent.primaryDisplayTokens,
    },
    { '@type': 'PropertyValue', name: 'tool_count', value: agent.toolCount },
    { '@type': 'PropertyValue', name: 'skill_count', value: agent.skillCount },
    {
      '@type': 'PropertyValue',
      name: 'subagent_count',
      value: agent.subagentCount,
    },
    { '@type': 'PropertyValue', name: 'agent_version', value: agent.version },
  ];

  if (agent.anthropicTotalTokens > 0) {
    variableMeasured.splice(1, 0, {
      '@type': 'PropertyValue',
      name: 'anthropic_total_tokens',
      value: agent.anthropicTotalTokens,
    });
  }

  return {
    '@context': 'https://schema.org',
    '@type': 'Dataset',
    name: `${agent.agentDisplayName} default footprint benchmark`,
    description: `Default token, tool, skill, and sub-agent footprint for ${agent.agentDisplayName} v${agent.version} captured by hibench.`,
    url: absoluteUrl(site, `/agents/${agent.agentId}/`),
    creator: {
      '@type': 'Organization',
      name: 'hibench',
      url: site,
    },
    variableMeasured,
    ...(agent.startedAt ? { dateModified: agent.startedAt } : {}),
    isAccessibleForFree: true,
    license: 'https://opensource.org/licenses/MIT',
  };
}

export function canonicalComparePair(
  agentA: string,
  agentB: string,
): [string, string] {
  return agentA < agentB ? [agentA, agentB] : [agentB, agentA];
}

export function compareSlug(agentA: string, agentB: string): string {
  const [a, b] = canonicalComparePair(agentA, agentB);
  return `${a}-vs-${b}`;
}

export function parseCompareSlug(
  slug: string,
): { agentA: string; agentB: string } | null {
  const marker = '-vs-';
  const index = slug.indexOf(marker);
  if (index <= 0 || index === slug.length - marker.length) return null;

  const agentA = slug.slice(0, index);
  const agentB = slug.slice(index + marker.length);
  if (!agentA || !agentB || agentA >= agentB) return null;

  return { agentA, agentB };
}

export function rankedAgents(
  agents: SeoAgentSummary[],
  useAnthropic = false,
): SeoAgentSummary[] {
  return [...agents].sort((a, b) => {
    const av = primaryTokenCount(a.latest, useAnthropic);
    const bv = primaryTokenCount(b.latest, useAnthropic);
    return bv - av;
  });
}

export type ComparePair = {
  agentA: string;
  agentB: string;
  slug: string;
};

/** High-intent pairs that must stay in the compare index even if ranking adjacency changes. */
export const INDEXED_COMPARISON_PAIRS: ReadonlyArray<readonly [string, string]> = [
  ['claude-code', 'codex'],
  ['claude-code', 'cursor-cli'],
  ['claude-code', 'gemini-cli'],
  ['codex', 'cursor-cli'],
  ['cline', 'opencode'],
];

export function generateComparePairs(
  agents: SeoAgentSummary[],
  useAnthropic = false,
): ComparePair[] {
  const ranked = rankedAgents(agents, useAnthropic);
  const agentIds = new Set(agents.map((agent) => agent.agentId));
  const pairs = new Map<string, ComparePair>();

  const addPair = (idA: string, idB: string) => {
    if (!agentIds.has(idA) || !agentIds.has(idB) || idA === idB) return;
    const [agentA, agentB] = canonicalComparePair(idA, idB);
    const slug = compareSlug(agentA, agentB);
    pairs.set(slug, { agentA, agentB, slug });
  };

  for (const [idA, idB] of INDEXED_COMPARISON_PAIRS) {
    addPair(idA, idB);
  }

  if (ranked.length >= 2) {
    addPair(ranked[0].agentId, ranked[ranked.length - 1].agentId);
  }

  for (let i = 0; i < ranked.length - 1; i += 1) {
    addPair(ranked[i].agentId, ranked[i + 1].agentId);
  }

  return [...pairs.values()].sort((a, b) => a.slug.localeCompare(b.slug));
}

export type CompareIndexEntry = {
  slug: string;
  agentADisplayName: string;
  agentBDisplayName: string;
};

export function compareIndexItemListSchema(
  site: string,
  entries: CompareIndexEntry[],
): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: 'Coding agent benchmark comparisons',
    description:
      'Side-by-side default footprint comparisons between coding agent pairs.',
    numberOfItems: entries.length,
    itemListElement: entries.map((entry, index) => ({
      '@type': 'ListItem',
      position: index + 1,
      name: `${entry.agentADisplayName} vs ${entry.agentBDisplayName}`,
      url: absoluteUrl(site, `/compare/${entry.slug}/`),
      description: `Compare ${entry.agentADisplayName} and ${entry.agentBDisplayName} default token footprint, tools, skills, and sub-agents.`,
    })),
  };
}

export function compareIndexPageSeo(
  site: string,
  entries: CompareIndexEntry[],
  lastUpdated?: string,
) {
  return {
    title: 'Coding Agent Comparisons | hibench',
    description: `Side-by-side benchmark comparisons for ${entries.length} high-intent coding-agent pairs: default tokens, tools, skills, and sub-agent footprint.`,
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Coding agent comparisons',
      description: `Index of ${entries.length} side-by-side hibench benchmark comparisons between coding agent pairs.`,
      url: absoluteUrl(site, '/compare/'),
      ...(lastUpdated ? { dateModified: lastUpdated } : {}),
      mainEntity: compareIndexItemListSchema(site, entries),
    },
  };
}

export function compareWebPageSchema(
  site: string,
  agentA: SeoAgentSummary,
  agentB: SeoAgentSummary,
  slug: string,
): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebPage',
    name: `${agentA.agentDisplayName} vs ${agentB.agentDisplayName} benchmark comparison`,
    description: `Side-by-side default footprint comparison between ${agentA.agentDisplayName} and ${agentB.agentDisplayName}.`,
    url: absoluteUrl(site, `/compare/${slug}/`),
    mainEntity: {
      '@type': 'ItemList',
      numberOfItems: 2,
      itemListElement: [
        {
          '@type': 'ListItem',
          position: 1,
          item: {
            '@type': 'Dataset',
            name: `${agentA.agentDisplayName} default footprint benchmark`,
            url: absoluteUrl(site, `/agents/${agentA.agentId}/`),
          },
        },
        {
          '@type': 'ListItem',
          position: 2,
          item: {
            '@type': 'Dataset',
            name: `${agentB.agentDisplayName} default footprint benchmark`,
            url: absoluteUrl(site, `/agents/${agentB.agentId}/`),
          },
        },
      ],
    },
  };
}

export function comparePageSeo(
  site: string,
  agentA: SeoAgentSummary,
  agentB: SeoAgentSummary,
) {
  const nameA = agentA.agentDisplayName;
  const nameB = agentB.agentDisplayName;
  const tokensA = primaryTokenMetric(agentA.latest, false);
  const tokensB = primaryTokenMetric(agentB.latest, false);
  const slug = compareSlug(agentA.agentId, agentB.agentId);

  return {
    title: `${nameA} vs ${nameB} Default Tokens | hibench`,
    description: `Compare ${nameA} (${formatNumber(tokensA.tokens)} ${tokensA.label}) vs ${nameB} (${formatNumber(tokensB.tokens)} ${tokensB.label}). Side-by-side tools, skills, sub-agents, and version footprint.`,
    jsonLd: [
      breadcrumbSchema(site, [
        { name: 'Compare', path: '/compare/' },
        { name: `${nameA} vs ${nameB}` },
      ]),
      compareWebPageSchema(site, agentA, agentB, slug),
    ],
  };
}

export type AgentUpdateSummary = {
  agentId: string;
  agentDisplayName: string;
  version: string;
  startedAt: string;
  primaryTokens: number;
  tokenDelta: number | null;
};

export function updatesItemListSchema(
  site: string,
  updates: AgentUpdateSummary[],
): JsonLd {
  return {
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name: 'Recent coding agent benchmark captures',
    description:
      'Latest hibench captures per agent with version and default token footprint changes.',
    numberOfItems: updates.length,
    itemListElement: updates.map((update, index) => {
      const deltaText =
        update.tokenDelta === null
          ? 'first captured version'
          : `${update.tokenDelta >= 0 ? '+' : ''}${update.tokenDelta.toLocaleString('en-US')} tokens vs previous version`;
      return {
        '@type': 'ListItem',
        position: index + 1,
        name: `${update.agentDisplayName} v${update.version}`,
        url: absoluteUrl(site, `/agents/${update.agentId}/`),
        description: `${update.agentDisplayName} v${update.version} captured ${formatBenchmarkDate(update.startedAt)} with ${update.primaryTokens.toLocaleString('en-US')} o200k tokens (${deltaText}).`,
      };
    }),
  };
}

type DataDownloadFile = {
  name: string;
  path: string;
  encodingFormat: string;
  optional?: boolean;
};

const DATA_DOWNLOAD_FILES: DataDownloadFile[] = [
  { name: 'runs.csv', path: '/data/runs.csv', encodingFormat: 'text/csv' },
  { name: 'tools.csv', path: '/data/tools.csv', encodingFormat: 'text/csv' },
  { name: 'skills.csv', path: '/data/skills.csv', encodingFormat: 'text/csv' },
  { name: 'subagents.csv', path: '/data/subagents.csv', encodingFormat: 'text/csv' },
  { name: 'mcp.csv', path: '/data/mcp.csv', encodingFormat: 'text/csv', optional: true },
  {
    name: 'text_fields.csv',
    path: '/data/text_fields.csv',
    encodingFormat: 'text/csv',
  },
  { name: 'export.json', path: '/data/export.json', encodingFormat: 'application/json' },
  {
    name: 'github_stars.json',
    path: '/data/github_stars.json',
    encodingFormat: 'application/json',
    optional: true,
  },
];

export function dataPageSeo(
  site: string,
  lastUpdated: string,
  availableFiles: string[],
) {
  const available = new Set(availableFiles);
  const distributions = DATA_DOWNLOAD_FILES.filter((file) => available.has(file.name)).map(
    (file) => ({
      '@type': 'DataDownload',
      name: file.name,
      contentUrl: absoluteUrl(site, file.path),
      encodingFormat: file.encodingFormat,
    }),
  );

  return {
    title: 'Benchmark Dataset Downloads | hibench',
    description:
      'Download hibench benchmark exports: runs, tools, skills, sub-agents, MCP, and text-field tables from the open-source coding-agent footprint dataset.',
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'Dataset',
      name: 'hibench coding-agent benchmark exports',
      description:
        'Canonical CSV and JSON exports from hibench captures of default coding-agent request footprint.',
      url: absoluteUrl(site, '/data/'),
      creator: {
        '@type': 'Organization',
        name: 'hibench',
        url: site,
      },
      license: 'https://opensource.org/licenses/MIT',
      isAccessibleForFree: true,
      measurementTechnique: 'Isolated Docker capture with local request interception',
      variableMeasured: [
        'total_body_tokens',
        'tool_count',
        'skill_count',
        'subagent_count',
        'mcp_count',
        'text_field_tokens',
      ],
      distribution: distributions,
      ...(lastUpdated ? { dateModified: lastUpdated } : {}),
      version: 'hibench.benchmark.v1',
    },
  };
}

export function updatesPageSeo(
  site: string,
  updates: AgentUpdateSummary[],
  agentCount: number,
  lastUpdated: string,
) {
  const formattedDate = formatBenchmarkDate(lastUpdated);
  const dateSuffix = formattedDate ? ` Last capture activity: ${formattedDate} UTC.` : '';

  return {
    title: 'Benchmark Updates | hibench',
    description: `Recent benchmark captures for ${agentCount} coding agents: latest versions, default token footprint deltas, and capture dates.${dateSuffix}`,
    jsonLd: {
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: 'Benchmark updates',
      description: `Changelog of recent hibench benchmark captures across ${agentCount} coding agents.`,
      url: absoluteUrl(site, '/updates/'),
      ...(lastUpdated ? { dateModified: lastUpdated } : {}),
      mainEntity: updatesItemListSchema(site, updates),
    },
  };
}

export function agentPageSeo(site: string, summary: SeoAgentSummary) {
  const agentName = summary.agentDisplayName;
  const { tokens, label } = primaryTokenMetric(summary.latest, false);
  const latest = summary.latest;

  return {
    title: `${agentName} Default Token Footprint | hibench`,
    description: `${agentName} loads ${formatNumber(tokens)} ${label}, ${latest.toolCount} tools, ${latest.skillCount} skills, and ${latest.subagentCount} sub-agents in v${latest.version}.`,
    ogImage: `/og/agents/${summary.agentId}.png`,
    ogImageAlt: `hibench social preview for ${agentName}, showing latest default footprint metrics.`,
    jsonLd: [
      breadcrumbSchema(site, [
        { name: 'Agents', path: '/agents/' },
        { name: agentName },
      ]),
      agentDatasetSchema(site, {
        agentId: summary.agentId,
        agentDisplayName: agentName,
        version: latest.version,
        o200kTotalTokens: latest.totalTokens,
        anthropicTotalTokens: latest.anthropicTotalTokens,
        primaryDisplayTokens: tokens,
        toolCount: latest.toolCount,
        skillCount: latest.skillCount,
        subagentCount: latest.subagentCount,
        startedAt: latest.startedAt,
      }),
    ],
  };
}