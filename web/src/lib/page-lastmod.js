import {
  getAgentVersions,
  getLatestBenchmarkDate,
  getRecentAgentUpdates,
} from '../data/benchmark-core.js';
import { METHODOLOGY_REVISION_DATE } from './methodology-date.mjs';

const COMPARE_SLUG_MARKER = '-vs-';

function normalizePathname(pathname) {
  let path = pathname || '/';
  const base = process.env.BASE_PATH || '';
  if (base && base !== '/') {
    const prefix = base.endsWith('/') ? base.slice(0, -1) : base;
    if (path === prefix) path = '/';
    else if (path.startsWith(`${prefix}/`)) path = path.slice(prefix.length) || '/';
  }
  if (!path.startsWith('/')) path = `/${path}`;
  if (path.length > 1 && path.endsWith('/')) path = path.slice(0, -1);
  return path;
}

function parseCompareSlug(slug) {
  const index = slug.indexOf(COMPARE_SLUG_MARKER);
  if (index <= 0 || index === slug.length - COMPARE_SLUG_MARKER.length) return null;
  const agentA = slug.slice(0, index);
  const agentB = slug.slice(index + COMPARE_SLUG_MARKER.length);
  if (!agentA || !agentB || agentA >= agentB) return null;
  return { agentA, agentB };
}

function getAgentLatestBenchmarkDate(agentId) {
  const versions = getAgentVersions(agentId);
  return versions.length ? versions[versions.length - 1].startedAt : '';
}

function maxIsoDate(...dates) {
  return dates.reduce((latest, value) => {
    if (!value) return latest;
    if (!latest || value > latest) return value;
    return latest;
  }, '');
}

/** Resolve sitemap/content lastmod for a site path or absolute URL. */
export function getPageLastModified(urlPathOrUrl) {
  const raw =
    urlPathOrUrl.includes('://') ? new URL(urlPathOrUrl).pathname : urlPathOrUrl;
  const path = normalizePathname(raw);

  if (path === '/' || path === '/rankings' || path === '/agents') {
    return getLatestBenchmarkDate();
  }

  if (path === '/updates') {
    const updates = getRecentAgentUpdates();
    return updates[0]?.startedAt || getLatestBenchmarkDate();
  }

  if (path === '/methodology') {
    return `${METHODOLOGY_REVISION_DATE}T00:00:00.000Z`;
  }

  if (path === '/data') {
    return getLatestBenchmarkDate();
  }

  if (path === '/compare') {
    return getLatestBenchmarkDate();
  }

  const agentMatch = path.match(/^\/agents\/([^/]+)$/);
  if (agentMatch) {
    return getAgentLatestBenchmarkDate(agentMatch[1]);
  }

  const compareMatch = path.match(/^\/compare\/([^/]+)$/);
  if (compareMatch) {
    const parsed = parseCompareSlug(compareMatch[1]);
    if (!parsed) return getLatestBenchmarkDate();
    return maxIsoDate(
      getAgentLatestBenchmarkDate(parsed.agentA),
      getAgentLatestBenchmarkDate(parsed.agentB),
    );
  }

  return '';
}