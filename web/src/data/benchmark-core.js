// Build-time benchmark data layer.
//
// Reads the canonical `results/*.csv` exports produced by `hibench export`
// and turns them into view-ready structures for the Astro pages and OG image
// generation. Everything here runs at build time (SSG), so Node `fs` access is
// fine.

import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseCsv } from './csv.js';

// ---------------------------------------------------------------------------
// Locate the results directory
// ---------------------------------------------------------------------------

function findResultsDir() {
  const fromEnv = process.env.RESULTS_DIR;
  if (fromEnv && existsSync(join(fromEnv, 'runs.csv'))) return fromEnv;

  // Walk upward from this module looking for a `results/runs.csv`.
  let dir = dirname(fileURLToPath(import.meta.url));
  for (let i = 0; i < 8; i += 1) {
    const candidate = join(dir, 'results');
    if (existsSync(join(candidate, 'runs.csv'))) return candidate;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error(
    'Could not locate results/runs.csv. Set RESULTS_DIR or run the build from within the repo.',
  );
}

const RESULTS_DIR = findResultsDir();

function findRepoRoot() {
  let dir = dirname(fileURLToPath(import.meta.url));
  for (let i = 0; i < 8; i += 1) {
    if (existsSync(join(dir, 'agents', 'codex', 'agent.json'))) return dir;
    const parent = dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  throw new Error('Could not locate repo root with agents/codex/agent.json.');
}

const REPO_ROOT = findRepoRoot();

function loadCsv(name) {
  const path = join(RESULTS_DIR, name);
  if (!existsSync(path)) return [];
  return parseCsv(readFileSync(path, 'utf8'));
}

// ---------------------------------------------------------------------------
// Helpers and shared agent metadata
// ---------------------------------------------------------------------------

const num = (v) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

function toGitHubUrl(repo) {
  return repo ? `https://github.com/${repo}` : undefined;
}

function loadAgentLinks() {
  const agentsDir = join(REPO_ROOT, 'agents');
  const links = {};
  for (const entry of readdirSync(agentsDir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const path = join(agentsDir, entry.name, 'agent.json');
    if (!existsSync(path)) continue;
    const raw = readJson(path);
    const rawLinks = raw && typeof raw.links === 'object' ? raw.links : {};
    const officialUrl = rawLinks.official_url || undefined;
    const githubRepo = rawLinks.github_repo || undefined;
    const githubUrl = rawLinks.github_url || toGitHubUrl(githubRepo);
    links[entry.name] = { officialUrl, githubRepo, githubUrl };
  }
  return links;
}

function loadGitHubStars() {
  const path = join(RESULTS_DIR, 'github_stars.json');
  if (!existsSync(path)) return {};
  const raw = readJson(path);
  return raw && typeof raw.agents === 'object' ? raw.agents : {};
}

export const AGENT_DISPLAY_NAMES = {
  codex: 'Codex CLI',
  'claude-code': 'Claude Code',
  'cursor-cli': 'Cursor CLI',
  devin: 'Devin',
  droid: 'Droid',
  'gemini-cli': 'Gemini CLI',
  'github-cli': 'Copilot CLI',
  'mistral-vibe': 'Mistral Vibe',
  openhands: 'OpenHands',
};

export const GENERIC_AGENT_LOGO = '/agent-logos/generic-agent.svg';

export const AGENT_LOGOS = {
  codex: {
    path: '/agent-logos/codex.svg',
    alt: 'Codex logo',
    source: 'official',
  },
  'claude-code': {
    path: '/agent-logos/claude-code.svg',
    alt: 'Claude Code logo',
    source: 'official',
  },
  cline: {
    path: '/agent-logos/cline.png',
    alt: 'Cline logo',
    source: 'official',
  },
  'cursor-cli': {
    path: '/agent-logos/cursor-cli.svg',
    alt: 'Cursor logo',
    source: 'official',
  },
  devin: {
    path: '/agent-logos/devin.png',
    alt: 'Devin logo',
    source: 'official',
  },
  droid: {
    path: '/agent-logos/droid.svg',
    alt: 'Droid logo',
    source: 'official',
  },
  'gemini-cli': {
    path: '/agent-logos/gemini-cli.png',
    alt: 'Gemini CLI logo',
    source: 'official',
  },
  openclaw: {
    path: '/agent-logos/openclaw.svg',
    alt: 'OpenClaw logo',
    source: 'official',
  },
  opencode: {
    path: '/agent-logos/opencode.png',
    alt: 'OpenCode logo',
    source: 'official',
  },
  'grok-cli': {
    path: '/agent-logos/grok-cli.svg',
    alt: 'Grok logo',
    source: 'official',
  },
  'github-cli': {
    path: '/agent-logos/github-cli.svg',
    alt: 'GitHub Copilot logo',
    source: 'official',
  },
  hermes: {
    path: '/agent-logos/hermes.png',
    alt: 'Hermes Agent logo',
    source: 'official',
  },
  kilo: {
    path: '/agent-logos/kilo.png',
    alt: 'Kilo Code logo',
    source: 'official',
  },
  'mistral-vibe': {
    path: '/agent-logos/mistral-vibe.svg',
    alt: 'Mistral Vibe logo',
    source: 'official',
  },
  openhands: {
    path: '/agent-logos/openhands.svg',
    alt: 'OpenHands logo',
    source: 'official',
  },
  pi: {
    path: '/agent-logos/pi.svg',
    alt: 'Pi logo',
    source: 'official',
  },
};

export const AGENT_LINKS = loadAgentLinks();
const GITHUB_STARS = loadGitHubStars();

function toAgentDisplayName(agentId, agentName) {
  return AGENT_DISPLAY_NAMES[agentId] ?? agentName;
}

function toAgentLogo(agentId, agentDisplayName) {
  return (
    AGENT_LOGOS[agentId] ?? {
      path: GENERIC_AGENT_LOGO,
      alt: `${agentDisplayName} generic coding agent logo`,
      source: 'generic',
    }
  );
}

function toAgentLinks(agentId) {
  const links = { ...(AGENT_LINKS[agentId] ?? {}) };
  const stars = GITHUB_STARS[agentId];
  if (!stars || !links.githubRepo) return links;
  const githubStars = num(stars.github_stars);
  const githubRepo = String(stars.github_repo || '');
  const repoMatches =
    !githubRepo || githubRepo.toLowerCase() === links.githubRepo.toLowerCase();
  if (githubStars > 0 && repoMatches) {
    links.githubStars = githubStars;
    links.githubStarsUpdatedAt = stars.updated_at || '';
  }
  return links;
}

/** Compare two dotted versions numerically (e.g. 2.1.9 < 2.1.100). */
export function compareVersions(a, b) {
  const pa = a.split('.');
  const pb = b.split('.');
  const len = Math.max(pa.length, pb.length);
  for (let i = 0; i < len; i += 1) {
    const x = parseInt(pa[i] ?? '0', 10) || 0;
    const y = parseInt(pb[i] ?? '0', 10) || 0;
    if (x !== y) return x - y;
  }
  return 0;
}

function toRun(r) {
  return {
    runId: r.run_id,
    agentId: r.agent_id,
    agentName: r.agent_name,
    version: r.agent_version,
    model: r.model,
    hasPrimary: r.has_primary_request === 'True',
    startedAt: r.started_at,
    bodyBytes: num(r.body_bytes),
    totalTokens: num(r.total_body_tokens),
    anthropicTotalTokens: num(r.anthropic_total_body_tokens),
    anthropicTokenizerModel: r.anthropic_tokenizer_model || '',
    systemPromptTokens: num(r.system_prompt_tokens),
    toolTokens: num(r.tool_definition_tokens),
    skillTokens: num(r.skill_definition_tokens),
    mcpTokens: num(r.mcp_tokens),
    subagentTokens: num(r.subagent_tokens),
    userPromptTokens: num(r.user_prompt_tokens),
    envContextTokens: num(r.environment_context_tokens),
    defaultContextTokens: num(r.default_context_tokens),
    toolCount: num(r.tool_count),
    skillCount: num(r.skills_count),
    mcpCount: num(r.mcp_count),
    subagentCount: num(r.subagent_count),
  };
}

// ---------------------------------------------------------------------------
// Cached loads
// ---------------------------------------------------------------------------

let _runs = null;

export function getPrimaryRuns() {
  if (_runs) return _runs;
  _runs = loadCsv('runs.csv').map(toRun).filter((r) => r.hasPrimary && r.totalTokens > 0);
  return _runs;
}

export function getAgentVersions(agentId) {
  return getPrimaryRuns()
    .filter((r) => r.agentId === agentId)
    .sort((a, b) => compareVersions(a.version, b.version));
}

export function getAgents() {
  const byAgent = new Map();
  for (const run of getPrimaryRuns()) {
    const list = byAgent.get(run.agentId) ?? [];
    list.push(run);
    byAgent.set(run.agentId, list);
  }

  const summaries = [];
  for (const [agentId, runs] of byAgent) {
    runs.sort((a, b) => compareVersions(a.version, b.version));
    const totals = runs.map((r) => r.totalTokens);
    const anthropicTotals = runs
      .map((r) => r.anthropicTotalTokens)
      .filter((value) => value > 0);
    const agentDisplayName = toAgentDisplayName(agentId, runs[0].agentName);
    summaries.push({
      agentId,
      agentName: runs[0].agentName,
      agentDisplayName,
      agentLogo: toAgentLogo(agentId, agentDisplayName),
      agentLinks: toAgentLinks(agentId),
      latest: runs[runs.length - 1],
      firstVersion: runs[0].version,
      versionCount: runs.length,
      minTotal: Math.min(...totals),
      maxTotal: Math.max(...totals),
      minAnthropicTotal: anthropicTotals.length ? Math.min(...anthropicTotals) : 0,
      maxAnthropicTotal: anthropicTotals.length ? Math.max(...anthropicTotals) : 0,
    });
  }
  // Default ranking: heaviest footprint first.
  summaries.sort((a, b) => b.latest.totalTokens - a.latest.totalTokens);
  return summaries;
}

export function getAgentIds() {
  return getAgents().map((a) => a.agentId);
}

// Tools / skills grouped by run id (lazy + cached).

let _toolsByRun = null;

export function getToolsForRun(runId) {
  if (!_toolsByRun) {
    _toolsByRun = new Map();
    for (const r of loadCsv('tools.csv')) {
      const list = _toolsByRun.get(r.run_id) ?? [];
      list.push({
        name: r.tool_name,
        type: r.tool_type,
        tokens: num(r.definition_tokens),
        isMcp: r.is_mcp_related === 'True',
        isSubagent: r.is_subagent_related === 'True',
      });
      _toolsByRun.set(r.run_id, list);
    }
  }
  const tools = _toolsByRun.get(runId) ?? [];
  return [...tools].sort((a, b) => b.tokens - a.tokens);
}

let _skillsByRun = null;

export function getSkillsForRun(runId) {
  if (!_skillsByRun) {
    _skillsByRun = new Map();
    for (const r of loadCsv('skills.csv')) {
      const list = _skillsByRun.get(r.run_id) ?? [];
      list.push({
        name: r.skill_name,
        tokens: num(r.definition_tokens),
        description: r.description,
      });
      _skillsByRun.set(r.run_id, list);
    }
  }
  const skills = _skillsByRun.get(runId) ?? [];
  return [...skills].sort((a, b) => b.tokens - a.tokens);
}

let _subagentsByRun = null;

export function getSubagentsForRun(runId) {
  if (!_subagentsByRun) {
    _subagentsByRun = new Map();
    for (const r of loadCsv('subagents.csv')) {
      if (r.is_counted !== 'True') continue;
      const list = _subagentsByRun.get(r.run_id) ?? [];
      list.push({
        name: r.marker_name,
        tokens: num(r.tokens),
        preview: r.preview,
        sourceType: r.source_type,
      });
      _subagentsByRun.set(r.run_id, list);
    }
  }
  const subagents = _subagentsByRun.get(runId) ?? [];
  return [...subagents].sort((a, b) => b.tokens - a.tokens);
}

// ---------------------------------------------------------------------------
// Footprint composition (the major token contributors of a request)
// ---------------------------------------------------------------------------

export function footprintParts(run) {
  return [
    { key: 'tools', label: 'Tool definitions', tokens: run.toolTokens, color: '#6366f1' },
    { key: 'system', label: 'System prompt', tokens: run.systemPromptTokens, color: '#0ea5e9' },
    { key: 'skills', label: 'Skills', tokens: run.skillTokens, color: '#10b981' },
    { key: 'subagents', label: 'Sub-agents', tokens: run.subagentTokens, color: '#f59e0b' },
    { key: 'mcp', label: 'MCP', tokens: run.mcpTokens, color: '#ec4899' },
    {
      key: 'context',
      label: 'User + environment',
      tokens: run.userPromptTokens + run.envContextTokens,
      color: '#94a3b8',
    },
  ].filter((p) => p.tokens > 0);
}

export function getGlobalStats() {
  const runs = getPrimaryRuns();
  const totals = runs.map((r) => r.totalTokens);
  return {
    agentCount: getAgents().length,
    versionCount: runs.length,
    minTotal: Math.min(...totals),
    maxTotal: Math.max(...totals),
  };
}

export function getLatestBenchmarkDate() {
  const runs = getPrimaryRuns();
  if (!runs.length) return '';
  return runs.reduce(
    (latest, run) => (run.startedAt > latest ? run.startedAt : latest),
    runs[0].startedAt,
  );
}

// ---------------------------------------------------------------------------
// Recent agent updates (latest capture + delta vs previous version)
// ---------------------------------------------------------------------------

/** Primary display tokens: Anthropic totals when enabled, else o200k. */
export function primaryTokenCount(run, useAnthropic) {
  return useAnthropic ? run.anthropicTotalTokens || run.totalTokens : run.totalTokens;
}

/** Pure helper: latest vs previous version deltas for one agent. */
export function computeAgentUpdateRow(latest, previous, useAnthropic) {
  const primaryTokens = primaryTokenCount(latest, useAnthropic);
  const previousPrimaryTokens = previous ? primaryTokenCount(previous, useAnthropic) : null;
  const tokenDelta =
    previousPrimaryTokens !== null ? primaryTokens - previousPrimaryTokens : null;
  const tokenDeltaPct =
    previousPrimaryTokens && previousPrimaryTokens > 0
      ? (tokenDelta / previousPrimaryTokens) * 100
      : null;

  return {
    version: latest.version,
    previousVersion: previous?.version ?? null,
    startedAt: latest.startedAt,
    totalTokens: latest.totalTokens,
    anthropicTotalTokens: latest.anthropicTotalTokens,
    primaryTokens,
    tokenDelta,
    tokenDeltaPct,
    toolCount: latest.toolCount,
    skillCount: latest.skillCount,
    subagentCount: latest.subagentCount,
    toolDelta: previous ? latest.toolCount - previous.toolCount : null,
    skillDelta: previous ? latest.skillCount - previous.skillCount : null,
    subagentDelta: previous ? latest.subagentCount - previous.subagentCount : null,
  };
}

export function getRecentAgentUpdates() {
  const agents = getAgents();
  const useAnthropic =
    agents.length > 0 && agents.every((a) => a.latest.anthropicTotalTokens > 0);

  const updates = agents.map((agent) => {
    const versions = getAgentVersions(agent.agentId);
    const latest = versions[versions.length - 1];
    const previous = versions.length > 1 ? versions[versions.length - 2] : null;
    return {
      agentId: agent.agentId,
      agentDisplayName: agent.agentDisplayName,
      agentLogo: agent.agentLogo,
      useAnthropic,
      ...computeAgentUpdateRow(latest, previous, useAnthropic),
    };
  });

  return updates.sort((a, b) => {
    if (a.startedAt > b.startedAt) return -1;
    if (a.startedAt < b.startedAt) return 1;
    return 0;
  });
}