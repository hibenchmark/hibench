#!/usr/bin/env node

import { mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import {
  GENERIC_AGENT_LOGO,
  footprintParts,
  getAgents,
  getGlobalStats,
} from '../src/data/benchmark-core.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const webRoot = resolve(__dirname, '..');
const publicDir = resolve(webRoot, 'public');
const outPath = resolve(publicDir, 'og-image.png');
const agentOutDir = resolve(publicDir, 'og', 'agents');

const WIDTH = 1200;
const HEIGHT = 630;

const THEMES = {
  'claude-code': {
    colors: ['#fde68a', '#fb923c', '#e11d48'],
    label: '#fdba74',
    glow: '#fb923c',
    badgeBg: '#412414',
    badgeStroke: '#fb923c',
  },
  cline: {
    colors: ['#f8fafc', '#cbd5e1', '#64748b', '#1f2937'],
    label: '#cbd5e1',
    glow: '#cbd5e1',
    badgeBg: '#1f2937',
    badgeStroke: '#cbd5e1',
  },
  codex: {
    colors: ['#ccfbf1', '#22d3ee', '#2563eb'],
    label: '#67e8f9',
    glow: '#22d3ee',
    badgeBg: '#0f3555',
    badgeStroke: '#22d3ee',
  },
  'cursor-cli': {
    colors: ['#fafaf9', '#a8a29e', '#44403c', '#1c1917'],
    label: '#d6d3d1',
    glow: '#f5f5f4',
    badgeBg: '#252321',
    badgeStroke: '#d6d3d1',
  },
  'github-cli': {
    colors: ['#dcfce7', '#22c55e', '#2563eb', '#111827'],
    label: '#86efac',
    glow: '#3b82f6',
    badgeBg: '#123122',
    badgeStroke: '#22c55e',
  },
  'grok-cli': {
    colors: ['#f8fafc', '#67e8f9', '#0891b2', '#0f172a'],
    label: '#a5f3fc',
    glow: '#67e8f9',
    badgeBg: '#12303a',
    badgeStroke: '#67e8f9',
  },
  hermes: {
    colors: ['#ede9fe', '#a855f7', '#4f46e5'],
    label: '#c4b5fd',
    glow: '#a855f7',
    badgeBg: '#2f1d47',
    badgeStroke: '#a855f7',
  },
  kilo: {
    colors: ['#fffbeb', '#ffe600', '#f5e216', '#7a6a00'],
    label: '#f5e216',
    glow: '#ffe600',
    badgeBg: '#3a3305',
    badgeStroke: '#ffe600',
  },
  opencode: {
    colors: ['#d1fae5', '#18e299', '#16a34a', '#0d9373'],
    label: '#86efac',
    glow: '#18e299',
    badgeBg: '#113a28',
    badgeStroke: '#18e299',
  },
  openclaw: {
    colors: ['#fee2e2', '#fb7185', '#e11d48', '#7f1d1d'],
    label: '#fda4af',
    glow: '#fb7185',
    badgeBg: '#461a22',
    badgeStroke: '#fb7185',
  },
  pi: {
    colors: ['#fef3c7', '#facc15', '#f97316', '#be123c'],
    label: '#fde047',
    glow: '#facc15',
    badgeBg: '#3b2b09',
    badgeStroke: '#facc15',
  },
};

const FALLBACK_THEMES = [
  { colors: ['#f0abfc', '#d946ef', '#7c3aed'], label: '#f0abfc', glow: '#d946ef', badgeBg: '#34193d', badgeStroke: '#d946ef' },
  { colors: ['#bef264', '#84cc16', '#15803d'], label: '#bef264', glow: '#84cc16', badgeBg: '#21320c', badgeStroke: '#84cc16' },
  { colors: ['#bfdbfe', '#60a5fa', '#4338ca'], label: '#93c5fd', glow: '#60a5fa', badgeBg: '#192846', badgeStroke: '#60a5fa' },
];

function escapeXml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function formatNumber(n) {
  return new Intl.NumberFormat('en-US').format(Math.round(n));
}

function formatDate(isoDate) {
  if (!isoDate) return '';
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(isoDate));
}

