// ============================================================================
// UHCR Documentation - Custom JavaScript
// Professional, smooth, and performant interactions
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
  // Initialize all features
  initThemeToggle();
  initDynamicYear();
  initCopyButtons();
  initSmoothScroll();
  initScrollProgress();
  initExternalLinks();
  initTableResponsive();
  
  // Mark body as loaded for CSS transitions
  document.body.classList.add('loaded');
});

// ============================================================================
// THEME TOGGLE - Light/Dark mode with localStorage
// ============================================================================
function initThemeToggle() {
  const toggle = document.getElementById('theme-toggle');
  if (!toggle) return;
  
  // Get saved theme or system preference
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');
  
  // Apply theme
  applyTheme(currentTheme);
  
  // Toggle on click
  toggle.addEventListener('click', function() {
    const theme = document.documentElement.getAttribute('data-theme');
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  });
  
  // Listen for system theme changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
    if (!localStorage.getItem('theme')) {
      applyTheme(e.matches ? 'dark' : 'light');
    }
  });
}

function applyTheme(theme) {
  const toggle = document.getElementById('theme-toggle');
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
    if (toggle) toggle.textContent = '☀️';
  } else {
    document.documentElement.removeAttribute('data-theme');
    if (toggle) toggle.textContent = '🌙';
  }
}

// ============================================================================
// DYNAMIC YEAR - Update copyright year
// ============================================================================
function initDynamicYear() {
  const yearElement = document.getElementById('year');
  if (yearElement) {
    yearElement.textContent = new Date().getFullYear();
  }
}

