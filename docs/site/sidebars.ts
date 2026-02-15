import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  apiSidebar: [
    'intro',
    'architecture',
    'edge',
    'vps',
    'data-model',
    {
      type: 'category',
      label: 'API Reference',
      items: [
        'api/ingest',
        'api/realtime',
        'api/series',
        'api/health',
      ],
    },
    'authentication',
    'errors',
    'configuration',
    'deployment',
    'operations',
    'security',
  ],
};

export default sidebars;
