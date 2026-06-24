export type SiteLink = {
  href: string;
  label: string;
  external?: boolean;
};

export const primaryNavLinks: SiteLink[] = [
  { href: '/rankings', label: 'Rankings' },
  { href: '/agents', label: 'Agents' },
  { href: '/methodology', label: 'Methodology' },
];

export const footerLinks: SiteLink[] = [
  ...primaryNavLinks,
  { href: '/compare', label: 'Compare' },
  { href: '/updates', label: 'Updates' },
];