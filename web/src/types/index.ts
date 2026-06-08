// Type definitions for the documentation site

export interface NavItem {
  id: string;
  label: string;
  path: string;
  children?: NavItem[];
}

export interface Heading {
  id: string;
  text: string;
  level: number;
}

export interface SearchResult {
  title: string;
  path: string;
  snippet: string;
  headingId?: string;
}

export interface DocRoute {
  path: string;
  markdownFile: string;
  title: string;
}

export type Theme = 'light' | 'dark';