function themeFor(agentId) {
  if (THEMES[agentId]) return THEMES[agentId];
  let hash = 0;
  for (const char of agentId) {
    hash = (hash * 31 + char.charCodeAt(0)) % FALLBACK_THEMES.length;
  }
  return FALLBACK_THEMES[hash];
}

function truncate(text, length = 13) {
  return text.length <= length ? text : `${text.slice(0, length - 1)}…`;
}

function initials(text) {
  const words = text
    .replaceAll(/[^A-Za-z0-9 ]/g, ' ')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
  if (!words.length) return 'AI';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words.at(-1)[0]}`.toUpperCase();
}

function gradientStops(colors) {
  if (colors.length === 1) return `<stop offset="0%" stop-color="${colors[0]}"/>`;
  return colors
    .map((color, index) => {
      const offset = Math.round((index / (colors.length - 1)) * 100);
      return `<stop offset="${offset}%" stop-color="${color}"/>`;
    })
    .join('');
}

function mimeForPath(path) {
  switch (extname(path).toLowerCase()) {
    case '.png':
      return 'image/png';
    case '.jpg':
    case '.jpeg':
      return 'image/jpeg';
    case '.webp':
      return 'image/webp';
    case '.svg':
    default:
      return 'image/svg+xml';
  }
}

async function dataUriForPublicPath(publicPath) {
  const normalized = publicPath.startsWith('/') ? publicPath.slice(1) : publicPath;
  const path = resolve(publicDir, normalized);
  const data = await readFile(path);
  return `data:${mimeForPath(path)};base64,${data.toString('base64')}`;
}

async function loadImageAssets(agents) {
  const [brandLogo, genericLogo] = await Promise.all([
    dataUriForPublicPath('/favicon.svg'),
    dataUriForPublicPath(GENERIC_AGENT_LOGO),
  ]);
  const agentLogos = new Map();
  const uniqueAgents = new Map(agents.map((agent) => [agent.agentId, agent]));
  await Promise.all(
    [...uniqueAgents.values()].map(async (agent) => {
      const logo = agent.agentLogo;
      try {
        agentLogos.set(agent.agentId, await dataUriForPublicPath(logo.path));
      } catch (error) {
        if (logo.source === 'generic') {
          agentLogos.set(agent.agentId, genericLogo);
          return;
        }
        throw new Error(
          `Failed to load configured logo for ${agent.agentId} at ${logo.path}`,
          { cause: error },
        );
      }
    }),
  );
  return { agentLogos, brandLogo };
}

function brandMark(brandLogo) {
  return `
    <rect x="40" y="36" width="134" height="40" rx="20" fill="#03110e" stroke="#80d2bc" stroke-opacity="0.24"/>
    <image x="50" y="44" width="24" height="24" href="${escapeXml(brandLogo)}" preserveAspectRatio="xMidYMid meet"/>
    <text x="84" y="62" font-size="18" font-weight="800" fill="#f5fff8">hibench</text>
  `;
}

function buildSvg(agents, runCount, assets) {
  const ranked = [
    ...agents.slice(0, 5),
    ...agents.slice(-5),
  ].filter(
    (agent, index, list) =>
      list.findIndex((candidate) => candidate.agentId === agent.agentId) === index,
  );

  const shownAgentCount = ranked.length;
  const max = Math.max(...ranked.map((agent) => agent.totalTokens), 1);
  const latestCapture = agents.reduce(
    (latest, agent) => (agent.startedAt > latest ? agent.startedAt : latest),
    '',
  );
  const updatedText = latestCapture ? `latest data: ${formatDate(latestCapture)}` : 'latest data';

  const defs = ranked
    .map((agent, index) => {
      const theme = themeFor(agent.agentId);
      return `
        <linearGradient id="bar-${index}" x1="0" x2="0" y1="0" y2="1">
          ${gradientStops(theme.colors)}
        </linearGradient>
        <radialGradient id="glow-${index}" cx="50%" cy="62%" r="55%">
          <stop offset="0%" stop-color="${theme.glow}" stop-opacity="0.46"/>
          <stop offset="100%" stop-color="${theme.glow}" stop-opacity="0"/>
        </radialGradient>
      `;
    })
    .join('');

  const cardX = 40;
  const cardY = 284;
  const baseline = 526;
  const barMaxHeight = 136;
  const barWidth = 86;
  const gap = 25;
  const startX = 72;

  const bars = ranked
    .map((agent, index) => {
      const theme = themeFor(agent.agentId);
      const displayRank = index + 1;
      const x = startX + index * (barWidth + gap);
      const height = Math.max(12, Math.round((agent.totalTokens / max) * barMaxHeight));
      const y = baseline - height;
      const center = x + barWidth / 2;
      const rankX = center;
      const label = truncate(agent.displayName);
      const value = formatNumber(agent.totalTokens);

      return `
        <g>
          <text x="${center}" y="${y - 16}" text-anchor="middle" class="bar-value">${value}</text>
          <ellipse cx="${center}" cy="${baseline + 4}" rx="62" ry="42" fill="url(#glow-${index})" opacity="0.52"/>
          <rect x="${x}" y="${y}" width="${barWidth}" height="${height}" rx="17" fill="url(#bar-${index})"/>
          <rect x="${x + 12}" y="${y + 10}" width="${barWidth - 24}" height="24" rx="12" fill="#ffffff" opacity="0.22"/>
          <rect x="${x}" y="${baseline - Math.min(46, height)}" width="${barWidth}" height="${Math.min(46, height)}" rx="0" fill="#020706" opacity="0.22"/>
          <line x1="${center}" y1="${baseline + 9}" x2="${center}" y2="${baseline + 20}" stroke="#80d2bc" stroke-opacity="0.22"/>
          <circle cx="${rankX}" cy="${baseline + 36}" r="12" fill="${theme.badgeBg}" stroke="${theme.badgeStroke}" stroke-opacity="0.72"/>
          <text x="${rankX}" y="${baseline + 40}" text-anchor="middle" class="rank">${displayRank}</text>
          <text x="${center}" y="${baseline + 66}" text-anchor="middle" class="agent-label" fill="${theme.label}">
            ${escapeXml(label)}
          </text>
        </g>
      `;
    })
    .join('');

  return `
