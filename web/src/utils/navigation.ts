import type { NavItem, DocRoute } from '../types';

// Route-to-markdown mapping
export const docRoutes: DocRoute[] = [
  { path: '/docs/quickstart', markdownFile: '/docs/quickstart.md', title: 'Quick Start' },
  { path: '/docs/jit-guide', markdownFile: '/docs/jit-guide.md', title: 'JIT Guide' },
  { path: '/docs/plugin-guide', markdownFile: '/docs/plugin-guide.md', title: 'Plugin Guide' },
  { path: '/docs/architecture', markdownFile: '/docs/architecture.md', title: 'Architecture' },
  { path: '/docs/api-reference', markdownFile: '/docs/api-reference.md', title: 'API Reference' },
  { path: '/docs/hardware-reference', markdownFile: '/docs/hardware-reference.md', title: 'Hardware Reference' },
  { path: '/docs/features', markdownFile: '/docs/features.md', title: 'Features' },
  { path: '/docs/benchmarks', markdownFile: '/docs/benchmarks.md', title: 'Benchmarks' },
  { path: '/docs/cli', markdownFile: '/docs/cli.md', title: 'CLI' },
  { path: '/docs/contributing', markdownFile: '/docs/contributing.md', title: 'Contributing' },
  { path: '/docs/guides', markdownFile: '/docs/guides.md', title: 'Guides' },
  { path: '/docs/how-uhcr-works', markdownFile: '/docs/how-uhcr-works.md', title: 'How UHCR Works' },
  { path: '/docs/multi-isa', markdownFile: '/docs/multi-isa.md', title: 'Multi-ISA Support' },
  { path: '/docs/network', markdownFile: '/docs/network.md', title: 'Network' },
  { path: '/docs/plugins', markdownFile: '/docs/plugins.md', title: 'Plugins' },
  { path: '/docs/reference', markdownFile: '/docs/reference.md', title: 'Reference' },
  { path: '/docs/runtime', markdownFile: '/docs/runtime.md', title: 'Runtime' },
  { path: '/docs/storage', markdownFile: '/docs/storage.md', title: 'Storage' },
];

// Navigation structure
export const navigation: NavItem[] = [
  {
    id: 'getting-started',
    label: 'Getting Started',
    path: '/docs/quickstart',
    children: [
      { id: 'quickstart', label: 'Quick Start', path: '/docs/quickstart' },
      { id: 'how-it-works', label: 'How UHCR Works', path: '/docs/how-uhcr-works' },
    ],
  },
  {
    id: 'guides',
    label: 'Guides',
    path: '/docs/guides',
    children: [
      { id: 'jit-guide', label: 'JIT Compilation', path: '/docs/jit-guide' },
      { id: 'plugin-guide', label: 'Plugin Development', path: '/docs/plugin-guide' },
      { id: 'multi-isa', label: 'Multi-ISA Support', path: '/docs/multi-isa' },
    ],
  },
  {
    id: 'reference',
    label: 'Reference',
    path: '/docs/reference',
    children: [
      { id: 'api-reference', label: 'API Reference', path: '/docs/api-reference' },
      { id: 'cli', label: 'CLI', path: '/docs/cli' },
      { id: 'hardware-reference', label: 'Hardware Reference', path: '/docs/hardware-reference' },
    ],
  },
  {
    id: 'architecture',
    label: 'Architecture',
    path: '/docs/architecture',
    children: [
      { id: 'architecture-overview', label: 'Overview', path: '/docs/architecture' },
      { id: 'runtime', label: 'Runtime', path: '/docs/runtime' },
      { id: 'storage', label: 'Storage', path: '/docs/storage' },
      { id: 'network', label: 'Network', path: '/docs/network' },
    ],
  },
  {
    id: 'features',
    label: 'Features',
    path: '/docs/features',
  },
  {
    id: 'plugins',
    label: 'Plugins',
    path: '/docs/plugins',
  },
  {
    id: 'benchmarks',
    label: 'Benchmarks',
    path: '/docs/benchmarks',
  },
  {
    id: 'contributing',
    label: 'Contributing',
    path: '/docs/contributing',
  },
];

// Helper function to get markdown file for a path
export function getMarkdownFile(path: string): string | undefined {
  const route = docRoutes.find((r) => r.path === path);
  return route?.markdownFile;
}

// Helper function to get page title for a path
export function getPageTitle(path: string): string {
  const route = docRoutes.find((r) => r.path === path);
  return route?.title || 'UHCR Documentation';
}
