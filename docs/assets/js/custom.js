// ============================================================================
// UHCR Documentation - Custom JavaScript
// Professional, smooth, and performant interactions
// ============================================================================

// Prevent transitions on page load
document.documentElement.classList.add('preload');

document.addEventListener('DOMContentLoaded', function() {
  // Remove preload class after a short delay
  setTimeout(function() {
    document.documentElement.classList.remove('preload');
  }, 100);
  
  // Initialize all features
  initThemeToggle();
  initDynamicYear();
  initSmoothScroll();
  initScrollProgress();
  initExternalLinks();
  initTableResponsive();
  initPWA();
  
  // Mark body as loaded for CSS transitions
  document.body.classList.add('loaded');
});

// ============================================================================
// THEME TOGGLE - Light/Dark mode with localStorage
// ============================================================================
function initThemeToggle() {
  let toggle = document.getElementById('theme-toggle');
  if (!toggle) {
    toggle = document.createElement('button');
    toggle.id = 'theme-toggle';
    toggle.className = 'theme-toggle';
    toggle.setAttribute('aria-label', 'Toggle dark mode');
    toggle.setAttribute('title', 'Toggle dark mode');
    toggle.textContent = '🌙';
    document.body.appendChild(toggle);
  }
  
  const savedTheme = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');
  
  applyTheme(currentTheme);
  
  toggle.addEventListener('click', function() {
    const theme = document.documentElement.getAttribute('data-theme');
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    applyTheme(newTheme);
    localStorage.setItem('theme', newTheme);
  });
  
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
// PWA - Register Service Worker
// ============================================================================
function initPWA() {
  if (!('serviceWorker' in navigator)) return;
  if (!window.__UHCR_SW_PATH) return;

  navigator.serviceWorker.register(window.__UHCR_SW_PATH)
    .then(function(registration) {
      console.log('UHCR PWA: Service worker registered at', registration.scope);
    })
    .catch(function(error) {
      console.warn('UHCR PWA: Service worker registration failed', error);
    });
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
        target.scrollIntoView({
          behavior: 'smooth',
          block: 'start'
        });
        history.pushState(null, null, href);
      }
    });
  });
}

// ============================================================================
// SCROLL PROGRESS - Subtle indicator
// ============================================================================
function initScrollProgress() {
  const progressBar = document.createElement('div');
  progressBar.className = 'scroll-progress';
  document.body.appendChild(progressBar);
  
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
  updateScrollProgress(progressBar);
}

function updateScrollProgress(progressBar) {
  const windowHeight = document.documentElement.scrollHeight - document.documentElement.clientHeight;
  const scrolled = windowHeight > 0 ? (window.scrollY / windowHeight) * 100 : 0;
  progressBar.style.width = Math.min(scrolled, 100) + '%';
}

// ============================================================================
// EXTERNAL LINKS - Add icon and attributes
// ============================================================================
function initExternalLinks() {
  const links = document.querySelectorAll('a[href^="http"]');
  
  links.forEach(function(link) {
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
    if (table.parentElement.classList.contains('table-wrapper')) return;
    const wrapper = document.createElement('div');
    wrapper.className = 'table-wrapper';
    table.parentNode.insertBefore(wrapper, table);
    wrapper.appendChild(table);
  });
}

// ============================================================================
// KEYBOARD SHORTCUTS
// ============================================================================
document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const searchInput = document.querySelector('.search-input, #search-input');
    if (searchInput) {
      searchInput.focus();
    }
  }
});