<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#020706"/>
      <stop offset="52%" stop-color="#06130f"/>
      <stop offset="100%" stop-color="#0b151f"/>
    </linearGradient>
    <radialGradient id="top-glow" cx="15%" cy="0%" r="58%">
      <stop offset="0%" stop-color="#31f7c3" stop-opacity="0.26"/>
      <stop offset="100%" stop-color="#31f7c3" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="side-glow" cx="85%" cy="6%" r="48%">
      <stop offset="0%" stop-color="#ffb86b" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="#ffb86b" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="brand" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#31f7c3"/>
      <stop offset="52%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#ffb86b"/>
    </linearGradient>
    ${defs}
    <style>
      .font { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      .title { font: 800 68px/1.02 Inter, ui-sans-serif, system-ui, sans-serif; fill: #f5fff8; letter-spacing: -2.8px; }
      .subtitle { font: 400 22px/1.4 Inter, ui-sans-serif, system-ui, sans-serif; fill: #b8fff0; }
      .eyebrow { font: 700 18px Inter, ui-sans-serif, system-ui, sans-serif; fill: #d8fff4; }
      .muted { font: 500 15px Inter, ui-sans-serif, system-ui, sans-serif; fill: #a9cabd; }
      .bar-value { font: 800 17px Inter, ui-sans-serif, system-ui, sans-serif; fill: #f5fff8; }
      .rank { font: 800 11px Inter, ui-sans-serif, system-ui, sans-serif; fill: #f5fff8; }
      .agent-label { font: 800 15px Inter, ui-sans-serif, system-ui, sans-serif; }
      .small { font: 700 13px Inter, ui-sans-serif, system-ui, sans-serif; fill: #78988d; }
    </style>
  </defs>

  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#bg)"/>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#top-glow)"/>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#side-glow)"/>
  <path d="M0 92H1200M0 184H1200M0 276H1200M0 368H1200M0 460H1200M0 552H1200M120 0V630M240 0V630M360 0V630M480 0V630M600 0V630M720 0V630M840 0V630M960 0V630M1080 0V630" stroke="#31f7c3" stroke-opacity="0.045"/>

  <g class="font">
    ${brandMark(assets.brandLogo)}

    <text x="40" y="134" class="title">Know what your agent</text>
    <text x="40" y="206" class="title">loads before it writes.</text>
    <text x="40" y="252" class="subtitle">
      Default system prompts, tools, skills, MCP and sub-agents before the first reply.
    </text>

    <rect x="${cardX}" y="${cardY}" width="1120" height="306" rx="22" fill="rgba(9, 28, 23, 0.78)" stroke="#80d2bc" stroke-opacity="0.24"/>
    <rect x="${cardX}" y="${cardY}" width="1120" height="306" rx="22" fill="url(#top-glow)" opacity="0.4"/>
    <text x="72" y="330" class="eyebrow">Top 5 + bottom 5 current agent releases</text>
    <text x="72" y="356" class="muted">latest version ranking · total request tokens · ${formatNumber(shownAgentCount)} agents shown</text>
    <text x="1128" y="330" text-anchor="end" class="small">${escapeXml(updatedText)}</text>
    <text x="1128" y="354" text-anchor="end" class="small">${formatNumber(runCount)} version captures</text>

    <line x1="72" y1="${baseline + 10}" x2="1128" y2="${baseline + 10}" stroke="#80d2bc" stroke-opacity="0.2"/>
    ${bars}

    <text x="40" y="617" class="small">coding-agent default footprint benchmark · measured with a fixed o200k_base tokenizer</text>
    <text x="1160" y="617" text-anchor="end" class="small">hibench.dev</text>
  </g>
</svg>
  `;
}

function stackedSegmentRects(parts, { x, y, width, height, clipId }) {
  const total = parts.reduce((sum, part) => sum + part.tokens, 0) || 1;
  let cursor = 0;
  return parts
    .map((part, index) => {
      const start = Math.round((cursor / total) * width);
      cursor += part.tokens;
      const end = index === parts.length - 1
        ? width
        : Math.round((cursor / total) * width);
      const segmentWidth = Math.max(0, end - start);
      if (segmentWidth <= 0) return '';
      return `<rect x="${x + start}" y="${y}" width="${segmentWidth}" height="${height}" fill="${part.color}" clip-path="url(#${clipId})"/>`;
    })
    .join('');
}

function metricBox({ x, y, value, label, accent }) {
  return `
    <g>
      <rect x="${x}" y="${y}" width="160" height="86" rx="18" fill="rgba(3, 17, 14, 0.74)" stroke="${accent}" stroke-opacity="0.32"/>
      <text x="${x + 18}" y="${y + 38}" class="metric-value">${escapeXml(value)}</text>
      <text x="${x + 18}" y="${y + 62}" class="metric-label">${escapeXml(label)}</text>
    </g>
  `;
}

function buildAgentSvg(agent, agentCount, assets) {
  const theme = themeFor(agent.agentId);
  const parts = footprintParts(agent);
  const agentLogo = assets.agentLogos.get(agent.agentId);
  const updatedText = agent.startedAt ? `latest data: ${formatDate(agent.startedAt)}` : 'latest data';
  const totalDelta = agent.totalTokens - agent.minTotal;
  const totalDeltaLabel =
    agent.versionCount > 1 && totalDelta !== 0
      ? `${totalDelta > 0 ? '+' : ''}${formatNumber(totalDelta)} vs min`
      : `${formatNumber(agent.versionCount)} version${agent.versionCount === 1 ? '' : 's'} captured`;
  const name = escapeXml(agent.displayName);
  const agentInitials = escapeXml(initials(agent.displayName));
  const titleSize = agent.displayName.length > 16 ? 57 : 64;

  const stackedSegments = stackedSegmentRects(parts, {
    x: 64,
    y: 486,
    width: 626,
    height: 28,
    clipId: 'composition-clip',
  });

  const legendRows = parts
    .slice(0, 6)
    .map((part, index) => {
      const col = index % 2;
      const row = Math.floor(index / 2);
      const x = 734 + col * 216;
      const y = 464 + row * 42;
      return `
        <g>
          <circle cx="${x}" cy="${y + 10}" r="6" fill="${part.color}"/>
          <text x="${x + 16}" y="${y + 9}" class="legend-label">${escapeXml(part.label)}</text>
          <text x="${x + 16}" y="${y + 29}" class="legend-value">${formatNumber(part.tokens)} tokens</text>
        </g>
      `;
    })
    .join('');

  const agentLogoContent = agentLogo
    ? `<image x="42" y="102" width="124" height="124" href="${escapeXml(agentLogo)}" preserveAspectRatio="xMidYMid meet" filter="url(#logo-shadow)"/>`
    : `<text x="104" y="180" text-anchor="middle" class="badge">${agentInitials}</text>`;

  return `
<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#020706"/>
      <stop offset="52%" stop-color="#06130f"/>
      <stop offset="100%" stop-color="#0b151f"/>
    </linearGradient>
    <radialGradient id="top-glow" cx="20%" cy="4%" r="58%">
      <stop offset="0%" stop-color="${theme.glow}" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="${theme.glow}" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="side-glow" cx="88%" cy="12%" r="48%">
      <stop offset="0%" stop-color="#ffb86b" stop-opacity="0.17"/>
      <stop offset="100%" stop-color="#ffb86b" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="brand" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0%" stop-color="#31f7c3"/>
      <stop offset="52%" stop-color="#38bdf8"/>
      <stop offset="100%" stop-color="#ffb86b"/>
    </linearGradient>
    <clipPath id="composition-clip">
      <rect x="64" y="486" width="626" height="28" rx="14"/>
    </clipPath>
    <filter id="logo-shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#000000" flood-opacity="0.34"/>
    </filter>
    <style>
      .font { font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      .title { font: 850 ${titleSize}px/1 Inter, ui-sans-serif, system-ui, sans-serif; fill: #f5fff8; letter-spacing: -2.5px; }
      .subtitle { font: 500 24px/1.35 Inter, ui-sans-serif, system-ui, sans-serif; fill: #b8fff0; }
      .muted { font: 650 15px Inter, ui-sans-serif, system-ui, sans-serif; fill: #a9cabd; }
      .small { font: 700 13px Inter, ui-sans-serif, system-ui, sans-serif; fill: #78988d; }
      .big-number { font: 900 92px/1 Inter, ui-sans-serif, system-ui, sans-serif; fill: #f5fff8; letter-spacing: -4px; }
      .number-label { font: 800 18px Inter, ui-sans-serif, system-ui, sans-serif; fill: #d8fff4; }
      .metric-value { font: 900 34px Inter, ui-sans-serif, system-ui, sans-serif; fill: #f5fff8; }
      .metric-label { font: 750 14px Inter, ui-sans-serif, system-ui, sans-serif; fill: #a9cabd; text-transform: uppercase; letter-spacing: 0.08em; }
      .legend-label { font: 800 15px Inter, ui-sans-serif, system-ui, sans-serif; fill: #f5fff8; }
      .legend-value { font: 650 13px Inter, ui-sans-serif, system-ui, sans-serif; fill: #a9cabd; }
      .badge { font: 900 42px Inter, ui-sans-serif, system-ui, sans-serif; fill: #020706; letter-spacing: -1px; }
    </style>
  </defs>

  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#bg)"/>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#top-glow)"/>
  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#side-glow)"/>
  <path d="M0 92H1200M0 184H1200M0 276H1200M0 368H1200M0 460H1200M0 552H1200M120 0V630M240 0V630M360 0V630M480 0V630M600 0V630M720 0V630M840 0V630M960 0V630M1080 0V630" stroke="#31f7c3" stroke-opacity="0.045"/>

  <g class="font">
    ${brandMark(assets.brandLogo)}
    <text x="1128" y="52" text-anchor="end" class="small">${escapeXml(updatedText)}</text>

    ${agentLogoContent}

    <text x="196" y="158" class="title">${name}</text>
    <text x="198" y="204" class="muted">rank #${agent.rank} of ${agentCount} current agent releases</text>

    <text x="56" y="350" class="big-number">${formatNumber(agent.totalTokens)}</text>
    <text x="64" y="382" class="number-label">total request tokens before the first reply</text>
    <text x="64" y="410" class="muted">${escapeXml(totalDeltaLabel)} · first captured ${escapeXml(agent.firstVersion)}</text>

    <rect x="720" y="104" width="430" height="262" rx="26" fill="rgba(9, 28, 23, 0.78)" stroke="#80d2bc" stroke-opacity="0.24"/>
    <rect x="720" y="104" width="430" height="262" rx="26" fill="url(#top-glow)" opacity="0.42"/>
    <text x="748" y="144" class="number-label">Latest footprint</text>
    ${metricBox({ x: 748, y: 166, value: formatNumber(agent.toolCount), label: 'tools', accent: theme.label })}
    ${metricBox({ x: 958, y: 166, value: formatNumber(agent.skillCount), label: 'skills', accent: '#10b981' })}
    ${metricBox({ x: 748, y: 268, value: formatNumber(agent.subagentCount), label: 'sub-agents', accent: '#ffb86b' })}
    ${metricBox({ x: 958, y: 268, value: formatNumber(agent.mcpCount), label: 'MCP', accent: '#ff5c8a' })}

    <rect x="40" y="430" width="1120" height="166" rx="24" fill="rgba(9, 28, 23, 0.78)" stroke="#80d2bc" stroke-opacity="0.24"/>
    <text x="64" y="466" class="number-label">Request composition</text>
    <rect x="64" y="486" width="626" height="28" rx="14" fill="rgba(128, 210, 188, 0.13)"/>
    ${stackedSegments}
    <text x="64" y="546" class="muted">stacked from the token detail shown at right</text>
    ${legendRows}

    <text x="40" y="617" class="small">coding-agent default footprint benchmark · measured with a fixed o200k_base tokenizer</text>
    <text x="1160" y="617" text-anchor="end" class="small">hibench.dev/agents/${escapeXml(agent.agentId)}</text>
  </g>
</svg>
  `;
}

function ogAgentsFromSummaries(summaries) {
  return summaries.map((summary, index) => ({
    ...summary.latest,
    agentId: summary.agentId,
    agentName: summary.agentName,
    displayName: summary.agentDisplayName,
    agentLogo: summary.agentLogo,
    firstVersion: summary.firstVersion,
    versionCount: summary.versionCount,
    minTotal: summary.minTotal,
    maxTotal: summary.maxTotal,
    rank: index + 1,
  }));
}

async function main() {
  const agents = ogAgentsFromSummaries(getAgents());
  if (!agents.length) {
    throw new Error('No primary benchmark runs found for OG image generation.');
  }
  const runCount = getGlobalStats().versionCount;
  const assets = await loadImageAssets(agents);
  const svg = buildSvg(agents, runCount, assets);
  await mkdir(dirname(outPath), { recursive: true });
  await writeFile(outPath, await sharp(Buffer.from(svg)).png().toBuffer());
  console.log(`Generated ${outPath}`);

  await rm(agentOutDir, { recursive: true, force: true });
  await mkdir(agentOutDir, { recursive: true });
  await Promise.all(
    agents.map(async (agent) => {
      const agentSvg = buildAgentSvg(agent, agents.length, assets);
      const agentOutPath = resolve(agentOutDir, `${agent.agentId}.png`);
      await writeFile(agentOutPath, await sharp(Buffer.from(agentSvg)).png().toBuffer());
      console.log(`Generated ${agentOutPath}`);
    }),
  );
}

await main();