// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

import tailwindcss from '@tailwindcss/vite';

const site = process.env.SITE_URL || 'https://hibench.dev';
const base = process.env.BASE_PATH || undefined;

// https://astro.build/config
export default defineConfig({
  site,
  base,
  integrations: [
    sitemap({
      filter: (page) => !page.includes('/_astro/'),
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