// ============================================================================
// COPY BUTTONS - Add to code blocks
// ============================================================================
function initCopyButtons() {
  const codeBlocks = document.querySelectorAll('div.highlight, pre');
  
  codeBlocks.forEach(function(block) {
    // Skip if already has a copy button
    if (block.querySelector('.copy-button')) return;
    
    // Create copy button
    const button = document.createElement('button');
    button.className = 'copy-button';
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5.5 2.5h7v9h-7v-9z" stroke="currentColor" stroke-width="1.5" fill="none"/>
        <path d="M3.5 4.5v9h7" stroke="currentColor" stroke-width="1.5" fill="none"/>
      </svg>
      <span>Copy</span>
    `;
    button.setAttribute('aria-label', 'Copy code to clipboard');
    
    // Position button
    block.style.position = 'relative';
    block.appendChild(button);
    
    // Add click handler
    button.addEventListener('click', function(e) {
      e.preventDefault();
      
      // Get code text
      const code = block.querySelector('code') || block;
      const text = code.textContent;
      
      // Copy to clipboard
      navigator.clipboard.writeText(text).then(function() {
        // Success feedback
        button.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 8l3 3 7-7" stroke="currentColor" stroke-width="2" fill="none"/>
          </svg>
          <span>Copied!</span>
        `;
        button.classList.add('copied');
        
        // Reset after 2 seconds
        setTimeout(function() {
          button.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M5.5 2.5h7v9h-7v-9z" stroke="currentColor" stroke-width="1.5" fill="none"/>
              <path d="M3.5 4.5v9h7" stroke="currentColor" stroke-width="1.5" fill="none"/>
            </svg>
            <span>Copy</span>
          `;
          button.classList.remove('copied');
        }, 2000);
      }).catch(function(err) {
        console.error('Failed to copy:', err);
      });
    });
  });
}

// ============================================================================
// SMOOTH SCROLL - For anchor links
// ============================================================================
function initSmoothScroll() {
  const links = document.querySelectorAll('a[href^="#"]');
  
  links.forEach(function(link) {
    link.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      if (href === '#') return;
      
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        
        // Smooth scroll to target
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

// ============================================================================
// SCROLL PROGRESS - Subtle indicator
// ============================================================================
function initScrollProgress() {
  // Create progress bar
  const progressBar = document.createElement('div');
  progressBar.className = 'scroll-progress';
  document.body.appendChild(progressBar);
  
  // Update on scroll
  let ticking = false;
  
  window.addEventListener('scroll', function() {
    if (!ticking) {
      window.requestAnimationFrame(function() {
        updateScrollProgress(progressBar);
        ticking = false;
      });
      ticking = true;
    }
  });
  
  // Initial update
  updateScrollProgress(progressBar);
}

function updateScrollProgress(progressBar) {
  const windowHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
  const scrolled = (window.scrollY / windowHeight) * 100;
  progressBar.style.width = Math.min(scrolled, 100) + '%';
}

// ============================================================================
// EXTERNAL LINKS - Add icon and attributes
// ============================================================================
function initExternalLinks() {
  const links = document.querySelectorAll('a[href^="http"]');
  
  links.forEach(function(link) {
    // Check if it's an external link
    if (!link.hostname.includes(window.location.hostname)) {
      link.classList.add('external-link');
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');
    }
  });
}

// ============================================================================
// RESPONSIVE TABLES - Make tables scrollable on mobile
// ============================================================================
function initTableResponsive() {
  const tables = document.querySelectorAll('.main-content table');
  
  tables.forEach(function(table) {
    // Skip if already wrapped
    if (table.parentElement.classList.contains('table-wrapper')) return;
    
    // Create wrapper
    const wrapper = document.createElement('div');
    wrapper.className = 'table-wrapper';
    
    // Wrap table
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
}

// ============================================================================
// KEYBOARD SHORTCUTS
// ============================================================================
document.addEventListener('keydown', function(e) {
  // Ctrl/Cmd + K to focus search
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const searchInput = document.querySelector('.search-input, #search-input');
    if (searchInput) {
      searchInput.focus();
    }
  }
});

// ============================================================================
// COPY BUTTONS - Add to code blocks
// ============================================================================
function initCopyButtons() {
  const codeBlocks = document.querySelectorAll('div.highlight, pre');
  
  codeBlocks.forEach(function(block) {
    // Skip if already has a copy button
    if (block.querySelector('.copy-button')) return;
    
    // Create copy button
    const button = document.createElement('button');
    button.className = 'copy-button';
    button.innerHTML = `
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5.5 2.5h7v9h-7v-9z" stroke="currentColor" stroke-width="1.5" fill="none"/>
        <path d="M3.5 4.5v9h7" stroke="currentColor" stroke-width="1.5" fill="none"/>
      </svg>
      <span>Copy</span>
    `;
    button.setAttribute('aria-label', 'Copy code to clipboard');
    
    // Position button
    block.style.position = 'relative';
    block.appendChild(button);
    
    // Add click handler
    button.addEventListener('click', function(e) {
      e.preventDefault();
      
      // Get code text
      const code = block.querySelector('code') || block;
      const text = code.textContent;
      
      // Copy to clipboard
      navigator.clipboard.writeText(text).then(function() {
        // Success feedback
        button.innerHTML = `
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M3 8l3 3 7-7" stroke="currentColor" stroke-width="2" fill="none"/>
          </svg>
          <span>Copied!</span>
        `;
        button.classList.add('copied');
        
        // Reset after 2 seconds
        setTimeout(function() {
          button.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M5.5 2.5h7v9h-7v-9z" stroke="currentColor" stroke-width="1.5" fill="none"/>
              <path d="M3.5 4.5v9h7" stroke="currentColor" stroke-width="1.5" fill="none"/>
            </svg>
            <span>Copy</span>
          `;
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

// ============================================================================
// SMOOTH SCROLL - For anchor links
// ============================================================================
function initSmoothScroll() {
  const links = document.querySelectorAll('a[href^="#"]');
  
  links.forEach(function(link) {
    link.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      if (href === '#') return;
      
      const target = document.querySelector(href);
      if (target) {
        e.preventDefault();
        
        // Smooth scroll to target
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

// ============================================================================
// SCROLL PROGRESS - Subtle indicator
// ============================================================================
function initScrollProgress() {
  // Create progress bar
  const progressBar = document.createElement('div');
  progressBar.className = 'scroll-progress';
  document.body.appendChild(progressBar);
  
  // Update on scroll
  let ticking = false;
  
  window.addEventListener('scroll', function() {
    if (!ticking) {
      window.requestAnimationFrame(function() {
        updateScrollProgress(progressBar);
        ticking = false;
      });
      ticking = true;
    }
  });
  
  // Initial update
  updateScrollProgress(progressBar);
}

function updateScrollProgress(progressBar) {
  const windowHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
  const scrolled = (window.scrollY / windowHeight) * 100;
  progressBar.style.width = Math.min(scrolled, 100) + '%';
}

// ============================================================================
// EXTERNAL LINKS - Add icon and attributes
// ============================================================================
function initExternalLinks() {
  const links = document.querySelectorAll('a[href^="http"]');
  
  links.forEach(function(link) {
    // Check if it's an external link
    if (!link.hostname.includes(window.location.hostname)) {
      link.classList.add('external-link');
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');
    }
  });
}

// ============================================================================
// RESPONSIVE TABLES - Make tables scrollable on mobile
// ============================================================================
function initTableResponsive() {
  const tables = document.querySelectorAll('.main-content table');
  
  tables.forEach(function(table) {
    // Skip if already wrapped
    if (table.parentElement.classList.contains('table-wrapper')) return;
    
    // Create wrapper
    const wrapper = document.createElement('div');
    wrapper.className = 'table-wrapper';
    
    // Wrap table
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
}

// ============================================================================
// KEYBOARD SHORTCUTS
// ============================================================================
document.addEventListener('keydown', function(e) {
  // Ctrl/Cmd + K to focus search
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const searchInput = document.querySelector('.search-input, #search-input');
    if (searchInput) {
      searchInput.focus();
    }
  }
});
