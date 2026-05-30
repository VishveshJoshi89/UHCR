// Custom JavaScript for UHCR Documentation

document.addEventListener('DOMContentLoaded', function() {
  
  // Add copy button to code blocks
  addCopyButtons();
  
  // Add smooth scroll for anchor links
  smoothScrollLinks();
  
  // Add syntax highlighting enhancements
  enhanceCodeBlocks();
  
  // Add table of contents highlighting
  highlightTOC();
  
  // Add loading animation
  addLoadingAnimation();
});

// Add copy buttons to code blocks
function addCopyButtons() {
  const codeBlocks = document.querySelectorAll('pre');
  
  codeBlocks.forEach(function(codeBlock) {
    const button = document.createElement('button');
    button.className = 'copy-button';
    button.textContent = 'Copy';
    button.setAttribute('aria-label', 'Copy code to clipboard');
    
    const wrapper = document.createElement('div');
    wrapper.className = 'code-block-wrapper';
    codeBlock.parentNode.insertBefore(wrapper, codeBlock);
    wrapper.appendChild(button);
    wrapper.appendChild(codeBlock);
    
    button.addEventListener('click', function() {
      const code = codeBlock.querySelector('code');
      const text = code ? code.textContent : codeBlock.textContent;
      
      navigator.clipboard.writeText(text).then(function() {
        button.textContent = 'Copied!';
        button.classList.add('copied');
        
        setTimeout(function() {
          button.textContent = 'Copy';
          button.classList.remove('copied');
        }, 2000);
      }).catch(function(err) {
        console.error('Failed to copy:', err);
        button.textContent = 'Failed';
        setTimeout(function() {
          button.textContent = 'Copy';
        }, 2000);
      });
    });
  });
}

// Smooth scroll for anchor links
function smoothScrollLinks() {
  const links = document.querySelectorAll('a[href^="#"]');
  
  links.forEach(function(link) {
    link.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      if (href === '#') return;
      
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
        
        // Update URL without jumping
        history.pushState(null, null, href);
      }
    });
  });
}

// Enhance code blocks with language labels
function enhanceCodeBlocks() {
  const codeBlocks = document.querySelectorAll('pre code[class*="language-"]');
  
  codeBlocks.forEach(function(code) {
    const pre = code.parentElement;
    const className = code.className;
    const match = className.match(/language-(\w+)/);
    
    if (match) {
      const language = match[1];
      const label = document.createElement('div');
      label.className = 'code-language-label';
      label.textContent = language;
      
      const wrapper = pre.parentElement;
      if (wrapper.classList.contains('code-block-wrapper')) {
        wrapper.insertBefore(label, wrapper.firstChild);
      }
    }
  });
}

// Highlight active section in TOC
function highlightTOC() {
  const observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      const id = entry.target.getAttribute('id');
      if (!id) return;
      
      const tocLink = document.querySelector(`.nav-list-link[href="#${id}"]`);
      if (tocLink) {
        if (entry.isIntersecting) {
          tocLink.classList.add('active');
        } else {
          tocLink.classList.remove('active');
        }
      }
    });
  }, {
    rootMargin: '-100px 0px -80% 0px'
  });
  
  // Observe all headings
  document.querySelectorAll('h2[id], h3[id]').forEach(function(heading) {
    observer.observe(heading);
  });
}

// Add loading animation
function addLoadingAnimation() {
  document.body.classList.add('loaded');
}

// Add keyboard shortcuts
document.addEventListener('keydown', function(e) {
  // Ctrl/Cmd + K to focus search
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const searchInput = document.querySelector('.search-input');
    if (searchInput) {
      searchInput.focus();
    }
  }
});

// Add external link icons
function addExternalLinkIcons() {
  const links = document.querySelectorAll('a[href^="http"]');
  
  links.forEach(function(link) {
    if (!link.hostname.includes(window.location.hostname)) {
      link.classList.add('external-link');
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');
    }
  });
}

// Initialize external link icons
addExternalLinkIcons();

// Add progress bar for page scroll
function addScrollProgress() {
  const progressBar = document.createElement('div');
  progressBar.className = 'scroll-progress';
  document.body.appendChild(progressBar);
  
  window.addEventListener('scroll', function() {
    const windowHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
    const scrolled = (window.scrollY / windowHeight) * 100;
    progressBar.style.width = scrolled + '%';
  });
}

addScrollProgress();

// Add theme toggle (if needed in future)
function addThemeToggle() {
  const toggle = document.createElement('button');
  toggle.className = 'theme-toggle';
  toggle.setAttribute('aria-label', 'Toggle theme');
  toggle.innerHTML = '🌙';
  
  document.body.appendChild(toggle);
  
  toggle.addEventListener('click', function() {
    document.body.classList.toggle('light-theme');
    toggle.innerHTML = document.body.classList.contains('light-theme') ? '☀️' : '🌙';
  });
}

// Uncomment to enable theme toggle
// addThemeToggle();
