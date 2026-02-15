import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

const config: Config = {
  title: 'Sungrow-to-VPS API',
  tagline: 'Solar telemetry API documentation',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  markdown: {
    mermaid: true,
  },
  themes: ['@docusaurus/theme-mermaid'],

  url: 'https://your-domain.example.com',
  baseUrl: '/',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          routeBasePath: 'docs',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Sungrow-to-VPS API',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'apiSidebar',
          position: 'left',
          label: 'Documentation',
        },
        {
          href: 'pathname:///openapi.json',
          label: 'OpenAPI Spec',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Documentation',
          items: [
            {
              label: 'Introduction',
              to: '/docs/intro',
            },
            {
              label: 'Authentication',
              to: '/docs/authentication',
            },
            {
              label: 'Error Reference',
              to: '/docs/errors',
            },
          ],
        },
        {
          title: 'API Reference',
          items: [
            {
              label: 'POST /v1/ingest',
              to: '/docs/api/ingest',
            },
            {
              label: 'GET /v1/realtime',
              to: '/docs/api/realtime',
            },
            {
              label: 'GET /v1/series',
              to: '/docs/api/series',
            },
            {
              label: 'GET /health',
              to: '/docs/api/health',
            },
          ],
        },
      ],
      copyright: `Copyright ${new Date().getFullYear()} Sungrow-to-VPS. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
