export type SiteLink = {
  href: string;
  label: string;
  external?: boolean;
};

export const primaryNavLinks: SiteLink[] = [
  { href: '/rankings', label: 'Rankings' },
  { href: '/agents', label: 'Agents' },
  { href: '/compare', label: 'Compare' },
  { href: '/updates', label: 'Updates' },
  { href: '/methodology', label: 'Methodology' },
  { href: '/data', label: 'Data' },
];

export const footerLinks: SiteLink[] = [
  { href: '/rankings', label: 'Rankings' },
  { href: '/agents', label: 'Agents' },
  { href: '/compare', label: 'Compare' },
  { href: '/updates', label: 'Updates' },
  { href: '/methodology', label: 'Methodology' },
  { href: '/data', label: 'Data' },
];