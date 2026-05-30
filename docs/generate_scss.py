import os

base_dir = "C:/UHCR/docs/_sass"
folders = ["tokens", "base", "layout", "components", "themes"]

for folder in folders:
    os.makedirs(os.path.join(base_dir, folder), exist_ok=True)

files = {
    "tokens/_colors.scss": """
// Color Tokens
:root {
  --color-primary: #2563eb;
  --color-primary-dark: #1d4ed8;
  --color-primary-light: #3b82f6;
  --color-success: #059669;
  --color-warning: #d97706;
  --color-danger: #dc2626;
  --color-info: #0284c7;
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  --transition: 200ms ease;
  --radius-sm: 4px;
  --radius-md: 8px;
}
""",
    "tokens/_typography.scss": """
// Typography Tokens
:root {
  --font-family-body: 'Inter', system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-family-code: ui-monospace, SFMono-Regular, Consolas, Monaco, monospace;
}
""",
    "tokens/_spacing.scss": """
// Spacing Tokens
:root {
  --sidebar-width: 280px;
}
""",
    "themes/_light.scss": """
// Light Theme
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f9fafb;
  --bg-tertiary: #f3f4f6;
  --text-primary: #111827;
  --text-secondary: #374151;
  --text-muted: #6b7280;
  --border-color: #e5e7eb;
  --sidebar-bg: #f9fafb;
}
""",
    "themes/_dark.scss": """
// Dark Theme
[data-theme="dark"] {
  --bg-primary: #111827;
  --bg-secondary: #1f2937;
  --bg-tertiary: #374151;
  --text-primary: #f9fafb;
  --text-secondary: #e5e7eb;
  --text-muted: #9ca3af;
  --border-color: #374151;
  --sidebar-bg: #1f2937;
  --color-primary: #3b82f6;
  --color-primary-dark: #2563eb;
  --color-primary-light: #60a5fa;
}
""",
    "base/_reset.scss": """
// Base Reset
*, *::before, *::after {
  box-sizing: border-box;
}
body {
  margin: 0;
  background: var(--bg-primary);
  color: var(--text-primary);
  transition: background var(--transition), color var(--transition);
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
*:focus-visible {
  outline: 2px solid var(--color-primary) !important;
  outline-offset: 2px !important;
  border-radius: 0.25rem !important;
}
::selection {
  background: var(--color-primary);
  color: white;
}
""",
    "base/_typography.scss": """
// Typography Styles
body {
  font-family: var(--font-family-body);
  font-size: 16px;
  line-height: 1.65;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, h4, h5, h6 {
  font-weight: 600;
  line-height: 1.3;
  margin-top: 2em;
  margin-bottom: 0.75em;
  color: var(--text-primary);
  letter-spacing: -0.01em;
}
h1:first-child { margin-top: 0; }
h1 { font-size: 2.25rem; font-weight: 700; margin-bottom: 1em; }
h2 { font-size: 1.75rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5em; margin-top: 2.5em; }
h3 { font-size: 1.375rem; margin-top: 2em; }
h4 { font-size: 1.125rem; }
p {
  margin-bottom: 1.25em;
  line-height: 1.7;
  color: var(--text-secondary);
}
ul, ol {
  margin: 1.25em 0;
  padding-left: 1.75em;
  li {
    margin-bottom: 0.625em;
    line-height: 1.7;
    color: var(--text-secondary);
  }
}
strong {
  font-weight: 600;
  color: var(--text-primary);
}
""",
    "layout/_sidebar.scss": """
// Sidebar Layout
.side-bar {
  width: var(--sidebar-width) !important;
  background: var(--sidebar-bg) !important;
  border-right: 1px solid var(--border-color) !important;
  height: 100vh !important;
  position: fixed !important;
  top: 0 !important;
  left: 0 !important;
  overflow-y: auto !important;
  overflow-x: hidden !important;
  padding: 0 !important;
  
  &::-webkit-scrollbar { width: 8px; }
  &::-webkit-scrollbar-track { background: transparent; }
  &::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 4px;
    &:hover { background: var(--text-muted); }
  }
}
.site-title {
  color: var(--color-primary) !important;
  font-weight: 700 !important;
  font-size: 1.25rem !important;
  &:hover { color: var(--color-primary-dark) !important; }
}
.site-header {
  background: var(--sidebar-bg) !important;
  border-bottom: 1px solid var(--border-color) !important;
  padding: 1.5rem 1rem !important;
  margin: 0 !important;
  min-height: auto !important;
}
.site-nav {
  padding: 1rem 0 !important;
  background: transparent !important;
}
.nav-list {
  padding: 0 !important;
  .nav-list-item {
    margin: 0 !important;
    .nav-list-link {
      padding: 0.5rem 1rem !important;
      color: var(--text-secondary) !important;
      font-size: 0.9375rem !important;
      border-left: 3px solid transparent !important;
      transition: all var(--transition) !important;
      &:hover {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
      }
      &.active {
        background: var(--bg-tertiary) !important;
        color: var(--color-primary) !important;
        border-left-color: var(--color-primary) !important;
        font-weight: 600 !important;
      }
    }
  }
}
@media (max-width: 768px) {
  .side-bar {
    width: 100% !important;
    position: relative !important;
    height: auto !important;
  }
}
""",
    "layout/_header.scss": """
// Header Layout
.main-header {
  background: var(--bg-primary) !important;
  border-bottom: 1px solid var(--border-color) !important;
  padding: 1rem 2rem !important;
  display: flex !important;
  align-items: center !important;
  gap: 1rem !important;
  min-height: auto !important;
}
.search {
  flex: 1 !important;
  max-width: 500px !important;
  .search-input {
    width: 100% !important;
    padding: 0.5rem 1rem !important;
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-color) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-size: 0.9375rem !important;
    &:focus {
      outline: none !important;
      border-color: var(--color-primary) !important;
      box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1) !important;
    }
  }
}
.aux-nav {
  display: flex !important;
  gap: 0.5rem !important;
  .site-button {
    background: var(--color-primary) !important;
    color: white !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.5rem 1rem !important;
    font-size: 0.875rem !important;
    font-weight: 500 !important;
    transition: all var(--transition) !important;
    &:hover {
      background: var(--color-primary-dark) !important;
      transform: translateY(-1px) !important;
    }
  }
}
""",
    "layout/_main.scss": """
// Main Content Layout
.main {
  margin-left: var(--sidebar-width) !important;
  background: var(--bg-primary) !important;
  min-height: 100vh !important;
}
#main-content-wrap {
  background: var(--bg-primary) !important;
  padding: 0 !important;
}
.main-content {
  padding: 2.5rem 3rem !important;
  max-width: 900px !important;
  margin: 0 auto !important;
  @media (max-width: 768px) {
    padding: 1.5rem 1rem !important;
  }
}
@media (max-width: 768px) {
  .main {
    margin-left: 0 !important;
  }
}
.site-footer {
  background: var(--bg-secondary) !important;
  border-top: 1px solid var(--border-color) !important;
  padding: 2rem !important;
  text-align: center !important;
  color: var(--text-muted) !important;
  font-size: 0.875rem !important;
  margin-top: 4rem !important;
  a {
    color: var(--color-primary) !important;
    &:hover { text-decoration: underline !important; }
  }
}
""",
    "components/_links.scss": """
// Links & Anchors
a {
  color: var(--color-primary);
  text-decoration: none;
  transition: color var(--transition);
  text-decoration-thickness: 1px;
  text-underline-offset: 2px;
  &:hover {
    color: var(--color-primary-dark);
    text-decoration: underline;
  }
}
.anchor-heading {
  display: none !important;
}
h1, h2, h3, h4, h5, h6 {
  position: relative;
  &:hover::before {
    content: '🔗';
    position: absolute;
    left: -1.5em;
    font-size: 0.8em;
    opacity: 0.5;
    cursor: pointer;
    transition: opacity var(--transition);
  }
  &:hover::before:hover {
    opacity: 1;
  }
}
""",
    "components/_code.scss": """
// Code Blocks
code {
  font-family: var(--font-family-code);
  font-size: 0.875em;
  font-variant-ligatures: none;
}
:not(pre) > code {
  background: var(--bg-tertiary);
  color: var(--color-primary);
  padding: 0.2em 0.4em;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  font-weight: 500;
}
.highlight, pre {
  background: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
  border-radius: var(--radius-md) !important;
  margin: 1.5em 0 !important;
  overflow-x: auto !important;
  box-shadow: var(--shadow-sm) !important;
  position: relative !important;
  pre {
    margin: 0 !important;
    padding: 1.25rem !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
  }
  code {
    color: var(--text-primary) !important;
  }
}
.copy-button {
  position: absolute;
  top: 0.75rem;
  right: 0.75rem;
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.875rem;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 0.8em;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
  z-index: 10;
  box-shadow: var(--shadow-sm);
  &:hover {
    background: var(--color-primary-dark);
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
  }
  &.copied { background: var(--color-success); }
}
""",
    "components/_tables.scss": """
// Tables
table {
  width: 100%;
  margin: 1.5em 0;
  border-collapse: collapse;
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-md);
  font-size: 0.95em;
  thead {
    background: var(--color-primary);
    th {
      padding: 0.875em 1em;
      text-align: left;
      font-weight: 600;
      color: white;
    }
  }
  tbody {
    background: var(--bg-secondary);
    tr {
      border-bottom: 1px solid var(--border-color);
      transition: background var(--transition);
      &:hover { background: var(--bg-tertiary); }
      &:last-child { border-bottom: none; }
    }
    td {
      padding: 0.875em 1em;
      color: var(--text-primary);
    }
  }
}
""",
    "components/_buttons.scss": """
// Buttons and Controls
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.625em 1.25em;
  font-size: 0.95em;
  font-weight: 500;
  border-radius: var(--radius-md);
  border: 1px solid transparent;
  cursor: pointer;
  transition: all var(--transition);
  text-decoration: none;
  box-shadow: var(--shadow-sm);
  &:hover {
    transform: translateY(-1px);
    box-shadow: var(--shadow-md);
    text-decoration: none;
  }
  &.btn-primary {
    background: var(--color-primary);
    color: white;
    &:hover { background: var(--color-primary-dark); }
  }
}
.theme-toggle {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  width: 3rem;
  height: 3rem;
  border-radius: 50%;
  background: var(--color-primary);
  border: none;
  color: white;
  font-size: 1.25rem;
  cursor: pointer;
  box-shadow: var(--shadow-lg);
  transition: all var(--transition);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  &:hover { transform: scale(1.1); }
  &:active { transform: scale(0.95); }
  @media (max-width: 768px) {
    bottom: 1rem !important;
    right: 1rem !important;
    width: 2.75rem !important;
    height: 2.75rem !important;
    font-size: 1.1rem !important;
  }
}
""",
    "custom.scss": """
// ============================================================================
// UHCR Documentation - Professional & Accessible Design
// Architecture: Tokens, Themes, Base, Layout, Components
// ============================================================================

// 1. Tokens
@import "tokens/colors";
@import "tokens/typography";
@import "tokens/spacing";

// 2. Themes
@import "themes/light";
@import "themes/dark";

// 3. Base
@import "base/reset";
@import "base/typography";

// 4. Layout
@import "layout/sidebar";
@import "layout/header";
@import "layout/main";

// 5. Components
@import "components/links";
@import "components/code";
@import "components/tables";
@import "components/buttons";
"""
}

for filepath, content in files.items():
    with open(os.path.join(base_dir, filepath), 'w', encoding='utf-8') as f:
        f.write(content.strip() + "\\n")

print("Generated SCSS architecture successfully.")
