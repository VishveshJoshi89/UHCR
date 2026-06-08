# UHCR Documentation

This directory contains the Jekyll-based documentation website for UHCR.

## 🌐 Live Site

Visit the documentation at: [https://vishveshjoshi89.github.io/UHCR/](https://vishveshjoshi89.github.io/UHCR/)

## 🎨 Features

- **Modern Dark Theme** with gradient accents
- **Responsive Design** optimized for all devices
- **Interactive Elements** including copy buttons, smooth scrolling, and animations
- **Search Functionality** powered by Just the Docs
- **Syntax Highlighting** with custom styling
- **Animated Backgrounds** and particle effects
- **Scroll Progress Indicator**
- **Custom 404 Page** with helpful navigation

## 📁 Structure

```
docs/
├── _config.yml              # Jekyll configuration
├── _layouts/
│   └── default.html         # Custom layout with CSS/JS includes
├── assets/
│   ├── css/
│   │   └── custom.scss      # Custom styling
│   └── js/
│       ├── custom.js        # Interactive features
│       └── animations.js    # Advanced animations
├── index.md                 # Homepage
├── quickstart.md            # Quick start guide
├── features.md              # Features showcase
├── jit-guide.md             # JIT compilation guide
├── plugin-guide.md          # Plugin development guide
├── contributing.md          # Contribution guidelines
├── architecture.md          # System architecture
├── api-reference.md         # API documentation
├── optimization-passes.md   # Optimization details
├── storage.md               # Storage subsystem
├── hardware-reference.md    # Hardware detection
└── 404.html                 # Custom 404 page
```

## 🚀 Local Development

### Prerequisites

- Ruby 2.7 or higher
- Bundler

### Setup

1. Install dependencies:
```bash
cd docs
bundle install
```

2. Run the development server:
```bash
bundle exec jekyll serve
```

3. Open your browser to `http://localhost:4000/UHCR/`

### Live Reload

Jekyll automatically rebuilds the site when you make changes. Just refresh your browser to see updates.

## 🎨 Customization

### Colors

Edit `docs/assets/css/custom.scss` to change the color scheme:

```scss
:root {
  --primary-color: #6366f1;
  --primary-dark: #4f46e5;
  --primary-light: #818cf8;
  // ... more colors
}
```

### Animations

Modify `docs/assets/js/animations.js` to adjust or disable animations:

```javascript
// Disable particle effects
// initParticles();

// Adjust typing speed
const typingSpeed = 20; // milliseconds per character
```

### Navigation

Update `_config.yml` to modify navigation structure:

```yaml
nav_enabled: true
nav_sort: case_insensitive
```

## 📝 Adding New Pages

1. Create a new Markdown file in `docs/`:
```markdown
---
layout: default
title: My New Page
nav_order: 11
---

# My New Page

Content goes here...
```

2. The page will automatically appear in the navigation.

## 🔧 Configuration

Key configuration options in `_config.yml`:

- `title`: Site title
- `description`: Site description
- `baseurl`: Base URL path (e.g., `/UHCR`)
- `url`: Full site URL
- `color_scheme`: Theme color scheme
- `search_enabled`: Enable/disable search
- `aux_links`: External links in header

## 🎯 Features Breakdown

### Copy Buttons

Automatically added to all code blocks. Click to copy code to clipboard.

### Smooth Scrolling

Anchor links smoothly scroll to their targets.

### Scroll Progress

A progress bar at the top shows reading progress.

### Syntax Highlighting

Powered by Rouge with custom dark theme styling.

### Responsive Tables

Tables automatically become scrollable on mobile devices.

### External Link Icons

External links automatically get an icon indicator.

## 🐛 Troubleshooting

### Jekyll Build Errors

If you encounter build errors:

1. Clear the cache:
```bash
bundle exec jekyll clean
```

2. Rebuild:
```bash
bundle exec jekyll build
```

### CSS Not Loading

Make sure the `custom.scss` file has the front matter:
```scss
---
---

@import "{{ site.theme }}";
// ... rest of CSS
```

### JavaScript Not Working

Check that scripts are loaded in `_layouts/default.html`:
```html
<script src="{{ '/assets/js/custom.js' | relative_url }}"></script>
<script src="{{ '/assets/js/animations.js' | relative_url }}" defer></script>
```

## 📚 Resources

- [Jekyll Documentation](https://jekyllrb.com/docs/)
- [Just the Docs Theme](https://just-the-docs.github.io/just-the-docs/)
- [Markdown Guide](https://www.markdownguide.org/)
- [Liquid Template Language](https://shopify.github.io/liquid/)

## 🤝 Contributing

To contribute to the documentation:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally with `bundle exec jekyll serve`
5. Submit a pull request

See [CONTRIBUTING.md](contributing) for more details.

## 📄 License

The documentation is part of the UHCR project and is licensed under the Apache-2.0 License.
