/** Shared formatting + base-path helpers (usable on server and client). */

const BASE = import.meta.env.BASE_URL || '/';

/** Prefix an internal path with the configured site base. */
export function withBase(path: string): string {
  const left = BASE.endsWith('/') ? BASE.slice(0, -1) : BASE;
  const right = path.startsWith('/') ? path : `/${path}`;
  return `${left}${right}` || '/';
}

const NUM = new Intl.NumberFormat('en-US');
const USD_PRECISE = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 4,
  maximumFractionDigits: 4,
});

export function formatNumber(n: number): string {
  return NUM.format(Math.round(n));
}

export function formatInputCost(tokens: number): string {
  return USD_PRECISE.format((tokens * 5) / 1_000_000);
}

/** Compact token formatting, e.g. 21414 -> "21.4k". */
export function formatCompact(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function pct(part: number, whole: number): number {
  if (whole <= 0) return 0;
  return (part / whole) * 100;
}
