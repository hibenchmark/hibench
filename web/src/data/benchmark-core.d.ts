export interface RunRow {
  runId: string;
  agentId: string;
  agentName: string;
  version: string;
  model: string;
  hasPrimary: boolean;
  startedAt: string;
  bodyBytes: number;
  totalTokens: number;
  anthropicTotalTokens: number;
  anthropicTokenizerModel: string;
  systemPromptTokens: number;
  toolTokens: number;
  skillTokens: number;
  mcpTokens: number;
  subagentTokens: number;
  userPromptTokens: number;
  envContextTokens: number;
  defaultContextTokens: number;
  toolCount: number;
  skillCount: number;
  mcpCount: number;
  subagentCount: number;
}

export interface AgentSummary {
  agentId: string;
  agentName: string;
  agentDisplayName: string;
  agentLogo: AgentLogo;
  agentLinks: AgentLinks;
  latest: RunRow;
  firstVersion: string;
  versionCount: number;
  minTotal: number;
  maxTotal: number;
  minAnthropicTotal: number;
  maxAnthropicTotal: number;
}

export interface AgentLogo {
  path: string;
  alt: string;
  source: 'official' | 'generic';
}

export interface AgentLinks {
  officialUrl?: string;
  githubRepo?: string;
  githubUrl?: string;
  githubStars?: number;
  githubStarsUpdatedAt?: string;
}

export interface ToolRow {
  name: string;
  type: string;
  tokens: number;
  isMcp: boolean;
  isSubagent: boolean;
}

export interface SkillRow {
  name: string;
  tokens: number;
  description: string;
}

export interface SubagentRow {
  name: string;
  tokens: number;
  preview: string;
  sourceType: string;
}

export interface FootprintPart {
  key: string;
  label: string;
  tokens: number;
  color: string;
}

export interface GlobalStats {
  agentCount: number;
  versionCount: number;
  minTotal: number;
  maxTotal: number;
}

export const AGENT_DISPLAY_NAMES: Record<string, string>;
export const GENERIC_AGENT_LOGO: string;
export const AGENT_LOGOS: Record<string, AgentLogo>;
export const AGENT_LINKS: Record<string, AgentLinks>;

export function compareVersions(a: string, b: string): number;
export function getPrimaryRuns(): RunRow[];
export function getAgentVersions(agentId: string): RunRow[];
export function getAgents(): AgentSummary[];
export function getAgentIds(): string[];
export function getToolsForRun(runId: string): ToolRow[];
export function getSkillsForRun(runId: string): SkillRow[];
export function getSubagentsForRun(runId: string): SubagentRow[];
export function footprintParts(run: RunRow): FootprintPart[];
export function getGlobalStats(): GlobalStats;