import { useMemo, useState } from 'react';

export interface RankRow {
  agentId: string;
  agentName: string;
  version: string;
  model: string;
  totalTokens: number;
  toolCount: number;
  skillCount: number;
  mcpCount: number;
  subagentCount: number;
  logoSrc: string;
  logoAlt: string;
  logoSource: 'official' | 'generic';
  href: string;
}

type SortKey = 'totalTokens' | 'toolCount' | 'skillCount' | 'agentName' | 'model' | 'version';

const fmt = new Intl.NumberFormat('en-US');

const COLUMNS: { key: SortKey; label: string; numeric: boolean }[] = [
  { key: 'agentName', label: 'Agent', numeric: false },
  { key: 'totalTokens', label: 'Token', numeric: true },
  { key: 'toolCount', label: 'Tools', numeric: true },
  { key: 'skillCount', label: 'Skills', numeric: true },
  { key: 'model', label: 'Model', numeric: false },
  { key: 'version', label: 'Version', numeric: false },
];

export default function RankingsTable({ rows }: { rows: RankRow[] }) {
  const [sortKey, setSortKey] = useState<SortKey>('totalTokens');
  const [asc, setAsc] = useState(false);

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      let cmp: number;
      if (sortKey === 'agentName') cmp = a.agentName.localeCompare(b.agentName);
      else if (sortKey === 'model') cmp = a.model.localeCompare(b.model);
      else if (sortKey === 'version') cmp = a.version.localeCompare(b.version);
      else cmp = (a[sortKey] as number) - (b[sortKey] as number);
      return asc ? cmp : -cmp;
    });
    return copy;
  }, [rows, sortKey, asc]);

  const max = Math.max(...rows.map((r) => r.totalTokens), 1);

  function onSort(key: SortKey) {
    if (key === sortKey) setAsc((v) => !v);
    else {
      setSortKey(key);
      setAsc(key === 'agentName' || key === 'model' || key === 'version');
    }
  }

  return (
    <div className="ui-card overflow-hidden rounded-xl">
      <div
        className="ui-table-scroll"
        role="region"
        aria-label="Default footprint ranking table"
        tabIndex={0}
      >
        <table className="w-full text-sm">
          <thead className="ui-table-head text-left">
            <tr>
              <th className="px-2 py-3 font-medium sm:px-4">#</th>
              {COLUMNS.map((c) => {
                const hide = c.key === 'model' || c.key === 'version' ? ' hidden lg:table-cell' : '';
                return (
                  <th key={c.key} className={`px-2 py-3 font-medium sm:px-4 ${c.numeric ? 'text-right' : ''}${hide}`}>
                    <button
                      type="button"
                      onClick={() => onSort(c.key)}
                      className="inline-flex items-center gap-1 hover:text-[var(--color-primary)]"
                    >
                      {c.label}
                      <span className="text-xs">{sortKey === c.key ? (asc ? '▲' : '▼') : '↕'}</span>
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--color-line)]">
            {sorted.map((r, i) => (
              <tr key={r.agentId} className="ui-table-row">
                <td className="px-2 py-3 tabular-nums ui-subtle sm:px-4">{i + 1}</td>
                <td className="max-w-[7rem] px-2 py-3 sm:max-w-none sm:px-4">
                  <div className="flex items-center gap-2 sm:gap-3">
                    <span
                      className={`agent-logo ${
                        r.logoSource === 'official' ? 'agent-logo-official' : 'agent-logo-generic'
                      } grid h-6 w-6 shrink-0 place-items-center overflow-hidden rounded-md p-1 sm:h-8 sm:w-8 sm:rounded-lg sm:p-1.5`}
                      title={r.logoAlt}
                    >
                      <img src={r.logoSrc} alt="" loading="lazy" decoding="async" className="h-full w-full object-contain" />
                    </span>
                    <div className="min-w-0">
                      <a href={r.href} className="block truncate font-medium ui-link">
                        {r.agentName}
                      </a>
                    </div>
                  </div>
                </td>
                <td className="px-2 py-3 text-right sm:px-4">
                  <div className="flex items-center justify-end gap-3">
                    <div className="ui-track hidden h-2 w-28 overflow-hidden rounded-full sm:block">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(r.totalTokens / max) * 100}%`,
                          background: 'linear-gradient(90deg, var(--color-primary), var(--color-secondary))',
                        }}
                      />
                    </div>
                    <span className="tabular-nums font-semibold ui-title">
                      {fmt.format(r.totalTokens)}
                    </span>
                  </div>
                </td>
                <td className="px-2 py-3 text-right tabular-nums sm:px-4">{r.toolCount}</td>
                <td className="px-2 py-3 text-right tabular-nums sm:px-4">{r.skillCount}</td>
                <td className="hidden px-2 py-3 ui-muted sm:px-4 lg:table-cell">{r.model}</td>
                <td className="hidden px-2 py-3 whitespace-nowrap sm:px-4 lg:table-cell">
                  <span className="ui-badge rounded px-1.5 py-0.5 text-xs">
                    v{r.version}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
