import { useEffect, useMemo, useState } from 'react';

export interface VersionPart {
  label: string;
  tokens: number;
  color: string;
}

export interface VersionTool {
  name: string;
  tokens: number;
  isMcp: boolean;
  isSubagent: boolean;
}

export interface VersionSkill {
  name: string;
  tokens: number;
  description: string;
}

export interface VersionSubagent {
  name: string;
  tokens: number;
  preview: string;
  sourceType: string;
}

export interface VersionDatum {
  version: string;
  model: string;
  totalTokens: number;
  bodyBytes: number;
  toolCount: number;
  skillCount: number;
  mcpCount: number;
  subagentCount: number;
  parts: VersionPart[];
  tools: VersionTool[];
  skills: VersionSkill[];
  subagents: VersionSubagent[];
}

const fmt = new Intl.NumberFormat('en-US');

export default function VersionExplorer({ versions }: { versions: VersionDatum[] }) {
  const [idx, setIdx] = useState(versions.length - 1);
  const hasVersions = versions.length > 0;
  const safeIdx = hasVersions ? Math.min(Math.max(idx, 0), versions.length - 1) : 0;
  const v = versions[safeIdx];

  useEffect(() => {
    if (idx !== safeIdx) setIdx(safeIdx);
  }, [idx, safeIdx]);

  const maxPart = useMemo(() => Math.max(...(v?.parts ?? []).map((p) => p.tokens), 1), [v]);

  if (!v) {
    return (
      <div className="ui-card rounded-xl p-5">
        <p className="text-sm ui-subtle">No benchmark versions available.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-sm font-medium ui-muted" htmlFor="version-select">
          Version
        </label>
        <select
          id="version-select"
          className="ui-input rounded-lg px-3 py-1.5 text-sm"
          value={safeIdx}
          onChange={(e) => setIdx(Number((e.target as HTMLSelectElement).value))}
        >
          {versions.map((d, i) => (
            <option key={d.version} value={i}>
              v{d.version} — {fmt.format(d.totalTokens)} tokens
            </option>
          ))}
        </select>
        <span className="text-xs ui-subtle">{versions.length} versions captured</span>
      </div>

      <div className="grid gap-3 sm:grid-cols-4">
        <Metric label="Total tokens" value={fmt.format(v.totalTokens)} />
        <Metric label="Tools" value={String(v.toolCount)} />
        <Metric label="Skills" value={String(v.skillCount)} />
        <Metric label="Body size" value={`${(v.bodyBytes / 1024).toFixed(0)} KB`} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="ui-card rounded-xl p-4 sm:p-5">
          <h3 className="mb-4 text-sm font-semibold ui-title">
            Footprint composition · v{v.version}
          </h3>
          <div className="space-y-3">
            {v.parts.map((p) => (
              <div key={p.label}>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="flex items-center gap-2 ui-muted">
                    <span className="h-2.5 w-2.5 rounded-sm" style={{ background: p.color }} />
                    {p.label}
                  </span>
                  <span className="tabular-nums font-medium">{fmt.format(p.tokens)}</span>
                </div>
                <div className="ui-track h-2 w-full overflow-hidden rounded-full">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${(p.tokens / maxPart) * 100}%`, background: p.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <TokenListCard
          title={`Tools by token · ${v.tools.length}`}
          emptyText="No tool definitions captured for this version."
          accent="linear-gradient(90deg, var(--color-primary), var(--color-secondary))"
          items={v.tools.map((t) => ({
            name: t.name,
            tokens: t.tokens,
            badges: [
              ...(t.isSubagent ? [{ label: 'sub', className: 'text-amber-600' }] : []),
              ...(t.isMcp ? [{ label: 'mcp', className: 'text-pink-600' }] : []),
            ],
          }))}
        />

        <TokenListCard
          title={`Sub-agents by token · ${v.subagents.length}`}
          emptyText="No sub-agent declarations captured for this version."
          accent="linear-gradient(90deg, #f59e0b, var(--color-primary))"
          items={v.subagents.map((s) => ({
            name: s.name,
            tokens: s.tokens,
            title: s.preview || s.sourceType || s.name,
          }))}
        />
        <TokenListCard
          title={`Skills by token · ${v.skills.length}`}
          emptyText="No skill entries captured for this version."
          accent="linear-gradient(90deg, #10b981, var(--color-secondary))"
          items={v.skills.map((s) => ({
            name: s.name,
            tokens: s.tokens,
            title: s.description || s.name,
          }))}
        />
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="ui-card rounded-xl p-4">
      <p className="text-xs font-medium ui-muted">{label}</p>
      <p className="mt-0.5 text-2xl font-semibold tabular-nums ui-title">{value}</p>
    </div>
  );
}

interface TokenBadge {
  label: string;
  className: string;
}

interface TokenListItem {
  name: string;
  tokens: number;
  title?: string;
  badges?: TokenBadge[];
}

function TokenListCard({
  title,
  items,
  emptyText,
  accent,
}: {
  title: string;
  items: TokenListItem[];
  emptyText: string;
  accent: string;
}) {
  const maxTokens = Math.max(...items.map((item) => item.tokens), 1);

  return (
    <div className="ui-card rounded-xl p-4 sm:p-5">
      <h3 className="mb-4 text-sm font-semibold ui-title">{title}</h3>
      <div className="max-h-72 space-y-2 overflow-y-auto pr-5 [scrollbar-gutter:stable]">
        {items.map((item, index) => (
          <div key={`${item.name}-${index}`} className="flex min-w-0 items-center gap-3 text-sm">
            <span className="flex w-36 shrink-0 items-center gap-1 truncate ui-muted" title={item.title ?? item.name}>
              <span className="truncate">{item.name}</span>
              {item.badges?.map((badge) => (
                <span key={badge.label} className={`shrink-0 text-[10px] ${badge.className}`}>
                  {badge.label}
                </span>
              ))}
            </span>
            <div className="ui-track h-2 min-w-0 flex-1 overflow-hidden rounded-full">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${(item.tokens / maxTokens) * 100}%`,
                  background: accent,
                }}
              />
            </div>
            <span className="w-16 shrink-0 text-right tabular-nums ui-subtle">{fmt.format(item.tokens)}</span>
          </div>
        ))}
        {items.length === 0 && <p className="text-sm ui-subtle">{emptyText}</p>}
      </div>
    </div>
  );
}
